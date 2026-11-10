from datetime import UTC, datetime
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlmodel import SQLModel, col, select
from sqlmodel.ext.asyncio.session import AsyncSession

import app.models  # noqa: F401 -- register all tables for create_all
from app.db.database import get_session, make_engine
from app.dependencies.auth import get_current_user
from app.main import app
from app.schemas.chat import ChatRole, Conversation, Message
from app.schemas.course import Course, CourseStatus
from app.schemas.feedback import AnswerFeedback, FeedbackRating
from app.schemas.user import User


@pytest_asyncio.fixture
async def feedback_ctx(test_database_url):
    engine = make_engine(test_database_url)
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
        await conn.run_sync(SQLModel.metadata.create_all)
    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with maker() as session:
        owner = User(email=f"{uuid4().hex}@example.com", hashed_password="x")
        stranger = User(email=f"{uuid4().hex}@example.com", hashed_password="x")
        session.add_all([owner, stranger])
        await session.flush()
        assert owner.id is not None and stranger.id is not None

        owner_course = Course(
            user_id=owner.id,
            code="NTBC",
            name="Owner course",
            year=2026,
            sem=1,
            status=CourseStatus.ACTIVE,
        )
        stranger_course = Course(
            user_id=stranger.id,
            code="OTHER",
            name="Stranger course",
            year=2026,
            sem=1,
            status=CourseStatus.ACTIVE,
        )
        session.add_all([owner_course, stranger_course])
        await session.flush()
        assert owner_course.id is not None and stranger_course.id is not None

        owner_conversation = Conversation(course_id=owner_course.id, title="Owner")
        stranger_conversation = Conversation(course_id=stranger_course.id, title="Stranger")
        session.add_all([owner_conversation, stranger_conversation])
        await session.flush()
        assert owner_conversation.id is not None and stranger_conversation.id is not None

        now = datetime.now(UTC)
        owner_question = Message(
            conversation_id=owner_conversation.id,
            scope_course_id=owner_course.id,
            role=ChatRole.USER,
            content="What is RAG?",
            created_at=now,
        )
        owner_answer = Message(
            conversation_id=owner_conversation.id,
            scope_course_id=owner_course.id,
            role=ChatRole.ASSISTANT,
            content="Retrieval-augmented generation.",
            grounded=True,
            citations=[],
            scope_snapshot={"retrieved_chunk_ids": [], "used_chunk_ids": []},
            created_at=now,
        )
        stranger_answer = Message(
            conversation_id=stranger_conversation.id,
            scope_course_id=stranger_course.id,
            role=ChatRole.ASSISTANT,
            content="Private answer",
            created_at=now,
        )
        session.add_all([owner_question, owner_answer, stranger_answer])
        await session.commit()
        assert owner_question.id is not None
        assert owner_answer.id is not None
        assert stranger_answer.id is not None

        ids = {
            "owner": owner.id,
            "question": owner_question.id,
            "answer": owner_answer.id,
            "stranger_answer": stranger_answer.id,
        }

    async def override_session():
        async with maker() as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_current_user] = lambda: {"sub": str(ids["owner"])}
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, maker, ids
    app.dependency_overrides.clear()
    await engine.dispose()


@pytest.mark.asyncio
async def test_feedback_can_be_created_read_and_updated(feedback_ctx):
    client, maker, ids = feedback_ctx

    created = await client.put(
        f"/chat/messages/{ids['answer']}/feedback",
        json={
            "rating": "negative",
            "reason": "answer_incomplete",
            "comment": "  Missing an example.  ",
        },
    )
    assert created.status_code == 200, created.text
    assert created.json()["comment"] == "Missing an example."

    read = await client.get(f"/chat/messages/{ids['answer']}/feedback")
    assert read.status_code == 200
    assert read.json()["reason"] == "answer_incomplete"

    updated = await client.put(
        f"/chat/messages/{ids['answer']}/feedback",
        json={"rating": "positive", "reason": None, "comment": None},
    )
    assert updated.status_code == 200
    assert updated.json()["rating"] == "positive"

    async with maker() as session:
        rows = (
            await session.exec(
                select(AnswerFeedback).where(
                    col(AnswerFeedback.message_id) == ids["answer"]
                )
            )
        ).all()
        assert len(rows) == 1
        assert rows[0].rating == FeedbackRating.POSITIVE


@pytest.mark.asyncio
@pytest.mark.parametrize("target", ["question", "stranger_answer"])
async def test_feedback_rejects_user_messages_and_other_users_messages(feedback_ctx, target):
    client, _maker, ids = feedback_ctx
    response = await client.put(
        f"/chat/messages/{ids[target]}/feedback",
        json={"rating": "negative", "reason": "answer_incorrect"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_positive_feedback_cannot_have_negative_reason(feedback_ctx):
    client, _maker, ids = feedback_ctx
    response = await client.put(
        f"/chat/messages/{ids['answer']}/feedback",
        json={"rating": "positive", "reason": "answer_incorrect"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_missing_feedback_is_404(feedback_ctx):
    client, _maker, ids = feedback_ctx
    response = await client.get(f"/chat/messages/{ids['answer']}/feedback")
    assert response.status_code == 404
