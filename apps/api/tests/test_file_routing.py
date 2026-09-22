import hashlib
from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.db.database import get_session
from app.dependencies.auth import get_current_user
from app.routers.files import course_files_router, files_router
from app.schemas.course import Course
from app.schemas.file import File as FileRow
from app.schemas.file import FileStatus
from app.schemas.folder import Folder
from app.services.storage import UploadTooLargeError


# Test Course with files
def test_list_course_files_returns_200_and_files():
    test_app = FastAPI()
    test_app.include_router(course_files_router, prefix="/courses")

    user_id = uuid4()
    course_id = uuid4()
    folder_id = uuid4()
    file_id = uuid4()

    fake_course = Course(
        id=course_id,
        user_id=user_id,
        code="SECJ3203",
        name="Software Engineering",
        year=2026,
        sem=1,
    )

    fake_file = FileRow(
        id=file_id,
        course_id=course_id,
        folder_id=folder_id,
        filename="lecture-1.pdf",
        storage_key=f"{user_id}/{file_id}/lecture-1.pdf",
        sha256="abc123",
        mime_type="application/pdf",
        size_bytes=1024,
        page_count=10,
        status=FileStatus.READY,
        error_message=None,
        uploaded_at=datetime.now(UTC),
        indexed_at=datetime.now(UTC),
    )

    course_result = Mock()
    course_result.first.return_value = fake_course

    files_result = Mock()
    files_result.all.return_value = [fake_file]

    fake_session = AsyncMock()
    fake_session.exec.side_effect = [
        course_result,
        files_result,
    ]

    async def override_session():
        return fake_session

    async def override_current_user():
        return {"sub": str(user_id)}

    test_app.dependency_overrides[get_session] = override_session
    test_app.dependency_overrides[get_current_user] = override_current_user

    client = TestClient(test_app)
    response = client.get(f"/courses/{course_id}/files")

    assert response.status_code == 200

    body = response.json()
    assert len(body) == 1

    returned_file = body[0]
    assert returned_file["id"] == str(file_id)
    assert returned_file["folder_id"] == str(folder_id)
    assert returned_file["filename"] == "lecture-1.pdf"
    assert returned_file["mime_type"] == "application/pdf"
    assert returned_file["size_bytes"] == 1024
    assert returned_file["page_count"] == 10
    assert returned_file["status"] == "ready"

    assert fake_session.exec.await_count == 2


# Test empty Course
def test_list_course_files_returns_empty_list_when_course_has_no_files():
    test_app = FastAPI()
    test_app.include_router(course_files_router, prefix="/courses")

    user_id = uuid4()
    course_id = uuid4()

    fake_course = Course(
        id=course_id,
        user_id=user_id,
        code="SECJ3203",
        name="Software Engineering",
        year=2026,
        sem=1,
    )

    course_result = Mock()
    course_result.first.return_value = fake_course

    files_result = Mock()
    files_result.all.return_value = []

    fake_session = AsyncMock()
    fake_session.exec.side_effect = [
        course_result,
        files_result,
    ]

    async def override_session():
        return fake_session

    async def override_current_user():
        return {"sub": str(user_id)}

    test_app.dependency_overrides[get_session] = override_session
    test_app.dependency_overrides[get_current_user] = override_current_user

    client = TestClient(test_app)
    response = client.get(f"/courses/{course_id}/files")

    assert response.status_code == 200
    assert response.json() == []

    assert fake_session.exec.await_count == 2


# Test Course not found
def test_list_course_files_returns_404_when_course_not_found():
    test_app = FastAPI()
    test_app.include_router(course_files_router, prefix="/courses")

    user_id = uuid4()
    course_id = uuid4()

    course_result = Mock()
    course_result.first.return_value = None

    fake_session = AsyncMock()
    fake_session.exec.return_value = course_result

    async def override_session():
        return fake_session

    async def override_current_user():
        return {"sub": str(user_id)}

    test_app.dependency_overrides[get_session] = override_session
    test_app.dependency_overrides[get_current_user] = override_current_user

    client = TestClient(test_app)
    response = client.get(f"/courses/{course_id}/files")

    assert response.status_code == 404
    assert response.json()["detail"] == "Course not found"

    fake_session.exec.assert_awaited_once()


def test_update_file_renames_file():
    test_app = FastAPI()
    test_app.include_router(files_router, prefix="/files")

    user_id = uuid4()
    course_id = uuid4()
    folder_id = uuid4()
    file_id = uuid4()

    fake_file = FileRow(
        id=file_id,
        course_id=course_id,
        folder_id=folder_id,
        filename="old-name.pdf",
        storage_key=f"{user_id}/{file_id}/old-name.pdf",
        sha256="abc123",
        mime_type="application/pdf",
        size_bytes=1024,
        page_count=10,
        status=FileStatus.READY,
        error_message=None,
        uploaded_at=datetime.now(UTC),
        indexed_at=datetime.now(UTC),
    )

    file_result = Mock()
    file_result.first.return_value = fake_file

    fake_session = AsyncMock()
    fake_session.exec.return_value = file_result

    async def override_session():
        return fake_session

    async def override_current_user():
        return {"sub": str(user_id)}

    test_app.dependency_overrides[get_session] = override_session
    test_app.dependency_overrides[get_current_user] = override_current_user

    client = TestClient(test_app)
    response = client.patch(
        f"/files/{file_id}",
        json={"filename": "new-name.pdf"},
    )

    assert response.status_code == 200
    assert response.json()["filename"] == "new-name.pdf"
    assert response.json()["folder_id"] == str(folder_id)

    assert fake_file.filename == "new-name.pdf"
    fake_session.commit.assert_awaited_once()
    fake_session.refresh.assert_awaited_once_with(fake_file)


def test_update_file_returns_409_when_moving_to_another_course():
    test_app = FastAPI()
    test_app.include_router(files_router, prefix="/files")

    user_id = uuid4()
    old_course_id = uuid4()
    old_folder_id = uuid4()

    new_course_id = uuid4()
    new_folder_id = uuid4()

    file_id = uuid4()

    fake_file = FileRow(
        id=file_id,
        course_id=old_course_id,
        folder_id=old_folder_id,
        filename="lecture.pdf",
        storage_key=f"{user_id}/{file_id}/lecture.pdf",
        sha256="abc123",
        mime_type="application/pdf",
        size_bytes=1024,
        page_count=10,
        status=FileStatus.READY,
        error_message=None,
        uploaded_at=datetime.now(UTC),
        indexed_at=datetime.now(UTC),
    )

    destination_folder = Folder(
        id=new_folder_id,
        course_id=new_course_id,
        parent_folder_id=None,
        name="New Folder",
        is_root=True,
        sort_order=0,
    )

    file_result = Mock()
    file_result.first.return_value = fake_file

    destination_result = Mock()
    destination_result.first.return_value = destination_folder

    fake_session = AsyncMock()
    fake_session.exec.side_effect = [
        file_result,
        destination_result,
    ]

    async def override_session():
        return fake_session

    async def override_current_user():
        return {"sub": str(user_id)}

    test_app.dependency_overrides[get_session] = override_session
    test_app.dependency_overrides[get_current_user] = override_current_user

    client = TestClient(test_app)
    response = client.patch(
        f"/files/{file_id}",
        json={"folder_id": str(new_folder_id)},
    )

    assert response.status_code == 409
    assert response.json() == {"detail": "A file cannot be moved to another course."}

    assert fake_file.folder_id == old_folder_id
    assert fake_file.course_id == old_course_id

    assert fake_session.exec.await_count == 2
    fake_session.commit.assert_not_awaited()
    fake_session.refresh.assert_not_awaited()


def test_update_file_moves_file_within_same_course():
    test_app = FastAPI()
    test_app.include_router(files_router, prefix="/files")

    user_id = uuid4()
    course_id = uuid4()
    old_folder_id = uuid4()
    new_folder_id = uuid4()
    file_id = uuid4()

    fake_file = FileRow(
        id=file_id,
        course_id=course_id,
        folder_id=old_folder_id,
        filename="lecture.pdf",
        storage_key=f"{user_id}/{file_id}/lecture.pdf",
        sha256="abc123",
        mime_type="application/pdf",
        size_bytes=1024,
        page_count=10,
        status=FileStatus.READY,
        error_message=None,
        uploaded_at=datetime.now(UTC),
        indexed_at=datetime.now(UTC),
    )

    destination_folder = Folder(
        id=new_folder_id,
        course_id=course_id,
        parent_folder_id=None,
        name="New Folder",
        is_root=True,
        sort_order=0,
    )

    file_result = Mock()
    file_result.first.return_value = fake_file

    destination_result = Mock()
    destination_result.first.return_value = destination_folder

    fake_session = AsyncMock()
    fake_session.exec.side_effect = [
        file_result,
        destination_result,
    ]

    async def override_session():
        return fake_session

    async def override_current_user():
        return {"sub": str(user_id)}

    test_app.dependency_overrides[get_session] = override_session
    test_app.dependency_overrides[get_current_user] = override_current_user

    client = TestClient(test_app)
    response = client.patch(
        f"/files/{file_id}",
        json={"folder_id": str(new_folder_id)},
    )

    assert response.status_code == 200
    assert response.json()["folder_id"] == str(new_folder_id)

    assert fake_file.folder_id == new_folder_id
    assert fake_file.course_id == course_id

    assert fake_session.exec.await_count == 2
    fake_session.commit.assert_awaited_once()
    fake_session.refresh.assert_awaited_once_with(fake_file)


def test_update_file_returns_404_when_file_not_found():
    test_app = FastAPI()
    test_app.include_router(files_router, prefix="/files")

    user_id = uuid4()
    file_id = uuid4()

    file_result = Mock()
    file_result.first.return_value = None

    fake_session = AsyncMock()
    fake_session.exec.return_value = file_result

    async def override_session():
        return fake_session

    async def override_current_user():
        return {"sub": str(user_id)}

    test_app.dependency_overrides[get_session] = override_session
    test_app.dependency_overrides[get_current_user] = override_current_user

    client = TestClient(test_app)
    response = client.patch(
        f"/files/{file_id}",
        json={"filename": "new-name.pdf"},
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "File not found"}

    fake_session.exec.assert_awaited_once()
    fake_session.commit.assert_not_awaited()
    fake_session.refresh.assert_not_awaited()


def test_update_file_returns_404_when_destination_folder_not_found():
    test_app = FastAPI()
    test_app.include_router(files_router, prefix="/files")

    user_id = uuid4()
    course_id = uuid4()
    original_folder_id = uuid4()
    destination_folder_id = uuid4()
    file_id = uuid4()

    fake_file = FileRow(
        id=file_id,
        course_id=course_id,
        folder_id=original_folder_id,
        filename="lecture.pdf",
        storage_key=f"{user_id}/{file_id}/lecture.pdf",
        sha256="abc123",
        mime_type="application/pdf",
        size_bytes=1024,
        page_count=10,
        status=FileStatus.READY,
        error_message=None,
        uploaded_at=datetime.now(UTC),
        indexed_at=datetime.now(UTC),
    )

    file_result = Mock()
    file_result.first.return_value = fake_file

    destination_result = Mock()
    destination_result.first.return_value = None

    fake_session = AsyncMock()
    fake_session.exec.side_effect = [
        file_result,
        destination_result,
    ]

    async def override_session():
        return fake_session

    async def override_current_user():
        return {"sub": str(user_id)}

    test_app.dependency_overrides[get_session] = override_session
    test_app.dependency_overrides[get_current_user] = override_current_user

    client = TestClient(test_app)
    response = client.patch(
        f"/files/{file_id}",
        json={"folder_id": str(destination_folder_id)},
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Destination folder not found"}

    assert fake_file.folder_id == original_folder_id
    assert fake_file.course_id == course_id

    assert fake_session.exec.await_count == 2
    fake_session.commit.assert_not_awaited()
    fake_session.refresh.assert_not_awaited()


def test_get_file_content_returns_file_bytes(tmp_path, monkeypatch):
    test_app = FastAPI()
    test_app.include_router(files_router, prefix="/files")

    user_id = uuid4()
    course_id = uuid4()
    folder_id = uuid4()
    file_id = uuid4()

    expected_content = b"%PDF-1.4\nfake pdf content"
    stored_file = tmp_path / "stored-file.pdf"
    stored_file.write_bytes(expected_content)

    fake_file = FileRow(
        id=file_id,
        course_id=course_id,
        folder_id=folder_id,
        filename="lecture-1.pdf",
        storage_key=f"{user_id}/{file_id}.pdf",
        sha256="abc123",
        mime_type="application/pdf",
        size_bytes=len(expected_content),
        page_count=1,
        status=FileStatus.READY,
        error_message=None,
        uploaded_at=datetime.now(UTC),
        indexed_at=datetime.now(UTC),
    )

    query_result = Mock()
    query_result.first.return_value = fake_file

    fake_session = AsyncMock()
    fake_session.exec.return_value = query_result

    async def override_session():
        return fake_session

    async def override_current_user():
        return {"sub": str(user_id)}

    test_app.dependency_overrides[get_session] = override_session
    test_app.dependency_overrides[get_current_user] = override_current_user

    fake_resolve = Mock(return_value=stored_file)
    monkeypatch.setattr("app.routers.files.resolve", fake_resolve)

    client = TestClient(test_app)
    response = client.get(f"/files/{file_id}/content")

    assert response.status_code == 200
    assert response.content == expected_content
    assert response.headers["content-type"] == "application/pdf"
    assert "inline" in response.headers["content-disposition"]
    assert "lecture-1.pdf" in response.headers["content-disposition"]
    fake_session.exec.assert_awaited_once()
    fake_resolve.assert_called_once_with(fake_file.storage_key)


def test_get_file_content_returns_404_when_file_not_found(monkeypatch):
    test_app = FastAPI()
    test_app.include_router(files_router, prefix="/files")

    user_id = uuid4()
    file_id = uuid4()

    query_result = Mock()
    query_result.first.return_value = None

    fake_session = AsyncMock()
    fake_session.exec.return_value = query_result

    fake_resolve = Mock()
    monkeypatch.setattr("app.routers.files.resolve", fake_resolve)

    async def override_session():
        return fake_session

    async def override_current_user():
        return {"sub": str(user_id)}

    test_app.dependency_overrides[get_session] = override_session
    test_app.dependency_overrides[get_current_user] = override_current_user

    client = TestClient(test_app)
    response = client.get(f"/files/{file_id}/content")

    assert response.status_code == 404
    assert response.json() == {"detail": "File not found"}
    fake_resolve.assert_not_called()


def test_get_file_content_returns_404_when_stored_file_is_missing(
    tmp_path,
    monkeypatch,
):
    test_app = FastAPI()
    test_app.include_router(files_router, prefix="/files")

    user_id = uuid4()
    course_id = uuid4()
    folder_id = uuid4()
    file_id = uuid4()

    fake_file = FileRow(
        id=file_id,
        course_id=course_id,
        folder_id=folder_id,
        filename="missing.pdf",
        storage_key=f"{user_id}/{file_id}.pdf",
        sha256="abc123",
        mime_type="application/pdf",
        size_bytes=1024,
        page_count=1,
        status=FileStatus.READY,
        error_message=None,
        uploaded_at=datetime.now(UTC),
        indexed_at=datetime.now(UTC),
    )

    query_result = Mock()
    query_result.first.return_value = fake_file

    fake_session = AsyncMock()
    fake_session.exec.return_value = query_result

    missing_file = tmp_path / "missing.pdf"
    monkeypatch.setattr(
        "app.routers.files.resolve",
        lambda storage_key: missing_file,
    )

    async def override_session():
        return fake_session

    async def override_current_user():
        return {"sub": str(user_id)}

    test_app.dependency_overrides[get_session] = override_session
    test_app.dependency_overrides[get_current_user] = override_current_user

    client = TestClient(test_app)
    response = client.get(f"/files/{file_id}/content")

    assert response.status_code == 404
    assert response.json() == {"detail": "File content not found"}


def test_delete_file_returns_204_and_removes_database_and_storage(monkeypatch):
    test_app = FastAPI()
    test_app.include_router(files_router, prefix="/files")

    user_id = uuid4()
    course_id = uuid4()
    folder_id = uuid4()
    file_id = uuid4()

    fake_file = FileRow(
        id=file_id,
        course_id=course_id,
        folder_id=folder_id,
        filename="lecture-1.pdf",
        storage_key=f"{user_id}/{file_id}.pdf",
        sha256="abc123",
        mime_type="application/pdf",
        size_bytes=1024,
        page_count=1,
        status=FileStatus.READY,
        error_message=None,
        uploaded_at=datetime.now(UTC),
        indexed_at=datetime.now(UTC),
    )

    query_result = Mock()
    query_result.first.return_value = fake_file

    fake_session = AsyncMock()
    fake_session.exec.return_value = query_result

    fake_delete_stored_file = Mock()
    monkeypatch.setattr(
        "app.routers.files.delete_stored_file",
        fake_delete_stored_file,
    )

    async def override_session():
        return fake_session

    async def override_current_user():
        return {"sub": str(user_id)}

    test_app.dependency_overrides[get_session] = override_session
    test_app.dependency_overrides[get_current_user] = override_current_user

    client = TestClient(test_app)
    response = client.delete(f"/files/{file_id}")

    assert response.status_code == 204
    assert response.content == b""

    fake_session.exec.assert_awaited_once()
    fake_session.delete.assert_awaited_once_with(fake_file)
    fake_session.commit.assert_awaited_once()
    fake_delete_stored_file.assert_called_once_with(fake_file.storage_key)


def test_delete_file_keeps_storage_when_database_commit_fails(monkeypatch):
    test_app = FastAPI()
    test_app.include_router(files_router, prefix="/files")

    user_id = uuid4()
    course_id = uuid4()
    folder_id = uuid4()
    file_id = uuid4()

    fake_file = FileRow(
        id=file_id,
        course_id=course_id,
        folder_id=folder_id,
        filename="lecture-1.pdf",
        storage_key=f"{user_id}/{file_id}.pdf",
        sha256="abc123",
        mime_type="application/pdf",
        size_bytes=1024,
        page_count=1,
        status=FileStatus.READY,
        error_message=None,
        uploaded_at=datetime.now(UTC),
        indexed_at=datetime.now(UTC),
    )

    query_result = Mock()
    query_result.first.return_value = fake_file

    fake_session = AsyncMock()
    fake_session.exec.return_value = query_result
    fake_session.commit.side_effect = RuntimeError("Database commit failed")

    fake_delete_stored_file = Mock()
    monkeypatch.setattr(
        "app.routers.files.delete_stored_file",
        fake_delete_stored_file,
    )

    async def override_session():
        return fake_session

    async def override_current_user():
        return {"sub": str(user_id)}

    test_app.dependency_overrides[get_session] = override_session
    test_app.dependency_overrides[get_current_user] = override_current_user

    client = TestClient(test_app, raise_server_exceptions=False)
    response = client.delete(f"/files/{file_id}")

    assert response.status_code == 500

    fake_session.delete.assert_awaited_once_with(fake_file)
    fake_session.commit.assert_awaited_once()
    fake_delete_stored_file.assert_not_called()


def test_delete_file_returns_404_when_file_not_found(monkeypatch):
    test_app = FastAPI()
    test_app.include_router(files_router, prefix="/files")

    user_id = uuid4()
    file_id = uuid4()

    query_result = Mock()
    query_result.first.return_value = None

    fake_session = AsyncMock()
    fake_session.exec.return_value = query_result

    fake_delete_stored_file = Mock()
    monkeypatch.setattr(
        "app.routers.files.delete_stored_file",
        fake_delete_stored_file,
    )

    async def override_session():
        return fake_session

    async def override_current_user():
        return {"sub": str(user_id)}

    test_app.dependency_overrides[get_session] = override_session
    test_app.dependency_overrides[get_current_user] = override_current_user

    client = TestClient(test_app)
    response = client.delete(f"/files/{file_id}")

    assert response.status_code == 404
    assert response.json() == {"detail": "File not found"}

    fake_delete_stored_file.assert_not_called()
    fake_session.delete.assert_not_awaited()
    fake_session.commit.assert_not_awaited()


def test_replace_file_content_returns_200_and_updates_metadata(monkeypatch):
    test_app = FastAPI()
    test_app.include_router(files_router, prefix="/files")

    user_id = uuid4()
    course_id = uuid4()
    folder_id = uuid4()
    file_id = uuid4()

    original_file = FileRow(
        id=file_id,
        course_id=course_id,
        folder_id=folder_id,
        filename="lecture.pdf",
        storage_key=f"{user_id}/{file_id}.pdf",
        sha256="old-sha256",
        mime_type="application/pdf",
        size_bytes=100,
        page_count=10,
        status=FileStatus.READY,
        error_message="old error",
        uploaded_at=datetime.now(UTC),
        indexed_at=datetime.now(UTC),
    )

    query_result = Mock()
    query_result.first.return_value = original_file

    fake_session = AsyncMock()
    fake_session.exec.return_value = query_result
    fake_session.add = Mock()

    async def override_session():
        return fake_session

    async def override_current_user():
        return {"sub": str(user_id)}

    test_app.dependency_overrides[get_session] = override_session
    test_app.dependency_overrides[get_current_user] = override_current_user

    new_content = b"%PDF-1.4\nreplacement content"
    new_sha256 = hashlib.sha256(new_content).hexdigest()

    fake_replace_upload = AsyncMock(
        return_value=(len(new_content), new_sha256),
    )
    monkeypatch.setattr(
        "app.routers.files.replace_upload",
        fake_replace_upload,
    )

    client = TestClient(test_app)
    response = client.put(
        f"/files/{file_id}/content",
        files={
            "upload": (
                "replacement.pdf",
                new_content,
                "application/pdf",
            )
        },
    )

    assert response.status_code == 200

    assert original_file.id == file_id
    assert original_file.filename == "lecture.pdf"
    assert original_file.storage_key == f"{user_id}/{file_id}.pdf"

    assert original_file.size_bytes == len(new_content)
    assert original_file.sha256 == new_sha256
    assert original_file.page_count is None
    assert original_file.status == FileStatus.UPLOADED
    assert original_file.error_message is None
    assert original_file.indexed_at is None

    fake_replace_upload.assert_awaited_once()

    replace_call = fake_replace_upload.await_args
    assert replace_call is not None
    assert replace_call.args[1] == original_file.storage_key
    assert fake_session.exec.await_count == 2
    deactivate_statement = fake_session.exec.await_args_list[1].args[0]
    assert deactivate_statement.table.name == "ingestion_run"
    deactivate_values = list(deactivate_statement._values.values())
    assert len(deactivate_values) == 1 and deactivate_values[0].value is False

    fake_session.add.assert_called_once_with(original_file)
    fake_session.commit.assert_awaited_once()
    fake_session.refresh.assert_awaited_once_with(original_file)


def test_replace_file_content_returns_415_when_file_type_does_not_match(
    monkeypatch,
):
    test_app = FastAPI()
    test_app.include_router(files_router, prefix="/files")

    user_id = uuid4()
    course_id = uuid4()
    folder_id = uuid4()
    file_id = uuid4()

    original_file = FileRow(
        id=file_id,
        course_id=course_id,
        folder_id=folder_id,
        filename="lecture.pdf",
        storage_key=f"{user_id}/{file_id}.pdf",
        sha256="old-sha256",
        mime_type="application/pdf",
        size_bytes=100,
        page_count=10,
        status=FileStatus.READY,
        error_message=None,
        uploaded_at=datetime.now(UTC),
        indexed_at=datetime.now(UTC),
    )

    query_result = Mock()
    query_result.first.return_value = original_file

    fake_session = AsyncMock()
    fake_session.exec.return_value = query_result
    fake_session.add = Mock()

    fake_replace_upload = AsyncMock()
    monkeypatch.setattr(
        "app.routers.files.replace_upload",
        fake_replace_upload,
    )

    async def override_session():
        return fake_session

    async def override_current_user():
        return {"sub": str(user_id)}

    test_app.dependency_overrides[get_session] = override_session
    test_app.dependency_overrides[get_current_user] = override_current_user

    client = TestClient(test_app)
    response = client.put(
        f"/files/{file_id}/content",
        files={
            "upload": (
                "replacement.docx",
                b"fake DOCX content",
                ("application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
            )
        },
    )

    assert response.status_code == 415
    assert response.json() == {"detail": "Replacement file type must match the original file type"}

    fake_replace_upload.assert_not_awaited()
    fake_session.add.assert_not_called()
    fake_session.commit.assert_not_awaited()


def test_replace_file_content_returns_404_when_file_not_found(monkeypatch):
    test_app = FastAPI()
    test_app.include_router(files_router, prefix="/files")

    user_id = uuid4()
    file_id = uuid4()

    query_result = Mock()
    query_result.first.return_value = None

    fake_session = AsyncMock()
    fake_session.exec.return_value = query_result
    fake_session.add = Mock()

    fake_replace_upload = AsyncMock()
    monkeypatch.setattr(
        "app.routers.files.replace_upload",
        fake_replace_upload,
    )

    async def override_session():
        return fake_session

    async def override_current_user():
        return {"sub": str(user_id)}

    test_app.dependency_overrides[get_session] = override_session
    test_app.dependency_overrides[get_current_user] = override_current_user

    client = TestClient(test_app)
    response = client.put(
        f"/files/{file_id}/content",
        files={
            "upload": (
                "replacement.pdf",
                b"%PDF-1.4\nnew content",
                "application/pdf",
            )
        },
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "File not found"}

    fake_replace_upload.assert_not_awaited()
    fake_session.add.assert_not_called()
    fake_session.commit.assert_not_awaited()


def test_replace_file_content_returns_413_when_upload_is_too_large(
    monkeypatch,
):
    test_app = FastAPI()
    test_app.include_router(files_router, prefix="/files")

    user_id = uuid4()
    course_id = uuid4()
    folder_id = uuid4()
    file_id = uuid4()

    original_file = FileRow(
        id=file_id,
        course_id=course_id,
        folder_id=folder_id,
        filename="lecture.pdf",
        storage_key=f"{user_id}/{file_id}.pdf",
        sha256="old-sha256",
        mime_type="application/pdf",
        size_bytes=100,
        page_count=10,
        status=FileStatus.READY,
        error_message=None,
        uploaded_at=datetime.now(UTC),
        indexed_at=datetime.now(UTC),
    )

    query_result = Mock()
    query_result.first.return_value = original_file

    fake_session = AsyncMock()
    fake_session.exec.return_value = query_result
    fake_session.add = Mock()

    fake_replace_upload = AsyncMock(
        side_effect=UploadTooLargeError("Upload exceeds maximum size"),
    )
    monkeypatch.setattr(
        "app.routers.files.replace_upload",
        fake_replace_upload,
    )

    async def override_session():
        return fake_session

    async def override_current_user():
        return {"sub": str(user_id)}

    test_app.dependency_overrides[get_session] = override_session
    test_app.dependency_overrides[get_current_user] = override_current_user

    client = TestClient(test_app)
    response = client.put(
        f"/files/{file_id}/content",
        files={
            "upload": (
                "replacement.pdf",
                b"x" * 4096,
                "application/pdf",
            )
        },
    )

    assert response.status_code == 413
    assert response.json() == {"detail": "Upload exceeds maximum size"}

    fake_replace_upload.assert_awaited_once()
    fake_session.add.assert_not_called()
    fake_session.commit.assert_not_awaited()

    assert original_file.sha256 == "old-sha256"
    assert original_file.size_bytes == 100
    assert original_file.status == FileStatus.READY
