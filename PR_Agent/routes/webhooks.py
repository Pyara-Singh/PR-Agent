from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, status

from PR_Agent.database import SessionFactory
from PR_Agent.events import KafkaReviewQueue
from PR_Agent.github import (
    GitHubClient,
    InvalidWebhookSignature,
    pull_request_from_webhook,
    verify_github_signature,
)
from PR_Agent.repository import create_or_get_webhook_review, upsert_pull_request

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/github", status_code=status.HTTP_202_ACCEPTED)
async def github_webhook(request: Request, background_tasks: BackgroundTasks) -> dict:
    body = await request.body()
    settings = request.app.state.settings
    try:
        verify_github_signature(
            body,
            request.headers.get("x-hub-signature-256"),
            settings.github_webhook_secret,
        )
    except InvalidWebhookSignature as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc

    event = request.headers.get("x-github-event", "")
    if event == "ping":
        return {"accepted": True, "event": "ping"}
    if event != "pull_request":
        return {"accepted": False, "reason": "event ignored"}
    payload = await request.json()
    if payload.get("action") not in {"opened", "reopened", "synchronize", "ready_for_review"}:
        return {"accepted": False, "reason": "action ignored"}

    github = GitHubClient(settings)
    try:
        diff = await github.fetch_diff(payload["pull_request"].get("diff_url", ""))
    except Exception:
        diff = ""
    pull_request_data = pull_request_from_webhook(payload, diff)
    async with SessionFactory() as session:
        pull_request = await upsert_pull_request(session, pull_request_data)
        review, created = await create_or_get_webhook_review(
            session, pull_request, request.headers.get("x-github-delivery", "")[:100]
        )

    if not created:
        return {"accepted": True, "review_id": review.id, "duplicate": True}

    if settings.queue_backend == "kafka":
        await KafkaReviewQueue(settings).publish(review.id)
    else:
        background_tasks.add_task(request.app.state.orchestrator.run, review.id)
    return {"accepted": True, "review_id": review.id, "duplicate": False}
