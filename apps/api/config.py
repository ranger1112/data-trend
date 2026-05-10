from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "data-trend"
    database_url: str = "sqlite:///./data-trend.db"
    cors_origins: list[str] = ["*"]
    worker_poll_seconds: int = 60
    alert_webhook_url: str | None = None
    admin_username: str = "admin"
    admin_password: str = "admin"
    admin_role: str = "operator"
    auth_token_secret: str = "change-me-in-production"
    auth_token_ttl_seconds: int = 86400
    crawl_job_max_retries: int = 3
    crawl_job_retry_delay_seconds: int = 300
    crawl_job_timeout_seconds: int = 1800

    model_config = SettingsConfigDict(env_prefix="DATA_TREND_", env_file=".env")


@lru_cache
def get_settings() -> Settings:
    return Settings()
