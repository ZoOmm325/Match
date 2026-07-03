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


class MajorListResponse(BaseModel):
    items: list[MajorResponse]
    total: int
    limit: int
    offset: int


class MajorSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=1000)
    top_k: int = Field(10, ge=1, le=50)

    @field_validator("query")
    @classmethod
    def normalize_query(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("query cannot be empty")
        return normalized


class MajorSearchResultResponse(MajorResponse):
    similarity_score: float = Field(..., ge=0, le=1)


class MajorSearchResponse(BaseModel):
    query: str
    results: list[MajorSearchResultResponse]
