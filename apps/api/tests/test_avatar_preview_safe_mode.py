import asyncio

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.api import avatar
from app.core.auth import get_bearer_token
from app.core.config import Settings
from app.core.supabase import get_supabase


def test_production_cannot_enable_preview_safe_mode():
    with pytest.raises(ValidationError, match="AVATAR_PREVIEW_SAFE_MODE cannot be enabled in production"):
        Settings(app_environment="production", avatar_preview_safe_mode=True, _env_file=None)


def test_preview_can_enable_safe_mode_and_normalizes_environment():
    configured = Settings(app_environment=" Preview ", avatar_preview_safe_mode=True, _env_file=None)
    assert configured.app_environment == "preview"
    assert configured.avatar_preview_safe_mode is True


def test_development_defaults_to_safe_mode_off():
    configured = Settings(_env_file=None)
    assert configured.app_environment == "development"
    assert configured.avatar_preview_safe_mode is False


def test_preview_with_safe_mode_false_uses_normal_flow(monkeypatch):
    monkeypatch.setattr(avatar.settings, "app_environment", "preview")
    monkeypatch.setattr(avatar.settings, "avatar_preview_safe_mode", False)
    assert avatar._preview_safe_mode_enabled() is False


def _client(monkeypatch, *, safe_mode=True):
    app = FastAPI()
    app.include_router(avatar.router, prefix="/api")
    app.dependency_overrides[get_bearer_token] = lambda: "test-token"
    app.dependency_overrides[get_supabase] = lambda: object()
    monkeypatch.setattr(avatar.settings, "app_environment", "preview")
    monkeypatch.setattr(avatar.settings, "avatar_preview_safe_mode", safe_mode)
    monkeypatch.setattr(avatar, "get_authenticated_user", lambda *_args: {"id": "user-1", "email": "preview@example.com"})
    monkeypatch.setattr(avatar, "assert_generation_quota", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(avatar, "get_dynamic_template_video_url", lambda _template_id: "https://preview.example/template.mp4")
    return TestClient(app)


def test_safe_mode_tts_success_stops_before_task_or_gpu(monkeypatch):
    calls = {"task": 0, "process": 0, "gpu": 0, "musetalk": 0, "usage": 0}

    async def fake_tts(*_args, **kwargs):
        assert kwargs["folder"] == "preview-tts/user-1"
        return {
            "audio_url": "https://preview-storage.example/voice.mp3",
            "voice": "zh_female_default",
            "language": "zh-CN",
            "duration": 1.2,
        }

    monkeypatch.setattr(avatar, "synthesize_speech_to_storage", fake_tts)
    monkeypatch.setattr(avatar, "_create_avatar_task", lambda *_args, **_kwargs: calls.__setitem__("task", calls["task"] + 1))

    async def fake_process(*_args, **_kwargs):
        calls["process"] += 1

    async def fake_gpu(*_args, **_kwargs):
        calls["gpu"] += 1

    async def fake_musetalk(*_args, **_kwargs):
        calls["musetalk"] += 1

    monkeypatch.setattr(avatar, "_process_avatar_task", fake_process)
    monkeypatch.setattr(avatar, "ensure_gpu_ready", fake_gpu)
    monkeypatch.setattr(avatar, "generate_avatar_video_with_musetalk", fake_musetalk)
    monkeypatch.setattr(avatar, "log_generation_usage", lambda *_args, **_kwargs: calls.__setitem__("usage", calls["usage"] + 1))

    response = _client(monkeypatch).post(
        "/api/avatar/template-generate",
        headers={"Authorization": "Bearer test-token"},
        json={
            "avatar_template_id": "business_female_01",
            "script_text": "预览文案",
            "language": "zh-CN",
            "voice": "zh_female_default",
            "speed_ratio": 1.0,
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "preview_safe_mode": True,
        "status": "tts_ready",
        "voice": "zh_female_default",
        "language": "zh-CN",
        "audio_url": "https://preview-storage.example/voice.mp3",
        "task_id": None,
        "video_url": None,
        "message": "预览配音已生成，未创建视频任务。",
    }
    assert calls == {"task": 0, "process": 0, "gpu": 0, "musetalk": 0, "usage": 0}


@pytest.mark.parametrize(
    ("payload", "status"),
    [
        ({"voice": "BV001_streaming", "language": "zh-CN"}, 422),
        ({"voice": "zh_female_default", "language": "en-US"}, 422),
    ],
)
def test_safe_mode_preserves_voice_validation_errors(monkeypatch, payload, status):
    async def validating_tts(*_args, **kwargs):
        from app.services.tts.voice_registry import resolve_voice

        resolve_voice(kwargs["voice_type"], kwargs["language"])

    monkeypatch.setattr(avatar, "synthesize_speech_to_storage", validating_tts)
    response = _client(monkeypatch).post(
        "/api/avatar/template-generate",
        headers={"Authorization": "Bearer test-token"},
        json={"avatar_template_id": "business_female_01", "script_text": "预览文案", **payload},
    )
    assert response.status_code == status


@pytest.mark.parametrize("status", [502, 503])
def test_safe_mode_preserves_stable_tts_errors(monkeypatch, status):
    detail = "配音服务暂时不可用，请稍后重试。" if status == 502 else "配音服务尚未完成配置。"

    async def fail_tts(*_args, **_kwargs):
        raise HTTPException(status_code=status, detail=detail)

    monkeypatch.setattr(avatar, "synthesize_speech_to_storage", fail_tts)
    response = _client(monkeypatch).post(
        "/api/avatar/template-generate",
        headers={"Authorization": "Bearer test-token"},
        json={
            "avatar_template_id": "business_female_01",
            "script_text": "预览文案",
            "language": "zh-CN",
            "voice": "zh_female_default",
        },
    )
    assert response.status_code == status
    assert response.json()["detail"] == detail
    for internal_word in ("AutoDL", "GPU", "MuseTalk", "Supabase", "Volcengine", "BV001_streaming"):
        assert internal_word not in str(response.json())


def test_safe_mode_rejects_existing_audio_before_task(monkeypatch):
    calls = {"task": 0, "tts": 0}

    async def fake_tts(*_args, **_kwargs):
        calls["tts"] += 1

    monkeypatch.setattr(avatar, "synthesize_speech_to_storage", fake_tts)
    monkeypatch.setattr(avatar, "_create_avatar_task", lambda *_args, **_kwargs: calls.__setitem__("task", calls["task"] + 1))
    response = _client(monkeypatch).post(
        "/api/avatar/template-generate",
        headers={"Authorization": "Bearer test-token"},
        json={"avatar_template_id": "business_female_01", "audio_url": "https://preview.example/existing.mp3"},
    )
    assert response.status_code == 409
    assert response.json()["detail"] == "预览安全模式暂不支持视频生成。"
    assert calls == {"task": 0, "tts": 0}


def test_safe_mode_rejects_custom_video_before_storage(monkeypatch):
    calls = {"storage": 0, "task": 0, "gpu": 0}

    async def fake_upload(*_args, **_kwargs):
        calls["storage"] += 1

    async def fake_gpu(*_args, **_kwargs):
        calls["gpu"] += 1

    monkeypatch.setattr(avatar, "upload_public_file", fake_upload)
    monkeypatch.setattr(avatar, "_create_avatar_task", lambda *_args, **_kwargs: calls.__setitem__("task", calls["task"] + 1))
    monkeypatch.setattr(avatar, "ensure_gpu_ready", fake_gpu)
    response = _client(monkeypatch).post(
        "/api/avatar/generate",
        headers={"Authorization": "Bearer test-token"},
        files={"video_file": ("preview.mp4", b"fake-video", "video/mp4")},
        data={"script_text": "预览文案", "voice": "zh_female_default"},
    )
    assert response.status_code == 409
    assert response.json()["detail"] == "预览安全模式暂不支持视频生成。"
    assert calls == {"storage": 0, "task": 0, "gpu": 0}


def test_background_guard_prevents_all_external_work(monkeypatch):
    calls = {"supabase": 0, "gpu": 0, "musetalk": 0}
    monkeypatch.setattr(avatar.settings, "app_environment", "preview")
    monkeypatch.setattr(avatar.settings, "avatar_preview_safe_mode", True)
    monkeypatch.setattr(avatar, "get_supabase", lambda: calls.__setitem__("supabase", calls["supabase"] + 1))

    async def fake_gpu(*_args, **_kwargs):
        calls["gpu"] += 1

    async def fake_musetalk(*_args, **_kwargs):
        calls["musetalk"] += 1

    monkeypatch.setattr(avatar, "ensure_gpu_ready", fake_gpu)
    monkeypatch.setattr(avatar, "generate_avatar_video_with_musetalk", fake_musetalk)
    with pytest.raises(RuntimeError, match="disabled in preview safe mode"):
        asyncio.run(avatar._process_avatar_task("task-1", "user-1", "video", "audio"))
    assert calls == {"supabase": 0, "gpu": 0, "musetalk": 0}


def test_health_does_not_call_musetalk_in_safe_mode(monkeypatch):
    calls = {"health": 0}

    async def fake_health():
        calls["health"] += 1

    monkeypatch.setattr(avatar, "check_musetalk_health", fake_health)
    response = _client(monkeypatch).get("/api/avatar/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "video_generation": {"status": "disabled"}}
    assert calls["health"] == 0
