import httpx
import pytest

from PR_Agent.llm import GeminiProvider


@pytest.mark.asyncio
async def test_gemini_provider_keeps_api_key_out_of_request_url(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    async def fake_post(self, url: str, **kwargs):
        del self
        captured["url"] = url
        captured["headers"] = kwargs["headers"]
        return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": "{}"}]}}]})

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    provider = GeminiProvider("https://example.test/models", "secret-value", "gemini-test")

    assert await provider.complete(system="system", prompt="prompt") == "{}"
    assert "secret-value" not in str(captured["url"])
    assert captured["headers"] == {"x-goog-api-key": "secret-value"}
