import json
from typing import Protocol

import httpx

from proofmerge.config import Settings


class LLMProvider(Protocol):
    async def complete(self, *, system: str, prompt: str) -> str: ...


class DeterministicProvider:
    """Safe default: agents use deterministic analyzers without a network call."""

    async def complete(self, *, system: str, prompt: str) -> str:
        del system, prompt
        return ""


class OllamaProvider:
    def __init__(self, settings: Settings) -> None:
        self.url = settings.ollama_url
        self.model = settings.ollama_model

    async def complete(self, *, system: str, prompt: str) -> str:
        payload = {
            "model": self.model,
            "system": system,
            "prompt": prompt,
            "stream": False,
            "format": "json",
        }
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(self.url, json=payload)
            response.raise_for_status()
            return str(response.json().get("response", ""))


def build_llm_provider(settings: Settings) -> LLMProvider:
    if settings.llm_provider == "ollama":
        return OllamaProvider(settings)
    return DeterministicProvider()


def parse_untrusted_json(raw: str) -> dict:
    """Parse model output as data only; model text never controls orchestration."""
    if not raw or len(raw) > 100_000:
        return {}
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}
