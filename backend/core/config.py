from functools import lru_cache
from typing import List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env."""

    app_name: str = "JD Major Match API"
    api_prefix: str = "/api"
    cors_origins: List[str] = Field(default_factory=lambda: ["*"])
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/match"
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    embedding_model: str = "text-embedding-3-small"
    openai_timeout_seconds: float = 30.0
    openai_max_retries: int = 3
    openai_rate_limit_per_minute: int = 60

    @field_validator("openai_api_key")
    @classmethod
    def validate_openai_api_key(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("OPENAI_API_KEY cannot be empty")
        return value

    @field_validator("openai_timeout_seconds")
    @classmethod
    def validate_timeout(cls, value: float) -> float:
        if value <= 0:
            raise ValueError("OPENAI_TIMEOUT_SECONDS must be greater than 0")
        return value

    @field_validator("openai_max_retries")
    @classmethod
    def validate_max_retries(cls, value: int) -> int:
        if value < 1:
            raise ValueError("OPENAI_MAX_RETRIES must be at least 1")
        return value

    @field_validator("openai_rate_limit_per_minute")
    @classmethod
    def validate_rate_limit(cls, value: int) -> int:
        if value < 1:
            raise ValueError("OPENAI_RATE_LIMIT_PER_MINUTE must be at least 1")
        return value

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
