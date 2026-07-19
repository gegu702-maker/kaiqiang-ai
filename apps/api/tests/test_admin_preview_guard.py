from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import admin


ADMIN_KEY = "preview-admin-key"
LEGACY_ADMIN_TASK_ROUTES = [
    ("GET", "/api/admin/tasks"),
    ("GET", "/api/admin/tasks/task-1"),
    ("PATCH", "/api/admin/tasks/task-1"),
    ("GET", "/api/admin/tasks/task-1/logs"),
    ("POST", "/api/admin/tasks/task-1/retry"),
]


def _client(monkeypatch, *, environment: str) -> tuple[TestClient, FastAPI]:
    monkeypatch.setattr(admin.settings, "admin_api_key", ADMIN_KEY)
    monkeypatch.setattr(admin.settings, "app_environment", environment)
    app = FastAPI()
    app.include_router(admin.router, prefix="/api/admin")
    return TestClient(app, raise_server_exceptions=False), app


def _video_task() -> dict:
    return {
        "id": "task-1",
        "user_email": "preview-admin@example.com",
        "product_name": "Preview task",
        "script": "Preview script",
        "language": "zh",
        "image_url": "https://example.invalid/image.png",
        "avatar_id": "sophia",
        "voice_url": "https://example.invalid/voice.wav",
        "tts_language": "zh",
        "tts_voice_name": "zh_female_default",
        "status": "completed",
        "created_at": "2026-07-15T00:00:00Z",
    }


def test_preview_valid_admin_fails_closed_before_database_storage_or_retry(monkeypatch):
    client, _ = _client(monkeypatch, environment="preview")
    reached: list[str] = []

    def forbidden(name: str):
        def fail(*args, **kwargs):
            reached.append(name)
            raise AssertionError(f"{name} must not be reached in Preview")

        return fail

    monkeypatch.setattr(admin, "get_supabase", forbidden("database"))
    monkeypatch.setattr(admin, "list_all_tasks", forbidden("video_tasks"))
    monkeypatch.setattr(admin, "get_task", forbidden("video_tasks"))
    monkeypatch.setattr(admin, "update_task", forbidden("video_tasks"))
    monkeypatch.setattr(admin, "upload_public_file", forbidden("storage"))
    monkeypatch.setattr(admin, "upload_public_bytes", forbidden("storage"))

    for method, path in LEGACY_ADMIN_TASK_ROUTES:
        response = client.request(method, path, headers={"X-Admin-Key": ADMIN_KEY})
        assert response.status_code == 409
        assert response.json() == {
            "detail": {
                "code": "preview_legacy_video_tasks_disabled",
                "message": "Legacy video-task administration is disabled in the isolated Preview environment.",
            }
        }
        safe_body = response.text.lower()
        assert "pgrst205" not in safe_body
        assert "does not exist" not in safe_body
        assert "supabase" not in safe_body
        assert ADMIN_KEY not in response.text

    assert reached == []


@pytest.mark.parametrize(("method", "path"), LEGACY_ADMIN_TASK_ROUTES)
def test_preview_invalid_admin_key_still_returns_401(monkeypatch, method, path):
    client, _ = _client(monkeypatch, environment="preview")

    response = client.request(method, path, headers={"X-Admin-Key": "invalid"})

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid admin key"}


@pytest.mark.parametrize(("method", "path"), LEGACY_ADMIN_TASK_ROUTES)
def test_preview_missing_admin_key_preserves_required_header_error(monkeypatch, method, path):
    client, _ = _client(monkeypatch, environment="preview")

    response = client.request(method, path)

    assert response.status_code == 422
    assert "preview_legacy_video_tasks_disabled" not in response.text


class _FakeQuery:
    def __init__(self, operations: list[tuple[str, str]], table: str):
        self.operations = operations
        self.table = table
        self.operation = "table"

    def select(self, *args, **kwargs):
        self.operation = "select"
        return self

    def update(self, *args, **kwargs):
        self.operation = "update"
        return self

    def insert(self, *args, **kwargs):
        self.operation = "insert"
        return self

    def eq(self, *args, **kwargs):
        return self

    def limit(self, *args, **kwargs):
        return self

    def execute(self):
        self.operations.append((self.table, self.operation))
        return SimpleNamespace(data=[])


class _FakeSupabase:
    def __init__(self):
        self.operations: list[tuple[str, str]] = []

    def table(self, name: str) -> _FakeQuery:
        return _FakeQuery(self.operations, name)


def test_non_preview_valid_admin_reaches_existing_list_patch_and_retry_handlers(monkeypatch):
    client, _ = _client(monkeypatch, environment="test")
    fake = _FakeSupabase()
    monkeypatch.setattr(admin, "get_supabase", lambda: fake)
    calls: list[str] = []

    def list_tasks(_supabase):
        calls.append("list")
        return []

    def update_task(_supabase, _task_id, **_kwargs):
        calls.append("patch")
        return _video_task()

    def get_task(_supabase, _task_id):
        calls.append("get")
        return _video_task()

    monkeypatch.setattr(admin, "list_all_tasks", list_tasks)
    monkeypatch.setattr(admin, "update_task", update_task)
    monkeypatch.setattr(admin, "get_task", get_task)

    headers = {"X-Admin-Key": ADMIN_KEY}
    list_response = client.get("/api/admin/tasks", headers=headers)
    patch_response = client.patch("/api/admin/tasks/task-1", headers=headers)
    retry_response = client.post("/api/admin/tasks/task-1/retry", headers=headers)

    assert list_response.status_code == 200
    assert list_response.json() == []
    assert patch_response.status_code == 200
    assert retry_response.status_code == 200
    assert calls == ["list", "patch", "get", "get"]
    assert ("video_tasks", "update") in fake.operations
    assert ("task_queue", "select") in fake.operations
    assert ("task_queue", "insert") in fake.operations
