"""Provider selection (Gemini first, Groq as sole-key fallback) and the Groq call."""

import json

import httpx
import pytest
from pydantic import SecretStr

from app.core.config import settings
from app.services import llm


def _keys(monkeypatch: pytest.MonkeyPatch, gemini: str, groq: str) -> None:
    monkeypatch.setattr(settings, "GEMINI_API_KEY", SecretStr(gemini))
    monkeypatch.setattr(settings, "GROQ_API_KEY", SecretStr(groq))


@pytest.mark.parametrize(
    ("gemini", "groq", "expected"),
    [("g", "q", "gemini"), ("g", "", "gemini"), ("", "q", "groq"), ("", "", None)],
)
def test_provider_selection(monkeypatch, gemini, groq, expected):
    _keys(monkeypatch, gemini, groq)
    assert settings.llm_provider == expected


@pytest.mark.asyncio
async def test_groq_call_retries_on_429(monkeypatch):
    _keys(monkeypatch, "", "q")
    monkeypatch.setattr(settings, "LLM_FAKE_MODE", False)
    sleeps: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    monkeypatch.setattr(llm.asyncio, "sleep", fake_sleep)

    answer = {"answer": "a", "grounded": True, "citations": [{"marker": 1, "quote": "q"}]}
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        assert request.headers["authorization"] == "Bearer q"
        assert json.loads(request.content)["model"] == "openai/gpt-oss-120b"
        if calls["n"] == 1:
            return httpx.Response(429, headers={"retry-after": "2"})
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(answer)}}]})

    real_client = httpx.AsyncClient
    monkeypatch.setattr(
        llm.httpx,
        "AsyncClient",
        lambda **kw: real_client(transport=httpx.MockTransport(handler), **kw),
    )

    result = await llm.generate_answer(question="?", context="c", sources=[])
    assert result.answer == "a" and result.grounded
    assert calls["n"] == 2 and sleeps == [2.0]
