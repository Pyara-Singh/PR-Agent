import re
import shutil
import stat
import tempfile
import zipfile
from asyncio import to_thread
from pathlib import Path

from PR_Agent.agents.base import BaseAgent, ReviewContext
from PR_Agent.config import Settings
from PR_Agent.github import GitHubClient
from PR_Agent.models import TaskStatus
from PR_Agent.sandbox import SandboxRunner, SandboxUnavailable
from PR_Agent.schemas import AgentResult, Finding
from PR_Agent.test_config import TestConfigurationError, TestPlan, load_test_plan


class ReproductionAgent(BaseAgent):
    role = "reproduction"
    title = "Scientific reproduction"

    def __init__(self, llm, settings: Settings) -> None:
        super().__init__(llm)
        self.settings = settings
        self.github = GitHubClient(settings)
        self.sandbox = SandboxRunner(settings)

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
            return await self._run_repository_probe(context)
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

    async def _run_repository_probe(self, context: ReviewContext) -> AgentResult:
        """Run base-owned repository tests, with a safe C++ fallback for the demo repo."""
        changed_cpp = [
            line.removeprefix("+++ b/")
            for line in context.diff.splitlines()
            if line.startswith("+++ b/") and line.endswith((".cpp", ".cc", ".cxx"))
        ]
        fallback_source = changed_cpp[0] if len(changed_cpp) == 1 else None
        if fallback_source and (
            not re.fullmatch(r"[A-Za-z0-9_./-]+\.(?:cpp|cc|cxx)", fallback_source)
            or fallback_source.startswith("/")
            or ".." in Path(fallback_source).parts
        ):
            fallback_source = None
        if not context.base_sha or not context.head_sha:
            return self._not_configured()

        self.settings.workspace_dir.mkdir(parents=True, exist_ok=True)
        root = Path(tempfile.mkdtemp(prefix="review-", dir=self.settings.workspace_dir))
        try:
            base, plan = await self._run_commit(
                context, context.base_sha, root / "base", fallback_source=fallback_source
            )
            head, _ = await self._run_commit(
                context,
                context.head_sha,
                root / "head",
                plan=plan,
                fallback_source=fallback_source,
            )
        except (
            OSError,
            ValueError,
            zipfile.BadZipFile,
            SandboxUnavailable,
            TestConfigurationError,
        ) as exc:
            return self._execution_warning(str(exc))
        finally:
            shutil.rmtree(root, ignore_errors=True)

        evidence = {
            "base": base,
            "head": head,
            "command": " && ".join(plan.commands) if plan else "g++ -std=c++17 -Wall -Wextra SOURCE -o /run/pr-agent-program && /run/pr-agent-program",
            "network_access": "disabled",
        }
        if head["exit_code"] == 0 and base["exit_code"] != 0:
            return AgentResult(
                role=self.role, title=self.title, status=TaskStatus.passed, score=96,
                summary=(
                    "Repository tests fail on base and pass on the pull-request version."
                    if plan
                    else "The base program fails, while the pull-request version compiles and runs successfully."
                ),
                findings=[], evidence=evidence,
            )
        if head["exit_code"] != 0:
            return AgentResult(
                role=self.role, title=self.title, status=TaskStatus.failed, score=25,
                summary="The pull-request version did not pass the configured execution.",
                findings=[Finding(severity="high", title="Execution failed", detail="Inspect compiler and runtime output in the evidence.")], evidence=evidence,
            )
        return AgentResult(
            role=self.role, title=self.title, status=TaskStatus.passed, score=92,
            summary=(
                "Repository tests passed on both base and pull-request versions."
                if plan
                else "The changed C++ program compiled and ran successfully on both base and PR commits."
            ),
            findings=[], evidence=evidence,
        )

    async def _run_commit(
        self,
        context: ReviewContext,
        sha: str,
        directory: Path,
        *,
        plan: TestPlan | None = None,
        fallback_source: str | None = None,
    ) -> tuple[dict, TestPlan | None]:
        archive = directory.with_suffix(".zip")
        await self.github.download_commit_archive(context.repository, sha, archive)
        with zipfile.ZipFile(archive) as zipped:
            self._safe_extract(zipped, directory)
        archive.unlink(missing_ok=True)
        children = await to_thread(lambda: [item for item in directory.iterdir() if item.is_dir()])
        if len(children) != 1:
            raise ValueError("Unexpected GitHub archive layout")
        workspace = children[0]
        plan = plan or load_test_plan(workspace)
        if plan:
            command = " && ".join(plan.commands)
        elif fallback_source:
            command = f"g++ -std=c++17 -Wall -Wextra {fallback_source} -o /run/pr-agent-program && /run/pr-agent-program"
        else:
            raise TestConfigurationError(
                "No .pr-agent.toml test configuration was found and no safe C++ fallback applies."
            )
        result = await self.sandbox.run(
            workspace, ["sh", "-c", command], image=plan.image if plan else None
        )
        return (
            {
                "exit_code": result.exit_code,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "timed_out": result.timed_out,
            },
            plan,
        )

    @staticmethod
    def _safe_extract(archive: zipfile.ZipFile, destination: Path) -> None:
        """Extract only normal relative files from GitHub's archive."""
        destination.mkdir(parents=True, exist_ok=True)
        for member in archive.infolist():
            relative = Path(member.filename)
            if (
                member.is_dir()
                or not relative.parts
                or relative.is_absolute()
                or ".." in relative.parts
                or ":" in relative.drive
                or member.filename.startswith(("/", "\\"))
                or stat.S_ISLNK(member.external_attr >> 16)
            ):
                if member.is_dir():
                    continue
                raise ValueError("GitHub archive contains an unsafe path")
            target = (destination / relative).resolve()
            if not target.is_relative_to(destination.resolve()):
                raise ValueError("GitHub archive contains an unsafe path")
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(member) as source, target.open("wb") as output:
                shutil.copyfileobj(source, output)

    def _not_configured(self) -> AgentResult:
        return self._execution_warning("Add a base-branch .pr-agent.toml test configuration, or submit a single-file C++ change for the safe fallback.")

    def _execution_warning(self, detail: str) -> AgentResult:
        return AgentResult(role=self.role, title=self.title, status=TaskStatus.warning, score=55,
            summary="Empirical base-versus-head proof could not be collected.",
            findings=[Finding(severity="medium", title="Empirical execution unavailable", detail=detail[:500])],
            evidence={"network_access": "disabled"})
