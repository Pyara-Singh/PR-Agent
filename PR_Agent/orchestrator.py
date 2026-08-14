import asyncio
import json
import traceback
from statistics import mean
from typing import TypedDict

import structlog
from langgraph.graph import END, START, StateGraph
from sqlalchemy import select

from PR_Agent.agents import (
    AdversarialAgent,
    AlignmentAgent,
    BehavioralAgent,
    ReproductionAgent,
    SecurityAgent,
)
from PR_Agent.agents.base import BaseAgent, ReviewContext
from PR_Agent.config import Settings
from PR_Agent.database import SessionFactory
from PR_Agent.github import GitHubClient, format_review_comment
from PR_Agent.knowledge import build_knowledge_store
from PR_Agent.llm import build_llm_provider
from PR_Agent.models import AgentTask, Decision, TaskStatus
from PR_Agent.repository import (
    complete_review,
    fail_review,
    get_review,
    mark_review_running,
    mark_task_running,
    prepare_tasks,
    save_agent_result,
)
from PR_Agent.schemas import AgentResult
from PR_Agent.storage import build_artifact_store

logger = structlog.get_logger(__name__)


class ReviewGraphState(TypedDict, total=False):
    review_id: str
    context: ReviewContext
    task_ids: dict[str, str]
    results: list[AgentResult]


class ReviewOrchestrator:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        provider = build_llm_provider(settings)
        knowledge = build_knowledge_store(settings)
        self.agents: list[BaseAgent] = [
            AlignmentAgent(provider, knowledge),
            ReproductionAgent(provider, settings),
            SecurityAgent(provider),
            AdversarialAgent(provider),
            BehavioralAgent(provider),
        ]
        self.artifacts = build_artifact_store(settings)
        graph = StateGraph(ReviewGraphState)
        graph.add_node("prepare", self._prepare)
        graph.add_node("analyze", self._analyze)
        graph.add_node("aggregate", self._aggregate)
        graph.add_edge(START, "prepare")
        graph.add_edge("prepare", "analyze")
        graph.add_edge("analyze", "aggregate")
        graph.add_edge("aggregate", END)
        self.graph = graph.compile()

    async def run(self, review_id: str) -> None:
        try:
            await self.graph.ainvoke({"review_id": review_id})
        except Exception as exc:
            logger.exception("review_failed", review_id=review_id)
            async with SessionFactory() as session:
                review = await get_review(session, review_id)
                if review is not None:
                    await fail_review(session, review, str(exc))

    async def _prepare(self, state: ReviewGraphState) -> ReviewGraphState:
        async with SessionFactory() as session:
            review = await get_review(session, state["review_id"])
            if review is None:
                raise LookupError(f"Review {state['review_id']} was not found")
            await mark_review_running(session, review)
            tasks = await prepare_tasks(
                session,
                review,
                [(agent.role, agent.title) for agent in self.agents],
            )
            pull_request = review.pull_request
            scenario = ""
            if pull_request.repository == "PR_Agent/demo" and pull_request.head_ref.startswith(
                "demo/"
            ):
                scenario = pull_request.head_ref.removeprefix("demo/")
            context = ReviewContext(
                repository=pull_request.repository,
                number=pull_request.number,
                title=pull_request.title,
                description=pull_request.description,
                author=pull_request.author,
                base_sha=pull_request.base_sha,
                head_sha=pull_request.head_sha,
                base_ref=pull_request.base_ref,
                head_ref=pull_request.head_ref,
                diff=pull_request.diff,
                metadata={"scenario": scenario} if scenario else {},
            )
            return {
                "context": context,
                "task_ids": {role: task.id for role, task in tasks.items()},
            }

    async def _analyze(self, state: ReviewGraphState) -> ReviewGraphState:
        context = state["context"]
        task_ids = state["task_ids"]
        results = await asyncio.gather(
            *(self._run_agent(agent, task_ids[agent.role], context) for agent in self.agents)
        )
        return {"results": list(results)}

    async def _run_agent(
        self, agent: BaseAgent, task_id: str, context: ReviewContext
    ) -> AgentResult:
        async with SessionFactory() as session:
            task = await session.scalar(select(AgentTask).where(AgentTask.id == task_id))
            if task is None:
                raise LookupError(f"Agent task {task_id} was not found")
            await mark_task_running(session, task)
            try:
                result = await agent.run(context)
            except Exception as exc:
                result = AgentResult(
                    role=agent.role,
                    title=agent.title,
                    status=TaskStatus.failed,
                    summary="The agent could not complete its evidence collection.",
                    score=0,
                    evidence={
                        "error": repr(exc)[:1000],
                        "error_type": type(exc).__name__,
                        "traceback": traceback.format_exc(limit=8)[-4000:],
                    },
                )
            await save_agent_result(session, task, result)
            return result

    async def _aggregate(self, state: ReviewGraphState) -> ReviewGraphState:
        results = state["results"]
        severities = [finding.severity for result in results for finding in result.findings]
        has_critical = "critical" in severities
        has_blocker = has_critical or any(result.status == TaskStatus.failed for result in results)
        if has_critical:
            decision = Decision.blocked
            summary = "Critical evidence blocks this change until it is remediated."
        elif has_blocker:
            decision = Decision.needs_work
            summary = "The change needs additional work before human approval."
        else:
            decision = Decision.pass_review
            summary = "Evidence supports the change; human sign-off is still required."

        alignment = next((result.score for result in results if result.role == "alignment"), 0)
        safety_scores = [
            result.score
            for result in results
            if result.role in {"security", "reproduction", "adversarial", "behavioral"}
        ]
        risk = round(100 - mean(safety_scores), 1) if safety_scores else 100.0
        report = {
            "review_id": state["review_id"],
            "decision": decision.value,
            "summary": summary,
            "alignment_score": round(alignment, 1),
            "risk_score": max(0, min(100, risk)),
            "agents": [result.model_dump(mode="json") for result in results],
        }
        artifact_uri = await self.artifacts.put_text(
            f"reviews/{state['review_id']}/evidence-report.json",
            json.dumps(report, indent=2),
            "application/json",
        )
        async with SessionFactory() as session:
            review = await get_review(session, state["review_id"])
            if review is None:
                raise LookupError(f"Review {state['review_id']} was not found")
            await complete_review(
                session,
                review,
                decision=decision,
                summary=summary,
                alignment_score=round(alignment, 1),
                risk_score=max(0, min(100, risk)),
                artifact_uri=artifact_uri,
            )
            repository = review.pull_request.repository
            number = review.pull_request.number
        if self.settings.github_comments_enabled:
            try:
                await GitHubClient(self.settings).post_comment(
                    repository, number, format_review_comment(report)
                )
            except Exception:
                logger.warning(
                    "github_evidence_comment_failed",
                    review_id=state["review_id"],
                    repository=repository,
                    number=number,
                )
        return {}
