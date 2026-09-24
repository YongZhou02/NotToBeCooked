from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

import pytest

from app.schemas.chunk import ChunkCreate
from app.schemas.ingestion_run import IngestionRun, IngestionRunStatus
from app.services.ingestion import extract_text
from app.services.processing import NoExtractableContentError, process_file, run_ingestion


def test_extract_text_keeps_text_without_page_provenance():
    document = SimpleNamespace(
        texts=[
            SimpleNamespace(
                label=SimpleNamespace(value="text"),
                text="Text extracted from a DOCX paragraph.",
                prov=[],
            )
        ]
    )

    assert extract_text(document) == [
        {
            "heading": None,
            "page_start": 1,
            "page_end": 1,
            "content": "Text extracted from a DOCX paragraph.",
        }
    ]


def test_extract_text_keeps_body_text_and_list_items_only():
    document = SimpleNamespace(
        texts=[
            SimpleNamespace(
                label=SimpleNamespace(value="section_header"),
                content_layer=SimpleNamespace(value="body"),
                text="Conflict",
                prov=[SimpleNamespace(page_no=3)],
            ),
            SimpleNamespace(
                label=SimpleNamespace(value="text"),
                content_layer=SimpleNamespace(value="body"),
                text="Conflict is a perception.",
                prov=[SimpleNamespace(page_no=3)],
            ),
            SimpleNamespace(
                label=SimpleNamespace(value="list_item"),
                content_layer=SimpleNamespace(value="body"),
                text="Interaction is required for conflict.",
                prov=[SimpleNamespace(page_no=4)],
            ),
            SimpleNamespace(
                label=SimpleNamespace(value="text"),
                content_layer=SimpleNamespace(value="furniture"),
                text="SCHOOL OF COMPUTER SCIENCES",
                prov=[SimpleNamespace(page_no=4)],
            ),
            SimpleNamespace(
                label=SimpleNamespace(value="page_footer"),
                content_layer=SimpleNamespace(value="body"),
                text="Page 4",
                prov=[SimpleNamespace(page_no=4)],
            ),
        ]
    )

    assert extract_text(document) == [
        {
            "heading": "Conflict",
            "page_start": 3,
            "page_end": 3,
            "content": "Conflict is a perception.",
        },
        {
            "heading": "Conflict",
            "page_start": 4,
            "page_end": 4,
            "content": "Interaction is required for conflict.",
        },
    ]


def make_chunk_create(file_id: UUID) -> ChunkCreate:

    test = ChunkCreate(
        file_id=file_id,
        chunk_index=0,
        page_start=1,
        page_end=1,
        heading="testing heading, bao sheng",
        content="testing content, bao sheng",
        token_count=45,
    )
    return test


# global variable
test_file_id = uuid4()
test_chunk_create = make_chunk_create(test_file_id)

fake_embedding = [0.0] * 1024


@pytest.mark.asyncio
async def test_process_file_creates_and_save_chunks():

    with patch(
        "app.services.processing.ingest_document",
        return_value="fake_document",
    ) as mock_ingest:
        with patch(
            "app.services.processing.extract_text",
            return_value="fake_extract_text",
        ) as mock_extract:
            with patch(
                "app.services.processing.create_chunk",
                return_value=[test_chunk_create],
            ) as mock_create:
                with patch(
                    "app.services.processing.embed_text",
                    return_value=[fake_embedding],
                ) as mock_embed:
                    with patch(
                        "app.services.processing.add_chunks",
                        new_callable=AsyncMock,
                    ) as mock_add:
                        course_id = uuid4()
                        ingestion_run_id = uuid4()
                        fake_session = AsyncMock()

                        await process_file(
                            file_id=test_file_id,
                            course_id=course_id,
                            ingestion_run_id=ingestion_run_id,
                            file_path="abc.pdf",
                            session=fake_session,
                        )

                        assert mock_ingest.call_count == 1
                        assert mock_extract.call_count == 1
                        assert mock_create.call_count == 1
                        assert mock_embed.call_count == 1
                        assert mock_add.await_count == 1
                        mock_add.assert_awaited_once()  # 我要求 mock_add 必须刚好被 await 一次

                        assert mock_add.await_args is not None
                        database_chunks, received_session = mock_add.await_args.args

                        database_chunk = database_chunks[0]
                        assert database_chunk.file_id == test_file_id
                        assert database_chunk.course_id == course_id
                        assert database_chunk.ingestion_run_id == ingestion_run_id
                        assert database_chunk.content == test_chunk_create.content
                        assert database_chunk.embedding == fake_embedding
                        assert len(database_chunk.embedding) == 1024
                        assert received_session is fake_session

                        mock_ingest.assert_called_once_with("abc.pdf")
                        mock_extract.assert_called_once_with("fake_document")
                        mock_create.assert_called_once_with("fake_extract_text", test_file_id)
                        mock_embed.assert_called_once_with([test_chunk_create.content])
                        mock_add.assert_awaited_once_with(database_chunks, fake_session)


@pytest.mark.asyncio
async def test_process_file_raises_when_embedding_count_does_not_match_chunks():
    second_chunk = ChunkCreate(
        file_id=test_file_id,
        chunk_index=2,
        page_start=2,
        page_end=2,
        heading="testing heading 2",
        content="testing content 2",
        token_count=30,
    )

    course_id = uuid4()
    ingestion_run_id = uuid4()
    fake_session = AsyncMock()

    with (
        patch(
            "app.services.processing.ingest_document",
            return_value="fake_document",
        ),
        patch(
            "app.services.processing.extract_text",
            return_value="fake_extract_text",
        ),
        patch(
            "app.services.processing.create_chunk",
            return_value=[test_chunk_create, second_chunk],
        ),
        patch(
            "app.services.processing.embed_text",
            return_value=[fake_embedding],
        ) as mock_embed,
        patch(
            "app.services.processing.add_chunks",
            new_callable=AsyncMock,
        ) as mock_add,
    ):
        with pytest.raises(ValueError):
            await process_file(
                file_id=test_file_id,
                course_id=course_id,
                ingestion_run_id=ingestion_run_id,
                file_path="abc.pdf",
                session=fake_session,
            )

    mock_embed.assert_called_once_with(
        [
            test_chunk_create.content,
            second_chunk.content,
        ]
    )

    mock_add.assert_not_awaited()


# assert= this condition must be true
@pytest.mark.asyncio
async def test_process_file_raises_when_document_has_no_extractable_content():
    course_id = uuid4()
    ingestion_run_id = uuid4()
    fake_session = AsyncMock()
    with (
        patch(
            "app.services.processing.ingest_document",
            return_value="fake_document",
        ),
        patch(
            "app.services.processing.extract_text",
            return_value=[],
        ),
        patch(
            "app.services.processing.create_chunk",
            return_value=[],
        ),
        patch(
            "app.services.processing.embed_text",
        ) as mock_embed,
        patch(
            "app.services.processing.add_chunks",
            new_callable=AsyncMock,
        ) as mock_add,
    ):
        with pytest.raises(NoExtractableContentError):
            await process_file(
                file_id=test_file_id,
                course_id=course_id,
                ingestion_run_id=ingestion_run_id,
                file_path="blank.pdf",
                session=fake_session,
            )

    mock_embed.assert_not_called()
    mock_add.assert_not_awaited()


@pytest.mark.asyncio
async def test_run_ingestion_marks_run_ready_after_success():
    ingestion_run_id = uuid4()
    course_id = uuid4()  # not understadn why need course_id

    ingestion_run = IngestionRun(
        id=ingestion_run_id,
        file_id=test_file_id,
        chunker_version="test-chunker",
        embedding_model="test_model",
        embedding_dim=1024,
    )

    fake_session = AsyncMock()
    fake_session.get.return_value = ingestion_run

    with patch(
        "app.services.processing.process_file",
        new_callable=AsyncMock,
    ) as mock_process_file:
        await run_ingestion(
            file_id=test_file_id,
            course_id=course_id,
            ingestion_run_id=ingestion_run_id,
            file_path="abc.pdf",
            session=fake_session,
        )

    fake_session.get.assert_awaited_once_with(IngestionRun, ingestion_run_id)

    mock_process_file.assert_awaited_once_with(
        file_id=test_file_id,
        course_id=course_id,
        ingestion_run_id=ingestion_run_id,
        file_path="abc.pdf",
        session=fake_session,
    )

    assert ingestion_run.status == IngestionRunStatus.READY
    assert ingestion_run.started_at is not None
    assert ingestion_run.completed_at is not None
    assert fake_session.commit.await_count == 2


@pytest.mark.asyncio
async def test_run_ingestion_marks_run_failed_when_processing_fails():
    ingestion_run_id = uuid4()
    course_id = uuid4()

    ingestion_run = IngestionRun(
        id=ingestion_run_id,
        file_id=test_file_id,
        chunker_version="test-chunker",
        embedding_model="test-model",
        embedding_dim=1024,
    )

    fake_session = AsyncMock()
    fake_session.get.return_value = ingestion_run

    with patch(
        "app.services.processing.process_file",
        new_callable=AsyncMock,
        side_effect=RuntimeError("internal technical error"),
    ) as mock_process_file:
        with pytest.raises(RuntimeError, match="internal technical error"):
            await run_ingestion(
                file_id=test_file_id,
                course_id=course_id,
                ingestion_run_id=ingestion_run_id,
                file_path="abc.pdf",
                session=fake_session,
            )

    fake_session.rollback.assert_awaited_once()
    mock_process_file.assert_awaited_once_with(
        file_id=test_file_id,
        course_id=course_id,
        ingestion_run_id=ingestion_run_id,
        file_path="abc.pdf",
        session=fake_session,
    )
    assert ingestion_run.status == IngestionRunStatus.FAILED
    assert fake_session.commit.await_count == 2
    assert ingestion_run.error_message != "internal technical error"
    assert ingestion_run.error_message == "File processing failed"
    assert ingestion_run.completed_at is not None


@pytest.mark.asyncio
async def test_run_ingestion_marks_run_failed_when_no_extractable_text():
    ingestion_run_id = uuid4()
    course_id = uuid4()

    ingestion_run = IngestionRun(
        id=ingestion_run_id,
        file_id=test_file_id,
        chunker_version="test_chunker_version",
        embedding_model="test_embedding_model",
        embedding_dim=1024,
    )
    fake_session = AsyncMock()
    fake_session.get.return_value = ingestion_run

    with patch(
        "app.services.processing.process_file",
        new_callable=AsyncMock,
        side_effect=NoExtractableContentError("No extractable content found"),
    ) as mock_file_processing:
        with pytest.raises(NoExtractableContentError, match="No extractable content found"):
            await run_ingestion(
                file_id=test_file_id,
                course_id=course_id,
                ingestion_run_id=ingestion_run_id,
                file_path="blank.pdf",
                session=fake_session,
            )

    mock_file_processing.assert_awaited_once_with(
        file_id=test_file_id,
        course_id=course_id,
        ingestion_run_id=ingestion_run_id,
        file_path="blank.pdf",
        session=fake_session,
    )
    fake_session.rollback.assert_awaited_once()
    assert fake_session.commit.await_count == 2
    assert ingestion_run.status == IngestionRunStatus.FAILED
    assert ingestion_run.error_message == "No extractable content found"
    assert ingestion_run.completed_at is not None
