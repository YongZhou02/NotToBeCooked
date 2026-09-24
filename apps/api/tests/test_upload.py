"""POST /files -- the four things that are not obvious from the handler.

Runs against a real database and real disk. The endpoint's whole job is to put
bytes somewhere and write a row that agrees with them, so mocking either half
would test nothing.
"""

import hashlib
from io import BytesIO
from uuid import uuid4

import pytest
import pytest_asyncio
from fastapi import UploadFile
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlmodel import SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession

import app.models  # noqa: F401  -- registers every table before create_all
from app.core.config import settings
from app.db.database import get_session, make_engine
from app.dependencies.auth import get_current_user
from app.main import app
from app.schemas.course import Course, CourseStatus
from app.schemas.file import File as FileRow
from app.schemas.file import FileStatus
from app.schemas.folder import Folder
from app.schemas.user import User
from app.services.storage import (
    UploadTooLargeError,
    replace_upload,
    resolve,
)

PDF = b"%PDF-1.4\nnot a real pdf, but real bytes\n"


@pytest_asyncio.fixture
async def ctx(tmp_path, monkeypatch, test_database_url):
    """A database built from the models, a temp storage dir, and one signed-in user.

    `test_database_url` rather than `settings.DATABASE_URL`: the two lines below
    drop every table, and pointed at the development database that is `pnpm test`
    deleting the developer's work with no warning. See tests/conftest.py.
    """
    monkeypatch.setattr(settings, "STORAGE_DIR", tmp_path)
    engine = make_engine(test_database_url)
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
        await conn.run_sync(SQLModel.metadata.create_all)
    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with maker() as session:
        # Primary keys are declared `UUID | None` on the models, so each id is
        # pinned to a local the moment it exists rather than read off the row
        # three times and narrowed three times.
        user = User(email=f"{uuid4().hex[:8]}@x.com", hashed_password="x")
        session.add(user)
        await session.flush()
        user_id = user.id
        assert user_id is not None

        course = Course(
            user_id=user_id,
            code="CSC3105",
            name="DA",
            year=2026,
            sem=1,
            status=CourseStatus.ACTIVE,
        )
        session.add(course)
        await session.flush()
        course_id = course.id
        assert course_id is not None

        folder = Folder(course_id=course_id, name="root", is_root=True, sort_order=0)
        session.add(folder)
        await session.commit()
        folder_id = folder.id
        assert folder_id is not None
        ids = (user_id, course_id, folder_id)

    async def _session():
        async with maker() as s:
            yield s

    app.dependency_overrides[get_session] = _session
    app.dependency_overrides[get_current_user] = lambda: {"sub": str(ids[0])}
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, maker, ids
    app.dependency_overrides.clear()
    await engine.dispose()


@pytest.mark.asyncio
async def test_upload_writes_bytes_and_row_that_agree(ctx):
    client, maker, (_user_id, course_id, folder_id) = ctx

    r = await client.post(
        "/files",
        data={"folder_id": str(folder_id)},
        files={"upload": ("L1.pdf", PDF, "application/pdf")},
    )
    assert r.status_code == 201, r.text
    body = r.json()

    # 1. The row says what the bytes actually are, not what the client claimed.
    assert body["size_bytes"] == len(PDF)
    assert body["sha256"] == hashlib.sha256(PDF).hexdigest()

    # 2. The bytes are where storage_key says they are.
    assert resolve(body["storage_key"]).read_bytes() == PDF

    # 3. Uploaded, not ready. Nothing has been indexed.
    assert body["status"] == FileStatus.UPLOADED.value

    # 4. course_id came from the folder, and r42's chain accepts the row --
    #    which it would not if the two disagreed.
    async with maker() as session:
        row = (
            (await session.execute(select(FileRow).where(FileRow.id == body["id"]))).scalars().one()
        )
        assert row.course_id == course_id


@pytest.mark.asyncio
async def test_upload_into_someone_elses_folder_is_404_not_403(ctx):
    """A stranger must not be able to tell a real folder id from a made-up one."""
    client, _maker, _ids = ctx
    r = await client.post(
        "/files",
        data={"folder_id": str(uuid4())},
        files={"upload": ("L1.pdf", PDF, "application/pdf")},
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_oversized_upload_leaves_nothing_behind(ctx, monkeypatch):
    """The limit is enforced mid-stream, and the partial file is removed."""
    client, maker, (_u, _c, folder_id) = ctx
    monkeypatch.setattr(settings, "MAX_UPLOAD_BYTES", 8)

    r = await client.post(
        "/files",
        data={"folder_id": str(folder_id)},
        files={"upload": ("big.pdf", b"x" * 4096, "application/pdf")},
    )
    assert r.status_code == 413

    async with maker() as session:
        rows = (await session.execute(select(FileRow))).scalars().all()
    assert rows == []
    assert list(settings.STORAGE_DIR.rglob("*.pdf")) == []


@pytest.mark.asyncio
async def test_replace_upload_replaces_existing_bytes(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "STORAGE_DIR", tmp_path)

    storage_key = "user-123/file-456.pdf"
    destination = resolve(storage_key)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(b"old file content")

    new_content = b"%PDF-1.4\nnew file content"
    upload = UploadFile(
        filename="replacement.pdf",
        file=BytesIO(new_content),
    )

    size_bytes, sha256 = await replace_upload(upload, storage_key)

    assert destination.read_bytes() == new_content
    assert size_bytes == len(new_content)
    assert sha256 == hashlib.sha256(new_content).hexdigest()
    assert list(tmp_path.rglob("*.tmp")) == []


@pytest.mark.asyncio
async def test_replace_upload_failure_preserves_existing_bytes(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(settings, "STORAGE_DIR", tmp_path)
    monkeypatch.setattr(settings, "MAX_UPLOAD_BYTES", 8)

    storage_key = "user-123/file-456.pdf"
    destination = resolve(storage_key)
    destination.parent.mkdir(parents=True, exist_ok=True)

    old_content = b"old file content"
    destination.write_bytes(old_content)

    upload = UploadFile(
        filename="replacement.pdf",
        file=BytesIO(b"x" * 4096),
    )

    with pytest.raises(UploadTooLargeError):
        await replace_upload(upload, storage_key)

    assert destination.read_bytes() == old_content
    assert list(tmp_path.rglob("*.tmp")) == []
