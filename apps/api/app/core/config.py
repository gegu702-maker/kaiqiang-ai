from typing import Any

from pydantic import AliasChoices, Field, ValidationInfo, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    supabase_url: str = "https://example.supabase.co"
    supabase_service_role_key: str = ""
    supabase_image_bucket: str = "images"
    supabase_voice_bucket: str = "voices"
    supabase_cloned_bucket: str = "cloned"
    supabase_video_bucket: str = "videos"
    supabase_subtitle_bucket: str = "subtitles"
    admin_api_key: str = "dev-admin-key"
    web_origin: str = "http://localhost:3000"
    cors_origins: str = "https://kaiqiang.ai,https://www.kaiqiang.ai,https://kaiqiang-58mkzjhmo-kaiqiang-ai-s-projects.vercel.app,http://localhost:3000,http://127.0.0.1:3000"
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
    elevenlabs_api_key: str = ""
    elevenlabs_voice_id: str = ""
    volcengine_tts_app_id: str = ""
    volcengine_tts_access_token: str = ""
    volcengine_tts_cluster: str = ""
    volcengine_tts_voice_type: str = ""
    volcengine_tts_endpoint: str = "https://openspeech.bytedance.com/api/v1/tts"
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
    autodl_start_timeout_seconds: int = 900
    gpu_idle_shutdown_minutes: int = 10

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

    @property
    def allowed_origins(self) -> list[str]:
        raw_origins = self.cors_origins
        if raw_origins.startswith("CORS_ORIGINS="):
            raw_origins = raw_origins.split("=", 1)[1]
        origins = [origin.strip() for origin in raw_origins.split(",") if origin.strip()]
        if self.web_origin not in origins:
            origins.append(self.web_origin)
        for origin in [
            "https://kaiqiang.ai",
            "https://www.kaiqiang.ai",
            "https://kaiqiang-58mkzjhmo-kaiqiang-ai-s-projects.vercel.app",
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ]:
            if origin not in origins:
                origins.append(origin)
        return origins

    @property
    def allowed_origin_regex(self) -> str:
        return r"^https://kaiqiang-[a-z0-9-]+-kaiqiang-ai-s-projects\.vercel\.app$"

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
