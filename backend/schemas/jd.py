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


class ExtractedJdSkillResponse(BaseModel):
    id: int
    skill_id: int
    name: str
    normalized_name: str
    category: str | None = None
    proficiency_required: str
    relevance_score: float
    extraction_method: str


class ExtractedSkillSummaryResponse(BaseModel):
    name: str
    normalized_name: str
    category: str | None = None
    proficiency_required: str
    relevance_score: float
    extraction_method: str


class JdExtractionStoredData(BaseModel):
    jd_id: int | None
    title: str | None = None
    company: str | None = None
    extraction_method: str = "llm"
    already_processed: bool = False
    skill_count: int
    skills: list[ExtractedSkillSummaryResponse]


class JdDetailResponse(JdResponse):
    skills: list[ExtractedJdSkillResponse] = Field(default_factory=list)


class JdListItemResponse(JdResponse):
    skill_count: int = 0


class JdListResponse(BaseModel):
    items: list[JdListItemResponse]
    total: int
    limit: int
    offset: int


class JdTrendPointResponse(BaseModel):
    date: str
    count: int


class JdTrendResponse(BaseModel):
    days: int
    total: int
    points: list[JdTrendPointResponse]


class JobMarketTrendPointResponse(BaseModel):
    year: int
    count: int


class JobMarketTrendResponse(BaseModel):
    keyword: str
    years: int
    total: int
    data_source: str = "local_jd_records"
    points: list[JobMarketTrendPointResponse]


class JdFetchRequest(BaseModel):
    keyword: str = Field(..., min_length=2, max_length=100, description="Job title keyword")
    city: str | None = Field(None, max_length=50, description="Optional city keyword")
    source_url: str | None = Field(
        None,
        max_length=2000,
        description="Optional public job detail URL. Login-only pages are not supported.",
    )
    max_results: int = Field(3, ge=1, le=5, description="Maximum public pages to inspect")

    @field_validator("keyword", "city", "source_url")
    @classmethod
    def normalize_fetch_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class JdFetchResponse(BaseModel):
    keyword: str
    title: str | None = None
    company: str | None = None
    source_url: str | None = None
    source_domain: str | None = None
    jd_text: str
    inspected_urls: list[str] = Field(default_factory=list)
    from_cache: bool = False
