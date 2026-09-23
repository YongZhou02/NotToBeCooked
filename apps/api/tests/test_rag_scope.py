"""What retrieval is allowed to read -- Gantt r48.

Against a real database, because the thing being tested is a join across
FILE -> FOLDER -> COURSE and the ownership predicate on the end of it. A mocked
session returns whatever it was told to return and would agree with a query
that selected every file in the table, which is the failure this file exists to
catch (finding R33).

The sharp one is `test_an_empty_scope_never_reaches_hybrid_search`. Inside
`hybrid_search`, `if file_ids:` means an empty list applies no filter at all --
so the difference between "this user can see nothing here" and "search
everything anyone has ever uploaded" is one early return.
"""

from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

import app.models  # noqa: F401  -- registers every table before create_all
from app.core.config import settings
from app.routers import rag as rag_module
from app.routers.rag import (
    _retrieve,
    _retrieve_document_chunks,
    _scope_file_ids,
)
from app.schemas.chunk import Chunk
from app.schemas.course import Course, CourseStatus
from app.schemas.file import File as FileRow
from app.schemas.file import FileStatus
from app.schemas.folder import Folder
from app.schemas.ingestion_run import (
    IngestionRun,
    IngestionRunStatus,
)
from app.schemas.rag import RagIntent, RagQueryRequest
from app.schemas.user import User


async def _make_owner(session, code: str):
    """One user, one course, one folder, one file. Returns the ids."""
    user = User(email=f"{uuid4().hex[:8]}@x.com", hashed_password="x")
    session.add(user)
    await session.flush()
    user_id = user.id
    assert user_id is not None

    course = Course(
        user_id=user_id, code=code, name=code, year=2026, sem=1, status=CourseStatus.ACTIVE
    )
    session.add(course)
    await session.flush()
    course_id = course.id
    assert course_id is not None

    folder = Folder(course_id=course_id, name="root", is_root=True, sort_order=0)
    session.add(folder)
    await session.flush()
    folder_id = folder.id
    assert folder_id is not None

    from datetime import UTC, datetime

    file_row = FileRow(
        folder_id=folder_id,
        course_id=course_id,
        filename=f"{code}.pdf",
        storage_key=f"{user_id}/{uuid4()}.pdf",
        mime_type="application/pdf",
        size_bytes=1,
        status=FileStatus.READY,
        uploaded_at=datetime.now(UTC),
    )
    session.add(file_row)
    await session.commit()
    file_id = file_row.id
    assert file_id is not None
    return user_id, course_id, file_id


async def _make_run(
    session: AsyncSession,
    file_id: UUID,
    *,
    active: bool,
) -> UUID:
    run = IngestionRun(
        file_id=file_id,
        status=IngestionRunStatus.READY,
        chunker_version="test",
        embedding_model="test",
        embedding_dim=settings.EMBEDDINGS_DIM,
        is_active=active,
    )

    session.add(run)
    await session.flush()

    assert run.id is not None
    return run.id


async def _make_chunk(
    session: AsyncSession,
    *,
    run_id: UUID,
    file_id: UUID,
    course_id: UUID,
    chunk_index: int,
    content: str,
) -> None:
    session.add(
        Chunk(
            ingestion_run_id=run_id,
            file_id=file_id,
            course_id=course_id,
            chunk_index=chunk_index,
            page_start=chunk_index + 1,
            page_end=chunk_index + 1,
            heading=None,
            content=content,
            token_count=len(content.split()),
            embedding=[0.0] * settings.EMBEDDINGS_DIM,
        )
    )


@pytest_asyncio.fixture
async def two_owners(test_database_url):
    """Two users who have never heard of each other, each with one file."""
    engine = create_async_engine(test_database_url)
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
        await conn.run_sync(SQLModel.metadata.create_all)
    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with maker() as session:
        mine = await _make_owner(session, "CPC251")
        theirs = await _make_owner(session, "CSC3105")

    async with maker() as session:
        yield session, mine, theirs

    await engine.dispose()


@pytest.mark.asyncio
async def test_no_scope_means_my_corpus_not_the_table(two_owners):
    session, (user_id, _, file_id), (_, _, their_file) = two_owners
    scope = await _scope_file_ids(RagQueryRequest(question="q"), session, user_id)
    assert scope == [file_id]
    assert their_file not in scope


@pytest.mark.asyncio
async def test_a_course_i_do_not_own_resolves_to_nothing(two_owners):
    session, (user_id, _, _), (_, their_course, _) = two_owners
    scope = await _scope_file_ids(
        RagQueryRequest(question="q", course_id=their_course), session, user_id
    )
    assert scope == []


@pytest.mark.asyncio
async def test_mentioning_someone_elses_file_drops_it_silently(two_owners):
    """404 would answer "is this a real file id". Dropping answers nothing."""
    session, (user_id, _, file_id), (_, _, their_file) = two_owners
    scope = await _scope_file_ids(
        RagQueryRequest(question="q", file_ids=[file_id, their_file]), session, user_id
    )
    assert scope == [file_id]


@pytest.mark.asyncio
async def test_an_empty_scope_never_reaches_hybrid_search(two_owners, monkeypatch):
    """The early return is the access control, not an optimisation."""
    session, (user_id, _, _), (_, their_course, _) = two_owners

    calls: list[object] = []

    async def spy(**kwargs):
        calls.append(kwargs)
        return []

    monkeypatch.setattr(rag_module, "hybrid_search", spy)

    chunks = await _retrieve(
        RagQueryRequest(question="q", course_id=their_course), session, user_id
    )
    assert chunks == []
    assert calls == [], "hybrid_search was called with a scope the caller cannot see"


@pytest.mark.asyncio
async def test_document_summary_uses_active_run_in_chunk_order(two_owners):
    session, (user_id, course_id, file_id), _ = two_owners

    inactive_run_id = await _make_run(
        session,
        file_id,
        active=False,
    )
    active_run_id = await _make_run(
        session,
        file_id,
        active=True,
    )

    await _make_chunk(
        session,
        run_id=inactive_run_id,
        file_id=file_id,
        course_id=course_id,
        chunk_index=0,
        content="obsolete content",
    )
    await _make_chunk(
        session,
        run_id=active_run_id,
        file_id=file_id,
        course_id=course_id,
        chunk_index=1,
        content="second active chunk",
    )

    await _make_chunk(
        session,
        run_id=active_run_id,
        file_id=file_id,
        course_id=course_id,
        chunk_index=0,
        content="first active chunk",
    )

    await session.commit()
    request = RagQueryRequest(
        question="Condense",
        file_ids=[file_id],
        intent=RagIntent.DOCUMENT_SUMMARY,
    )
    chunks = await _retrieve_document_chunks(
        request,
        session,
        user_id,
    )
    assert [chunk.content for chunk in chunks] == [
        "first active chunk",
        "second active chunk",
    ]

    assert all(chunk.file_id == file_id for chunk in chunks)

    assert "obsolete content" not in [chunk.content for chunk in chunks]
