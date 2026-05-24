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
    cors_origins: str = "https://kaiqiang.ai,https://www.kaiqiang.ai,http://localhost:3000,http://127.0.0.1:3000"
    minimax_api_key: str = ""
    minimax_group_id: str = ""
    cosyvoice_url: str = "http://localhost:50000"
    cosyvoice_timeout_seconds: int = 1800
    cosyvoice_prompt_text: str = "这是一段用于克隆音色的参考声音。"
    cosyvoice_sample_rate: int = 22050
    public_site_url: str = "http://localhost:3000"
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
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
    openai_model: str = "gpt-4o-mini"
    openai_tts_model: str = "gpt-4o-mini-tts"
    openai_tts_voice: str = "alloy"
    llm_provider: str = "deepseek"
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"
    elevenlabs_api_key: str = ""
    elevenlabs_voice_id: str = ""
    heygen_api_key: str = ""
    heygen_avatar_id: str = ""
    heygen_voice_id: str = ""
    enable_task_worker: bool = True
    task_worker_poll_seconds: int = 8
    ffmpeg_path: str = "ffmpeg"
    voice_clone_provider: str = "mock"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @property
    def allowed_origins(self) -> list[str]:
        origins = [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]
        if self.web_origin not in origins:
            origins.append(self.web_origin)
        for origin in ["https://kaiqiang.ai", "https://www.kaiqiang.ai", "http://localhost:3000", "http://127.0.0.1:3000"]:
            if origin not in origins:
                origins.append(origin)
        return origins


settings = Settings()
