"""Provider selection (Gemini first, Groq as sole-key fallback) and the Groq call."""

import json
from uuid import uuid4

import httpx
import pytest
from pydantic import SecretStr

from app.core.config import settings
from app.schemas.rag import RetrievedChunk
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

    answer = {
        "claims": [{"text": "a", "markers": [1]}],
        "grounded": True,
        "citations": [{"marker": 1, "evidence_id": "1.1"}],
    }
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

    source = RetrievedChunk(
        chunk_id=uuid4(),
        file_id=uuid4(),
        course_id=uuid4(),
        filename="source.pdf",
        page_start=1,
        page_end=1,
        heading=None,
        score=1.0,
        content="q",
    )
    result = await llm.generate_answer(question="?", context="c", sources=[source])
    assert result.answer == "a [1]" and result.grounded
    assert result.citations[0].quote == "q"
    assert calls["n"] == 2 and sleeps == [2.0]


def test_groq_claims_are_rendered_by_the_server():
    answer = llm.GroqAnswer.model_validate(
        {
            "claims": [
                {"text": "First fact.", "markers": [2, 1, 2]},
                {"text": "Second fact.", "markers": [3]},
            ],
            "grounded": True,
            "citations": [
                {"marker": 1, "evidence_id": "1.1"},
                {"marker": 2, "evidence_id": "2.1"},
                {"marker": 3, "evidence_id": "3.1"},
            ],
        }
    ).render({"1.1": (1, "one"), "2.1": (2, "two"), "3.1": (3, "three")})

    assert answer.answer == "First fact. [2] [1]\n\nSecond fact. [3]"
    assert [citation.quote for citation in answer.citations] == ["one", "two", "three"]


def test_visual_marker_brackets_are_canonicalised_but_numbers_are_unchanged():
    answer = llm.LlmAnswer(
        answer="First 【5】 and second ［12］.", grounded=True, citations=[]
    )
    assert answer.answer == "First [5] and second [12]."


def test_grounded_groq_claim_without_a_marker_is_rejected():
    answer = llm.GroqAnswer.model_validate(
        {
            "claims": [{"text": "Unsupported claim.", "markers": []}],
            "grounded": True,
            "citations": [],
        }
    )
    with pytest.raises(ValueError, match="needs a source marker"):
        answer.render({})


def test_evidence_catalog_quotes_are_exact_source_substrings():
    source = RetrievedChunk(
        chunk_id=uuid4(),
        file_id=uuid4(),
        course_id=uuid4(),
        filename="source.pdf",
        page_start=1,
        page_end=1,
        heading=None,
        score=1.0,
        content="First sentence. ▪ Second sentence.\nThird line.",
    )

    evidence, rendered = llm._evidence_catalog([source])

    assert evidence == {
        "1.1": (1, "First sentence."),
        "1.2": (1, "Second sentence."),
        "1.3": (1, "Third line."),
    }
    assert all(quote in source.content for _, quote in evidence.values())
    assert "1.2: Second sentence." in rendered


def test_evidence_id_cannot_escape_its_source_marker():
    answer = llm.GroqAnswer.model_validate(
        {
            "claims": [{"text": "Claim.", "markers": [2]}],
            "grounded": True,
            "citations": [{"marker": 2, "evidence_id": "1.1"}],
        }
    )
    with pytest.raises(ValueError, match="belongs to marker 1"):
        answer.render({"1.1": (1, "source text")})
