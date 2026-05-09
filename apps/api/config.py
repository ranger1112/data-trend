from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "data-trend"
    database_url: str = "sqlite:///./data-trend.db"
    cors_origins: list[str] = ["*"]

    model_config = SettingsConfigDict(env_prefix="DATA_TREND_", env_file=".env")


@lru_cache
def get_settings() -> Settings:
    return Settings()

