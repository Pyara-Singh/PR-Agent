from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from proofmerge.models import (
    AgentTask,
    Decision,
    HumanDecision,
    PullRequest,
    ReviewSession,
    ReviewStatus,
    TaskStatus,
)
from proofmerge.schemas import AgentResult, PullRequestCreate


def utcnow() -> datetime:
    return datetime.now(UTC)


async def upsert_pull_request(session: AsyncSession, data: PullRequestCreate) -> PullRequest:
    statement = select(PullRequest).where(
        PullRequest.repository == data.repository,
        PullRequest.number == data.number,
    )
    pull_request = await session.scalar(statement)
    if pull_request is None:
        pull_request = PullRequest(**data.model_dump())
        session.add(pull_request)
    else:
        for key, value in data.model_dump().items():
            setattr(pull_request, key, value)
    await session.flush()
    return pull_request


async def create_review(session: AsyncSession, pull_request: PullRequest) -> ReviewSession:
    review = ReviewSession(pull_request_id=pull_request.id)
    session.add(review)
    await session.commit()
    return review


def review_load_options() -> tuple:
    return (
        selectinload(ReviewSession.pull_request),
        selectinload(ReviewSession.tasks),
        selectinload(ReviewSession.approval),
    )


async def get_review(session: AsyncSession, review_id: str) -> ReviewSession | None:
    statement = (
        select(ReviewSession).options(*review_load_options()).where(ReviewSession.id == review_id)
    )
    return await session.scalar(statement)


async def list_reviews(
    session: AsyncSession, *, limit: int = 50, offset: int = 0
) -> tuple[list[ReviewSession], int]:
    statement = (
        select(ReviewSession)
        .options(*review_load_options())
        .order_by(ReviewSession.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    items = list((await session.scalars(statement)).all())
    total = int((await session.scalar(select(func.count(ReviewSession.id)))) or 0)
    return items, total


async def mark_review_running(session: AsyncSession, review: ReviewSession) -> None:
    review.status = ReviewStatus.running
    review.summary = "Agents are collecting evidence"
    review.started_at = utcnow()
    review.error = ""
    await session.commit()


async def prepare_tasks(
    session: AsyncSession, review: ReviewSession, agents: list[tuple[str, str]]
) -> dict[str, AgentTask]:
    existing = {task.agent_role: task for task in review.tasks}
    tasks: dict[str, AgentTask] = {}
    for role, title in agents:
        task = existing.get(role)
        if task is None:
            task = AgentTask(session_id=review.id, agent_role=role, title=title)
            session.add(task)
        task.status = TaskStatus.queued
        task.summary = "Waiting to run"
        task.findings = []
        task.evidence = {}
        task.started_at = None
        task.completed_at = None
        tasks[role] = task
    await session.commit()
    return tasks


async def mark_task_running(session: AsyncSession, task: AgentTask) -> None:
    task.status = TaskStatus.running
    task.summary = "Inspecting the change"
    task.started_at = utcnow()
    await session.commit()


async def save_agent_result(session: AsyncSession, task: AgentTask, result: AgentResult) -> None:
    task.status = result.status
    task.title = result.title
    task.summary = result.summary
    task.score = result.score
    task.findings = [finding.model_dump() for finding in result.findings]
    task.evidence = result.evidence
    task.completed_at = utcnow()
    await session.commit()


async def complete_review(
    session: AsyncSession,
    review: ReviewSession,
    *,
    decision: Decision,
    summary: str,
    alignment_score: float,
    risk_score: float,
    artifact_uri: str = "",
) -> None:
    review.status = ReviewStatus.awaiting_approval
    review.overall_decision = decision
    review.summary = summary
    review.alignment_score = alignment_score
    review.risk_score = risk_score
    review.artifact_uri = artifact_uri
    review.completed_at = utcnow()
    await session.commit()


async def fail_review(session: AsyncSession, review: ReviewSession, message: str) -> None:
    review.status = ReviewStatus.failed
    review.overall_decision = Decision.blocked
    review.summary = "Review execution failed"
    review.error = message[:4000]
    review.completed_at = utcnow()
    await session.commit()


async def save_human_decision(
    session: AsyncSession,
    review: ReviewSession,
    *,
    decision: str,
    reviewer: str,
    note: str,
) -> HumanDecision:
    if review.approval is not None:
        approval = review.approval
        approval.decision = decision
        approval.reviewer = reviewer
        approval.note = note
        approval.created_at = utcnow()
    else:
        approval = HumanDecision(
            session_id=review.id,
            decision=decision,
            reviewer=reviewer,
            note=note,
        )
        session.add(approval)
        review.approval = approval
    review.status = ReviewStatus.approved if decision == "approve" else ReviewStatus.rejected
    await session.commit()
    return approval
