from fastapi import APIRouter, Request

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/policies")
async def policy_status(request: Request) -> dict:
    """Expose operational safeguards without exposing any credential or secret."""
    settings = request.app.state.settings
    return {
        "environment": settings.environment,
        "review": {
            "human_approval_required": True,
            "github_evidence_comments_enabled": settings.github_comments_enabled,
            "webhook_signature_required": bool(settings.github_webhook_secret),
        },
        "execution": {
            "backend": settings.sandbox_backend,
            "network_access": "disabled in Docker sandbox",
            "local_execution_enabled": settings.allow_local_execution,
            "timeout_seconds": settings.sandbox_timeout_seconds,
        },
        "coding_agent": {
            "enabled": settings.coding_agent_enabled,
            "remote_push_enabled": settings.coding_auto_push,
            "maximum_proposed_files": settings.coding_max_files,
            "requires_clean_repository": True,
        },
    }
