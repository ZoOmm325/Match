from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class MajorBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="Major name")
    code: str | None = Field(None, max_length=50, description="Major code")
    category: str | None = Field(None, max_length=100, description="Discipline category")
    description: str | None = Field(None, description="Major description")
    curriculum: dict[str, Any] | list[Any] | None = Field(None, description="Curriculum structure")
    embedding: list[float] | None = Field(None, description="1024-dimensional pgvector embedding")

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("name cannot be empty")
        return normalized

    @field_validator("code", "category", "description")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator("embedding")
    @classmethod
    def validate_embedding_dimension(cls, value: list[float] | None) -> list[float] | None:
        if value is not None and len(value) != 1024:
            raise ValueError("embedding must contain exactly 1024 dimensions")
        return value


class MajorCreate(MajorBase):
    pass


class MajorResponse(MajorBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
