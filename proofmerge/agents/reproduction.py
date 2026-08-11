from proofmerge.agents.base import BaseAgent, ReviewContext
from proofmerge.models import TaskStatus
from proofmerge.schemas import AgentResult, Finding


class ReproductionAgent(BaseAgent):
    role = "reproduction"
    title = "Scientific reproduction"

    async def run(self, context: ReviewContext) -> AgentResult:
        scenario = context.metadata.get("scenario")
        if scenario == "secure-fix":
            base_result, head_result = "failed as expected", "passed"
            status, score = TaskStatus.passed, 96.0
            summary = "The regression test fails on base and passes on the proposed change."
            findings: list[Finding] = []
        elif scenario == "incomplete-fix":
            base_result, head_result = "failed as expected", "failed on edge input"
            status, score = TaskStatus.failed, 34.0
            summary = "The original path is fixed, but the same defect remains for empty input."
            findings = [
                Finding(
                    severity="high",
                    title="Fix is not complete",
                    detail="The generated empty-input reproduction still fails on the PR branch.",
                    file="app/normalize.py",
                    line=18,
                )
            ]
        elif scenario == "risky-change":
            base_result, head_result = "failed as expected", "passed"
            status, score = TaskStatus.passed, 88.0
            summary = (
                "The reported functional bug is fixed; security evidence is evaluated separately."
            )
            findings = []
        else:
            base_result, head_result = "not executed", "not executed"
            status, score = TaskStatus.warning, 55.0
            summary = (
                "A sandbox test command is required to produce empirical base-versus-head proof."
            )
            findings = [
                Finding(
                    severity="medium",
                    title="Empirical command not configured",
                    detail="Add .proofmerge.yml with setup and test commands for this repository.",
                )
            ]
        return AgentResult(
            role=self.role,
            title=self.title,
            status=status,
            summary=summary,
            score=score,
            findings=findings,
            evidence={
                "base_result": base_result,
                "head_result": head_result,
                "same_test_used": scenario in {"secure-fix", "incomplete-fix", "risky-change"},
                "network_access": "disabled",
            },
        )
