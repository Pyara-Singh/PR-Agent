import asyncio
import subprocess
from pathlib import Path

import pytest

from PR_Agent.coding import CodingAgentService
from PR_Agent.config import Settings


class DraftProvider:
    def __init__(self) -> None:
        self.calls = 0

    async def complete(self, *, system: str, prompt: str) -> str:
        del system, prompt
        self.calls += 1
        if self.calls == 1:
            return '{"edits":[{"path":"app.py","instruction":"Return a greeting."}]}'
        return '{"content":"def greeting():\\n    return \\"hello\\"\\n"}'


def git(repository: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repository), *args], check=True, capture_output=True)


@pytest.mark.asyncio
async def test_coding_drafts_without_writing_until_approval(tmp_path: Path) -> None:
    repository = tmp_path / "repo"
    repository.mkdir()
    git(repository, "init")
    git(repository, "config", "user.email", "test@example.com")
    git(repository, "config", "user.name", "Test")
    source = repository / "app.py"
    source.write_text("def greeting():\n    return 'old'\n", encoding="utf-8")
    git(repository, "add", "app.py")
    git(repository, "commit", "-m", "initial")
    settings = Settings(coding_agent_enabled=True, coding_allowed_roots=str(tmp_path))
    service = CodingAgentService(settings, DraftProvider())
    job = service.create_job("Update the greeting", str(repository))

    await service.run(job.id)

    assert job.status == "awaiting_approval"
    assert job.proposals[0].path == "app.py"
    assert source.read_text(encoding="utf-8") == "def greeting():\n    return 'old'\n"

    await service.decide(job.id, [], "No change", False)

    assert job.status == "rejected"
    assert source.read_text(encoding="utf-8") == "def greeting():\n    return 'old'\n"


@pytest.mark.asyncio
async def test_coding_commits_only_the_explicitly_approved_draft(tmp_path: Path) -> None:
    repository = tmp_path / "repo"
    repository.mkdir()
    git(repository, "init")
    git(repository, "config", "user.email", "test@example.com")
    git(repository, "config", "user.name", "Test")
    source = repository / "app.py"
    source.write_text("def greeting():\n    return 'old'\n", encoding="utf-8")
    git(repository, "add", "app.py")
    git(repository, "commit", "-m", "initial")
    service = CodingAgentService(
        Settings(coding_agent_enabled=True, coding_allowed_roots=str(tmp_path)), DraftProvider()
    )
    job = service.create_job("Update the greeting", str(repository))
    await service.run(job.id)

    await service.decide(job.id, ["app.py"], "Improve greeting", False)

    assert job.status == "committed"
    assert job.branch.startswith("pr-agent/coding-")
    assert "hello" in source.read_text(encoding="utf-8")
    assert "Improve greeting" in await asyncio.to_thread(
        subprocess.check_output,
        ["git", "-C", str(repository), "log", "-1", "--format=%s"],
        text=True,
    )
