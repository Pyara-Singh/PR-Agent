from fastapi import APIRouter, Request

from proofmerge import __version__
from proofmerge.schemas import HealthRead

router = APIRouter(tags=["system"])


@router.get("/health", response_model=HealthRead)
async def health(request: Request) -> HealthRead:
    return HealthRead(version=__version__, environment=request.app.state.settings.environment)
