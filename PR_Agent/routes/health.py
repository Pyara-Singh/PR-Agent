from fastapi import APIRouter, Request

from PR_Agent import __version__
from PR_Agent.schemas import HealthRead

router = APIRouter(tags=["system"])


@router.get("/health", response_model=HealthRead)
async def health(request: Request) -> HealthRead:
    return HealthRead(version=__version__, environment=request.app.state.settings.environment)
