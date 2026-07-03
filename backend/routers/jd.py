from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any, Protocol

from fastapi import APIRouter, Depends, HTTPException, Query, status

from backend.schemas.jd import (
    ExtractedJdSkillResponse,
    ExtractedSkillSummaryResponse,
    JdDetailResponse,
    JdExtractionStoredData,
    JdListItemResponse,
    JdListResponse,
)
from backend.schemas.jd_extraction import (
    ApiResponse,
    JdSkillExtractionData,
    JdSkillExtractionRequest,
)
from backend.services.jd_service import ExtractedSkillResult, JdExtractionResult, JdService
from backend.services.jd_skill_extractor import JdSkillExtractor

router = APIRouter(prefix="/jd", tags=["JD"])
extractor = JdSkillExtractor()


class JdReadRepository(Protocol):
    async def get_jd_detail(self, jd_id: int) -> JdDetailResponse | None: ...

    async def list_jds(self, *, limit: int, offset: int) -> JdListResponse: ...

    async def delete_jd(self, jd_id: int) -> bool: ...


class SqlAlchemyJdReadRepository:
    def __init__(self, session: Any) -> None:
        self.session = session

    async def get_jd_detail(self, jd_id: int) -> JdDetailResponse | None:
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload

        from backend.models.jd import Jd
        from backend.models.jd_skill import JdSkill

        result = await self.session.execute(
            select(Jd)
            .options(selectinload(Jd.skills).selectinload(JdSkill.skill))
            .where(Jd.id == jd_id)
        )
        jd = result.scalar_one_or_none()
        if jd is None:
            return None
        return self._detail_response(jd)

    async def list_jds(self, *, limit: int, offset: int) -> JdListResponse:
        from sqlalchemy import func, select
        from sqlalchemy.orm import selectinload

        from backend.models.jd import Jd

        total_result = await self.session.execute(select(func.count()).select_from(Jd))
        total = int(total_result.scalar_one())
        result = await self.session.execute(
            select(Jd)
            .options(selectinload(Jd.skills))
            .order_by(Jd.created_at.desc(), Jd.id.desc())
            .offset(offset)
            .limit(limit)
        )
        jds = result.scalars().all()
        return JdListResponse(
            items=[
                JdListItemResponse(
                    id=jd.id,
                    raw_text=jd.raw_text,
                    title=jd.title,
                    company=jd.company,
                    source=jd.source,
                    created_at=jd.created_at,
                    updated_at=jd.updated_at,
                    skill_count=len(jd.skills),
                )
                for jd in jds
            ],
            total=total,
            limit=limit,
            offset=offset,
        )

    async def delete_jd(self, jd_id: int) -> bool:
        from sqlalchemy import delete

        from backend.models.jd import Jd

        result = await self.session.execute(delete(Jd).where(Jd.id == jd_id))
        if result.rowcount == 0:
            return False
        await self.session.commit()
        return True

    def _detail_response(self, jd: Any) -> JdDetailResponse:
        return JdDetailResponse(
            id=jd.id,
            raw_text=jd.raw_text,
            title=jd.title,
            company=jd.company,
            source=jd.source,
            created_at=jd.created_at,
            updated_at=jd.updated_at,
            skills=[
                ExtractedJdSkillResponse(
                    id=link.id,
                    skill_id=link.skill_id,
                    name=link.skill.name,
                    normalized_name=link.skill.normalized_name,
                    category=link.skill.category,
                    proficiency_required=JdService.proficiency_for_score(link.relevance_score),
                    relevance_score=link.relevance_score,
                    extraction_method=link.extraction_method,
                )
                for link in jd.skills
            ],
        )


async def get_session() -> AsyncIterator[Any]:
    from backend.core.database import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        yield session


def get_jd_service(session: Any = Depends(get_session)) -> JdService:
    return JdService(session=session)


def get_jd_read_repository(session: Any = Depends(get_session)) -> JdReadRepository:
    return SqlAlchemyJdReadRepository(session)


def build_extraction_response(
    payload: JdSkillExtractionRequest,
) -> ApiResponse[JdSkillExtractionData]:
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


def build_stored_extraction_response(
    payload: JdSkillExtractionRequest,
    extraction: JdExtractionResult,
) -> ApiResponse[JdExtractionStoredData]:
    return ApiResponse(
        code=0,
        message="success",
        data=JdExtractionStoredData(
            jd_id=extraction.jd_id,
            title=payload.title,
            company=payload.company,
            already_processed=extraction.already_processed,
            skill_count=len(extraction.skills),
            skills=[_skill_result_to_response(skill) for skill in extraction.skills],
        ),
    )


def _skill_result_to_response(skill: ExtractedSkillResult) -> ExtractedSkillSummaryResponse:
    return ExtractedSkillSummaryResponse(
        name=skill.name,
        normalized_name=skill.normalized_name,
        category=skill.category,
        proficiency_required=skill.proficiency_required,
        relevance_score=JdService.score_for_proficiency(skill.proficiency_required),
        extraction_method="llm",
    )


@router.post(
    "/extract",
    response_model=ApiResponse[JdExtractionStoredData],
    summary="Extract skills from a job description and persist the JD",
)
async def extract_jd_skills(
    payload: JdSkillExtractionRequest,
    service: JdService = Depends(get_jd_service),
) -> ApiResponse[JdExtractionStoredData]:
    try:
        extraction = await service.extract_skills(
            payload.jd_text,
            title=payload.title,
            company=payload.company,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return build_stored_extraction_response(payload, extraction)


@router.post(
    "/extract-skills",
    response_model=ApiResponse[JdSkillExtractionData],
    include_in_schema=False,
)
async def extract_jd_skills_legacy(
    payload: JdSkillExtractionRequest,
) -> ApiResponse[JdSkillExtractionData]:
    return build_extraction_response(payload)


@router.get("", response_model=ApiResponse[JdListResponse], summary="List submitted JDs")
async def list_jds(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    repository: JdReadRepository = Depends(get_jd_read_repository),
) -> ApiResponse[JdListResponse]:
    return ApiResponse(
        code=0, message="success", data=await repository.list_jds(limit=limit, offset=offset)
    )


@router.get("/{jd_id}", response_model=ApiResponse[JdDetailResponse], summary="Get JD details")
async def get_jd(
    jd_id: int,
    repository: JdReadRepository = Depends(get_jd_read_repository),
) -> ApiResponse[JdDetailResponse]:
    jd = await repository.get_jd_detail(jd_id)
    if jd is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="JD not found")
    return ApiResponse(code=0, message="success", data=jd)


@router.delete("/{jd_id}", response_model=ApiResponse[None], summary="Delete a JD")
async def delete_jd(
    jd_id: int,
    repository: JdReadRepository = Depends(get_jd_read_repository),
) -> ApiResponse[None]:
    deleted = await repository.delete_jd(jd_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="JD not found")
    return ApiResponse(code=0, message="success", data=None)
