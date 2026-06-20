from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class JdBase(BaseModel):
    raw_text: str = Field(..., min_length=20, max_length=20000, description="Original JD text")
    title: str | None = Field(None, max_length=255, description="Job title")
    company: str | None = Field(None, max_length=255, description="Company name")
    source: str | None = Field(None, max_length=100, description="JD source")

    @field_validator("raw_text")
    @classmethod
    def validate_raw_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("raw_text cannot be empty")
        return normalized

    @field_validator("title", "company", "source")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class JdCreate(JdBase):
    pass


class JdResponse(JdBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
