from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SkillBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="Original skill name")
    normalized_name: str = Field(..., min_length=1, max_length=255, description="Canonical skill name")
    category: str | None = Field(None, max_length=100, description="Skill category")
    embedding: list[float] | None = Field(None, description="1536-dimensional pgvector embedding")

    @field_validator("name", "normalized_name")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("field cannot be empty")
        return normalized

    @field_validator("category")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator("embedding")
    @classmethod
    def validate_embedding_dimension(cls, value: list[float] | None) -> list[float] | None:
        if value is not None and len(value) != 1536:
            raise ValueError("embedding must contain exactly 1536 dimensions")
        return value


class SkillCreate(SkillBase):
    pass


class SkillResponse(SkillBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
