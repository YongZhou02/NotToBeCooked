import json

import httpx
import pytest
from pydantic import SecretStr

from app.core.config import settings
from app.services import query_rewrite


@pytest.mark.asyncio
@pytest.mark.parametrize("provider", ["groq", "gemini"])
async def test_rewrite_provider_contract(monkeypatch, provider):
    monkeypatch.setattr(settings, "GROQ_API_KEY", SecretStr("q" if provider == "groq" else ""))
    monkeypatch.setattr(settings, "GEMINI_API_KEY", SecretStr("g" if provider == "gemini" else ""))
    requests = []

    def handler(request):
        payload = json.loads(request.content)
        requests.append(payload)
        if provider == "groq":
            supplied = json.loads(payload["messages"][1]["content"])
        else:
            supplied = json.loads(payload["contents"][0]["parts"][0]["text"])
        assert supplied == {
            "question": "what about its uses?",
            "previous_question": "What is a lexer?",
        }
        content = json.dumps({"query": "  lexer\n uses "})
        body = (
            {"choices": [{"message": {"content": content}}]}
            if provider == "groq"
            else {"candidates": [{"content": {"parts": [{"text": content}]}}]}
        )
        return httpx.Response(200, json=body)

    real_client = httpx.AsyncClient
    monkeypatch.setattr(
        query_rewrite.httpx,
        "AsyncClient",
        lambda **kw: real_client(
            transport=httpx.MockTransport(handler),
            **kw,
        ),
    )
    assert (
        await query_rewrite.rewrite_query("what about its uses?", "What is a lexer?")
        == "lexer uses"
    )
    assert len(requests) == 1
