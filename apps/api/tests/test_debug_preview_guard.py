from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import debug


PREVIEW_DISABLED_RESPONSE = {
    "detail": {
        "code": "preview_debug_route_disabled",
        "message": "This debug route is disabled in the Preview environment.",
    }
}

PREVIEW_ROUTES = [
    ("GET", "/debug/supabase", None),
    ("GET", "/debug/config", None),
    ("POST", "/api/debug/avatar-video-test", {}),
    ("POST", "/api/debug/musetalk-test", None),
    ("POST", "/api/debug/liveportrait-test", {}),
]


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(debug.router)
    return TestClient(app)


@pytest.mark.parametrize(("method", "path", "payload"), PREVIEW_ROUTES)
def test_preview_debug_routes_fail_before_every_side_effect(monkeypatch, method, path, payload):
    calls: list[str] = []

    def forbidden(name):
        def fail(*_args, **_kwargs):
            calls.append(name)
            raise AssertionError(f"Preview debug guard allowed side effect: {name}")

        return fail

    def forbidden_async(name):
        async def fail(*_args, **_kwargs):
            calls.append(name)
            raise AssertionError(f"Preview debug guard allowed side effect: {name}")

        return fail

    monkeypatch.setattr(debug.settings, "app_environment", "preview")
    monkeypatch.setattr(debug, "get_supabase", forbidden("supabase/database/storage"))
    monkeypatch.setattr(debug, "get_avatar_template", forbidden("template/file"))
    monkeypatch.setattr(debug, "get_avatar_motion_provider", forbidden("liveportrait/replicate"))
    monkeypatch.setattr(debug, "upload_public_bytes", forbidden("storage upload"))
    monkeypatch.setattr(debug.httpx, "AsyncClient", forbidden("external http"))
    monkeypatch.setattr(debug, "synthesize_speech_to_storage", forbidden_async("tts"))
    monkeypatch.setattr(debug, "render_static_avatar_video", forbidden_async("ffmpeg"))
    monkeypatch.setattr(debug, "package_dynamic_avatar_video", forbidden_async("ffmpeg/package"))
    monkeypatch.setattr(debug, "_debug_musetalk_with_autodl_sample_audio", forbidden_async("musetalk/gpu"))

    request_kwargs = {"json": payload} if payload is not None else {}
    response = _client().request(method, path, **request_kwargs)

    assert response.status_code == 409
    assert response.json() == PREVIEW_DISABLED_RESPONSE
    assert calls == []


class NonPreviewHandlerReached(Exception):
    pass


@pytest.mark.parametrize(
    ("method", "path", "payload", "first_dependency"),
    [
        ("GET", "/debug/supabase", None, "get_supabase"),
        ("POST", "/api/debug/avatar-video-test", {}, "get_avatar_template"),
        ("POST", "/api/debug/musetalk-test", None, "get_supabase"),
        ("POST", "/api/debug/liveportrait-test", {}, "get_avatar_template"),
    ],
)
def test_non_preview_guard_allows_existing_handlers(monkeypatch, method, path, payload, first_dependency):
    monkeypatch.setattr(debug.settings, "app_environment", "development")

    def reached(*_args, **_kwargs):
        raise NonPreviewHandlerReached

    monkeypatch.setattr(debug, first_dependency, reached)
    request_kwargs = {"json": payload} if payload is not None else {}

    with pytest.raises(NonPreviewHandlerReached):
        _client().request(method, path, **request_kwargs)


def test_non_preview_debug_config_preserves_existing_response(monkeypatch):
    class ConfigSettings:
        app_environment = "development"

        @property
        def admin_api_key(self):
            raise NonPreviewHandlerReached

    monkeypatch.setattr(debug, "settings", ConfigSettings())

    with pytest.raises(NonPreviewHandlerReached):
        _client().get("/debug/config")


def test_web_preview_debug_guard_is_before_body_and_backend_fetch():
    web_root = Path(__file__).resolve().parents[2] / "web"
    helper = (web_root / "lib" / "previewDebugRoutes.ts").read_text(encoding="utf-8")
    assert 'code: "preview_debug_route_disabled"' in helper
    assert 'message: "This debug route is disabled in the Preview environment."' in helper
    assert 'toLowerCase() === "preview"' in helper

    for route in ("tts-test", "avatar-video-test", "liveportrait-test"):
        source = (web_root / "app" / "api" / "debug" / route / "route.ts").read_text(encoding="utf-8")
        guard_position = source.index("if (previewDebugRoutesDisabled())")
        body_position = source.index("request.json()")
        fetch_position = source.index("fetch(")
        assert guard_position < body_position
        assert guard_position < fetch_position
        assert "PREVIEW_DEBUG_ROUTE_DISABLED_DETAIL" in source
        assert "{ status: 409 }" in source
