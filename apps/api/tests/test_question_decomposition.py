from unittest.mock import AsyncMock, Mock

import pytest

from app.core.config import settings
from app.services import question_decomposition


class FakeResponse:
    def __init__(self, content: str, status_code: int = 200):
        self.content = content
        self.status_code = status_code
        self.headers = {}

    def raise_for_status(self):
        return None

    def json(self):
        return {"choices": [{"message": {"content": self.content}}]}


@pytest.mark.asyncio
async def test_decomposition_is_bounded_deduplicated_and_never_answers(monkeypatch):
    monkeypatch.setattr(settings, "GEMINI_API_KEY", Mock(get_secret_value=lambda: ""))
    monkeypatch.setattr(settings, "GROQ_API_KEY", Mock(get_secret_value=lambda: "key"))
    monkeypatch.setattr(settings, "RETRIEVAL_DECOMPOSITION_MAX_QUESTIONS", 3)
    post = AsyncMock(
        return_value=FakeResponse(
            '{"questions":[" First fact? ","Second fact?","Second fact?","Fourth?"]}'
        )
    )
    client = AsyncMock()
    client.__aenter__.return_value.post = post
    monkeypatch.setattr(question_decomposition.httpx, "AsyncClient", Mock(return_value=client))

    result = await question_decomposition.decompose_question(
        "Complex original question?", ["Named entity and stage " * 50] * 5
    )

    assert result == ["First fact?", "Second fact?", "Fourth?"]
    assert post.await_args is not None
    payload = post.await_args.kwargs["json"]
    assert len(payload["messages"]) == 2
    assert "Do not answer" in payload["messages"][0]["content"]
    assert len(payload["messages"][1]["content"]) < 1400


@pytest.mark.asyncio
async def test_only_one_503_retry(monkeypatch):
    client = AsyncMock()
    client.post = AsyncMock(side_effect=[FakeResponse("", 503), FakeResponse("{}", 200)])
    sleep = AsyncMock()
    monkeypatch.setattr(question_decomposition.asyncio, "sleep", sleep)
    response = await question_decomposition._post_with_one_service_retry(
        client, "https://example.test"
    )
    assert response.status_code == 200
    assert client.post.await_count == 2
    sleep.assert_awaited_once()
