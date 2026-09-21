"""app/db/vector_ops.py against a real database -- Gantt r28 (b).

Each test seeds rows inside one transaction that is rolled back afterwards
(finding R33). A mocked session returns whatever it is told to, so it would agree
with a query that ignored `is_active` or dropped the scope filter. Only Postgres
can disagree.
"""

import math
from collections.abc import AsyncGenerator, Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

import app.models  # noqa: F401  -- registers every table before create_all
from app.core.config import settings
from app.db.database import make_engine
from app.db.vector_ops import (
    SearchConfig,
    _full_text_search,
    _vector_similarity_search,
    hybrid_search,
)
from app.schemas.chunk import Chunk
from app.schemas.course import Course, CourseStatus
from app.schemas.file import File as FileRow
from app.schemas.file import FileStatus
from app.schemas.folder import Folder
from app.schemas.ingestion_run import IngestionRun, IngestionRunStatus
from app.schemas.user import User

QUERY_TEXT = "backpropagation"


def direction(*axes: int) -> list[float]:
    """A length-1 vector spread evenly over `axes`, so similarities are easy to predict."""
    vector = [0.0] * settings.EMBEDDINGS_DIM
    for axis in axes:
        vector[axis] = 1.0 / math.sqrt(len(axes))
    return vector


QUERY_VECTOR = direction(0)


@pytest_asyncio.fixture
async def session(test_database_url) -> AsyncGenerator[AsyncSession, None]:
    engine = make_engine(test_database_url)
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
        await conn.run_sync(SQLModel.metadata.create_all)

    async with engine.connect() as conn:
        transaction = await conn.begin()
        session = AsyncSession(bind=conn, expire_on_commit=False)
        try:
            yield session
        finally:
            await session.close()
            await transaction.rollback()
    await engine.dispose()


async def add_course(session: AsyncSession, code: str) -> tuple[UUID, UUID]:
    """A user, their course, and the course's root folder. Returns (course_id, folder_id)."""
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
    return course_id, folder_id


async def add_file(session: AsyncSession, course_id: UUID, folder_id: UUID) -> UUID:
    name = f"{uuid4()}.pdf"
    file_row = FileRow(
        folder_id=folder_id,
        course_id=course_id,
        filename=name,
        storage_key=name,
        mime_type="application/pdf",
        size_bytes=1,
        status=FileStatus.READY,
        uploaded_at=datetime.now(UTC),
    )
    session.add(file_row)
    await session.flush()
    file_id = file_row.id
    assert file_id is not None
    return file_id


async def add_run(session: AsyncSession, file_id: UUID, *, active: bool) -> UUID:
    run = IngestionRun(
        file_id=file_id,
        status=IngestionRunStatus.READY,
        is_active=active,
        chunker_version="test",
        embedding_model="test",
        embedding_dim=settings.EMBEDDINGS_DIM,
    )
    session.add(run)
    await session.flush()
    run_id = run.id
    assert run_id is not None
    return run_id


async def add_chunk(
    session: AsyncSession,
    *,
    run_id: UUID,
    file_id: UUID,
    course_id: UUID,
    content: str,
    embedding: list[float],
) -> UUID:
    chunk = Chunk(
        ingestion_run_id=run_id,
        file_id=file_id,
        course_id=course_id,
        chunk_index=0,
        page_start=1,
        content=content,
        token_count=len(content.split()),
        embedding=embedding,
    )
    session.add(chunk)
    await session.flush()
    return chunk.id


async def add_indexed_file(
    session: AsyncSession,
    course_id: UUID,
    folder_id: UUID,
    *,
    content: str,
    embedding: list[float],
) -> tuple[UUID, UUID]:
    """A file with one active run holding one chunk. Returns (file_id, chunk_id)."""
    file_id = await add_file(session, course_id, folder_id)
    run_id = await add_run(session, file_id, active=True)
    chunk_id = await add_chunk(
        session,
        run_id=run_id,
        file_id=file_id,
        course_id=course_id,
        content=content,
        embedding=embedding,
    )
    return file_id, chunk_id


Search = Callable[[AsyncSession, UUID | None, list[UUID]], Awaitable[set[UUID]]]


async def vector_path(session: AsyncSession, course_id: UUID | None, file_ids: list[UUID]):
    rows = await _vector_similarity_search(QUERY_VECTOR, session, course_id, file_ids, top_k=50)
    return {chunk.id for chunk, _, _ in rows}


async def keyword_path(session: AsyncSession, course_id: UUID | None, file_ids: list[UUID]):
    rows = await _full_text_search(QUERY_TEXT, session, course_id, file_ids, top_k=50)
    return {chunk.id for chunk, _, _ in rows}


async def hybrid_path(session: AsyncSession, course_id: UUID | None, file_ids: list[UUID]):
    results = await hybrid_search(
        query_text=QUERY_TEXT,
        query_vector=QUERY_VECTOR,
        course_id=course_id,
        session=session,
        file_ids=file_ids,
        config=None,
    )
    return {result.chunk_id for result in results}


EVERY_PATH = pytest.mark.parametrize(
    "search",
    [vector_path, keyword_path, hybrid_path],
    ids=["vector", "keyword", "hybrid"],
)


@EVERY_PATH
@pytest.mark.asyncio
async def test_chunks_from_an_inactive_run_are_never_returned(session, search: Search):
    course_id, folder_id = await add_course(session, "CSC3105")
    file_id = await add_file(session, course_id, folder_id)

    # The stale chunk is the better match on both paths, so the only thing that
    # can keep it out of the results is the is_active join.
    old_run = await add_run(session, file_id, active=False)
    stale = await add_chunk(
        session,
        run_id=old_run,
        file_id=file_id,
        course_id=course_id,
        content="backpropagation backpropagation, from the old run",
        embedding=QUERY_VECTOR,
    )
    new_run = await add_run(session, file_id, active=True)
    current = await add_chunk(
        session,
        run_id=new_run,
        file_id=file_id,
        course_id=course_id,
        content="backpropagation, from the current run",
        embedding=direction(0, 1),
    )

    found = await search(session, None, [file_id])

    assert current in found
    assert stale not in found


@dataclass
class TwoCourses:
    course_a: UUID
    file_a: UUID
    chunk_a: UUID
    course_b: UUID
    file_b: UUID
    chunk_b: UUID


@pytest_asyncio.fixture
async def two_courses(session) -> TwoCourses:
    course_a, folder_a = await add_course(session, "CPC251")
    file_a, chunk_a = await add_indexed_file(
        session, course_a, folder_a, content="backpropagation in CPC251", embedding=QUERY_VECTOR
    )
    course_b, folder_b = await add_course(session, "CSC3105")
    file_b, chunk_b = await add_indexed_file(
        session, course_b, folder_b, content="backpropagation in CSC3105", embedding=QUERY_VECTOR
    )
    return TwoCourses(course_a, file_a, chunk_a, course_b, file_b, chunk_b)


SCOPES = pytest.mark.parametrize(
    ("scope", "expected"),
    [
        pytest.param(
            lambda w: (w.course_a, [w.file_b]),
            lambda w: {w.chunk_b},
            id="file_ids_win_over_course_id",
        ),
        pytest.param(
            lambda w: (None, [w.file_a, w.file_b]),
            lambda w: {w.chunk_a, w.chunk_b},
            id="file_ids_may_cross_courses",
        ),
        pytest.param(
            lambda w: (w.course_a, []),
            lambda w: {w.chunk_a},
            id="empty_file_ids_fall_through_to_course_id",
        ),
        pytest.param(
            lambda w: (None, []),
            lambda w: {w.chunk_a, w.chunk_b},
            id="empty_file_ids_and_no_course_search_every_chunk",
        ),
    ],
)


@EVERY_PATH
@SCOPES
@pytest.mark.asyncio
async def test_scope_precedence(session, two_courses, search: Search, scope, expected):
    """`if file_ids:` then `elif course_id`, where `[]` reads as no file filter.

    The last case is pinned deliberately: an empty scope with no course returns
    every chunk in the table. `_retrieve` returns early rather than make that call,
    and this test is what fails if the function's own behaviour ever changes.
    """
    course_id, file_ids = scope(two_courses)

    found = await search(session, course_id, file_ids)

    assert found == expected(two_courses)


@pytest.mark.asyncio
async def test_a_chunk_found_by_both_searches_outranks_one_found_by_either(session):
    course_id, folder_id = await add_course(session, "CSC3105")
    file_both, both = await add_indexed_file(
        session,
        course_id,
        folder_id,
        content="backpropagation updates each weight",
        embedding=direction(0, 1),
    )
    file_vector, vector_only = await add_indexed_file(
        session,
        course_id,
        folder_id,
        content="gradient descent in general",
        embedding=QUERY_VECTOR,
    )
    file_keyword, keyword_only = await add_indexed_file(
        session,
        course_id,
        folder_id,
        content="backpropagation backpropagation backpropagation",
        embedding=direction(2),
    )

    # Two results per path: vector returns vector_only then both; keyword returns
    # keyword_only and both. So `both` is the only chunk that scores twice.
    results = await hybrid_search(
        query_text=QUERY_TEXT,
        query_vector=QUERY_VECTOR,
        course_id=None,
        session=session,
        file_ids=[file_both, file_vector, file_keyword],
        config=SearchConfig(vector_limit=2, keyword_limit=2),
    )
    scores = {result.chunk_id: result.score for result in results}

    assert set(scores) == {both, vector_only, keyword_only}
    assert results[0].chunk_id == both
    assert scores[both] > scores[vector_only]
    assert scores[both] > scores[keyword_only]
