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

    @field_validator("openai_api_key")
    @classmethod
    def validate_openai_api_key(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("OPENAI_API_KEY cannot be empty")
        return value

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
