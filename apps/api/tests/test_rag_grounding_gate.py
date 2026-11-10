"""What /rag/query does with an answer it cannot verify.

These exercise the decision between the model and the response, which is the
only place `grounded` is allowed to become True. The session and the
conversation lookup are mocked; everything from `_retrieve` onwards is the real
code path.
"""

from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.config import settings
from app.db.database import get_session
from app.dependencies.auth import get_current_user
from app.routers import rag as rag_module
from app.schemas.chat import ChatRole, Conversation
from app.schemas.rag import RetrievedChunk
from app.services.llm import GENERATION_FAILED, NOTHING_CITED, REFUSAL, UNVERIFIED, LlmAnswer

USER_ID = uuid4()
COURSE_ID = uuid4()
CONVERSATION_ID = uuid4()

SOURCES = [
    RetrievedChunk(
        chunk_id=uuid4(),
        file_id=uuid4(),
        course_id=COURSE_ID,
        filename="Lecture 3.pdf",
        page_start=12,
        page_end=12,
        heading="Indexing",
        score=0.81,
        content="A partial index covers only the rows matching its WHERE clause,\n"
        "so it is smaller than a full index.",
    ),
    RetrievedChunk(
        chunk_id=uuid4(),
        file_id=uuid4(),
        course_id=COURSE_ID,
        filename="Lecture 4.pdf",
        page_start=5,
        page_end=5,
        heading=None,
        score=0.74,
        content="A B-tree index stores keys in sorted order.",
    ),
]


@pytest.fixture
def client(monkeypatch):
    """A /rag/query with retrieval stubbed to SOURCES and the database mocked.

    `added` on the client collects every row the route wrote, so a test can
    assert on the stored turn as well as on the response.
    """
    added: list[object] = []

    conversation = Conversation(id=CONVERSATION_ID, course_id=COURSE_ID, title="t")

    async def fake_conversation(**_kwargs):
        return conversation

    async def fake_retrieve(_request, _session, _user_id, **_kwargs):
        return list(SOURCES)

    monkeypatch.setattr(rag_module, "get_or_create_conversation", fake_conversation)
    monkeypatch.setattr(rag_module, "_retrieve", fake_retrieve)
    monkeypatch.setattr(settings, "LLM_FAKE_MODE", True)

    session = AsyncMock()
    session.add = Mock(side_effect=added.append)

    test_app = FastAPI()
    test_app.include_router(rag_module.rag_router, prefix="/rag")
    test_app.dependency_overrides[get_session] = lambda: session
    test_app.dependency_overrides[get_current_user] = lambda: {"sub": str(USER_ID)}

    test_client = TestClient(test_app)
    test_client.added = added  # pyright: ignore[reportAttributeAccessIssue]
    return test_client


def _assistant_turn(client):
    return next(m for m in client.added if m.role == ChatRole.ASSISTANT)


def test_retrieval_confidence_combines_peak_and_support():
    weak = rag_module._confidence_from_similarities([0.507, 0.479, 0.477, 0.476, 0.472])
    strong = rag_module._confidence_from_similarities([0.62, 0.55, 0.51, 0.44, 0.40])
    assert weak["strong_chunk_count"] == 1
    assert weak["score"] == pytest.approx(0.466333, abs=1e-5)
    assert weak["score"] < 0.5 < strong["score"]


def test_rrf_merge_rewards_chunks_found_by_both_queries():
    shared = SOURCES[0]
    original_only = SOURCES[1]
    rewritten_only = SOURCES[1].model_copy(update={"chunk_id": uuid4(), "page_start": 99})
    merged = rag_module._rrf_merge([original_only, shared], [rewritten_only, shared], limit=3)
    assert [chunk.chunk_id for chunk in merged] == [
        shared.chunk_id,
        rewritten_only.chunk_id,
        original_only.chunk_id,
    ]


def test_anchor_terms_keep_content_and_drop_question_framing():
    assert rag_module._anchor_terms(
        "A source comment disappears before parsing, whereas count becomes an identifier token."
    ) == ["comment", "disappears", "parsing", "count", "identifier", "token"]


def test_low_confidence_rewrites_before_one_generation_and_keeps_scope(client, monkeypatch):
    monkeypatch.setattr(settings, "LLM_FAKE_MODE", False)
    monkeypatch.setattr(settings, "QUERY_REWRITE_ENABLED", True)
    monkeypatch.setattr(rag_module, "embed_query", lambda _query: [0.0] * 1024)
    monkeypatch.setattr(
        rag_module,
        "_retrieval_confidence",
        AsyncMock(side_effect=[{"score": 0.4}, {"score": 0.8}]),
    )
    rewrite = AsyncMock(return_value="partial index WHERE clause")
    monkeypatch.setattr(rag_module, "rewrite_query", rewrite)
    retry_source = SOURCES[0].model_copy(update={"chunk_id": uuid4(), "page_start": 99})
    retrieve = AsyncMock(side_effect=[list(SOURCES), [retry_source]])
    monkeypatch.setattr(rag_module, "_retrieve", retrieve)
    monkeypatch.setattr(
        rag_module, "_keyword_anchor_retrieve", AsyncMock(return_value=[retry_source])
    )
    candidate = LlmAnswer(
        answer="A partial index covers matching rows [1].",
        grounded=True,
        citations=[rag_module.LlmCitation(marker=1, quote=retry_source.content)],
    )
    generate = AsyncMock(return_value=candidate)
    monkeypatch.setattr(rag_module, "generate_answer", generate)
    body = client.post(
        "/rag/query",
        json={
            "question": "What is a partial index?",
            "course_id": str(COURSE_ID),
            "file_ids": [str(SOURCES[0].file_id)],
        },
    ).json()
    assert generate.await_count == 1
    assert retrieve.await_count == 2
    original = retrieve.await_args_list[0].args
    retry_call = retrieve.await_args_list[1]
    retry = retry_call.args
    assert retry[0].question == "partial index WHERE clause"
    assert retry[0].file_ids == original[0].file_ids
    assert retry[0].course_id == original[0].course_id
    assert retry[2] == original[2] == USER_ID
    assert retry_call.kwargs["search_config"].keyword_weight == 2.0
    assert retry_call.kwargs["search_config"].vector_weight == 1.0
    assert generate.await_args.kwargs["question"] == "What is a partial index?"
    assert [source.page_start for source in generate.await_args.kwargs["sources"]] == [99, 12, 5]
    assert body["grounded"] is True
    trace = _assistant_turn(client).scope_snapshot["query_rewrite"]
    assert trace["attempted"]
    assert trace["accepted"] is True
    assert body["citations"][0]["page"] == 99
    assert str(retry_source.chunk_id) in _assistant_turn(client).scope_snapshot["used_chunk_ids"]


def test_high_confidence_does_not_rewrite(client, monkeypatch):
    monkeypatch.setattr(settings, "LLM_FAKE_MODE", False)
    monkeypatch.setattr(settings, "QUERY_REWRITE_ENABLED", True)
    monkeypatch.setattr(rag_module, "embed_query", lambda _query: [0.0] * 1024)
    monkeypatch.setattr(rag_module, "_retrieval_confidence", AsyncMock(return_value={"score": 0.8}))
    rewrite = AsyncMock()
    monkeypatch.setattr(rag_module, "rewrite_query", rewrite)
    generate = AsyncMock(return_value=LlmAnswer(answer=REFUSAL, grounded=False, citations=[]))
    monkeypatch.setattr(rag_module, "generate_answer", generate)
    body = client.post("/rag/query", json={"question": "What is a partial index?"}).json()
    rewrite.assert_not_awaited()
    assert body["grounded"] is False


def test_a_verifiable_answer_is_sent_and_marked_grounded(client):
    body = client.post("/rag/query", json={"question": "What is a partial index?"}).json()

    assert body["grounded"] is True
    assert body["used_chunks"] == 2
    assert [c["marker"] for c in body["citations"]] == [1, 2]
    assert _assistant_turn(client).grounded is True


def test_citations_take_their_provenance_from_the_chunk_not_the_model(client):
    """The model supplies a marker and a quote. Nothing else."""
    body = client.post("/rag/query", json={"question": "What is a partial index?"}).json()

    first = body["citations"][0]
    assert first["file_id"] == str(SOURCES[0].file_id)
    assert first["filename"] == "Lecture 3.pdf"
    assert first["page"] == 12


def test_one_altered_word_in_a_quote_costs_the_whole_answer(client, monkeypatch):
    """only -> never. The sentence still reads; it is no longer in the source."""
    honest = rag_module.generate_answer

    async def liar(*, question, context, sources, **kwargs):
        draft = await honest(
            question=question,
            context=context,
            sources=sources,
            **kwargs,
        )
        draft.citations[0].quote = draft.citations[0].quote.replace("only", "never")
        return draft

    monkeypatch.setattr(rag_module, "generate_answer", liar)

    body = client.post("/rag/query", json={"question": "What is a partial index?"}).json()

    assert body["grounded"] is False
    assert body["citations"] == []
    assert body["answer"] == UNVERIFIED
    # Not a 500. The pipeline worked; the answer failed its own check.
    assert _assistant_turn(client).grounded is False


def test_a_citation_the_answer_never_uses_is_dropped_not_fatal(client, monkeypatch):
    """Before 24 Sep this refused the whole answer. The extra citation supports
    nothing the reader sees, so it goes, and the answer it was attached to is sent."""
    honest = rag_module.generate_answer

    async def lists_an_extra(
        *,
        question,
        context,
        sources,
        **kwargs,
    ):
        draft = await honest(
            question=question,
            context=context,
            sources=sources,
            **kwargs,
        )
        draft.answer = draft.answer.replace(" [2]", "")
        return draft

    monkeypatch.setattr(rag_module, "generate_answer", lists_an_extra)

    body = client.post("/rag/query", json={"question": "What is a partial index?"}).json()

    assert body["grounded"] is True
    assert [c["marker"] for c in body["citations"]] == [1]


def test_a_bad_quote_beside_a_good_one_on_the_same_marker_is_dropped(client, monkeypatch):
    """Before 24 Sep one bad quote refused the whole answer, even when the same
    marker carried an exact one. Now the bad quote goes and the answer is sent."""
    honest = rag_module.generate_answer

    async def one_bad_extra(*, question, context, sources, **kwargs):
        draft = await honest(
            question=question,
            context=context,
            sources=sources,
            **kwargs,
        )
        bad = draft.citations[0].model_copy(update={"quote": "a partial index covers every row"})
        draft.citations.append(bad)
        return draft

    monkeypatch.setattr(rag_module, "generate_answer", one_bad_extra)

    body = client.post("/rag/query", json={"question": "What is a partial index?"}).json()

    assert body["grounded"] is True
    assert "every row" not in str(body["citations"])
    assert [c["marker"] for c in body["citations"]] == [1, 2]


def test_a_marker_with_nothing_behind_it_costs_the_whole_answer(client, monkeypatch):
    honest = rag_module.generate_answer

    async def over_cites(*, question, context, sources, **kwargs):
        draft = await honest(
            question=question,
            context=context,
            sources=sources,
            **kwargs,
        )
        draft.answer += " And a third point [3]."
        return draft

    monkeypatch.setattr(rag_module, "generate_answer", over_cites)

    body = client.post("/rag/query", json={"question": "What is a partial index?"}).json()
    assert body["grounded"] is False
    assert body["answer"] == UNVERIFIED


def test_a_failing_generator_says_so_rather_than_500s(client, monkeypatch):
    async def boom(**_kwargs):
        raise RuntimeError("Gemini 503: upstream unavailable")

    monkeypatch.setattr(rag_module, "generate_answer", boom)

    response = client.post("/rag/query", json={"question": "What is a partial index?"})
    assert response.status_code == 200
    # Not REFUSAL: nobody checked the material, so "it does not cover this"
    # would be an unchecked claim about the user's notes.
    assert response.json()["answer"] == GENERATION_FAILED
    assert response.json()["answer"] != REFUSAL
    assert response.json()["grounded"] is False


def test_the_scope_snapshot_separates_what_was_retrieved_from_what_was_used(client):
    file_ids = [str(uuid4())]
    client.post(
        "/rag/query",
        json={"question": "What is a partial index?", "file_ids": file_ids},
    )

    snapshot = _assistant_turn(client).scope_snapshot
    assert len(snapshot["retrieved_chunk_ids"]) == 2
    assert len(snapshot["used_chunk_ids"]) == 2
    assert snapshot["mentioned_file_ids"] == file_ids
    # Recorded because two vectors of equal dimension from different models are
    # not comparable, and a snapshot without this cannot be re-checked (R5).
    assert snapshot["embedding_model"]


# --- r47: what happens to the model's claim about partial coverage -------------


def test_a_named_gap_reaches_the_response_and_the_stored_turn(client, monkeypatch):
    """`uncovered` is a column for the same reason `grounded` is one: a
    conversation reopened next week has to show the caveat it showed when it
    was written, and nothing can parse that back out of the prose."""
    honest = rag_module.generate_answer
    GAP = "The sources do not cover B-tree range scans."

    async def partial(*, question, context, sources, **kwargs):
        draft = await honest(
            question=question,
            context=context,
            sources=sources,
            **kwargs,
        )
        draft.uncovered = GAP
        return draft

    monkeypatch.setattr(rag_module, "generate_answer", partial)

    body = client.post("/rag/query", json={"question": "Indexes?"}).json()

    assert body["grounded"] is True
    assert body["uncovered"] == GAP
    assert _assistant_turn(client).uncovered == GAP


def test_a_gap_declared_with_no_citations_costs_the_whole_answer(client, monkeypatch):
    """The model says the sources cover part of the question and then cites
    none of them. Both claims cannot be true, so neither is sent -- and the
    reader is told nothing was found, not that citations failed a check."""

    async def inconsistent(*, question, context, sources, **_kwargs):
        return LlmAnswer(
            answer="Partial indexes are covered by the material.",
            grounded=True,
            citations=[],
            uncovered="The sources do not cover B-tree range scans.",
        )

    monkeypatch.setattr(rag_module, "generate_answer", inconsistent)

    body = client.post("/rag/query", json={"question": "Indexes?"}).json()

    assert body["answer"] == NOTHING_CITED
    assert body["grounded"] is False
    assert body["uncovered"] is None
    assert _assistant_turn(client).uncovered is None


def test_a_gap_with_a_marker_but_no_citation_is_still_unverified(client, monkeypatch):
    """[1] in the text with nothing listed behind it is a citation that failed,
    so this one keeps UNVERIFIED."""

    async def dangling(*, question, context, sources, **_kwargs):
        return LlmAnswer(
            answer="Partial indexes are smaller [1].",
            grounded=True,
            citations=[],
            uncovered="The sources do not cover B-tree range scans.",
        )

    monkeypatch.setattr(rag_module, "generate_answer", dangling)

    body = client.post("/rag/query", json={"question": "Indexes?"}).json()

    assert body["answer"] == UNVERIFIED
    assert body["grounded"] is False


def test_an_ungrounded_answer_carries_no_gap(client, monkeypatch):
    """A refusal covers nothing, so naming one missing part would read as a
    narrower claim than the refusal sitting beside it."""
    honest = rag_module.generate_answer

    async def modest(*, question, context, sources, **kwargs):
        draft = await honest(
            question=question,
            context=context,
            sources=sources,
            **kwargs,
        )
        draft.citations = []
        draft.answer = "Indexes are complicated."
        draft.uncovered = None
        return draft

    monkeypatch.setattr(rag_module, "generate_answer", modest)

    body = client.post("/rag/query", json={"question": "Indexes?"}).json()
    assert body["grounded"] is False
    assert body["uncovered"] is None
