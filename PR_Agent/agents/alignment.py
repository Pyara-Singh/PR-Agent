import re

from PR_Agent.agents.base import BaseAgent, ReviewContext
from PR_Agent.knowledge import KnowledgeStore
from PR_Agent.llm import LLMProvider
from PR_Agent.models import TaskStatus
from PR_Agent.schemas import AgentResult, Finding


class AlignmentAgent(BaseAgent):
    role = "alignment"
    title = "Strategic alignment"

    def __init__(self, llm: LLMProvider, knowledge: KnowledgeStore) -> None:
        super().__init__(llm)
        self.knowledge = knowledge

    async def run(self, context: ReviewContext) -> AgentResult:
        text = f"{context.title} {context.description}".lower()
        intent_terms = {"fix", "security", "performance", "reliability", "test", "bug"}
        risky_terms = {"temporary", "workaround", "disable", "skip", "bypass"}
        intents = sorted(term for term in intent_terms if re.search(rf"\b{term}\b", text))
        risks = sorted(term for term in risky_terms if re.search(rf"\b{term}\b", text))
        has_description = len(context.description.strip()) >= 30
        project_context = await self.knowledge.search(f"{context.title}\n{context.description}")
        score = 58 + min(len(intents) * 7, 28) + (8 if has_description else -12) - len(risks) * 8
        if project_context:
            score += 4
        score = float(max(0, min(100, score)))
        findings: list[Finding] = []
        if not has_description:
            findings.append(
                Finding(
                    severity="medium",
                    title="PR intent is under-documented",
                    detail="Add expected behavior and a link to the motivating issue or ADR.",
                )
            )
        if risks:
            findings.append(
                Finding(
                    severity="medium",
                    title="Potential scope or policy concern",
                    detail=f"The description contains cautionary terms: {', '.join(risks)}.",
                )
            )
        observation = await self.llm_observation(
            context,
            "Identify stated objective, likely scope creep, and relevant architecture goals.",
        )
        status = TaskStatus.passed if score >= 70 else TaskStatus.warning
        return AgentResult(
            role=self.role,
            title=self.title,
            status=status,
            summary=(
                "The change has a clear, goal-oriented rationale."
                if status == TaskStatus.passed
                else "The change needs stronger strategic context before merge."
            ),
            score=score,
            findings=findings,
            evidence={
                "intent_terms": intents,
                "description_present": has_description,
                "project_context": project_context,
                "model_observation": observation,
            },
        )
