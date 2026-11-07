"""Retry failed files touched since a UTC timestamp, one at a time.

Example: uv run python scripts/retry_failed_ingestion.py --since 2026-11-07T00:00:00+00:00
Add --execute to perform the retries. No uploaded files or past runs are deleted.
"""

import argparse
import asyncio
from datetime import datetime

from fastapi import BackgroundTasks
from sqlmodel import col, select

from app.core.logging import configure_logging
from app.db.database import async_session_maker
from app.routers.files import ingest_file
from app.schemas.course import Course
from app.schemas.file import File as FileRow
from app.schemas.file import FileStatus
from app.schemas.ingestion_run import IngestionRun


async def retry(since: datetime, execute: bool) -> None:
    async with async_session_maker() as session:
        rows = (
            await session.exec(
                select(FileRow.id, Course.user_id, FileRow.filename)
                .join(Course, col(Course.id) == col(FileRow.course_id))
                .join(IngestionRun, col(IngestionRun.file_id) == col(FileRow.id))
                .where(
                    col(FileRow.status) == FileStatus.FAILED, col(IngestionRun.started_at) >= since
                )
                .distinct()
            )
        ).all()
    print(f"Found {len(rows)} failed files", flush=True)
    failures = []
    for file_id, user_id, filename in rows:
        if file_id is None:
            continue
        print(f"Retry: {filename} ({file_id})", flush=True)
        if not execute:
            continue
        async with async_session_maker() as session:
            file_row = await session.get(FileRow, file_id)
            if file_row is None or file_row.status != FileStatus.FAILED:
                continue
            tasks = BackgroundTasks()
            await ingest_file(file_id, tasks, session, {"sub": str(user_id)})
        await tasks()
        async with async_session_maker() as session:
            file_row = await session.get(FileRow, file_id)
            print(f"Result: {file_row.status if file_row else 'deleted'}", flush=True)
            if file_row and file_row.status != FileStatus.READY:
                failures.append(str(file_id))
    if failures:
        raise RuntimeError(f"Files still failed: {', '.join(failures)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--since", required=True, type=datetime.fromisoformat)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    if args.since.tzinfo is None:
        parser.error("--since must include a timezone offset")
    configure_logging()
    asyncio.run(retry(args.since, args.execute))
