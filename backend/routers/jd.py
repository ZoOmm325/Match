from fastapi import APIRouter

from backend.schemas.jd_extraction import (
    ApiResponse,
    JdSkillExtractionData,
    JdSkillExtractionRequest,
)
from backend.services.jd_skill_extractor import JdSkillExtractor

router = APIRouter(prefix="/jd", tags=["JD"])
extractor = JdSkillExtractor()


def build_extraction_response(payload: JdSkillExtractionRequest) -> ApiResponse[JdSkillExtractionData]:
    skills = extractor.extract(payload.jd_text)
    return ApiResponse(
        code=0,
        message="success",
        data=JdSkillExtractionData(
            title=payload.title,
            company=payload.company,
            skill_count=len(skills),
            skills=skills,
        ),
    )


@router.post(
    "/extract",
    response_model=ApiResponse[JdSkillExtractionData],
    summary="Extract structured skills from a job description",
)
async def extract_jd_skills(
    payload: JdSkillExtractionRequest,
) -> ApiResponse[JdSkillExtractionData]:
    return build_extraction_response(payload)


@router.post(
    "/extract-skills",
    response_model=ApiResponse[JdSkillExtractionData],
    include_in_schema=False,
)
async def extract_jd_skills_legacy(
    payload: JdSkillExtractionRequest,
) -> ApiResponse[JdSkillExtractionData]:
    return build_extraction_response(payload)
