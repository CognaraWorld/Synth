from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql://synth:synth@localhost:5432/synth"

    # Auth
    secret_key: str = "change-me-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440  # 24 hours

    # Claude API
    anthropic_api_key: str = ""

    # Recall.ai
    recall_api_key: str = ""

    # SearXNG
    searxng_url: str = "http://localhost:8080"

    # File storage
    upload_dir: str = "./uploads"
    summary_dir: str = "./summaries"

    # Frontend
    frontend_url: str = "http://localhost:3000"

    model_config = {"env_file": ".env", "extra": "ignore"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
