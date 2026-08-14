from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="PR_AGENT_",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "PR_Agent"
    environment: Literal["development", "test", "production"] = "development"
    api_prefix: str = "/api/v1"
    database_url: str = "sqlite+aiosqlite:///./PR_Agent.db"
    web_url: str = "http://localhost:3000"
    cors_origins: str = "http://localhost:3000"

    github_webhook_secret: str = ""
    github_token: str = ""
    github_comments_enabled: bool = False

    sandbox_backend: Literal["docker", "local", "disabled"] = "docker"
    allow_local_execution: bool = False
    sandbox_image: str = "gcc:14"
    sandbox_timeout_seconds: int = Field(default=300, ge=5, le=1800)

    llm_provider: Literal["deterministic", "ollama", "openai", "gemini", "grok"] = "deterministic"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    openai_url: str = "https://api.openai.com/v1/chat/completions"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    gemini_url: str = "https://generativelanguage.googleapis.com/v1beta/models"
    grok_api_key: str = ""
    grok_model: str = "grok-4.5"
    grok_url: str = "https://api.x.ai/v1/chat/completions"
    ollama_url: str = "http://localhost:11434/api/generate"
    ollama_model: str = "llama3.2:1b"

    queue_backend: Literal["memory", "kafka"] = "memory"
    kafka_bootstrap_servers: str = "localhost:19092"
    kafka_topic: str = "PR_Agent.reviews"

    qdrant_url: str = ""
    qdrant_collection: str = "PR_Agent_knowledge"

    artifact_dir: Path = Path(".PR_Agent-artifacts")
    workspace_dir: Path = Path(".PR_Agent-workspaces")
    s3_endpoint_url: str = ""
    s3_bucket: str = "PR_Agent-artifacts"
    s3_access_key: str = ""
    s3_secret_key: str = ""

    coding_agent_enabled: bool = False
    coding_allowed_roots: str = ""
    coding_auto_push: bool = False
    coding_max_files: int = Field(default=8, ge=1, le=25)

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def coding_root_list(self) -> list[Path]:
        return [Path(root.strip()).resolve() for root in self.coding_allowed_roots.split(",") if root.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
