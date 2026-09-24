"""R35 -- a JSONB column declared `list[UUID]` could not be written at all.

`json.dumps(UUID(...))` raises, and a JSONB column is written by calling
`json.dumps` on the Python value. So `MESSAGE.mentioned_file_ids`, typed
`list[UUID] | None`, committed when it was `None` or `[]` and raised
`StatementError: Object of type UUID is not JSON serializable` the moment it
held one id -- which is every `/rag/query` carrying an @-mention.

Nothing caught it. pyright cannot: `list[UUID]` is what the column claims to
hold. The existing tests cannot: they mock the session, and a mock serialises
nothing.

The fix is `json_serializer` on the engine, so it is tested here at the engine
level rather than through a route -- a route test would pass the day someone
built a second engine without it.
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlmodel import SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession

import app.models  # noqa: F401  -- registers every table before create_all
from app.db.database import make_engine
from app.schemas.chat import ChatRole, Conversation, Message, MessageRead
from app.schemas.course import Course, CourseStatus
from app.schemas.user import User


@pytest_asyncio.fixture
async def ctx(test_database_url):
    engine = make_engine(test_database_url)
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
        await conn.run_sync(SQLModel.metadata.create_all)
    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with maker() as session:
        user = User(email=f"{uuid4().hex[:8]}@x.com", hashed_password="x")
        session.add(user)
        await session.flush()
        assert user.id is not None

        course = Course(
            user_id=user.id,
            code="C",
            name="N",
            year=2026,
            sem=1,
            status=CourseStatus.ACTIVE,
        )
        session.add(course)
        await session.flush()
        assert course.id is not None

        conversation = Conversation(course_id=course.id, title="t")
        session.add(conversation)
        await session.commit()
        assert conversation.id is not None
        ids = (conversation.id, course.id)

    yield maker, ids
    await engine.dispose()


@pytest.mark.asyncio
async def test_a_message_with_mentioned_files_can_be_written_and_read(ctx):
    maker, (conversation_id, course_id) = ctx
    mentioned = [uuid4(), uuid4()]

    async with maker() as session:
        session.add(
            Message(
                id=uuid4(),
                conversation_id=conversation_id,
                scope_course_id=course_id,
                role=ChatRole.USER,
                content="what does @[L1.pdf] say about recursion",
                grounded=False,
                citations=None,
                mentioned_file_ids=mentioned,
                created_at=datetime.now(UTC),
            )
        )
        # Before the fix this raised StatementError here, not at the assert.
        await session.commit()

    async with maker() as session:
        row = (await session.exec(select(Message))).one()
        # The column holds strings -- that is what JSON is.
        assert row.mentioned_file_ids == [str(m) for m in mentioned]
        # And the response model is what turns them back into UUIDs, which is
        # the half that makes the string form invisible outside this layer.
        assert MessageRead.model_validate(row).mentioned_file_ids == mentioned


@pytest.mark.asyncio
async def test_a_value_that_is_not_a_uuid_still_raises(ctx):
    """The serializer handles UUID and nothing else, on purpose.

    `default=str` would have been one character shorter and would silently store
    a stray model instance as "<Course object at 0x7f...>".
    """
    maker, (conversation_id, course_id) = ctx

    async with maker() as session:
        session.add(
            Message(
                id=uuid4(),
                conversation_id=conversation_id,
                scope_course_id=course_id,
                role=ChatRole.USER,
                content="q",
                grounded=False,
                citations=[{"bad": object()}],  # type: ignore[list-item]
                mentioned_file_ids=None,
                created_at=datetime.now(UTC),
            )
        )
        with pytest.raises(Exception) as caught:
            await session.commit()
        assert "not JSON serializable" in str(caught.value)
