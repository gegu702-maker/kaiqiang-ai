from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.api import avatar, billing
from app.core import supabase as supabase_core


SECRET_KEY = "sb_secret_test_value"
LEGACY_KEY = "header.payload.signature"


def _configure(monkeypatch, key: str) -> None:
    monkeypatch.setattr(supabase_core.settings, "supabase_url", "https://preview.example.supabase.co")
    monkeypatch.setattr(supabase_core.settings, "supabase_service_role_key", key)


def test_opaque_secret_initializes_without_bearer_misuse(monkeypatch):
    _configure(monkeypatch, SECRET_KEY)

    client = supabase_core.get_supabase()

    assert client.options.headers["apiKey"] == SECRET_KEY
    assert SECRET_KEY not in client.options.headers.get("Authorization", "")
    assert SECRET_KEY not in client.auth._headers.get("Authorization", "")
    assert SECRET_KEY not in client.postgrest.session.headers.get("Authorization", "")


def test_opaque_secret_and_user_jwt_use_separate_headers():
    observed = []

    def handle_request(request):
        observed.append(request)
        if request.url.path.startswith("/auth/v1/user"):
            return httpx.Response(
                200,
                json={
                    "id": "00000000-0000-0000-0000-000000000001",
                    "aud": "authenticated",
                    "role": "authenticated",
                    "email": "preview-user@example.invalid",
                    "app_metadata": {},
                    "user_metadata": {},
                    "created_at": "2026-01-01T00:00:00Z",
                    "updated_at": "2026-01-01T00:00:00Z",
                },
            )
        return httpx.Response(200, json=[])

    options = supabase_core._client_options_for_key(SECRET_KEY)
    assert options is not None
    options.httpx_client = httpx.Client(transport=httpx.MockTransport(handle_request))
    client = supabase_core.create_client(
        "https://preview.example.supabase.co",
        SECRET_KEY,
        options,
    )

    data_result = client.table("profiles").select("id").limit(1).execute()
    user_result = client.auth.get_user("user.jwt.token")

    assert data_result.data == []
    assert user_result.user is not None
    assert observed[0].headers["apikey"] == SECRET_KEY
    assert SECRET_KEY not in observed[0].headers.get("Authorization", "")
    assert observed[1].headers["apikey"] == SECRET_KEY
    assert observed[1].headers["Authorization"] == "Bearer user.jwt.token"
    assert SECRET_KEY not in observed[1].headers["Authorization"]


def test_legacy_service_role_jwt_keeps_existing_header_behavior(monkeypatch):
    _configure(monkeypatch, LEGACY_KEY)

    client = supabase_core.get_supabase()

    assert client.options.headers["apiKey"] == LEGACY_KEY
    assert client.options.headers["Authorization"] == f"Bearer {LEGACY_KEY}"


@pytest.mark.parametrize(
    "key",
    ["", "not-a-supported-key", "sb_secret_", "sb_publishable_test_value"],
)
def test_invalid_key_fails_closed_without_exposure(monkeypatch, key):
    _configure(monkeypatch, key)

    with pytest.raises(HTTPException) as exc_info:
        supabase_core.get_supabase()

    assert exc_info.value.status_code == 500
    if key:
        assert key not in str(exc_info.value.detail)


def test_initialization_error_is_generic_and_does_not_expose_secret(monkeypatch):
    _configure(monkeypatch, SECRET_KEY)

    def fail_create_client(*_args, **_kwargs):
        raise RuntimeError(f"client failed for {SECRET_KEY}")

    monkeypatch.setattr(supabase_core, "create_client", fail_create_client)
    with pytest.raises(HTTPException) as exc_info:
        supabase_core.get_supabase()

    assert exc_info.value.status_code == 500
    assert exc_info.value.detail == "Supabase client initialization failed."
    assert SECRET_KEY not in exc_info.value.detail


class _Query:
    def __init__(self, client, table_name):
        self.client = client
        self.table_name = table_name

    def select(self, *_args, **_kwargs):
        self.client.operations.append(("select", self.table_name))
        return self

    def eq(self, *_args, **_kwargs):
        return self

    def is_(self, *_args, **_kwargs):
        return self

    def order(self, *_args, **_kwargs):
        return self

    def limit(self, *_args, **_kwargs):
        return self

    def execute(self):
        if self.client.fail_table == self.table_name:
            raise RuntimeError("safe simulated query failure")
        return SimpleNamespace(data=self.client.rows.get(self.table_name, []))


class _Auth:
    def get_user(self, token):
        assert token == "preview-user-token"
        return SimpleNamespace(
            user=SimpleNamespace(id="user-1", email="preview-user@example.invalid")
        )


class _FakeSupabase:
    def __init__(self, *, fail_table=None):
        self.auth = _Auth()
        self.fail_table = fail_table
        self.operations = []
        self.rows = {
            "avatar_tasks": [],
            "profiles": [
                {
                    "id": "user-1",
                    "email": "preview-user@example.invalid",
                    "plan": "free",
                    "monthly_quota": 3,
                    "custom_quota": None,
                    "voice_clone_enabled": False,
                    "default_voice_id": None,
                    "status": "active",
                }
            ],
            "subscriptions": [{"id": "subscription-1"}],
            "user_quotas": [
                {
                    "id": "quota-1",
                    "plan": "free",
                    "monthly_limit": 3,
                    "used_count": 0,
                    "remaining_count": 3,
                }
            ],
            "plans": [{"code": "free", "monthly_quota": 3, "voice_clone_enabled": False}],
        }

    def table(self, table_name):
        return _Query(self, table_name)


def _api_client(monkeypatch, *, fail_table=None):
    _configure(monkeypatch, SECRET_KEY)
    fake = _FakeSupabase(fail_table=fail_table)

    def fake_create_client(url, key, options=None):
        assert url == "https://preview.example.supabase.co"
        assert key == SECRET_KEY
        assert options is not None
        assert options.headers["Authorization"] == ""
        return fake

    monkeypatch.setattr(supabase_core, "create_client", fake_create_client)
    app = FastAPI()
    app.include_router(avatar.router, prefix="/api")
    app.include_router(billing.router, prefix="/api")
    return TestClient(app, raise_server_exceptions=False), fake


def test_avatar_tasks_uses_opaque_secret_dependency_read_only(monkeypatch):
    client, fake = _api_client(monkeypatch)

    response = client.get(
        "/api/avatar/tasks",
        headers={"Authorization": "Bearer preview-user-token"},
    )

    assert response.status_code == 200
    assert response.json() == []
    assert fake.operations == [("select", "avatar_tasks")]


def test_billing_usage_uses_opaque_secret_dependency_read_only(monkeypatch):
    client, fake = _api_client(monkeypatch)

    response = client.get(
        "/api/billing/usage",
        headers={"Authorization": "Bearer preview-user-token"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "plan": "free",
        "monthly_quota": 3,
        "used": 0,
        "remaining": 3,
        "period_start": response.json()["period_start"],
        "voice_clone_enabled": False,
        "default_voice_id": None,
    }
    assert all(operation == "select" for operation, _table in fake.operations)


@pytest.mark.parametrize("path", ["/api/avatar/tasks", "/api/billing/usage"])
def test_authenticated_query_failure_remains_500_without_secret(monkeypatch, path):
    fail_table = "avatar_tasks" if path.endswith("tasks") else "profiles"
    client, _fake = _api_client(monkeypatch, fail_table=fail_table)

    response = client.get(
        path,
        headers={"Authorization": "Bearer preview-user-token"},
    )

    assert response.status_code == 500
    assert SECRET_KEY not in response.text


@pytest.mark.parametrize("path", ["/api/avatar/tasks", "/api/billing/usage"])
def test_unauthenticated_requests_remain_rejected(monkeypatch, path):
    client, fake = _api_client(monkeypatch)

    response = client.get(path)

    assert response.status_code == 401
    assert fake.operations == []
