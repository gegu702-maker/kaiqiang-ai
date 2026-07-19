import asyncio

import pytest
from fastapi import HTTPException
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.api import avatar
from app.api.avatar import TemplateAvatarGenerateRequest
from app.core.auth import get_bearer_token
from app.core.supabase import get_supabase
from app.services import tts
from app.services.tts import voice_registry
from app.services.tts import volcengine_tts

NEW_VOICES = [
    ("zh_dongbei_laotie", "zh-CN", "volcengine_voice_zh_dongbei_laotie", "BV021_streaming"),
    ("en_energetic_male_jackson", "en-US", "volcengine_voice_en_energetic_male_jackson", "BV504_streaming"),
    ("zh_gentle_young_man", "zh-CN", "volcengine_voice_zh_gentle_young_man", "BV033_streaming"),
    ("zh_refined_youth", "zh-CN", "volcengine_voice_zh_refined_youth", "BV102_streaming"),
    ("en_energetic_female_ariana", "en-US", "volcengine_voice_en_energetic_female_ariana", "BV503_streaming"),
    ("ja_male", "ja-JP", "volcengine_voice_ja_male", "BV524_streaming"),
    ("ja_elegant_female", "ja-JP", "volcengine_voice_ja_elegant_female", "BV522_streaming"),
    ("zh_sunny_male", "zh-CN", "volcengine_voice_zh_sunny_male", "BV056_streaming"),
    ("zh_intellectual_female_bilingual", "zh-CN", "volcengine_voice_zh_intellectual_female_bilingual", "BV034_streaming"),
    ("zh_friendly_female", "zh-CN", "volcengine_voice_zh_friendly_female", "BV007_streaming"),
    ("zh_guangxi_cousin", "zh-CN", "volcengine_voice_zh_guangxi_cousin", "BV213_streaming"),
    ("zh_lively_female", "zh-CN", "volcengine_voice_zh_lively_female", "BV005_streaming"),
]


@pytest.fixture(autouse=True)
def empty_voice_configuration(monkeypatch):
    monkeypatch.setattr(voice_registry.settings, "volcengine_default_voice_key", "zh_female_default")
    monkeypatch.setattr(voice_registry.settings, "volcengine_tts_voice_type", "")
    for setting_name in voice_registry.VOICE_SETTING_MAP.values():
        monkeypatch.setattr(voice_registry.settings, setting_name, "")


def test_default_business_key_resolves(monkeypatch):
    monkeypatch.setattr(voice_registry.settings, "volcengine_voice_zh_female_default", "provider-default")
    result = voice_registry.resolve_voice(None, "zh-CN")
    assert result.requested_key == "zh_female_default"
    assert result.resolved_key == "zh_female_default"
    assert result.provider_voice_id == "provider-default"
    assert result.used_fallback is False


def test_configured_business_key_resolves(monkeypatch):
    monkeypatch.setattr(voice_registry.settings, "volcengine_voice_zh_male_default", "BV002_streaming")
    result = voice_registry.resolve_voice("zh_male_default", "zh-CN")
    assert result.requested_key == "zh_male_default"
    assert result.resolved_key == "zh_male_default"
    assert result.provider_voice_id == "BV002_streaming"
    assert result.used_fallback is False


def test_unconfigured_male_voice_fails_without_female_fallback(monkeypatch):
    monkeypatch.setattr(voice_registry.settings, "volcengine_voice_zh_female_default", "BV001_streaming")
    with pytest.raises(HTTPException) as error:
        voice_registry.resolve_voice("zh_male_default", "zh-CN")
    assert error.value.status_code == 503
    assert error.value.detail == "所选音色暂未配置，请选择其他音色。"


def test_unconfigured_key_falls_back_to_default(monkeypatch):
    monkeypatch.setattr(voice_registry.settings, "volcengine_voice_zh_female_default", "provider-default")
    result = voice_registry.resolve_voice("zh_warm_female", "zh-CN")
    assert result.resolved_key == "zh_female_default"
    assert result.provider_voice_id == "provider-default"
    assert result.used_fallback is True


@pytest.mark.parametrize("value", ["random", "BV001_streaming", "../../voice"])
def test_unknown_or_provider_voice_is_rejected(value):
    with pytest.raises(HTTPException) as error:
        voice_registry.resolve_voice(value, "zh-CN")
    assert error.value.status_code == 422


def test_language_and_voice_mismatch_is_rejected():
    with pytest.raises(HTTPException) as error:
        voice_registry.resolve_voice("zh_female_default", "en-US")
    assert error.value.status_code == 422


@pytest.mark.parametrize(("voice_key", "language", "setting_name", "provider_voice"), NEW_VOICES)
def test_new_voice_registry_resolves_exact_provider_voice(monkeypatch, voice_key, language, setting_name, provider_voice):
    monkeypatch.setattr(voice_registry.settings, setting_name, provider_voice)
    result = voice_registry.resolve_voice(voice_key, language)
    assert result.requested_key == voice_key
    assert result.resolved_key == voice_key
    assert result.provider_voice_id == provider_voice
    assert result.used_fallback is False


@pytest.mark.parametrize(("voice_key", "language", "_setting_name", "_provider_voice"), NEW_VOICES)
def test_unconfigured_new_voice_never_falls_back(monkeypatch, voice_key, language, _setting_name, _provider_voice):
    monkeypatch.setattr(voice_registry.settings, "volcengine_voice_zh_female_default", "BV001_streaming")
    with pytest.raises(HTTPException) as error:
        voice_registry.resolve_voice(voice_key, language)
    assert error.value.status_code == 503


@pytest.mark.parametrize(("voice_key", "language", "_setting_name", "_provider_voice"), NEW_VOICES)
def test_new_voice_rejects_wrong_language(voice_key, language, _setting_name, _provider_voice):
    wrong_language = "ja-JP" if language != "ja-JP" else "en-US"
    with pytest.raises(HTTPException) as error:
        voice_registry.resolve_voice(voice_key, wrong_language)
    assert error.value.status_code == 422


def test_legacy_request_field_accepts_business_key():
    payload = TemplateAvatarGenerateRequest(avatar_template_id="business_female_01", voice_type="zh_female_default")
    assert payload.voice is None
    assert payload.voice_type == "zh_female_default"


def test_male_business_key_is_normalized_without_provider_exposure():
    result = voice_registry.normalize_legacy_voice_request("zh_male_default", None)
    assert result.requested_key == "zh_male_default"
    assert result.legacy_provider_voice_id is None


@pytest.mark.parametrize("legacy_voice", ["BV001_streaming", "BV002_streaming"])
def test_exact_legacy_voice_type_is_temporarily_normalized(legacy_voice):
    result = voice_registry.normalize_legacy_voice_request(None, legacy_voice)
    assert result.requested_key == "zh_female_default"
    assert result.legacy_provider_voice_id == legacy_voice


@pytest.mark.parametrize("public_voice", ["BV001_streaming", "BV002_streaming"])
def test_provider_id_in_public_voice_field_is_rejected(public_voice):
    with pytest.raises(HTTPException) as error:
        voice_registry.normalize_legacy_voice_request(public_voice, None)
    assert error.value.status_code == 422


@pytest.mark.parametrize("legacy_voice", ["BV003_streaming", "random_provider_id"])
def test_unknown_legacy_voice_type_is_rejected_by_resolver(legacy_voice):
    normalized = voice_registry.normalize_legacy_voice_request(None, legacy_voice)
    with pytest.raises(HTTPException) as error:
        voice_registry.resolve_voice(normalized.requested_key, "zh-CN")
    assert error.value.status_code == 422


def test_public_voice_takes_priority_over_legacy_voice_type(monkeypatch):
    monkeypatch.setattr(voice_registry.settings, "volcengine_voice_zh_female_default", "provider-default")
    normalized = voice_registry.normalize_legacy_voice_request("zh_female_default", "BV002_streaming")
    assert normalized.requested_key == "zh_female_default"
    assert normalized.legacy_provider_voice_id is None


def test_invalid_public_voice_cannot_use_legacy_voice_type():
    with pytest.raises(HTTPException) as error:
        voice_registry.normalize_legacy_voice_request("random", "BV001_streaming")
    assert error.value.status_code == 422


@pytest.mark.parametrize("speed", [0.5, 2.0])
def test_speed_boundaries_are_allowed(speed):
    assert TemplateAvatarGenerateRequest(avatar_template_id="business_female_01", speed_ratio=speed).speed_ratio == speed


@pytest.mark.parametrize("speed", [0.49, 2.01])
def test_speed_outside_boundaries_is_rejected(speed):
    with pytest.raises(ValidationError):
        TemplateAvatarGenerateRequest(avatar_template_id="business_female_01", speed_ratio=speed)


def test_legacy_provider_voice_is_last_fallback(monkeypatch):
    monkeypatch.setattr(voice_registry.settings, "volcengine_tts_voice_type", "legacy-provider")
    result = voice_registry.resolve_voice("zh_warm_female", "zh-CN")
    assert result.provider_voice_id == "legacy-provider"
    assert result.used_fallback is True


def test_all_voice_configuration_missing_fails_before_network():
    with pytest.raises(HTTPException) as error:
        voice_registry.resolve_voice("zh_female_default", "zh-CN")
    assert error.value.status_code == 503


@pytest.mark.parametrize(
    ("voice_key", "setting_name", "provider_voice"),
    [
        ("zh_female_default", "volcengine_voice_zh_female_default", "BV001_streaming"),
        ("zh_male_default", "volcengine_voice_zh_male_default", "BV002_streaming"),
        *[(voice_key, setting_name, provider_voice) for voice_key, _language, setting_name, provider_voice in NEW_VOICES],
    ],
)
def test_synthesis_resolves_business_key_without_real_network(monkeypatch, voice_key, setting_name, provider_voice):
    captured = {}

    class FakeVolcengineTTSProvider:
        async def synthesize(self, **kwargs):
            captured.update(kwargs)
            return {
                "audio_bytes": b"fake-mp3",
                "extension": ".mp3",
                "content_type": "audio/mpeg",
                "provider": "volcengine",
                "language": kwargs["language"],
                "voice_type": kwargs["voice_type"],
            }

    monkeypatch.setattr(voice_registry.settings, setting_name, provider_voice)
    monkeypatch.setattr(tts.settings, "voice_clone_provider", "volcengine")
    monkeypatch.setattr(tts, "VolcengineTTSProvider", FakeVolcengineTTSProvider)
    monkeypatch.setattr(tts, "upload_public_bytes", lambda *_args, **_kwargs: "https://storage.example/audio.mp3")
    monkeypatch.setattr(tts, "probe_audio_duration", lambda _audio: 1.23)

    language = voice_registry.VOICE_LANGUAGE_MAP[voice_key]
    result = asyncio.run(
        tts.synthesize_speech_to_storage(
            object(), text="voice test", language=language, voice_type=voice_key, speed_ratio=1.0
        )
    )

    assert captured["voice_type"] == provider_voice
    assert result["voice"] == voice_key
    assert result["used_fallback"] is False
    assert "voice_type" not in result


def test_provider_error_body_is_not_exposed(monkeypatch):
    leaked_body = "BV001_streaming secret-token https://provider.example raw-body"

    class FakeResponse:
        status_code = 400
        text = leaked_body

    class FakeClient:
        def __init__(self, **_kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def post(self, *_args, **_kwargs):
            return FakeResponse()

    monkeypatch.setattr(volcengine_tts.httpx, "AsyncClient", FakeClient)
    provider = volcengine_tts.VolcengineTTSProvider(
        app_id="app", access_token="secret-token", cluster="cluster", endpoint="https://provider.example"
    )

    with pytest.raises(HTTPException) as error:
        asyncio.run(provider.synthesize(text="测试", language="zh-CN", voice_type="BV001_streaming"))

    assert error.value.status_code == 502
    assert error.value.detail == "配音服务暂时不可用，请稍后重试。"
    for secret in ("BV001_streaming", "secret-token", "provider.example", "raw-body"):
        assert secret not in str(error.value.detail)


def test_provider_configuration_error_is_stable_and_hides_env_names():
    provider = volcengine_tts.VolcengineTTSProvider(app_id="", access_token="", cluster="", endpoint="")
    with pytest.raises(HTTPException) as error:
        asyncio.run(provider.synthesize(text="测试", language="zh-CN", voice_type="provider-internal"))
    assert error.value.status_code == 503
    assert error.value.detail == "配音服务尚未完成配置。"
    assert "VOLCENGINE_TTS_ZH_CN_FEMALE_VOICE_TYPE" not in str(error.value.detail)


def test_resolver_failure_does_not_create_task_or_start_gpu(monkeypatch):
    app = FastAPI()
    app.include_router(avatar.router, prefix="/api")
    app.dependency_overrides[get_bearer_token] = lambda: "test-token"
    app.dependency_overrides[get_supabase] = lambda: object()
    calls = {"task": 0, "gpu": 0}

    monkeypatch.setattr(avatar, "get_authenticated_user", lambda *_args: {"id": "user-1", "email": "test@example.com"})
    monkeypatch.setattr(avatar, "assert_generation_quota", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(avatar, "get_dynamic_template_video_url", lambda _template_id: "https://example.com/template.mp4")
    monkeypatch.setattr(avatar, "_create_avatar_task", lambda *_args, **_kwargs: calls.__setitem__("task", calls["task"] + 1))

    async def fake_gpu(*_args, **_kwargs):
        calls["gpu"] += 1

    monkeypatch.setattr(avatar, "ensure_gpu_ready", fake_gpu)

    response = TestClient(app).post(
        "/api/avatar/template-generate",
        headers={"Authorization": "Bearer test-token"},
        json={
            "avatar_template_id": "business_female_01",
            "script_text": "测试文案",
            "language": "zh-CN",
            "voice": "BV001_streaming",
            "speed_ratio": 1.0,
        },
    )

    assert response.status_code == 422
    assert calls == {"task": 0, "gpu": 0}


def test_provider_failure_does_not_create_task_or_start_gpu(monkeypatch):
    app = FastAPI()
    app.include_router(avatar.router, prefix="/api")
    app.dependency_overrides[get_bearer_token] = lambda: "test-token"
    app.dependency_overrides[get_supabase] = lambda: object()
    calls = {"task": 0, "gpu": 0}

    monkeypatch.setattr(avatar, "get_authenticated_user", lambda *_args: {"id": "user-1", "email": "test@example.com"})
    monkeypatch.setattr(avatar, "assert_generation_quota", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(avatar, "get_dynamic_template_video_url", lambda _template_id: "https://example.com/template.mp4")
    monkeypatch.setattr(avatar, "_create_avatar_task", lambda *_args, **_kwargs: calls.__setitem__("task", calls["task"] + 1))

    async def fail_tts(*_args, **_kwargs):
        raise HTTPException(status_code=502, detail="配音服务暂时不可用，请稍后重试。")

    async def fake_gpu(*_args, **_kwargs):
        calls["gpu"] += 1

    monkeypatch.setattr(avatar, "synthesize_speech_to_storage", fail_tts)
    monkeypatch.setattr(avatar, "ensure_gpu_ready", fake_gpu)

    response = TestClient(app).post(
        "/api/avatar/template-generate",
        headers={"Authorization": "Bearer test-token"},
        json={
            "avatar_template_id": "business_female_01",
            "script_text": "测试文案",
            "language": "zh-CN",
            "voice": "zh_female_default",
            "speed_ratio": 1.0,
        },
    )

    assert response.status_code == 502
    assert response.json()["detail"] == "配音服务暂时不可用，请稍后重试。"
    assert calls == {"task": 0, "gpu": 0}
