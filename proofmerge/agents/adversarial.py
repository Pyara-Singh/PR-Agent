import re

from proofmerge.agents.base import BaseAgent, ReviewContext
from proofmerge.models import TaskStatus
from proofmerge.schemas import AgentResult, Finding


class AdversarialAgent(BaseAgent):
    role = "adversarial"
    title = "Adversarial hardening"

    async def run(self, context: ReviewContext) -> AgentResult:
        scenario = context.metadata.get("scenario")
        removed_tests = sum(
            1
            for line in context.diff.splitlines()
            if line.startswith("-") and re.search(r"\b(test_|assert|expect\()", line)
        )
        added_tests = sum(
            1
            for line in context.diff.splitlines()
            if line.startswith("+") and re.search(r"\b(test_|assert|expect\()", line)
        )
        findings: list[Finding] = []
        if removed_tests > added_tests:
            findings.append(
                Finding(
                    severity="high",
                    title="Possible test weakening",
                    detail="More test assertions were removed than added in this change.",
                )
            )
        if scenario == "incomplete-fix":
            findings.append(
                Finding(
                    severity="high",
                    title="Empty input breaks the fix",
                    detail="An adversarial case reaches the original failure through a second branch.",
                )
            )
        score = float(max(10, 100 - removed_tests * 18 - len(findings) * 30))
        status = (
            TaskStatus.failed if any(f.severity == "high" for f in findings) else TaskStatus.passed
        )
        cases = [
            "empty input",
            "null value",
            "oversized payload",
            "repeated request",
            "concurrent call",
        ]
        return AgentResult(
            role=self.role,
            title=self.title,
            status=status,
            summary=(
                "Generated edge cases did not invalidate the proposed fix."
                if status == TaskStatus.passed
                else "Adversarial checks found a reproducible weakness."
            ),
            score=score,
            findings=findings,
            evidence={
                "cases_generated": cases,
                "removed_test_signals": removed_tests,
                "added_test_signals": added_tests,
            },
        )
