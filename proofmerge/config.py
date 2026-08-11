from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="PROOFMERGE_",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "ProofMerge"
    environment: Literal["development", "test", "production"] = "development"
    api_prefix: str = "/api/v1"
    database_url: str = "sqlite+aiosqlite:///./proofmerge.db"
    web_url: str = "http://localhost:3000"
    cors_origins: str = "http://localhost:3000"

    github_webhook_secret: str = ""
    github_token: str = ""

    sandbox_backend: Literal["docker", "local", "disabled"] = "docker"
    allow_local_execution: bool = False
    sandbox_image: str = "python:3.12-slim"
    sandbox_timeout_seconds: int = Field(default=300, ge=5, le=1800)

    llm_provider: Literal["deterministic", "ollama"] = "deterministic"
    ollama_url: str = "http://localhost:11434/api/generate"
    ollama_model: str = "llama3.2:1b"

    queue_backend: Literal["memory", "kafka"] = "memory"
    kafka_bootstrap_servers: str = "localhost:19092"
    kafka_topic: str = "proofmerge.reviews"

    qdrant_url: str = ""
    qdrant_collection: str = "proofmerge_knowledge"

    artifact_dir: Path = Path(".proofmerge-artifacts")
    workspace_dir: Path = Path(".proofmerge-workspaces")
    s3_endpoint_url: str = ""
    s3_bucket: str = "proofmerge-artifacts"
    s3_access_key: str = ""
    s3_secret_key: str = ""

    auto_fix_enabled: bool = False

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
