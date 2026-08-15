import json
from typing import Protocol

import httpx

from PR_Agent.config import Settings


class LLMProvider(Protocol):
    async def complete(self, *, system: str, prompt: str) -> str: ...


class DeterministicProvider:
    """Safe default: agents use deterministic analyzers without a network call."""

    async def complete(self, *, system: str, prompt: str) -> str:
        del system, prompt
        return ""


class OpenAICompatibleProvider:
    """Provider for OpenAI Chat Completions-compatible APIs, including Grok."""

    def __init__(self, url: str, api_key: str, model: str) -> None:
        self.url = url
        self.api_key = api_key
        self.model = model

    async def complete(self, *, system: str, prompt: str) -> str:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0,
            "response_format": {"type": "json_object"},
        }
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(
                self.url,
                headers={"Authorization": f"Bearer {self.api_key}"},
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
        return str(data["choices"][0]["message"].get("content", ""))


class GeminiProvider:
    def __init__(self, url: str, api_key: str, model: str) -> None:
        self.url = url.rstrip("/")
        self.api_key = api_key
        self.model = model

    async def complete(self, *, system: str, prompt: str) -> str:
        payload = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"responseMimeType": "application/json"},
        }
        url = f"{self.url}/{self.model}:generateContent"
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(
                url,
                headers={"x-goog-api-key": self.api_key},
                json=payload,
            )
            if response.is_error:
                detail = "Gemini did not provide an error message."
                try:
                    detail = str(response.json().get("error", {}).get("message", detail))
                except ValueError:
                    pass
                raise RuntimeError(f"Gemini request failed ({response.status_code}): {detail[:500]}")
            data = response.json()
        return str(data["candidates"][0]["content"]["parts"][0].get("text", ""))


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
    if settings.llm_provider in {"openai", "grok"}:
        provider = settings.llm_provider
        api_key = getattr(settings, f"{provider}_api_key")
        if not api_key:
            raise ValueError(f"PR_AGENT_{provider.upper()}_API_KEY is required when using {provider}")
        return OpenAICompatibleProvider(
            getattr(settings, f"{provider}_url"), api_key, getattr(settings, f"{provider}_model")
        )
    if settings.llm_provider == "gemini":
        if not settings.gemini_api_key:
            raise ValueError("PR_AGENT_GEMINI_API_KEY is required when using gemini")
        return GeminiProvider(settings.gemini_url, settings.gemini_api_key, settings.gemini_model)
    return DeterministicProvider()


def parse_untrusted_json(raw: str) -> dict:
    """Parse model output as data only; model text never controls orchestration."""
    if not raw or len(raw) > 100_000:
        return {}
    raw = raw.strip()
    if raw.startswith("```") and raw.endswith("```"):
        raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}
