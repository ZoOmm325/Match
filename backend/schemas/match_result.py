from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class MatchResultBase(BaseModel):
    jd_id: int = Field(..., gt=0, description="JD foreign key")
    major_id: int = Field(..., gt=0, description="Major foreign key")
    similarity_score: float = Field(..., ge=0, le=1, description="Vector similarity score")
    final_score: float = Field(..., ge=0, le=1, description="Weighted final score")
    rank: int = Field(..., gt=0, description="Ranking position")
    match_details: dict[str, Any] | list[Any] | None = Field(
        None,
        description="Matched and missing skills details",
    )


class MatchResultCreate(MatchResultBase):
    pass


class MatchResultResponse(MatchResultBase):
    id: int

    model_config = ConfigDict(from_attributes=True)


class MatchRequest(BaseModel):
    jd_text: str = Field(..., min_length=20, max_length=20000)
    skill_top_k: int = Field(20, ge=1, le=100)
    major_top_n: int = Field(5, ge=1, le=50)
    skill_threshold: float = Field(0.5, ge=0, le=1)
    generate_reasons: bool = False

    @field_validator("jd_text")
    @classmethod
    def validate_jd_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("jd_text cannot be empty")
        return normalized


class SkillMatchInput(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    category: str = Field("other", min_length=1, max_length=100)
    proficiency_required: str = Field("intermediate")
    embedding: list[float] | None = Field(None, min_length=1024, max_length=1024)

    @field_validator("name", "category", "proficiency_required")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("value cannot be empty")
        return normalized

    @field_validator("embedding", mode="before")
    @classmethod
    def validate_embedding(cls, value: object) -> object:
        if value is None:
            return value
        if not isinstance(value, list) or len(value) != 1024:
            raise ValueError("embedding must contain exactly 1024 dimensions")
        if any(isinstance(item, bool) for item in value):
            raise ValueError("embedding must contain only numeric values")
        return value


class MatchBySkillsRequest(BaseModel):
    skills: list[SkillMatchInput] = Field(..., min_length=1, max_length=100)
    top_n: int = Field(5, ge=1, le=50)
    generate_reasons: bool = False


class MatchRecommendationResponse(BaseModel):
    rank: int
    major_id: int | None
    major_name: str
    major_code: str | None = None
    final_score: float
    skill_similarity_score: float
    skill_coverage_score: float
    employment_alignment_score: float
    matched_skills: list[str]
    missing_skills: list[str]
    recommendation_reason: str
    score_details: dict[str, Any]


class MatchResponseData(BaseModel):
    jd_id: int | None = None
    extracted_skill_count: int
    persisted_count: int = 0
    already_processed: bool = False
    recommendations: list[MatchRecommendationResponse]


class MatchHistoryResponseData(BaseModel):
    jd_id: int
    recommendations: list[MatchRecommendationResponse]
