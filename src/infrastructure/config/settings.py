from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_env: str = "development"
    app_name: str = "agente-citas-backend"
    app_debug: bool = False
    app_port: int = 8000
    app_cors_origins: str = ""

    # Credentials must come from .env / environment variables. The default
    # is an unusable placeholder so that `import` succeeds without secrets,
    # but `create_async_engine` will fail fast if it is ever used as-is.
    database_url: str = "postgresql+asyncpg://localhost/agente_citas"
    redis_url: str = "redis://localhost:6379/0"
    redis_cache_ttl: int = 60

    anthropic_api_key: str = ""
    anthropic_model_reasoning: str = "claude-sonnet-4-6"
    anthropic_model_fast: str = "claude-haiku-4-5-20251001"
    anthropic_max_tokens: int = 500
    anthropic_temperature: float = 0.3

    openai_api_key: str = ""
    openai_whisper_model: str = "whisper-1"

    voyage_api_key: str = ""
    voyage_embedding_model: str = "voyage-multilingual-2"

    whatsapp_api_version: str = "v23.0"
    whatsapp_phone_number_id: str = ""
    whatsapp_access_token: str = ""
    whatsapp_verify_token: str = ""
    whatsapp_app_secret: str = ""

    rate_limit_per_minute: int = 10
    rate_limit_per_hour: int = 50

    log_level: str = "info"
    log_format: str = "json"

    sentry_dsn: str = ""
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "https://cloud.langfuse.com"

    jwt_secret_key: str = Field(default="change-me", min_length=8)
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60

    @property
    def app_cors_origins_list(self) -> list[str]:
        if not self.app_cors_origins:
            return []
        return [origin.strip() for origin in self.app_cors_origins.split(",") if origin.strip()]

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
