import re

from PR_Agent.agents.base import BaseAgent, ReviewContext
from PR_Agent.models import TaskStatus
from PR_Agent.schemas import AgentResult, Finding

RULES: list[tuple[str, str, str, str]] = [
    (r"\beval\s*\(", "high", "Dynamic code execution", "Avoid eval on untrusted input."),
    (r"\bexec\s*\(", "high", "Dynamic code execution", "Avoid exec on untrusted input."),
    (r"os\.system\s*\(", "critical", "Shell execution", "Use an argument-safe process API."),
    (r"shell\s*=\s*True", "critical", "Shell injection surface", "Do not invoke a shell."),
    (r"verify\s*=\s*False", "high", "TLS verification disabled", "Keep TLS verification enabled."),
    (
        r"(?i)(api[_-]?key|password|secret)\s*=\s*['\"][^'\"]+['\"]",
        "critical",
        "Possible committed secret",
        "Move the value to a secret manager.",
    ),
    (r"(?i)md5\s*\(", "medium", "Weak digest", "Use a modern password or integrity primitive."),
    (r"(?i)select.+\{.+\}", "high", "Possible SQL interpolation", "Use parameterized queries."),
]


class SecurityAgent(BaseAgent):
    role = "security"
    title = "Security and quality"

    async def run(self, context: ReviewContext) -> AgentResult:
        added_lines = [
            line[1:]
            for line in context.diff.splitlines()
            if line.startswith("+") and not line.startswith("+++")
        ]
        added = "\n".join(added_lines)
        findings: list[Finding] = []
        weights = {"info": 0, "low": 5, "medium": 15, "high": 30, "critical": 55}
        penalty = 0
        for pattern, severity, title, detail in RULES:
            if re.search(pattern, added):
                findings.append(Finding(severity=severity, title=title, detail=detail))
                penalty += weights[severity]
        scenario = context.metadata.get("scenario")
        if scenario == "risky-change":
            findings.append(
                Finding(
                    severity="critical",
                    title="Authentication bypass demonstrated",
                    detail="The changed authorization path accepts an unsigned administrative request.",
                    file="app/auth.py",
                    line=42,
                )
            )
            penalty += 55
        score = float(max(0, 100 - penalty))
        if any(item.severity == "critical" for item in findings):
            status = TaskStatus.failed
        elif findings:
            status = TaskStatus.warning
        else:
            status = TaskStatus.passed
        observation = await self.llm_observation(
            context, "Find security regressions, trust-boundary changes, and suspicious data flows."
        )
        return AgentResult(
            role=self.role,
            title=self.title,
            status=status,
            summary=(
                "No high-confidence security regression was found."
                if not findings
                else f"Found {len(findings)} security concern(s) requiring review."
            ),
            score=score,
            findings=findings,
            evidence={
                "rules_checked": len(RULES),
                "added_lines_scanned": len(added_lines),
                "model_observation": observation,
            },
        )
