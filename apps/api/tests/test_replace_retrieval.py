"""Replacing a file's bytes takes its old chunks out of retrieval -- Gantt r82.

R34's fix (PUT /files/{id}/content deactivates the active INGESTION_RUN) was
closed on a reading of the code. Its own tests in test_file_routing.py check that
the UPDATE was composed; they cannot see what search then returns, because the
session there is a mock. This test asks the question the finding was about,
against a real database: after the PUT, does hybrid_search still hand back a
passage from the old bytes?

The chunk is seeded rather than produced by a real ingest. Parsing and embedding
are not what is under test, and running them would cost minutes and the local
model; what matters is the state ingestion leaves behind -- one READY, active
run holding one chunk.

Delete the `update(IngestionRun)` statement in replace_file and this test fails.
"""

from uuid import UUID

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import settings
from app.db.vector_ops import hybrid_search
from app.schemas.chunk import Chunk
from app.schemas.ingestion_run import IngestionRun, IngestionRunStatus

# The ctx fixture (real database, temp storage dir, one signed-in user) is the one
# POST /files is tested with; reusing it keeps one definition of "a real request".
from tests.test_upload import PDF, ctx  # noqa: F401

QUERY_TEXT = "backpropagation"


def unit_vector() -> list[float]:
    vector = [0.0] * settings.EMBEDDINGS_DIM
    vector[0] = 1.0
    return vector


async def search(session: AsyncSession, course_id: UUID) -> set[UUID]:
    results = await hybrid_search(
        query_text=QUERY_TEXT,
        query_vector=unit_vector(),
        course_id=course_id,
        session=session,
        file_ids=[],
        config=None,
    )
    return {result.chunk_id for result in results}


@pytest.mark.asyncio
async def test_replaced_file_old_chunk_is_not_retrieved(ctx):  # noqa: F811
    client, maker, (_user_id, course_id, folder_id) = ctx

    r = await client.post(
        "/files",
        data={"folder_id": str(folder_id)},
        files={"upload": ("L1.pdf", PDF, "application/pdf")},
    )
    assert r.status_code == 201, r.text
    file_id = UUID(r.json()["id"])

    # What a finished ingest leaves behind: one READY, active run with one chunk.
    async with maker() as session:
        run = IngestionRun(
            file_id=file_id,
            status=IngestionRunStatus.READY,
            is_active=True,
            chunker_version="test",
            embedding_model="test",
            embedding_dim=settings.EMBEDDINGS_DIM,
        )
        session.add(run)
        await session.flush()
        assert run.id is not None
        chunk = Chunk(
            ingestion_run_id=run.id,
            file_id=file_id,
            course_id=course_id,
            chunk_index=0,
            page_start=1,
            content="Backpropagation sends the error gradient backwards.",
            token_count=6,
            embedding=unit_vector(),
        )
        session.add(chunk)
        await session.commit()
        old_chunk_id = chunk.id

    # Before the replacement the chunk is found -- otherwise the assertion at the
    # end would pass for the wrong reason.
    async with maker() as session:
        assert old_chunk_id in await search(session, course_id)

    r = await client.put(
        f"/files/{file_id}/content",
        files={"upload": ("L1.pdf", PDF + b"new lecture\n", "application/pdf")},
    )
    assert r.status_code == 200, r.text

    async with maker() as session:
        assert old_chunk_id not in await search(session, course_id)
        # Kept, not deleted: the history stays, it just stops being searched.
        assert await session.get(Chunk, old_chunk_id) is not None
