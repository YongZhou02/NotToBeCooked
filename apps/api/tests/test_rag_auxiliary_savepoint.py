"""A database error inside rewrite or decomposition costs that step, not the turn.

Both steps run retrieval queries inside a `try` that catches everything, so that
a failure falls back to the first search. A provider error does. A database
error did not: PostgreSQL aborts the whole transaction on the first failed
statement, the `except` cannot undo that, and the commit at the end of the
route -- which also carries the user turn -- failed. The reader got a 500 and
neither turn was saved.

A mocked session cannot show any of this, because a mock has no transaction to
abort. These run against the test database, with the failure being a real
statement that PostgreSQL rejects.
"""

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlmodel import SQLModel, col, select
from sqlmodel.ext.asyncio.session import AsyncSession

import app.models  # noqa: F401  -- registers every table before create_all
from app.core.config import settings
from app.db.database import get_session, make_engine
from app.dependencies.auth import get_current_user
from app.routers import rag as rag_module
from app.schemas.chat import ChatRole, Message
from app.schemas.user import User
from app.services.llm import REFUSAL, LlmAnswer

COMPLEX_QUESTION = (
    "How does the example progress from source identifiers to a tree with type conversion?"
)
SUB_QUESTIONS = ["How are source identifiers mapped?", "Where is type conversion inserted?"]


async def _invalid_sql(session: AsyncSession) -> None:
    # Through the session's own connection, so it fails inside the request's
    # transaction exactly as a broken retrieval query would.
    connection = await session.connection()
    await connection.execute(text("SELECT no_such_column FROM no_such_table"))


@pytest_asyncio.fixture
async def ctx(test_database_url, monkeypatch):
    """/rag/query on a real session; only the model and the embedder are fakes.

    The user has no files, so every real retrieval returns [] and real
    confidence is 0 -- low enough that the rewrite is attempted.
    """
    engine = make_engine(test_database_url)
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
        await conn.run_sync(SQLModel.metadata.create_all)
    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with maker() as session:
        user = User(email=f"{uuid4().hex[:8]}@x.com", hashed_password="x")
        session.add(user)
        await session.commit()
        user_id = user.id

    async def _session():
        async with maker() as s:
            yield s

    monkeypatch.setattr(settings, "LLM_FAKE_MODE", False)
    monkeypatch.setattr(rag_module, "embed_query", lambda _query: [0.0] * 1024)
    monkeypatch.setattr(
        rag_module,
        "generate_answer",
        AsyncMock(return_value=LlmAnswer(answer=REFUSAL, grounded=False, citations=[])),
    )

    test_app = FastAPI()
    test_app.include_router(rag_module.rag_router, prefix="/rag")
    test_app.dependency_overrides[get_session] = _session
    test_app.dependency_overrides[get_current_user] = lambda: {"sub": str(user_id)}
    # A 500 comes back as a response rather than an exception, so a failure
    # reads as the status code the reader would have seen.
    transport = ASGITransport(app=test_app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, maker
    await engine.dispose()


async def _stored_turns(maker) -> list[Message]:
    async with maker() as session:
        statement = select(Message).order_by(col(Message.created_at))
        return list((await session.exec(statement)).all())


@pytest.mark.asyncio
async def test_a_database_error_in_the_rewrite_keeps_both_turns(ctx, monkeypatch):
    client, maker = ctx
    monkeypatch.setattr(settings, "QUERY_REWRITE_ENABLED", True)
    monkeypatch.setattr(
        rag_module, "rewrite_query", AsyncMock(return_value="partial index WHERE clause")
    )

    async def broken_anchor(_request, session, _user_id):
        await _invalid_sql(session)
        return []

    monkeypatch.setattr(rag_module, "_keyword_anchor_retrieve", broken_anchor)

    response = await client.post("/rag/query", json={"question": "What is a partial index?"})

    assert response.status_code == 200
    assert response.json()["answer"] == REFUSAL
    turns = await _stored_turns(maker)
    assert [turn.role for turn in turns] == [ChatRole.USER, ChatRole.ASSISTANT]
    assert turns[1].scope_snapshot is not None
    trace = turns[1].scope_snapshot["query_rewrite"]
    assert trace["attempted"] is True
    assert trace["error_type"] == "ProgrammingError"
    assert trace["accepted"] is False


@pytest.mark.asyncio
async def test_a_database_error_in_decomposition_keeps_both_turns(ctx, monkeypatch):
    client, maker = ctx
    monkeypatch.setattr(settings, "RETRIEVAL_DECOMPOSITION_ENABLED", True)
    monkeypatch.setattr(rag_module, "decompose_question", AsyncMock(return_value=SUB_QUESTIONS))
    real_retrieve = rag_module._retrieve

    async def retrieve(request, session, user_id, **kwargs):
        # The first search is real; the first sub-question's search breaks.
        if request.question in SUB_QUESTIONS:
            await _invalid_sql(session)
        return await real_retrieve(request, session, user_id, **kwargs)

    monkeypatch.setattr(rag_module, "_retrieve", retrieve)

    response = await client.post("/rag/query", json={"question": COMPLEX_QUESTION})

    assert response.status_code == 200
    turns = await _stored_turns(maker)
    assert [turn.role for turn in turns] == [ChatRole.USER, ChatRole.ASSISTANT]
    assert turns[1].scope_snapshot is not None
    trace = turns[1].scope_snapshot["question_decomposition"]
    assert trace["attempted"] is True
    assert trace["error_type"] == "ProgrammingError"
    assert trace["accepted"] is False
