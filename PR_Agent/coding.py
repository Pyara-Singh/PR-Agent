"""Guarded local coding workflow. It never writes until an explicit approval request."""

from __future__ import annotations

import asyncio
import difflib
import subprocess
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from PR_Agent.config import Settings
from PR_Agent.llm import LLMProvider, parse_untrusted_json

SOURCE_SUFFIXES = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".json", ".md", ".cpp", ".cc", ".cxx", ".h", ".hpp"
}


class CodingAgentError(ValueError):
    pass


@dataclass
class ProposedEdit:
    path: str
    original: str
    content: str
    diff: str

    def public(self) -> dict:
        return {"path": self.path, "diff": self.diff}


@dataclass
class CodingJob:
    id: str
    prompt: str
    repository_path: str
    status: str = "queued"
    plan: list[dict[str, str]] = field(default_factory=list)
    proposals: list[ProposedEdit] = field(default_factory=list)
    events: list[str] = field(default_factory=list)
    error: str = ""
    branch: str = ""
    commit: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def public(self) -> dict:
        return {
            "id": self.id,
            "prompt": self.prompt,
            "repository_path": self.repository_path,
            "status": self.status,
            "plan": self.plan,
            "proposals": [proposal.public() for proposal in self.proposals],
            "events": self.events,
            "error": self.error,
            "branch": self.branch,
            "commit": self.commit,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class CodingAgentService:
    def __init__(self, settings: Settings, provider: LLMProvider) -> None:
        self.settings = settings
        self.provider = provider
        self.jobs: dict[str, CodingJob] = {}
        self.lock = asyncio.Lock()

    def create_job(self, prompt: str, repository_path: str) -> CodingJob:
        repository = self._validate_repository(Path(repository_path))
        job = CodingJob(id=str(uuid.uuid4()), prompt=prompt, repository_path=str(repository))
        self.jobs[job.id] = job
        self._event(job, "Job created; no repository files have been changed.")
        return job

    def get_job(self, job_id: str) -> CodingJob | None:
        return self.jobs.get(job_id)

    async def run(self, job_id: str) -> None:
        job = self._require_job(job_id)
        try:
            job.status = "planning"
            self._event(job, "Reading safe, tracked source-file names for the plan.")
            repository = Path(job.repository_path)
            files = await asyncio.to_thread(self._tracked_source_files, repository)
            raw_plan = await self.provider.complete(
                system=(
                    "You plan a local code change. Return JSON only: "
                    '{"edits":[{"path":"existing/source.py","instruction":"precise change"}]}. '
                    "Choose only listed existing paths and at most 8 edits."
                ),
                prompt=f"Request: {job.prompt}\nTracked safe files:\n" + "\n".join(files),
            )
            parsed = parse_untrusted_json(raw_plan)
            edits = self._validate_plan(parsed.get("edits"), files)
            job.plan = edits
            job.status = "drafting"
            self._event(job, f"Plan accepted with {len(edits)} proposed file change(s).")
            for edit in edits:
                await self._draft_edit(job, repository, edit)
            if not job.proposals:
                raise CodingAgentError("The model did not produce a changed, valid source file.")
            job.status = "awaiting_approval"
            self._event(job, "Drafts are ready. Approve individual files before any write or commit.")
        except Exception as exc:
            job.status = "failed"
            job.error = str(exc)[:1000]
            self._event(job, f"Stopped safely: {job.error}")

    async def decide(
        self, job_id: str, approved_paths: list[str], commit_message: str, push: bool
    ) -> CodingJob:
        async with self.lock:
            job = self._require_job(job_id)
            if job.status != "awaiting_approval":
                raise CodingAgentError("This coding job is not awaiting approval.")
            if push and not self.settings.coding_auto_push:
                raise CodingAgentError("Remote push is disabled by PR_AGENT_CODING_AUTO_PUSH.")
            approved_paths_set = set(approved_paths)
            approved = [proposal for proposal in job.proposals if proposal.path in approved_paths_set]
            if not approved:
                job.status = "rejected"
                self._event(job, "No file was approved; the repository remains unchanged.")
                return job
            repository = self._validate_repository(Path(job.repository_path))
            if await asyncio.to_thread(self._run_git, repository, ["status", "--porcelain"]):
                raise CodingAgentError(
                    "Repository has uncommitted changes. Commit or stash them before applying a draft."
                )
            branch = f"pr-agent/coding-{job.id[:8]}"
            await asyncio.to_thread(self._run_git, repository, ["switch", "-c", branch])
            for proposal in approved:
                target = self._safe_existing_file(repository, proposal.path)
                target.write_text(proposal.content, encoding="utf-8")
            await asyncio.to_thread(self._run_git, repository, ["add", "--", *[item.path for item in approved]])
            await asyncio.to_thread(self._run_git, repository, ["commit", "-m", commit_message])
            commit = await asyncio.to_thread(self._run_git, repository, ["rev-parse", "HEAD"])
            job.branch, job.commit, job.status = branch, commit.strip(), "committed"
            self._event(job, f"Committed {len(approved)} approved file(s) locally on {branch}.")
            if push:
                await asyncio.to_thread(self._run_git, repository, ["push", "-u", "origin", branch])
                job.status = "pushed"
                self._event(job, "Approved commit pushed to origin.")
            return job

    async def _draft_edit(self, job: CodingJob, repository: Path, edit: dict[str, str]) -> None:
        target = self._safe_existing_file(repository, edit["path"])
        original = target.read_text(encoding="utf-8")
        raw = await self.provider.complete(
            system=(
                "Rewrite exactly one existing file. Return JSON only: {\"content\": \"complete file contents\"}. "
                "Do not use markdown fences or explain the change."
            ),
            prompt=(
                f"User request: {job.prompt}\nInstruction: {edit['instruction']}\n"
                f"Path: {edit['path']}\nCurrent contents:\n{original}"
            ),
        )
        content = parse_untrusted_json(raw).get("content")
        if not isinstance(content, str) or len(content) > 200_000:
            raise CodingAgentError(f"Invalid draft returned for {edit['path']}.")
        if content == original:
            self._event(job, f"Skipped unchanged draft for {edit['path']}.")
            return
        diff = "".join(
            difflib.unified_diff(
                original.splitlines(keepends=True), content.splitlines(keepends=True),
                fromfile=f"a/{edit['path']}", tofile=f"b/{edit['path']}",
            )
        )
        job.proposals.append(ProposedEdit(edit["path"], original, content, diff[:100_000]))
        self._event(job, f"Drafted {edit['path']} without writing it to disk.")

    def _validate_repository(self, repository: Path) -> Path:
        if not self.settings.coding_agent_enabled:
            raise CodingAgentError("Coding Agent is disabled. Set PR_AGENT_CODING_AGENT_ENABLED=true.")
        resolved = repository.expanduser().resolve()
        roots = self.settings.coding_root_list
        if not roots or not any(resolved.is_relative_to(root) for root in roots):
            raise CodingAgentError("Repository path is not inside PR_AGENT_CODING_ALLOWED_ROOTS.")
        if not (resolved / ".git").exists():
            raise CodingAgentError("Repository path must be a local Git repository.")
        return resolved

    def _tracked_source_files(self, repository: Path) -> list[str]:
        output = self._run_git(repository, ["ls-files"])
        files: list[str] = []
        for raw_path in output.splitlines():
            try:
                target = self._safe_existing_file(repository, raw_path)
            except CodingAgentError:
                continue
            if target.stat().st_size <= 128_000:
                files.append(raw_path)
            if len(files) >= 200:
                break
        return files

    def _safe_existing_file(self, repository: Path, relative_path: str) -> Path:
        candidate = Path(relative_path)
        if candidate.is_absolute() or ".." in candidate.parts or candidate.suffix.lower() not in SOURCE_SUFFIXES:
            raise CodingAgentError("Only existing, allow-listed source files may be changed.")
        target = (repository / candidate).resolve()
        if not target.is_relative_to(repository) or not target.is_file():
            raise CodingAgentError("Requested path is outside the repository or is not a file.")
        return target

    def _validate_plan(self, value: object, allowed_files: list[str]) -> list[dict[str, str]]:
        if not isinstance(value, list) or not value:
            raise CodingAgentError("The model did not return a valid file-edit plan.")
        allowed = set(allowed_files)
        edits: list[dict[str, str]] = []
        seen: set[str] = set()
        for item in value[: self.settings.coding_max_files]:
            if not isinstance(item, dict):
                continue
            path, instruction = item.get("path"), item.get("instruction")
            if (
                isinstance(path, str)
                and isinstance(instruction, str)
                and path in allowed
                and path not in seen
                and instruction.strip()
                and len(instruction) <= 800
            ):
                edits.append({"path": path, "instruction": instruction.strip()})
                seen.add(path)
        if not edits:
            raise CodingAgentError("The model selected no allowed source files.")
        return edits

    @staticmethod
    def _run_git(repository: Path, arguments: list[str]) -> str:
        completed = subprocess.run(
            ["git", "-C", str(repository), *arguments], capture_output=True, text=True, check=False
        )
        if completed.returncode != 0:
            raise CodingAgentError((completed.stderr or completed.stdout or "Git command failed").strip()[:800])
        return completed.stdout

    def _event(self, job: CodingJob, message: str) -> None:
        job.events = [*job.events[-99:], message]
        job.updated_at = datetime.now(UTC).isoformat()

    def _require_job(self, job_id: str) -> CodingJob:
        job = self.get_job(job_id)
        if job is None:
            raise CodingAgentError("Coding job not found.")
        return job
