from typing import Any

from pydantic import BaseModel, ConfigDict, Field


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
