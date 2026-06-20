from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, Field, field_validator


class JdSkillExtractionRequest(BaseModel):
    jd_text: str = Field(..., min_length=20, max_length=20000, description="岗位 JD 原文")
    title: str | None = Field(None, max_length=120, description="岗位名称")
    company: str | None = Field(None, max_length=120, description="公司名称")

    @field_validator("jd_text")
    @classmethod
    def validate_jd_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("jd_text cannot be empty")
        return normalized


class SkillExtractionItem(BaseModel):
    name: str = Field(..., description="技能名称")
    category: str = Field(..., description="技能分类")
    proficiency_required: Literal["basic", "intermediate", "advanced"] = Field(
        ..., description="要求熟练度"
    )
    evidence: str = Field(..., description="触发抽取的 JD 片段")
    confidence: float = Field(..., ge=0, le=1, description="抽取置信度")


class JdSkillExtractionData(BaseModel):
    title: str | None = None
    company: str | None = None
    extraction_method: Literal["keyword_rules"] = "keyword_rules"
    skill_count: int
    skills: list[SkillExtractionItem]


DataT = TypeVar("DataT")


class ApiResponse(BaseModel, Generic[DataT]):
    code: int = Field(..., description="业务状态码，0 表示成功")
    data: DataT | None = None
    message: str
