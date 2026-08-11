from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from proofmerge.models import Decision, ReviewStatus, TaskStatus


class Finding(BaseModel):
    severity: Literal["info", "low", "medium", "high", "critical"] = "info"
    title: str
    detail: str
    file: str | None = None
    line: int | None = None


class AgentResult(BaseModel):
    role: str
    title: str
    status: TaskStatus
    summary: str
    score: float = Field(ge=0, le=100)
    findings: list[Finding] = Field(default_factory=list)
    evidence: dict = Field(default_factory=dict)


class PullRequestCreate(BaseModel):
    repository: str
    number: int = Field(gt=0)
    title: str
    author: str = "unknown"
    description: str = ""
    base_sha: str = ""
    head_sha: str = ""
    base_ref: str = "main"
    head_ref: str = ""
    html_url: str = ""
    diff: str = ""


class TaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    agent_role: str
    status: TaskStatus
    title: str
    summary: str
    score: float | None
    findings: list[dict]
    evidence: dict
    started_at: datetime | None
    completed_at: datetime | None


class PullRequestRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    repository: str
    number: int
    title: str
    author: str
    description: str
    base_ref: str
    head_ref: str
    html_url: str


class HumanDecisionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    decision: str
    reviewer: str
    note: str
    created_at: datetime


class ReviewRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    status: ReviewStatus
    overall_decision: Decision | None
    alignment_score: float | None
    risk_score: float | None
    summary: str
    artifact_uri: str
    error: str
    trace_id: str
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime
    pull_request: PullRequestRead
    tasks: list[TaskRead] = Field(default_factory=list)
    approval: HumanDecisionRead | None = None


class ReviewList(BaseModel):
    items: list[ReviewRead]
    total: int


class HumanDecisionCreate(BaseModel):
    decision: Literal["approve", "reject"]
    reviewer: str = Field(default="local-reviewer", min_length=1, max_length=255)
    note: str = Field(default="", max_length=4000)


class DemoReviewCreate(BaseModel):
    scenario: Literal["secure-fix", "risky-change", "incomplete-fix"] = "secure-fix"


class HealthRead(BaseModel):
    status: Literal["ok"] = "ok"
    version: str
    environment: str
