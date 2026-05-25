from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class CoreSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = "postgresql+asyncpg://sutram:sutram@localhost:5432/sutram"
    redis_url: str = "redis://localhost:6379/0"
    jwt_secret: str = "dev-secret-change-in-production"
    jwt_algorithm: str = "HS256"
    internal_auth_token: str = "dev-internal-token-change-in-production"
    openai_api_key: str = ""
    sutram_env: str = "development"  # set to "production" or "staging" to enable secret validation


@lru_cache
def get_settings() -> CoreSettings:
    return CoreSettings()
