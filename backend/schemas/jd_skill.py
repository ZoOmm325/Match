from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class JdSkillBase(BaseModel):
    jd_id: int = Field(..., gt=0, description="JD foreign key")
    skill_id: int = Field(..., gt=0, description="Skill foreign key")
    relevance_score: float = Field(..., ge=0, le=1, description="Relevance score from 0 to 1")
    extraction_method: Literal["llm", "manual", "keyword_rules"] = Field(
        ...,
        description="Extraction method",
    )


class JdSkillCreate(JdSkillBase):
    pass


class JdSkillResponse(JdSkillBase):
    id: int

    model_config = ConfigDict(from_attributes=True)
