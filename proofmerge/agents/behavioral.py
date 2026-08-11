import re

from proofmerge.agents.base import BaseAgent, ReviewContext
from proofmerge.models import TaskStatus
from proofmerge.schemas import AgentResult, Finding


class BehavioralAgent(BaseAgent):
    role = "behavioral"
    title = "Behavioral compatibility"

    async def run(self, context: ReviewContext) -> AgentResult:
        removed_signatures = [
            line[1:].strip()
            for line in context.diff.splitlines()
            if line.startswith("-")
            and re.match(r"\s*(def |async def |class |export |public |interface )", line[1:])
        ]
        findings = [
            Finding(
                severity="medium",
                title="Public contract changed",
                detail=f"Verify compatibility for removed or changed declaration: {signature[:160]}",
            )
            for signature in removed_signatures[:5]
        ]
        score = float(max(35, 100 - len(findings) * 14))
        status = TaskStatus.warning if findings else TaskStatus.passed
        return AgentResult(
            role=self.role,
            title=self.title,
            status=status,
            summary=(
                "No obvious public contract regression was detected."
                if not findings
                else "Potential public contract changes need owner confirmation."
            ),
            score=score,
            findings=findings,
            evidence={"changed_contracts": removed_signatures[:20]},
        )
