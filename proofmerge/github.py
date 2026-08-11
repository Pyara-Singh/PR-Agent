import hashlib
import hmac

import httpx

from proofmerge.config import Settings
from proofmerge.schemas import PullRequestCreate


class InvalidWebhookSignature(ValueError):
    pass


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
            "User-Agent": "proofmerge/0.1",
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
