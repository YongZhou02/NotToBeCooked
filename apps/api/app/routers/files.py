import logging
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse
from sqlalchemy import func, update
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import settings
from app.db.database import async_session_maker, get_session
from app.dependencies.auth import get_current_user
from app.schemas.chunk import Chunk
from app.schemas.course import Course
from app.schemas.file import File as FileRow
from app.schemas.file import FileRead, FileStatus, FileUpdate, IngestionResponse
from app.schemas.folder import Folder
from app.schemas.ingestion_run import IngestionRun, IngestionRunStatus
from app.services.processing import NoExtractableContentError, run_ingestion
from app.services.storage import (
    UploadTooLargeError,
    build_storage_key,
    replace_upload,
    resolve,
    write_upload,
)
from app.services.storage import delete as delete_stored_file

# The only logger in app/ so far. It exists because of _ingest_in_background: a
# background task has no caller to raise to, so without this an exception leaves
# no trace anywhere except a generic string on the INGESTION_RUN row.
logger = logging.getLogger(__name__)

files_router = APIRouter(dependencies=[Depends(get_current_user)])
course_files_router = APIRouter(dependencies=[Depends(get_current_user)])


@files_router.post(
    "",
    response_model=FileRead,
    status_code=status.HTTP_201_CREATED,
)
async def upload_file(
    folder_id: UUID = Form(...),
    upload: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
    user: dict = Depends(get_current_user),
) -> FileRow:
    """Store an uploaded file and record it. Does not index it.

    Upload and ingestion are two endpoints on purpose, which is why `uploaded`
    exists as a FileStatus value (restored 18 Aug). This one returns as soon as
    the bytes are safe; `POST /files/{file_id}/ingest` is what turns them into
    chunks.

    `course_id` is read from the folder, never from the request. The client
    could send one, and a client that sends the wrong one would be writing a row
    that r42's composite foreign key rejects -- so the correct value is already
    known server-side, and asking for it only creates a way to be wrong.
    """
    user_id = UUID(user["sub"])

    # One query answers both "does this folder exist" and "does this caller own
    # it". Splitting them would mean a 404 and a 403 that together tell a
    # stranger which folder ids are real.
    statement = (
        select(Folder)
        .join(Course, col(Course.id) == col(Folder.course_id))  # pyright: ignore[reportArgumentType]
        .where(Folder.id == folder_id, Course.user_id == user_id)
    )
    folder = (await session.exec(statement)).first()
    if folder is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Folder not found")

    filename = upload.filename or "untitled"
    file_id = uuid4()
    storage_key = build_storage_key(user_id, file_id, filename)

    try:
        size_bytes, sha256 = await write_upload(upload, storage_key)
    except UploadTooLargeError as exc:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, str(exc)) from exc

    row = FileRow(
        id=file_id,
        # folder_id rather than folder.id: same value, but the column is declared
        # `UUID | None` on the model, and the form field is not.
        folder_id=folder_id,
        course_id=folder.course_id,
        filename=filename,
        storage_key=storage_key,
        sha256=sha256,
        mime_type=upload.content_type or "application/octet-stream",
        size_bytes=size_bytes,
        status=FileStatus.UPLOADED,
        uploaded_at=datetime.now(UTC),
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row


@files_router.post(
    "/{file_id}/ingest",
    response_model=IngestionResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def ingest_file(
    file_id: UUID,
    background: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
    user: dict = Depends(get_current_user),
) -> IngestionResponse:
    user_id = UUID(user["sub"])

    # Ownership is checked by the join, not by a separate lookup. FILE.course_id
    # exists and would be one hop shorter, but the composite FK only guarantees it
    # agrees with the folder -- it says nothing about who owns the course. Walking
    # FILE -> FOLDER -> COURSE reaches the one column that does: COURSE.user_id.
    #
    # A file owned by someone else therefore falls out of the same query as a file
    # that does not exist, and both leave below as 404. That is deliberate: a 403
    # here would confirm the id is real, which is exactly what a stranger probing
    # ids is trying to learn.
    statement = (
        select(FileRow)
        .join(Folder, col(Folder.id) == col(FileRow.folder_id))
        .join(Course, col(Course.id) == col(Folder.course_id))
        .where(FileRow.id == file_id, Course.user_id == user_id)
    )
    file_row = (await session.exec(statement)).first()
    if file_row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "File not found")

    # The run is recorded before any work starts, so a crash mid-ingest leaves a
    # row saying what was attempted rather than nothing at all. The three settings
    # are copied in rather than read back later: they are what THIS run used, and
    # re-indexing under a new chunker or a new embedding model must not silently
    # rewrite the history of the old one.
    #
    # is_active stays False here. R19 (ck_ingestion_run_active_is_ready) is
    # `NOT is_active OR status = 'ready'`, so an active run that is still QUEUED is
    # rejected by the database on insert.
    run = IngestionRun(
        file_id=file_id,
        status=IngestionRunStatus.QUEUED,
        chunker_version=settings.CHUNKER_VERSION,
        embedding_model=settings.MODEL_TYPE,
        embedding_dim=settings.EMBEDDINGS_DIM,
        is_active=False,
    )
    session.add(run)
    await session.commit()
    await session.refresh(run)
    # refresh() has just repopulated the row, so id is set; the annotation is
    # UUID | None only because SQLModel lets the database default it.
    assert run.id is not None

    # The work is handed off and the response goes out now. 202, not 200: parsing
    # a real lecture PDF measured 430.84 s on 31 Aug 2026 against 0.02 s for the
    # upload before it, and nothing holds a request open for seven minutes.
    background.add_task(
        _ingest_in_background,
        file_id=file_id,
        course_id=file_row.course_id,
        ingestion_run_id=run.id,
        storage_key=file_row.storage_key,
    )

    return IngestionResponse(
        file_id=file_id,
        ingestion_run_id=run.id,
        status="queued",
        chunk_count=None,
        error=None,
    )


async def _ingest_in_background(
    file_id: UUID,
    course_id: UUID,
    ingestion_run_id: UUID,
    storage_key: str,
) -> None:
    """Parse, chunk, embed and store one file, after the response has gone out.

    Three things are different from doing this inside the request, and each one
    is a thing that breaks silently if it is got wrong.

    **It opens its own session.** BackgroundTasks runs after the response is
    sent, by which point `get_session`'s `async with` has closed the request's
    session. Passing that session in here would work in a unit test with a
    hand-made session and fail in production with "session is closed" -- so the
    session is not a parameter at all. Nor is the FILE row: an ORM object bound
    to a closed session is the same trap wearing a different hat, so the row is
    re-read here from its id.

    **Nothing raises out of it.** There is no caller left to catch anything and
    the client already has its 202. An exception escaping here reaches Starlette
    and is logged, and the caller polling `GET /ingestion-runs/{id}` sees
    `queued` for ever -- a run that never finishes and never fails. Every failure
    path therefore ends in a committed row, not in a raise.

    **The caller learns nothing from the return value**, because it has already
    been answered. Everything the caller can act on has to be written down:
    INGESTION_RUN carries the detail, FILE.status carries the summary the file
    list renders.
    """
    async with async_session_maker() as session:
        run = await session.get(IngestionRun, ingestion_run_id)
        file_row = await session.get(FileRow, file_id)
        if run is None or file_row is None:
            # The file was deleted between the 202 and this task starting. There
            # is nobody to tell, and nothing to clean up that CASCADE has not
            # already taken.
            return

        try:
            await run_ingestion(
                file_id=file_id,
                course_id=course_id,
                ingestion_run_id=ingestion_run_id,
                # storage_key is an object-store key, not a path. resolve() is the
                # one place that knows how a key maps onto the filesystem today,
                # and the only line that changes when it becomes a bucket.
                file_path=str(resolve(storage_key)),
                session=session,
            )
        except NoExtractableContentError:
            # run_ingestion has already marked the INGESTION_RUN row failed. This
            # marks the FILE row, which nothing else touches -- without it a
            # scanned PDF sits at `uploaded` for ever and the UI cannot say why.
            file_row.status = FileStatus.FAILED
            file_row.error_message = (
                "This PDF has no selectable text (usually a scan or images only)."
            )
            await session.commit()
            return
        except Exception:
            # Log first, then record. Not swallowing this is the whole point:
            # measured 2 Sep 2026, a broken cv2 produced exactly this path and the
            # only surviving trace was "File processing failed" on the run row --
            # a string that names neither the module nor the cause. The
            # synchronous version got a traceback for free because its `raise`
            # became a 500; nothing here does that for us.
            logger.exception(
                "ingestion failed: file_id=%s ingestion_run_id=%s",
                file_id,
                ingestion_run_id,
            )
            # The stored message stays generic on purpose: whatever went wrong is
            # ours rather than something the caller can act on, and exception text
            # can carry filesystem paths. The traceback above is for us; this is
            # for them.
            #
            # No `raise`. The response left before this ran, so a raise would only
            # reach Starlette's logger and leave the run stuck at `queued`.
            file_row.status = FileStatus.FAILED
            file_row.error_message = "Ingestion failed. Please try again or contact support."
            await session.commit()
            return

        # Deactivate before activate, never the other way round.
        # ix_ingestion_run_one_active is a partial UNIQUE on file_id WHERE
        # is_active, so two runs must not both be active for even one statement.
        # Setting run.is_active first does not merely read wrong -- session.exec()
        # autoflushes the pending change ahead of the UPDATE, so the collision
        # happens before the statement that would have resolved it is ever sent.
        await session.exec(
            update(IngestionRun)
            .where(col(IngestionRun.file_id) == file_id, col(IngestionRun.is_active))
            .values(is_active=False)
        )
        run.is_active = True

        file_row.status = FileStatus.READY
        file_row.error_message = None
        file_row.indexed_at = datetime.now(UTC)
        await session.commit()


async def chunk_count_for_run(session: AsyncSession, ingestion_run_id: UUID) -> int:
    """Counted by ingestion_run_id, not file_id.

    Nothing in the codebase deletes chunks, so a file ingested three times has
    three generations of rows and file_id would report their sum -- a number that
    only ever grows. Kept as a function rather than inlined because the count now
    belongs to whoever polls the run, not to the route that started it.
    """
    return (
        await session.exec(
            select(func.count())
            .select_from(Chunk)
            .where(col(Chunk.ingestion_run_id) == ingestion_run_id)
        )
    ).one()


@course_files_router.get(
    "/{course_id}/files",
    response_model=list[FileRead],
)
async def list_course_files(
    course_id: UUID,
    session: AsyncSession = Depends(get_session),
    user: dict = Depends(get_current_user),
) -> list[FileRead]:
    user_id = UUID(user["sub"])

    statement = select(Course).where(
        col(Course.id) == course_id,
        col(Course.user_id) == user_id,
    )
    result = await session.exec(statement)
    course = result.first()
    if course is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found",
        )

    statement2 = (
        select(FileRow)
        .join(Folder, col(FileRow.folder_id) == col(Folder.id))
        .join(Course, col(Folder.course_id) == col(Course.id))
        .where(
            col(Course.id) == course_id,  # for safty purpose so check again
            col(Course.user_id) == user_id,  # for safty purpose so check again
            col(FileRow.course_id) == course_id,
        )
        .order_by(col(FileRow.uploaded_at).desc())
    )

    result2 = await session.exec(statement2)
    file_all = result2.all()

    return [FileRead.model_validate(file) for file in file_all]


@files_router.patch(
    "/{file_id}",
    response_model=FileRead,
)
async def update_file(
    file_id: UUID,
    data: FileUpdate,
    session: AsyncSession = Depends(get_session),
    user: dict = Depends(get_current_user),
) -> FileRead:
    user_id = UUID(user["sub"])
    statement = (
        select(FileRow)
        .join(
            Folder,
            (col(FileRow.folder_id)) == col(Folder.id),
        )
        .join(Course, col(Folder.course_id) == col(Course.id))
        .where(
            col(FileRow.id) == file_id,
            col(Course.user_id) == user_id,
        )
    )

    result = await session.exec(statement)
    file_row = result.first()

    if file_row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found",
        )

    # if frontend provide new filename, then change file name
    if data.filename is not None:
        file_row.filename = data.filename
    # if frontend provide new folder id, then "move folder"
    if data.folder_id is not None:
        statement2 = (
            select(Folder)
            .join(Course, col(Folder.course_id) == col(Course.id))
            .where(col(Folder.id) == data.folder_id, col(Course.user_id) == user_id)
        )
        result2 = await session.exec(statement2)
        destination_folder = result2.first()
        if destination_folder is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Destination folder not found",
            )
        if destination_folder.course_id != file_row.course_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A file cannot be moved to another course.",
            )
        file_row.folder_id = data.folder_id

    await session.commit()
    await session.refresh(file_row)
    return FileRead.model_validate(file_row)


@files_router.get("/{file_id}/content", response_class=FileResponse)
async def get_file_content(
    file_id: UUID,
    session: AsyncSession = Depends(get_session),
    user: dict = Depends(get_current_user),
) -> FileResponse:
    user_id = UUID(user["sub"])

    statement = (
        select(FileRow)
        .join(Folder, col(FileRow.folder_id) == col(Folder.id))
        .join(Course, col(Folder.course_id) == col(Course.id))
        .where(col(Course.user_id) == user_id, col(FileRow.id) == file_id)
    )
    result = await session.exec(statement)
    file_row = result.first()

    if file_row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")

    file_path = resolve(file_row.storage_key)
    if not file_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File content not found",
        )

    return FileResponse(
        path=file_path,
        media_type=file_row.mime_type,
        filename=file_row.filename,
        content_disposition_type="inline",
    )


@files_router.delete(
    "/{file_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_file(
    file_id: UUID,
    session: AsyncSession = Depends(get_session),
    user: dict = Depends(get_current_user),
) -> None:
    user_id = UUID(user["sub"])

    statement = (
        select(FileRow)
        .join(
            Folder,
            col(FileRow.folder_id) == col(Folder.id),
        )
        .join(
            Course,
            col(Folder.course_id) == col(Course.id),
        )
        .where(
            col(Course.user_id) == user_id,
            col(FileRow.id) == file_id,
        )
    )

    file_row = (await session.exec(statement)).first()

    if file_row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found",
        )

    # Delete the database record
    await session.delete(file_row)

    # Commit the transaction
    await session.commit()

    # Delete the physical file from storage
    delete_stored_file(file_row.storage_key)


@files_router.put(
    "/{file_id}/content",
    response_model=FileRead,
    status_code=status.HTTP_200_OK,
)
async def replace_file(
    file_id: UUID,
    upload: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
    user: dict = Depends(get_current_user),
) -> FileRead:
    user_id = UUID(user["sub"])

    statement = (
        select(FileRow)
        .join(
            Folder,
            col(FileRow.folder_id) == col(Folder.id),
        )
        .join(
            Course,
            col(Folder.course_id) == col(Course.id),
        )
        .where(
            col(Course.user_id) == user_id,
            col(FileRow.id) == file_id,
        )
    )

    file_row = (await session.exec(statement)).first()
    if file_row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found",
        )

    original_suffix = Path(file_row.filename).suffix.lower()
    replacement_suffix = Path(upload.filename or "").suffix.lower()

    if not replacement_suffix or (original_suffix != replacement_suffix):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Replacement file type must match the original file type",
        )
    try:
        size_bytes, sha256 = await replace_upload(
            upload,
            file_row.storage_key,
        )
    except UploadTooLargeError as exc:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=str(exc),
        ) from exc

    file_row.size_bytes = size_bytes
    file_row.sha256 = sha256
    file_row.page_count = None
    file_row.status = FileStatus.UPLOADED
    file_row.error_message = None
    file_row.indexed_at = None
    file_row.uploaded_at = datetime.now(UTC)

    # Replacement bytes no longer match chunks from the previously active run.
    # Keep the historical run and its chunks, but remove it from retrieval until
    # the replacement is ingested and a new run becomes active.
    await session.exec(
        update(IngestionRun)
        .where(col(IngestionRun.file_id) == file_id, col(IngestionRun.is_active))
        .values(is_active=False)
    )

    session.add(file_row)
    await session.commit()
    await session.refresh(file_row)
    return FileRead.model_validate(file_row)
