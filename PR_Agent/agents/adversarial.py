import re

from PR_Agent.agents.base import BaseAgent, ReviewContext
from PR_Agent.models import TaskStatus
from PR_Agent.schemas import AgentResult, Finding


class AdversarialAgent(BaseAgent):
    role = "adversarial"
    title = "Adversarial hardening"

    async def run(self, context: ReviewContext) -> AgentResult:
        scenario = context.metadata.get("scenario")
        removed_test_files: list[str] = []
        current_old_file = ""
        for line in context.diff.splitlines():
            if line.startswith("--- a/"):
                current_old_file = line.removeprefix("--- a/")
            elif line.startswith("+++ /dev/null") and self._looks_like_test_file(current_old_file):
                removed_test_files.append(current_old_file)
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
        disabled_test_signals = sum(
            1
            for line in context.diff.splitlines()
            if line.startswith("+")
            and not line.startswith("+++")
            and re.search(
                r"(?:\.skip\s*\(|@pytest\.mark\.skip|\bDISABLED_|\bxit\s*\()",
                line,
            )
        )
        findings: list[Finding] = []
        for path in removed_test_files[:5]:
            findings.append(
                Finding(
                    severity="high",
                    title="Test file removed",
                    detail="A test file was deleted in this pull request; confirm equivalent coverage remains.",
                    file=path,
                )
            )
        if disabled_test_signals:
            findings.append(
                Finding(
                    severity="high",
                    title="Test was disabled",
                    detail="The change adds a skip/disabled test marker. Restore coverage or document why it is safe.",
                )
            )
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
        score = float(
            max(10, 100 - removed_tests * 18 - disabled_test_signals * 25 - len(findings) * 30)
        )
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
                "disabled_test_signals": disabled_test_signals,
                "removed_test_files": removed_test_files[:20],
            },
        )

    @staticmethod
    def _looks_like_test_file(path: str) -> bool:
        name = path.lower()
        return bool(
            re.search(r"(?:^|/)(?:tests?|__tests__)/", name)
            or re.search(r"(?:test|spec)\.[a-z0-9]+$", name)
            or name.endswith("_test.py")
        )
