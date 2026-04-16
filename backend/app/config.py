from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql://synth:synth@localhost:5432/synth"

    # Environment: "development" or "production"
    environment: str = "development"

    # When True, GET /api/health/meeting-latency exposes in-process p50/p95 (lock down in prod)
    expose_meeting_latency_metrics: bool = Field(
        default=False,
        validation_alias=AliasChoices(
            "expose_meeting_latency_metrics",
            "EXPOSE_MEETING_LATENCY_METRICS",
        ),
    )

    # Auth
    secret_key: str = "change-me-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440  # 24 hours
    service_secret: str = Field(default="cognara-service-secret-dev", alias="BACKEND_SERVICE_SECRET")

    # Claude API
    anthropic_api_key: str = ""

    # Recall.ai
    recall_api_key: str = ""
    recall_region: str = "us-west-2"
    webhook_base_url: str = ""
    webhook_secret: str = ""

    # CORS
    cors_origins: str = "http://localhost:3000"

    # Gemini (fast path LLM)
    gemini_api_key: str = ""

    # Deepgram (transcription via Recall.ai)
    deepgram_api_key: str = ""

    # Web Search
    serper_api_key: str = ""
    searxng_url: str = "http://localhost:8080"

    # File storage
    upload_dir: str = "./uploads"
    summary_dir: str = "./summaries"

    # Email — Resend (preferred)
    resend_api_key: str = ""

    # Email — SMTP (fallback)
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    from_email: str = "synth@example.com"

    # Stripe
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""

    # Frontend
    frontend_url: str = "http://localhost:3000"
    frontend_success_url: str = "http://localhost:3000/dashboard/settings?payment=success"
    frontend_cancel_url: str = "http://localhost:3000/dashboard/settings?payment=cancelled"

    model_config = {"env_file": ".env", "extra": "ignore"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
