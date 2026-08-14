import uuid
from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import JSON, DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from PR_Agent.database import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class ReviewStatus(StrEnum):
    queued = "queued"
    running = "running"
    awaiting_approval = "awaiting_approval"
    approved = "approved"
    rejected = "rejected"
    failed = "failed"


class TaskStatus(StrEnum):
    queued = "queued"
    running = "running"
    passed = "passed"
    warning = "warning"
    failed = "failed"
    skipped = "skipped"


class Decision(StrEnum):
    pass_review = "pass"
    needs_work = "needs_work"
    blocked = "blocked"


class PullRequest(Base):
    __tablename__ = "pull_requests"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    repository: Mapped[str] = mapped_column(String(255), index=True)
    number: Mapped[int] = mapped_column(Integer, index=True)
    title: Mapped[str] = mapped_column(String(500))
    author: Mapped[str] = mapped_column(String(255), default="unknown")
    description: Mapped[str] = mapped_column(Text, default="")
    base_sha: Mapped[str] = mapped_column(String(64), default="")
    head_sha: Mapped[str] = mapped_column(String(64), default="")
    base_ref: Mapped[str] = mapped_column(String(255), default="main")
    head_ref: Mapped[str] = mapped_column(String(255), default="")
    html_url: Mapped[str] = mapped_column(String(1000), default="")
    diff: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    sessions: Mapped[list["ReviewSession"]] = relationship(
        back_populates="pull_request", cascade="all, delete-orphan"
    )


class ReviewSession(Base):
    __tablename__ = "review_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    pull_request_id: Mapped[str] = mapped_column(ForeignKey("pull_requests.id"), index=True)
    status: Mapped[ReviewStatus] = mapped_column(
        Enum(ReviewStatus), default=ReviewStatus.queued, index=True
    )
    overall_decision: Mapped[Decision | None] = mapped_column(Enum(Decision), nullable=True)
    alignment_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    risk_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    summary: Mapped[str] = mapped_column(Text, default="Review queued")
    artifact_uri: Mapped[str] = mapped_column(String(1000), default="")
    error: Mapped[str] = mapped_column(Text, default="")
    trace_id: Mapped[str] = mapped_column(String(36), default=lambda: str(uuid.uuid4()), index=True)
    source_delivery_id: Mapped[str | None] = mapped_column(
        String(100), unique=True, nullable=True, index=True
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    pull_request: Mapped[PullRequest] = relationship(back_populates="sessions")
    tasks: Mapped[list["AgentTask"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )
    approval: Mapped["HumanDecision | None"] = relationship(
        back_populates="session", cascade="all, delete-orphan", uselist=False
    )


class AgentTask(Base):
    __tablename__ = "agent_tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id: Mapped[str] = mapped_column(ForeignKey("review_sessions.id"), index=True)
    agent_role: Mapped[str] = mapped_column(String(80), index=True)
    status: Mapped[TaskStatus] = mapped_column(Enum(TaskStatus), default=TaskStatus.queued)
    title: Mapped[str] = mapped_column(String(255))
    summary: Mapped[str] = mapped_column(Text, default="")
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    findings: Mapped[list[dict]] = mapped_column(JSON, default=list)
    evidence: Mapped[dict] = mapped_column(JSON, default=dict)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    session: Mapped[ReviewSession] = relationship(back_populates="tasks")


class HumanDecision(Base):
    __tablename__ = "human_decisions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id: Mapped[str] = mapped_column(
        ForeignKey("review_sessions.id"), unique=True, index=True
    )
    decision: Mapped[str] = mapped_column(String(30))
    reviewer: Mapped[str] = mapped_column(String(255), default="local-reviewer")
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    session: Mapped[ReviewSession] = relationship(back_populates="approval")
