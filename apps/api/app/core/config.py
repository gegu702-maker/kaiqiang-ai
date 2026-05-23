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
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    minimax_api_key: str = ""
    minimax_group_id: str = ""
    cosyvoice_url: str = "http://localhost:50000"
    cosyvoice_timeout_seconds: int = 1800
    cosyvoice_prompt_text: str = "这是一段用于克隆音色的参考声音。"
    cosyvoice_sample_rate: int = 22050

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @property
    def allowed_origins(self) -> list[str]:
        origins = [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]
        if self.web_origin not in origins:
            origins.append(self.web_origin)
        return origins


settings = Settings()
