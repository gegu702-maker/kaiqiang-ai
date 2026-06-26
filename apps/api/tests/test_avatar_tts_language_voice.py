import asyncio

import pytest
from fastapi import HTTPException
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import avatar
from app.core.auth import get_bearer_token
from app.core.supabase import get_supabase
from app.services import tts


def test_default_language_preserves_current_voice_validation_behavior():
    assert avatar._normalize_tts_language(None) is None
    assert avatar._normalize_tts_language("") is None


def test_zh_cn_allows_confirmed_template_voices():
    avatar._validate_template_tts_voice("zh-CN", "BV001_streaming")
    avatar._validate_template_tts_voice("zh-CN", "BV002_streaming")


def test_unsupported_language_returns_clear_error():
    with pytest.raises(HTTPException) as error:
        avatar._normalize_tts_language("fr-FR")

    assert error.value.status_code == 400
    assert "Unsupported TTS language" in str(error.value.detail)


def test_en_us_without_configured_voice_returns_clear_error(monkeypatch):
    monkeypatch.setattr(avatar.settings, "volcengine_tts_en_us_female_voice_type", "")
    monkeypatch.setattr(avatar.settings, "volcengine_tts_en_us_male_voice_type", "")

    with pytest.raises(HTTPException) as error:
        avatar._validate_template_tts_voice("en-US", "BV001_streaming")

    assert error.value.status_code == 400
    assert "English TTS voices are not configured yet" in str(error.value.detail)


def test_synthesize_speech_passes_language_and_audio_controls(monkeypatch):
    captured = {}

    class FakeVolcengineTTSProvider:
        async def synthesize(self, **kwargs):
            captured.update(kwargs)
            return {
                "audio_bytes": b"fake-mp3",
                "extension": ".mp3",
                "content_type": "audio/mpeg",
                "provider": "volcengine",
                "language": kwargs.get("language"),
                "voice_type": kwargs.get("voice_type"),
            }

    monkeypatch.setattr(tts.settings, "voice_clone_provider", "volcengine")
    monkeypatch.setattr(tts, "VolcengineTTSProvider", FakeVolcengineTTSProvider)
    monkeypatch.setattr(tts, "upload_public_bytes", lambda *_args, **_kwargs: "https://storage.example/audio.mp3")
    monkeypatch.setattr(tts, "probe_audio_duration", lambda _audio: 1.23)

    result = asyncio.run(
        tts.synthesize_speech_to_storage(
            object(),
            text="你好",
            folder="avatar/template-generate/tts",
            language="zh-CN",
            voice_type="BV001_streaming",
            speed_ratio=0.9,
            volume_ratio=0.8,
            pitch_ratio=1.1,
        )
    )

    assert captured == {
        "text": "你好",
        "language": "zh-CN",
        "voice_type": "BV001_streaming",
        "speed_ratio": 0.9,
        "volume_ratio": 0.8,
        "pitch_ratio": 1.1,
    }
    assert result["language"] == "zh-CN"
    assert result["voice_type"] == "BV001_streaming"
    assert result["audio_url"] == "https://storage.example/audio.mp3"


def test_tts_preview_speed_out_of_range_returns_400(monkeypatch):
    app = FastAPI()
    app.include_router(avatar.router, prefix="/api")
    client = TestClient(app)

    app.dependency_overrides[get_bearer_token] = lambda: "test-token"
    app.dependency_overrides[get_supabase] = lambda: object()
    monkeypatch.setattr(avatar, "get_authenticated_user", lambda *_args, **_kwargs: {"id": "user-1", "email": "test@example.com"})

    for speed in (0.4, 2.1):
        response = client.post(
            "/api/avatar/tts-preview",
            json={"text": "hello", "language": "zh-CN", "voice": "BV001_streaming", "speed": speed},
        )
        assert response.status_code == 400
        assert response.json()["detail"] == "speed must be between 0.5 and 2.0"

    app.dependency_overrides.clear()
