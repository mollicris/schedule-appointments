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
    redis_url: str = ""
    redis_cache_ttl: int = 60

    anthropic_api_key: str = ""
    anthropic_model_reasoning: str = "claude-sonnet-4-6"
    anthropic_model_fast: str = "claude-haiku-4-5-20251001"
    anthropic_max_tokens: int = 500
    anthropic_temperature: float = 0.3
    # Social channels are read-only: they inform and take a phone number, they
    # never book, cancel or move an appointment. A worse-worded answer is the
    # worst that can happen there, so the cheaper model earns its keep. Set to
    # false to put every channel back on the reasoning model.
    anthropic_fast_on_social: bool = True
    # System prompt and tool schemas repeat verbatim on every turn; caching
    # them costs a tenth of re-sending them. Off only for debugging.
    anthropic_prompt_cache: bool = True

    openai_api_key: str = ""
    openai_whisper_model: str = "whisper-1"

    voyage_api_key: str = ""
    voyage_embedding_model: str = "voyage-multilingual-2"

    whatsapp_api_version: str = "v23.0"
    whatsapp_phone_number_id: str = ""
    whatsapp_access_token: str = ""
    whatsapp_verify_token: str = ""
    whatsapp_app_secret: str = ""

    # Meta App credentials for Embedded Signup OAuth flow
    meta_app_id: str = ""
    meta_app_secret: str = ""
    # Verify token for the Messenger / Instagram webhook. Falls back to the
    # WhatsApp one so an existing deployment keeps working with a single token.
    meta_verify_token: str = ""

    # Minutes after which an unresolved handover lets the bot take over again.
    # 0 disables it: a real handover then waits for a human to resolve the
    # transfer. Useful while testing, where nobody is watching the queue.
    escalation_auto_resume_minutes: int = 0

    # ── Proactive campaigns (gym module) ─────────────────────────────────────
    # Off by default: writing outside Meta's 24h window requires templates
    # approved in the Meta dashboard first. With no template names configured,
    # sending fails closed even if the flag is on.
    campaigns_enabled: bool = False
    campaign_poll_interval_seconds: int = 3600
    campaign_expiring_days: int = 7        # warn members whose plan ends within N days
    campaign_inactive_days: int = 30       # win-back after N days without activity
    campaign_daily_send_cap: int = 50      # per business, per cycle
    whatsapp_template_language: str = "es"
    whatsapp_template_membership_expiring: str = ""
    whatsapp_template_winback: str = ""

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

    # ── Email ────────────────────────────────────────────────────────────────
    # email_provider: "console" | "resend" | "smtp"
    email_provider: str = "console"
    email_from: str = "Agente Citas <noreply@agentecitas.com>"
    email_landing_base_url: str = "http://localhost:5174"

    # Resend
    resend_api_key: str = ""

    # SMTP
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_use_tls: bool = True

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
