from __future__ import annotations

from fastapi.testclient import TestClient
import pytest

import app.main as main_module


class RunningTask:
    def done(self) -> bool:
        return False


def test_preview_readiness_is_public_safe_and_side_effect_free(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(main_module.settings, "app_environment", "preview")
    monkeypatch.setattr(main_module.settings, "viral_async_jobs_enabled", True)
    monkeypatch.setattr(main_module.settings, "enable_task_worker", True)
    monkeypatch.setattr(
        main_module,
        "background_tasks",
        {
            "task-worker": RunningTask(),
            "viral-job-worker": RunningTask(),
            "autodl-idle-shutdown": RunningTask(),
        },
    )
    monkeypatch.setenv("RAILWAY_DEPLOYMENT_ID", "deployment-safe")
    monkeypatch.setenv("RAILWAY_GIT_COMMIT_SHA", "commit-safe")
    monkeypatch.setenv("RAILWAY_SERVICE_NAME", "preview-api")

    response = TestClient(main_module.app).get("/api/diagnostics/preview-readiness")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["deployment"] == {
        "id": "deployment-safe",
        "commit_sha": "commit-safe",
        "service": "preview-api",
    }
    assert payload["async_jobs_enabled"] is True
    serialized = response.text.lower()
    for forbidden in ("service_role", "sb_secret_", "authorization", "token", "cookie", "user_id"):
        assert forbidden not in serialized


def test_preview_readiness_reports_stopped_worker(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(main_module.settings, "app_environment", "preview")
    monkeypatch.setattr(main_module.settings, "viral_async_jobs_enabled", True)
    monkeypatch.setattr(main_module.settings, "enable_task_worker", False)
    monkeypatch.setattr(main_module, "background_tasks", {"autodl-idle-shutdown": RunningTask()})

    response = TestClient(main_module.app).get("/api/diagnostics/preview-readiness")

    assert response.status_code == 200
    assert response.json()["status"] == "degraded"
    assert response.json()["background_tasks"]["viral-job-worker"] == "stopped"


def test_preview_readiness_is_not_exposed_outside_preview(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(main_module.settings, "app_environment", "production")
    response = TestClient(main_module.app).get("/api/diagnostics/preview-readiness")
    assert response.status_code == 404
