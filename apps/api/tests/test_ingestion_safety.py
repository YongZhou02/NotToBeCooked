import asyncio
import contextlib
from datetime import UTC, datetime
from typing import Literal
from unittest.mock import Mock
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlmodel import SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession

import app.models  # noqa: F401  -- registers every table before create_all
from app.db.database import make_engine
from app.routers import files
from app.schemas.course import Course
from app.schemas.file import File as FileRow
from app.schemas.file import FileStatus
from app.schemas.folder import Folder
from app.schemas.ingestion_run import IngestionRun, IngestionRunStatus
from app.schemas.user import User
from app.services import ingestion, processing


def test_windows_parsing_disables_native_compilation(monkeypatch):
    converter = Mock()
    monkeypatch.setattr(ingestion.sys, "platform", "win32")
    monkeypatch.setattr(ingestion, "DocumentConverter", Mock(return_value=converter))
    monkeypatch.setattr(ingestion.docling_settings.inference, "compile_torch_models", True)
    ingestion.ingest_document("example.pdf")
    assert ingestion.docling_settings.inference.compile_torch_models is False
    converter.convert.assert_called_once_with("example.pdf")


@pytest_asyncio.fixture
async def maker(test_database_url):
    engine = make_engine(test_database_url)
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
        await conn.run_sync(SQLModel.metadata.create_all)
    yield async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    await engine.dispose()


async def _seed(session: AsyncSession, count: int) -> tuple[UUID, list[tuple[UUID, UUID]]]:
    """`count` uploaded files, each with the QUEUED run that POST /ingest leaves."""
    user = User(email=f"{uuid4().hex[:8]}@x.com", hashed_password="x")
    session.add(user)
    await session.flush()
    assert user.id is not None
    course = Course(user_id=user.id, code="CST235", name="NLP", year=2, sem=2)
    session.add(course)
    await session.flush()
    assert course.id is not None
    folder = Folder(course_id=course.id, name="root", is_root=True, sort_order=0)
    session.add(folder)
    await session.flush()
    assert folder.id is not None

    seeded = []
    for number in range(count):
        row = FileRow(
            course_id=course.id,
            folder_id=folder.id,
            filename=f"{number}.pdf",
            storage_key=f"k/{uuid4()}",
            mime_type="application/pdf",
            size_bytes=1,
            status=FileStatus.UPLOADED,
            uploaded_at=datetime.now(UTC),
        )
        session.add(row)
        await session.flush()
        assert row.id is not None
        run = IngestionRun(
            file_id=row.id,
            status=IngestionRunStatus.QUEUED,
            chunker_version="v",
            embedding_model="m",
            embedding_dim=1024,
        )
        session.add(run)
        await session.flush()
        assert run.id is not None
        seeded.append((row.id, run.id))
    await session.commit()
    return course.id, seeded


class _ObservedSlot(asyncio.Semaphore):
    """A one-place slot that says when an ingest starts waiting for it."""

    def __init__(self) -> None:
        super().__init__(1)
        self.someone_waiting = asyncio.Event()

    async def acquire(self) -> Literal[True]:
        if self.locked():
            self.someone_waiting.set()
        return await super().acquire()


@pytest.mark.asyncio
async def test_heavy_ingestion_is_serialized_and_slot_recovers_after_failure(maker, monkeypatch):
    active = 0
    peak = 0
    calls = 0

    async def work(file_id, course_id, ingestion_run_id, file_path, session):
        nonlocal active, peak, calls
        active += 1
        calls += 1
        number = calls
        peak = max(peak, active)
        try:
            await asyncio.sleep(0)
            if number == 1:
                raise ValueError("parse failed")
            return 3
        finally:
            active -= 1

    async with maker() as session:
        course_id, seeded = await _seed(session, 3)

    monkeypatch.setattr(files, "async_session_maker", maker)
    monkeypatch.setattr(files, "ingestion_slot", asyncio.Semaphore(1))
    monkeypatch.setattr(processing, "process_file", work)
    await asyncio.gather(
        *(
            files._ingest_in_background(file_id, course_id, run_id, f"k/{file_id}")
            for file_id, run_id in seeded
        )
    )

    async with maker() as session:
        statuses = []
        for file_id, _ in seeded:
            row = await session.get(FileRow, file_id)
            assert row is not None
            statuses.append(row.status)
    assert peak == 1
    assert sorted(statuses) == [FileStatus.FAILED, FileStatus.READY, FileStatus.READY]


@pytest.mark.asyncio
async def test_ingest_waiting_for_the_slot_stays_queued(maker, monkeypatch):
    """Found 24 Nov 2026: the slot was taken inside process_file, after both the
    FILE row and the run had been marked PROCESSING. A file waiting behind
    another read as indexing, its "Replace file…" item was disabled, and the
    run's started_at counted the wait as indexing time."""
    slot = _ObservedSlot()
    first_started = asyncio.Event()
    release_first = asyncio.Event()

    async with maker() as session:
        course_id, [(first_file, first_run), (second_file, second_run)] = await _seed(session, 2)

    async def slow_work(file_id, course_id, ingestion_run_id, file_path, session):
        if file_id == first_file:
            first_started.set()
            await release_first.wait()
        return 3

    monkeypatch.setattr(files, "async_session_maker", maker)
    monkeypatch.setattr(files, "ingestion_slot", slot)
    monkeypatch.setattr(processing, "process_file", slow_work)

    first = asyncio.create_task(
        files._ingest_in_background(first_file, course_id, first_run, "k/first")
    )
    await asyncio.wait_for(first_started.wait(), 5)
    second = asyncio.create_task(
        files._ingest_in_background(second_file, course_id, second_run, "k/second")
    )
    await asyncio.wait_for(slot.someone_waiting.wait(), 5)

    async with maker() as session:
        holder = await session.get(FileRow, first_file)
        waiting_file = await session.get(FileRow, second_file)
        waiting_run = await session.get(IngestionRun, second_run)
        assert holder is not None and waiting_file is not None and waiting_run is not None
        assert holder.status == FileStatus.PROCESSING
        assert waiting_file.status == FileStatus.UPLOADED
        assert waiting_run.status == IngestionRunStatus.QUEUED
        assert waiting_run.started_at is None

    release_first.set()
    await asyncio.wait_for(asyncio.gather(first, second), 5)

    async with maker() as session:
        for file_id, run_id in [(first_file, first_run), (second_file, second_run)]:
            row = await session.get(FileRow, file_id)
            run = await session.get(IngestionRun, run_id)
            assert row is not None and run is not None
            assert (row.status, run.status) == (FileStatus.READY, IngestionRunStatus.READY)


async def _owner(session: AsyncSession, course_id: UUID) -> dict:
    course = await session.get(Course, course_id)
    assert course is not None
    return {"sub": str(course.user_id)}


async def _open_runs(session: AsyncSession, file_id: UUID) -> int:
    runs = (await session.exec(select(IngestionRun).where(IngestionRun.file_id == file_id))).all()
    return sum(r.status in (IngestionRunStatus.QUEUED, IngestionRunStatus.PROCESSING) for r in runs)


@pytest.mark.asyncio
async def test_a_second_ingest_while_one_is_queued_is_refused(maker):
    """Found 24 Nov 2026: a file waiting for the slot still reads `uploaded`, so
    "Start indexing" stays in its menu, and a second click queued a second run
    that parsed the same bytes again after the first one finished."""
    async with maker() as session:
        course_id, [(file_id, earlier_run)] = await _seed(session, 1)
        earlier = await session.get(IngestionRun, earlier_run)
        assert earlier is not None
        earlier.status = IngestionRunStatus.FAILED  # an old attempt; it must not block
        await session.commit()
        user = await _owner(session, course_id)

        accepted = await files.ingest_file(file_id, Mock(), session=session, user=user)
        assert accepted.status == "queued"

        with pytest.raises(HTTPException) as refused:
            await files.ingest_file(file_id, Mock(), session=session, user=user)
        assert refused.value.status_code == 409

        assert await _open_runs(session, file_id) == 1


@pytest.mark.asyncio
async def test_two_ingests_at_once_queue_one_run(maker, monkeypatch):
    """A double click sends both requests before either has committed, so a
    check that only reads the run table lets both through.

    Each request's commit waits up to a second for the other to reach its own
    commit, which pins the bad interleaving: both checks done, neither insert
    visible. With the FILE row locked, the second request is still waiting for
    the lock at that point, so the first one commits alone after the timeout."""
    async with maker() as session:
        course_id, [(file_id, earlier_run)] = await _seed(session, 1)
        earlier = await session.get(IngestionRun, earlier_run)
        assert earlier is not None
        earlier.status = IngestionRunStatus.FAILED
        await session.commit()
        user = await _owner(session, course_id)

    reached_commit = 0
    both_checked = asyncio.Event()

    async def click():
        async with maker() as session:
            commit = session.commit

            async def commit_once_both_have_checked():
                nonlocal reached_commit
                reached_commit += 1
                if reached_commit == 2:
                    both_checked.set()
                with contextlib.suppress(TimeoutError):
                    await asyncio.wait_for(both_checked.wait(), 1)
                await commit()

            monkeypatch.setattr(session, "commit", commit_once_both_have_checked)
            return await files.ingest_file(file_id, Mock(), session=session, user=user)

    results = await asyncio.gather(click(), click(), return_exceptions=True)

    refused = [r for r in results if isinstance(r, HTTPException)]
    assert [r.status_code for r in refused] == [409], results
    async with maker() as session:
        assert await _open_runs(session, file_id) == 1


@pytest.mark.asyncio
async def test_a_run_left_by_a_restart_does_not_block_ingest_for_ever(maker):
    async with maker() as session:
        course_id, [(file_id, _)] = await _seed(session, 1)  # QUEUED, as a crash leaves it
        user = await _owner(session, course_id)

        with pytest.raises(HTTPException):
            await files.ingest_file(file_id, Mock(), session=session, user=user)

        await processing.recover_interrupted_ingestion(session)

        accepted = await files.ingest_file(file_id, Mock(), session=session, user=user)
        assert accepted.status == "queued"
