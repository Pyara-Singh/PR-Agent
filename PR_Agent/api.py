from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from PR_Agent import __version__
from PR_Agent.coding import CodingAgentService
from PR_Agent.config import get_settings
from PR_Agent.database import create_schema, dispose_engine
from PR_Agent.llm import build_llm_provider
from PR_Agent.orchestrator import ReviewOrchestrator
from PR_Agent.routes import coding, health, reviews, webhooks


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    settings.artifact_dir.mkdir(parents=True, exist_ok=True)
    settings.workspace_dir.mkdir(parents=True, exist_ok=True)
    await create_schema()
    app.state.settings = settings
    app.state.orchestrator = ReviewOrchestrator(settings)
    app.state.coding_agent = CodingAgentService(settings, build_llm_provider(settings))
    yield
    await dispose_engine()


def create_app() -> FastAPI:
    settings = get_settings()
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.add_log_level,
            structlog.processors.JSONRenderer(),
        ]
    )
    app = FastAPI(
        title="PR_Agent API",
        description="Zero-trust, evidence-driven pull request review API",
        version=__version__,
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health.router, prefix=settings.api_prefix)
    app.include_router(reviews.router, prefix=settings.api_prefix)
    app.include_router(webhooks.router, prefix=settings.api_prefix)
    app.include_router(coding.router, prefix=settings.api_prefix)
    return app


app = create_app()
