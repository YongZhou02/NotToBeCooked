import asyncio
from datetime import UTC, datetime
from uuid import UUID

from sqlmodel.ext.asyncio.session import AsyncSession

from app.db.vector_ops import add_chunks
from app.schemas.chunk import Chunk, ChunkCreate
from app.schemas.ingestion_run import IngestionRun, IngestionRunStatus
from app.services.embeddings import embed_text
from app.services.ingestion import count_pages, create_chunk, extract_text, ingest_document


class NoExtractableContentError(Exception):
    """Raised when a document produces no extractable chunks."""


def _parse_and_chunk(file_path: str, file_id: UUID) -> tuple[list[ChunkCreate], int | None]:
    """The synchronous half of ingestion, kept in one function so it costs one hop.

    Docling's parse and the tokenizer behind `create_chunk` are CPU work inside C
    extensions. Called straight from an async function they hold the event loop
    for the whole run, and "the whole run" is not a figure of speech.

    **Measured 10 September 2026**, 60 pages, on this machine (12 cores):

        ingest             395 s  ->  ready, 41 chunks
        GET /health        40 s, 40 s, 40 s   -- three attempts, none answered;
                           40 s was the client's limit, not the server's latency
        GET /health after  0.00 s

    Nothing answered for six and a half minutes. The 1 September note recorded
    this as `TimeoutError 30.07s`, which reads like a slow response and is not --
    30 s was that client's timeout. It is total unavailability for the length of
    the ingest, and `GET /ingestion-runs/{id}` is inside it, so the 202-and-poll
    contract from CR-33 cannot be honoured while the work it describes is running.

    Two hops, not three: parse, extract and chunk run back to back on the same
    document, so splitting them buys nothing and costs two more context switches.
    """
    document = ingest_document(file_path)
    return create_chunk(extract_text(document), file_id), count_pages(document)


async def process_file(
    file_id: UUID,
    course_id: UUID,
    ingestion_run_id: UUID,
    file_path: str,
    session: AsyncSession,
) -> int | None:
    """Returns the page count, which only the parsed document knows."""
    chunk_creates, page_count = await asyncio.to_thread(_parse_and_chunk, file_path, file_id)
    if not chunk_creates:
        raise NoExtractableContentError("No extractable content found")

    content_list = []  # list that save content inside chunk object
    for chunk in chunk_creates:
        content_list.append(chunk.content)

    # Same reason as _parse_and_chunk: SentenceTransformer.encode is a blocking
    # call into torch. It is the larger half of the two -- 239 s of the 395 s
    # above, against 125 s for the parse.
    embeddings = await asyncio.to_thread(embed_text, content_list)

    database_chunks = []
    for chunk_create, embedding in zip(chunk_creates, embeddings, strict=True):
        database_chunk = Chunk(
            file_id=chunk_create.file_id,
            course_id=course_id,
            ingestion_run_id=ingestion_run_id,
            chunk_index=chunk_create.chunk_index,
            page_start=chunk_create.page_start,
            page_end=chunk_create.page_end,
            heading=chunk_create.heading,
            content=chunk_create.content,
            token_count=chunk_create.token_count,
            embedding=embedding,
        )
        database_chunks.append(database_chunk)

    await add_chunks(database_chunks, session)
    return page_count


async def run_ingestion(
    file_id: UUID,
    course_id: UUID,
    ingestion_run_id: UUID,
    file_path: str,
    session: AsyncSession,
) -> int | None:
    """Returns the page count from process_file, for the FILE row."""
    ingestion_run = await session.get(
        IngestionRun, ingestion_run_id
    )  # 去 database 的 IngestionRun 里面，根据 ingestion_run_id 找到那一笔 record/object。

    if ingestion_run is None:
        raise ValueError(f"Ingestion run {ingestion_run_id} not found")

    ingestion_run.status = IngestionRunStatus.PROCESSING
    ingestion_run.started_at = datetime.now(UTC)
    await session.commit()

    try:
        page_count = await process_file(
            file_id=file_id,
            course_id=course_id,
            ingestion_run_id=ingestion_run_id,
            file_path=file_path,
            session=session,
        )
    except NoExtractableContentError:
        await session.rollback()
        ingestion_run.status = IngestionRunStatus.FAILED
        ingestion_run.error_message = "No extractable content found"
        ingestion_run.completed_at = datetime.now(UTC)
        await session.commit()
        raise

    except Exception:
        await session.rollback()
        ingestion_run.status = IngestionRunStatus.FAILED
        ingestion_run.error_message = "File processing failed"
        ingestion_run.completed_at = datetime.now(UTC)
        await session.commit()
        raise

    ingestion_run.status = IngestionRunStatus.READY
    ingestion_run.completed_at = datetime.now(UTC)
    await session.commit()
    return page_count
