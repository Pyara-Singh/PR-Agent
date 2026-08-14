import hashlib
import hmac
import re
from asyncio import to_thread
from pathlib import Path

import httpx

from PR_Agent.config import Settings
from PR_Agent.schemas import PullRequestCreate


class InvalidWebhookSignature(ValueError):
    pass


def format_review_comment(report: dict) -> str:
    """Create a bounded, human-readable GitHub comment from stored review evidence."""
    decision = str(report.get("decision", "needs_work")).replace("_", " ").upper()
    summary = str(report.get("summary", "Evidence report completed."))[:500]
    lines = [
        "## PR_Agent evidence report",
        "",
        f"**Advisory decision:** `{decision}`",
        f"{summary}",
        "",
        "| Evidence area | Status | Score |",
        "| --- | --- | ---: |",
    ]
    findings: list[str] = []
    for agent in report.get("agents", []):
        title = str(agent.get("title", agent.get("role", "Agent")))[:80]
        status = str(agent.get("status", "unknown"))[:24]
        score = agent.get("score")
        score_text = f"{float(score):.0f}" if isinstance(score, (int, float)) else "—"
        lines.append(f"| {title} | `{status}` | {score_text} |")
        for finding in agent.get("findings", [])[:3]:
            severity = str(finding.get("severity", "info")).upper()
            title = str(finding.get("title", "Finding"))[:160]
            findings.append(f"- **{severity}:** {title}")
    if findings:
        lines.extend(["", "### Findings", *findings[:8]])
    lines.extend(
        [
            "",
            "This report is advisory. A human reviewer must still approve or request changes.",
        ]
    )
    return "\n".join(lines)


def verify_github_signature(body: bytes, signature: str | None, secret: str) -> None:
    if not secret:
        return
    if not signature or not signature.startswith("sha256="):
        raise InvalidWebhookSignature("Missing GitHub webhook signature")
    expected = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise InvalidWebhookSignature("Invalid GitHub webhook signature")


class GitHubClient:
    def __init__(self, settings: Settings) -> None:
        self.token = settings.github_token

    @property
    def headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "PR_Agent/0.1",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    async def fetch_diff(self, diff_url: str) -> str:
        if not diff_url:
            return ""
        headers = {**self.headers, "Accept": "application/vnd.github.v3.diff"}
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            response = await client.get(diff_url, headers=headers)
            response.raise_for_status()
            return response.text[:2_000_000]

    async def download_commit_archive(self, repository: str, sha: str, destination: Path) -> None:
        """Download one GitHub commit snapshot without running repository-controlled commands."""
        if not re.fullmatch(r"[A-Fa-f0-9]{7,64}", sha):
            raise ValueError("Invalid commit SHA")
        owner, separator, name = repository.partition("/")
        if not separator or not owner or not name or "/" in name:
            raise ValueError("Repository must be in owner/name format")
        url = f"https://api.github.com/repos/{owner}/{name}/zipball/{sha}"
        async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
            response = await client.get(url, headers=self.headers)
            response.raise_for_status()
        await to_thread(destination.write_bytes, response.content)

    async def post_comment(self, repository: str, number: int, body: str) -> None:
        if not self.token:
            return
        url = f"https://api.github.com/repos/{repository}/issues/{number}/comments"
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(url, headers=self.headers, json={"body": body})
            response.raise_for_status()


def pull_request_from_webhook(payload: dict, diff: str) -> PullRequestCreate:
    pull_request = payload["pull_request"]
    repository = payload["repository"]["full_name"]
    return PullRequestCreate(
        repository=repository,
        number=int(pull_request["number"]),
        title=pull_request.get("title") or "Untitled pull request",
        author=(pull_request.get("user") or {}).get("login", "unknown"),
        description=pull_request.get("body") or "",
        base_sha=(pull_request.get("base") or {}).get("sha", ""),
        head_sha=(pull_request.get("head") or {}).get("sha", ""),
        base_ref=(pull_request.get("base") or {}).get("ref", "main"),
        head_ref=(pull_request.get("head") or {}).get("ref", ""),
        html_url=pull_request.get("html_url") or "",
        diff=diff,
    )
