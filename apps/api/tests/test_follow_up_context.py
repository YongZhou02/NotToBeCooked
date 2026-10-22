"""US-14: a follow-up question is read against the turns before it.

The history is context for understanding the question, never a source, so the
grounding gate is untouched: these tests check what reaches retrieval and the
prompt, and that the history is read from the right conversation in order.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
import pytest_asyncio
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

import app.models  # noqa: F401  -- registers every table before create_all
from app.core.config import settings
from app.db.database import get_session, make_engine
from app.dependencies.auth import get_current_user
from app.routers import rag as rag_module
from app.schemas.chat import ChatRole, Conversation, Message
from app.schemas.course import Course
from app.schemas.rag import RagQueryRequest, RetrievedChunk
from app.schemas.user import User
from app.services.prompt import render_history

COURSE_ID = uuid4()


def _msg(role: ChatRole, content: str, grounded: bool = False) -> Message:
    return Message(
        conversation_id=uuid4(),
        scope_course_id=COURSE_ID,
        role=role,
        content=content,
        grounded=grounded,
        created_at=datetime.now(UTC),
    )


def _chunk(text: str) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=uuid4(),
        file_id=uuid4(),
        course_id=COURSE_ID,
        filename="01 Overview.pdf",
        page_start=13,
        page_end=13,
        heading=None,
        score=0.5,
        content=text,
    )


def test_only_grounded_answers_are_carried_and_only_the_last_two_turns():
    messages = [
        _msg(ChatRole.USER, "what is nlp"),
        _msg(ChatRole.ASSISTANT, "NLP is ... [1]", grounded=True),
        _msg(ChatRole.USER, "what is rrf_k"),
        _msg(ChatRole.ASSISTANT, "No passage in your material ..."),
        _msg(ChatRole.USER, "what is a lexicon"),
        _msg(ChatRole.ASSISTANT, "A lexicon is the set of available words [1].", grounded=True),
    ]
    assert rag_module._pair_turns(messages) == [
        ("what is rrf_k", None),
        ("what is a lexicon", "A lexicon is the set of available words [1]."),
    ]


def test_history_block_strips_old_markers_and_is_empty_on_a_first_question():
    assert render_history([]) == ""
    block = render_history([("what is a lexicon", "A lexicon is a word list [1] [2].")])
    assert "Student: what is a lexicon" in block
    assert "Assistant: A lexicon is a word list." in block
    assert "[1]" not in block
    assert "never cite it" in block


def test_interleave_alternates_without_repeats_and_respects_the_limit():
    a, b, c, d = (_chunk(x) for x in "abcd")
    assert rag_module._interleave([a, b], [c, a, d], limit=5) == [a, c, b, d]
    assert rag_module._interleave([a, b], [c, d], limit=3) == [a, c, b]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("similarity", "first"),
    [(0.3, "joined"), (0.5, "alone"), (0.7, "alone")],
)
async def test_a_follow_up_leads_with_the_search_that_can_stand_alone(
    monkeypatch, similarity, first
):
    # "what does it used for" after "finite state automata": searched alone it
    # matched nothing on FSA, so the joined search has to lead.
    vectors = []

    async def fake_retrieve(request, _session, _user_id, query_vector=None):
        vectors.append(query_vector)
        return [_chunk("joined" if request.question.startswith("finite") else "alone")]

    async def fake_best_similarity(_request, query_vector, _session, _user_id):
        assert query_vector == [0.1]
        return similarity

    monkeypatch.setattr(rag_module, "embed_query", lambda _question: [0.1])
    monkeypatch.setattr(rag_module, "_retrieve", fake_retrieve)
    monkeypatch.setattr(rag_module, "_best_similarity", fake_best_similarity)

    chunks = await rag_module._retrieve_follow_up(
        RagQueryRequest(question="what does it used for", course_id=COURSE_ID),
        "finite state automata",
        AsyncMock(),
        uuid4(),
    )

    assert [chunk.content for chunk in chunks][0] == first
    # The alone search and the similarity share one embedding; the joined
    # search embeds its own question.
    assert vectors == [[0.1], None]


@pytest.mark.asyncio
async def test_a_first_question_searches_once_and_never_measures_similarity(monkeypatch):
    searches = []

    async def fake_retrieve(request, _session, _user_id, query_vector=None):
        searches.append(request.question)
        return []

    async def no_similarity(*_args):
        raise AssertionError("a first question has nothing to be a follow-up to")

    monkeypatch.setattr(rag_module, "_retrieve", fake_retrieve)
    monkeypatch.setattr(rag_module, "_best_similarity", no_similarity)

    await rag_module._retrieve_follow_up(
        RagQueryRequest(question="what is a lexicon", course_id=COURSE_ID),
        None,
        AsyncMock(),
        uuid4(),
    )

    assert searches == ["what is a lexicon"]


@pytest_asyncio.fixture
async def maker(test_database_url):
    engine = make_engine(test_database_url)
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
        await conn.run_sync(SQLModel.metadata.create_all)
    yield async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    await engine.dispose()


@pytest.mark.asyncio
async def test_recent_turns_reads_one_conversation_in_time_order(maker):
    async with maker() as session:
        user = User(email=f"{uuid4().hex[:8]}@x.com", hashed_password="x")
        session.add(user)
        await session.flush()
        assert user.id is not None
        course = Course(user_id=user.id, code="CST235", name="NLP", year=2, sem=2)
        session.add(course)
        await session.flush()
        assert course.id is not None
        mine = Conversation(course_id=course.id)
        other = Conversation(course_id=course.id)
        session.add_all([mine, other])
        await session.flush()
        assert mine.id is not None and other.id is not None

        start = datetime.now(UTC)
        rows = [
            (mine.id, ChatRole.USER, "what is a lexicon", False, 0),
            (other.id, ChatRole.USER, "unrelated question", False, 1),
            (mine.id, ChatRole.ASSISTANT, "A lexicon is a word list [1].", True, 2),
        ]
        for conv, role, text, grounded, seconds in rows:
            session.add(
                Message(
                    conversation_id=conv,
                    scope_course_id=course.id,
                    role=role,
                    content=text,
                    grounded=grounded,
                    created_at=start + timedelta(seconds=seconds),
                )
            )
        await session.commit()
        conversation_id = mine.id

    async with maker() as session:
        turns = await rag_module._recent_turns(session, conversation_id)

    assert turns == [("what is a lexicon", "A lexicon is a word list [1].")]


@pytest.fixture
def follow_up(monkeypatch):
    """/rag/query with retrieval and the model replaced by recorders."""
    seen: dict = {"searches": [], "history": None}
    conversation = Conversation(id=uuid4(), course_id=COURSE_ID, title="t")
    source = _chunk("Lexicon refers to the set of available words in a given context.")

    async def fake_conversation(**_kwargs):
        return conversation

    async def fake_turns(_session, _conversation_id):
        return [("what is a lexicon", "A lexicon is the set of available words [1].")]

    async def fake_retrieve(request, _session, _user_id, query_vector=None):
        seen["searches"].append(request.question)
        return [source]

    async def fake_best_similarity(_request, _query_vector, _session, _user_id):
        return 0.7

    honest = rag_module.generate_answer

    async def recording_generate(**kwargs):
        seen["history"] = kwargs.get("history")
        return await honest(**kwargs)

    monkeypatch.setattr(rag_module, "get_or_create_conversation", fake_conversation)
    monkeypatch.setattr(rag_module, "_recent_turns", fake_turns)
    monkeypatch.setattr(rag_module, "_retrieve", fake_retrieve)
    monkeypatch.setattr(rag_module, "embed_query", lambda _question: [0.0])
    monkeypatch.setattr(rag_module, "_best_similarity", fake_best_similarity)
    monkeypatch.setattr(rag_module, "generate_answer", recording_generate)
    monkeypatch.setattr(settings, "LLM_FAKE_MODE", True)

    session = AsyncMock()
    session.add = Mock()
    test_app = FastAPI()
    test_app.include_router(rag_module.rag_router, prefix="/rag")
    test_app.dependency_overrides[get_session] = lambda: session
    test_app.dependency_overrides[get_current_user] = lambda: {"sub": str(uuid4())}
    return TestClient(test_app), seen, conversation


def test_a_follow_up_searches_with_the_previous_question_and_shows_the_model_the_history(
    follow_up,
):
    client, seen, conversation = follow_up
    body = client.post(
        "/rag/query",
        json={"question": "what are its parts?", "conversation_id": str(conversation.id)},
    ).json()

    assert seen["searches"] == ["what are its parts?", "what is a lexicon what are its parts?"]
    assert "Student: what is a lexicon" in seen["history"]
    # The history changed what was searched and read, not how the answer is checked.
    assert body["grounded"] is True


def test_a_first_question_reads_no_history(follow_up):
    client, seen, _conversation = follow_up
    client.post("/rag/query", json={"question": "what is a lexicon?"})

    assert seen["searches"] == ["what is a lexicon?"]
    assert seen["history"] == ""
