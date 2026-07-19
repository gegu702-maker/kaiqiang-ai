from typing import Any
from urllib.parse import urlsplit, urlunsplit

from pydantic import AliasChoices, Field, ValidationInfo, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _parse_cors_origins(raw_origins: str) -> list[str]:
    origins: list[str] = []
    for raw_origin in raw_origins.split(","):
        origin = raw_origin.strip()
        if not origin:
            continue
        if origin == "*":
            raise ValueError("CORS_ALLOWED_ORIGINS cannot contain '*'")

        parsed = urlsplit(origin)
        if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
            raise ValueError(f"Invalid CORS origin: {origin}")
        if parsed.username or parsed.password:
            raise ValueError(f"CORS origin must not contain credentials: {origin}")
        if parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
            raise ValueError(f"CORS origin must not contain a path, query, or fragment: {origin}")
        try:
            parsed.port
        except ValueError as error:
            raise ValueError(f"Invalid CORS origin port: {origin}") from error

        normalized = urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), "", "", ""))
        if normalized not in origins:
            origins.append(normalized)
    return origins


class Settings(BaseSettings):
    app_environment: str = "development"
    avatar_preview_safe_mode: bool = False
    supabase_url: str = "https://example.supabase.co"
    supabase_service_role_key: str = ""
    supabase_image_bucket: str = "images"
    supabase_voice_bucket: str = "voices"
    supabase_cloned_bucket: str = "cloned"
    supabase_video_bucket: str = "videos"
    supabase_subtitle_bucket: str = "subtitles"
    admin_api_key: str = "dev-admin-key"
    web_origin: str = "http://localhost:3000"
    cors_allowed_origins: str = Field(
        "",
        validation_alias=AliasChoices("CORS_ALLOWED_ORIGINS", "CORS_ORIGINS"),
    )
    minimax_api_key: str = ""
    minimax_group_id: str = ""
    cosyvoice_url: str = "http://localhost:50000"
    cosyvoice_timeout_seconds: int = 1800
    cosyvoice_prompt_text: str = "这是一段用于克隆音色的参考声音。"
    cosyvoice_sample_rate: int = 22050
    public_site_url: str = "http://localhost:3000"
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    lemon_squeezy_api_key: str = ""
    creem_api_key: str = ""
    payment_provider: str = "manual"
    paypal_client_id: str = ""
    paypal_client_secret: str = ""
    paypal_api_base: str = "https://api-m.sandbox.paypal.com"
    pingpp_api_key: str = ""
    pingpp_app_id: str = ""
    wechat_pay_mch_id: str = ""
    wechat_pay_api_key: str = ""
    alipay_app_id: str = ""
    alipay_private_key: str = ""
    openai_api_key: str = ""
    gemini_api_key: str = ""
    dashscope_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    openai_tts_model: str = "gpt-4o-mini-tts"
    openai_tts_voice: str = "alloy"
    llm_provider: str = "deepseek"
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"
    faster_whisper_model_size: str = Field("small", validation_alias=AliasChoices("FASTER_WHISPER_MODEL_SIZE", "ASR_MODEL_SIZE"))
    faster_whisper_device: str = Field("cpu", validation_alias=AliasChoices("FASTER_WHISPER_DEVICE", "ASR_DEVICE"))
    faster_whisper_compute_type: str = Field("int8", validation_alias=AliasChoices("FASTER_WHISPER_COMPUTE_TYPE", "ASR_COMPUTE_TYPE"))
    viral_max_video_duration_seconds: int = 120
    viral_max_download_mb: int = 100
    viral_pipeline_timeout_seconds: int = 180
    viral_pipeline_allowed_emails: str = ""
    douyin_cookie_file: str = ""
    elevenlabs_api_key: str = ""
    elevenlabs_voice_id: str = ""
    volcengine_tts_app_id: str = ""
    volcengine_tts_access_token: str = ""
    volcengine_tts_cluster: str = ""
    volcengine_tts_voice_type: str = ""
    volcengine_tts_endpoint: str = "https://openspeech.bytedance.com/api/v1/tts"
    volcengine_default_voice_key: str = "zh_female_default"
    volcengine_voice_zh_female_default: str = ""
    volcengine_voice_zh_male_default: str = ""
    volcengine_voice_zh_warm_female: str = ""
    volcengine_voice_zh_steady_male: str = ""
    volcengine_voice_zh_energetic_female: str = ""
    volcengine_voice_zh_knowledge_host: str = ""
    volcengine_voice_zh_business_narration: str = ""
    volcengine_voice_zh_casual_spoken: str = ""
    volcengine_voice_zh_dongbei_laotie: str = ""
    volcengine_voice_en_energetic_male_jackson: str = ""
    volcengine_voice_zh_gentle_young_man: str = ""
    volcengine_voice_zh_refined_youth: str = ""
    volcengine_voice_en_energetic_female_ariana: str = ""
    volcengine_voice_ja_male: str = ""
    volcengine_voice_ja_elegant_female: str = ""
    volcengine_voice_zh_sunny_male: str = ""
    volcengine_voice_zh_intellectual_female_bilingual: str = ""
    volcengine_voice_zh_friendly_female: str = ""
    volcengine_voice_zh_guangxi_cousin: str = ""
    volcengine_voice_zh_lively_female: str = ""
    heygen_api_key: str = ""
    heygen_avatar_id: str = ""
    heygen_voice_id: str = ""
    enable_task_worker: bool = True
    task_worker_poll_seconds: int = 8
    ffmpeg_path: str = "ffmpeg"
    voice_clone_provider: str = "mock"
    avatar_motion_provider: str = "static"
    liveportrait_api_base_url: str = ""
    liveportrait_api_key: str = ""
    liveportrait_default_driving_video_url: str = ""
    replicate_api_token: str = ""
    replicate_liveportrait_model: str = "fofr/live-portrait"
    muse_talk_api_base_url: str = Field(
        "",
        validation_alias=AliasChoices("MUSE_TALK_API_BASE_URL", "MUSETALK_API_BASE_URL"),
    )
    muse_talk_template_video_urls: str = Field(
        "",
        validation_alias=AliasChoices("MUSE_TALK_TEMPLATE_VIDEO_URLS", "MUSETALK_TEMPLATE_VIDEO_URLS"),
    )
    muse_talk_default_template_video_url: str = Field(
        "",
        validation_alias=AliasChoices("MUSE_TALK_DEFAULT_TEMPLATE_VIDEO_URL", "MUSETALK_DEFAULT_TEMPLATE_VIDEO_URL"),
    )
    muse_talk_api_key: str = Field(
        "",
        validation_alias=AliasChoices("MUSE_TALK_API_KEY", "MUSETALK_API_KEY"),
    )
    muse_talk_timeout_seconds: int = Field(
        1800,
        validation_alias=AliasChoices("MUSE_TALK_TIMEOUT_SECONDS", "MUSETALK_TIMEOUT_SECONDS"),
    )
    autodl_api_token: str = ""
    autodl_instance_id: str = ""
    autodl_region: str = ""
    autodl_api_base_url: str = "https://api.autodl.com"
    autodl_auto_start_enabled: bool = False
    autodl_start_timeout_seconds: int = 900
    gpu_idle_shutdown_minutes: int = 10
    avatar_subtitles_enabled: bool = True
    avatar_subtitle_font: str = "Noto Sans CJK SC"
    avatar_subtitle_fallback_on_error: bool = True

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @field_validator("*", mode="before")
    @classmethod
    def strip_accidental_env_key_prefix(cls, value: Any, info: ValidationInfo) -> Any:
        if not isinstance(value, str):
            return value
        env_name = info.field_name.upper()
        prefix = f"{env_name}="
        if value.startswith(prefix):
            return value[len(prefix) :].strip()
        return value

    @field_validator("app_environment", mode="before")
    @classmethod
    def normalize_app_environment(cls, value: Any) -> str:
        normalized = str(value or "development").strip().lower()
        if normalized not in {"development", "test", "preview", "production"}:
            raise ValueError("APP_ENVIRONMENT must be development, test, preview, or production")
        return normalized

    @model_validator(mode="after")
    def reject_preview_safe_mode_in_production(self) -> "Settings":
        if self.app_environment == "production" and self.avatar_preview_safe_mode:
            raise ValueError("AVATAR_PREVIEW_SAFE_MODE cannot be enabled in production")
        if self.app_environment == "preview" and not self.allowed_origins:
            raise ValueError("CORS_ALLOWED_ORIGINS must be configured for preview")
        return self

    @property
    def allowed_origins(self) -> list[str]:
        configured = _parse_cors_origins(self.cors_allowed_origins)
        if self.app_environment == "production":
            defaults = ["https://kaiqiang.ai", "https://www.kaiqiang.ai"]
        elif self.app_environment in {"development", "test"}:
            defaults = ["http://localhost:3000", "http://127.0.0.1:3000"]
        else:
            defaults = []
        return list(dict.fromkeys([*defaults, *configured]))

    @property
    def musetalk_api_base_url(self) -> str:
        return self.muse_talk_api_base_url

    @property
    def musetalk_template_video_urls(self) -> str:
        return self.muse_talk_template_video_urls

    @property
    def musetalk_default_template_video_url(self) -> str:
        return self.muse_talk_default_template_video_url

    @property
    def musetalk_api_key(self) -> str:
        return self.muse_talk_api_key

    @property
    def musetalk_timeout_seconds(self) -> int:
        return self.muse_talk_timeout_seconds


settings = Settings()
