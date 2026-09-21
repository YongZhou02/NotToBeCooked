"""r51 -- the milestone CRUD routes.

Split on purpose. The ownership and routing checks run against a fake session,
like `test_folder.py`: they are about which query is built and which status code
comes back, and a real database would only make them slower.

Everything touching `file_ids` runs against a real database, because the thing
that goes wrong there is invisible to a mock. `Milestone.file_ids` is declared
`list[UUID]` over a JSONB column, and a JSONB column is written through
`json.dumps`, which raises `TypeError: Object of type UUID is not JSON
serializable`. A mocked session never serialises anything, so a mock-only suite
would pass on a handler that cannot write a single row. Measured 21 September
2026 against `PGDialect_asyncpg`.

That is the shape of R33 and R34 a third time: the test asserts what the handler
intends, and the damage is in what the layer underneath actually does.
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession

import app.models  # noqa: F401  -- registers every table before create_all
from app.db.database import get_session
from app.dependencies.auth import get_current_user
from app.main import app
from app.routers.milestone import milestones_router
from app.schemas.course import Course, CourseStatus
from app.schemas.file import File as FileRow
from app.schemas.file import FileStatus
from app.schemas.folder import Folder
from app.schemas.milestone import Milestone, MilestoneStatus
from app.schemas.user import User


@pytest_asyncio.fixture
async def ctx(test_database_url):
    """A database built from the models, one signed-in user, one course, two files.

    `test_database_url` rather than `settings.DATABASE_URL` -- the two lines
    below drop every table. See tests/conftest.py.
    """
    engine = create_async_engine(test_database_url)
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
        await conn.run_sync(SQLModel.metadata.create_all)
    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def add_file(session, course_id, folder_id) -> UUID:
        name = f"{uuid4()}.pdf"
        row = FileRow(
            course_id=course_id,
            folder_id=folder_id,
            filename=name,
            storage_key=name,
            mime_type="application/pdf",
            size_bytes=1,
            status=FileStatus.READY,
            uploaded_at=datetime.now(UTC),
        )
        session.add(row)
        await session.flush()
        assert row.id is not None
        return row.id

    async with maker() as session:
        user = User(email=f"{uuid4().hex[:8]}@x.com", hashed_password="x")
        session.add(user)
        await session.flush()
        user_id = user.id
        assert user_id is not None

        course = Course(
            user_id=user_id, code="CSC3105", name="DA", year=2026, sem=1,
            status=CourseStatus.ACTIVE,
        )
        other_course = Course(
            user_id=user_id, code="CSC9999", name="Other", year=2026, sem=1,
            status=CourseStatus.ACTIVE,
        )
        session.add(course)
        session.add(other_course)
        await session.flush()
        course_id, other_course_id = course.id, other_course.id
        assert course_id is not None and other_course_id is not None

        folder = Folder(course_id=course_id, name="root", is_root=True, sort_order=0)
        other_folder = Folder(
            course_id=other_course_id, name="root", is_root=True, sort_order=0
        )
        session.add(folder)
        session.add(other_folder)
        await session.flush()
        assert folder.id is not None and other_folder.id is not None

        file_a = await add_file(session, course_id, folder.id)
        file_b = await add_file(session, course_id, folder.id)
        foreign_file = await add_file(session, other_course_id, other_folder.id)
        await session.commit()

    async def _session():
        async with maker() as s:
            yield s

    app.dependency_overrides[get_session] = _session
    app.dependency_overrides[get_current_user] = lambda: {"sub": str(user_id)}
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, maker, course_id, [file_a, file_b], foreign_file
    app.dependency_overrides.clear()
    await engine.dispose()


@pytest.mark.asyncio
async def test_file_ids_survive_a_write_and_a_read(ctx):
    """The one this file exists for.

    Two uuids go in through JSON, through a JSONB column, and come back out as
    uuids. Before `_checked_file_ids` converted them to strings this raised
    TypeError at commit -- a 500 on every create that attached a file.
    """
    client, maker, course_id, files, _foreign = ctx

    r = await client.post(
        f"/courses/{course_id}/milestones",
        json={
            "title": "Week 3 - Recursion",
            "position": 0,
            "week": 3,
            "due_date": "2026-10-09",
            "file_ids": [str(files[0]), str(files[1])],
        },
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["file_ids"] == [str(files[0]), str(files[1])]

    # ... and it is really in the column, not only in the response object the
    # handler happened to still be holding.
    read_back = await client.get(f"/courses/{course_id}/milestones/{body['id']}")
    assert read_back.status_code == 200
    assert read_back.json()["file_ids"] == [str(files[0]), str(files[1])]

    async with maker() as session:
        row = (
            await session.exec(select(Milestone).where(Milestone.id == body["id"]))
        ).one()
        # Stored as JSON strings; MilestoneRead is what turns them back into UUIDs.
        assert row.file_ids == [str(files[0]), str(files[1])]


@pytest.mark.asyncio
async def test_attaching_a_file_from_another_course_is_404(ctx):
    """JSONB enforces no foreign key, so the handler is the only thing checking."""
    client, _maker, course_id, _files, foreign_file = ctx

    r = await client.post(
        f"/courses/{course_id}/milestones",
        json={"title": "M", "file_ids": [str(foreign_file)]},
    )
    assert r.status_code == 404, r.text
    assert str(foreign_file) in r.json()["detail"]


@pytest.mark.asyncio
async def test_patch_clears_a_nullable_field_and_bumps_updated_at(ctx):
    """`week: null` means clear it. An `if value is not None` chain cannot.

    Also covers `updated_at`: the column has no `onupdate`, so the handler sets
    it by hand or a roadmap edited every week keeps reporting its creation date.
    """
    client, _maker, course_id, _files, _foreign = ctx

    created = await client.post(
        f"/courses/{course_id}/milestones",
        json={"title": "M", "week": 3, "due_date": "2026-10-09"},
    )
    assert created.status_code == 201, created.text
    milestone_id = created.json()["id"]
    before = created.json()["updated_at"]

    r = await client.patch(
        f"/courses/{course_id}/milestones/{milestone_id}",
        json={"week": None, "status": "in_progress"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["week"] is None
    assert body["status"] == MilestoneStatus.IN_PROGRESS.value
    # Untouched keys keep their values -- PATCH, not PUT.
    assert body["due_date"] == "2026-10-09"
    assert body["title"] == "M"
    assert body["updated_at"] > before


@pytest.mark.asyncio
async def test_list_comes_back_in_position_order(ctx):
    client, _maker, course_id, _files, _foreign = ctx

    for position, title in ((2, "third"), (0, "first"), (1, "second")):
        r = await client.post(
            f"/courses/{course_id}/milestones",
            json={"title": title, "position": position},
        )
        assert r.status_code == 201, r.text

    listed = await client.get(f"/courses/{course_id}/milestones")
    assert listed.status_code == 200
    assert [m["title"] for m in listed.json()] == ["first", "second", "third"]


@pytest.mark.asyncio
async def test_delete_removes_the_milestone_and_not_the_files(ctx):
    """`file_ids` is a list of references. Deleting the holder frees the
    references, not the files -- which is why there is no emptiness check here,
    unlike `delete_folder`."""
    client, maker, course_id, files, _foreign = ctx

    created = await client.post(
        f"/courses/{course_id}/milestones",
        json={"title": "M", "file_ids": [str(files[0])]},
    )
    milestone_id = created.json()["id"]

    r = await client.delete(f"/courses/{course_id}/milestones/{milestone_id}")
    assert r.status_code == 204

    assert (await client.get(f"/courses/{course_id}/milestones/{milestone_id}")).status_code == 404

    async with maker() as session:
        still_there = (
            await session.exec(select(FileRow).where(FileRow.id == files[0]))
        ).one()
        assert still_there.id == files[0]


def test_another_users_milestone_is_404_not_403():
    """404, never 403. A 403 confirms the id exists and belongs to someone else,
    which turns the endpoint into a membership oracle."""
    test_app = FastAPI()
    test_app.include_router(milestones_router, prefix="/courses")

    fake_session = AsyncMock()
    fake_result = Mock()
    fake_session.exec.return_value = fake_result
    # The join filters on Course.user_id, so somebody else's row simply is not
    # in the result set -- the handler never sees it to compare owners.
    fake_result.first.return_value = None

    async def override_session():
        return fake_session

    test_app.dependency_overrides[get_session] = override_session
    test_app.dependency_overrides[get_current_user] = lambda: {"sub": str(uuid4())}

    client = TestClient(test_app)
    r = client.get(f"/courses/{uuid4()}/milestones/{uuid4()}")

    assert r.status_code == 404
    assert r.json()["detail"] == "Milestone not found"


def test_create_under_a_course_you_do_not_own_is_404():
    test_app = FastAPI()
    test_app.include_router(milestones_router, prefix="/courses")

    fake_session = AsyncMock()
    fake_result = Mock()
    fake_session.exec.return_value = fake_result
    fake_result.first.return_value = None
    fake_session.add = Mock()

    async def override_session():
        return fake_session

    test_app.dependency_overrides[get_session] = override_session
    test_app.dependency_overrides[get_current_user] = lambda: {"sub": str(uuid4())}

    client = TestClient(test_app)
    r = client.post(f"/courses/{uuid4()}/milestones", json={"title": "M"})

    assert r.status_code == 404
    assert r.json()["detail"] == "Course not found"
    # Nothing was written on the way to the refusal.
    fake_session.add.assert_not_called()
