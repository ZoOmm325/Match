from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, date, datetime, time, timedelta
from typing import Any, Protocol

from fastapi import APIRouter, Depends, HTTPException, Query, status

from backend.schemas.jd import (
    ExtractedJdSkillResponse,
    ExtractedSkillSummaryResponse,
    JdDetailResponse,
    JdExtractionStoredData,
    JdFetchRequest,
    JdFetchResponse,
    JdListItemResponse,
    JdListResponse,
    JdTrendPointResponse,
    JdTrendResponse,
    JobMarketTrendResponse,
)
from backend.schemas.jd_extraction import (
    ApiResponse,
    JdSkillExtractionData,
    JdSkillExtractionRequest,
)
from backend.services.jd_service import ExtractedSkillResult, JdExtractionResult, JdService
from backend.services.jd_skill_extractor import JdSkillExtractor
from backend.services.job_fetcher import PublicJdFetchError, PublicJobFetcher, PublicJobTrendFetcher

router = APIRouter(prefix="/jd", tags=["JD"])
extractor = JdSkillExtractor()


class JdReadRepository(Protocol):
    async def get_jd_detail(self, jd_id: int) -> JdDetailResponse | None: ...

    async def list_jds(self, *, limit: int, offset: int) -> JdListResponse: ...

    async def get_jd_trend(self, *, days: int) -> JdTrendResponse: ...

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

    async def get_jd_trend(self, *, days: int) -> JdTrendResponse:
        from sqlalchemy import func, select

        from backend.models.jd import Jd

        end_date = datetime.now(UTC).date()
        start_date = end_date - timedelta(days=days - 1)
        start_datetime = datetime.combine(start_date, time.min, tzinfo=UTC)

        result = await self.session.execute(
            select(func.date(Jd.created_at), func.count())
            .where(Jd.created_at >= start_datetime)
            .group_by(func.date(Jd.created_at))
            .order_by(func.date(Jd.created_at))
        )
        counts_by_date = {_coerce_date(bucket): int(count) for bucket, count in result.all()}
        points = [
            JdTrendPointResponse(
                date=(start_date + timedelta(days=index)).isoformat(),
                count=counts_by_date.get(start_date + timedelta(days=index), 0),
            )
            for index in range(days)
        ]
        return JdTrendResponse(
            days=days,
            total=sum(point.count for point in points),
            points=points,
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


def get_public_job_fetcher() -> PublicJobFetcher:
    return PublicJobFetcher()


def get_public_job_trend_fetcher() -> PublicJobTrendFetcher:
    return PublicJobTrendFetcher()


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


def _coerce_date(value: Any) -> date:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    return date.fromisoformat(str(value)[:10])


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
    "/fetch",
    response_model=ApiResponse[JdFetchResponse],
    summary="Fetch a public job description by keyword or URL",
)
async def fetch_public_jd(
    payload: JdFetchRequest,
    fetcher: PublicJobFetcher = Depends(get_public_job_fetcher),
) -> ApiResponse[JdFetchResponse]:
    try:
        data = await fetcher.fetch(payload)
    except PublicJdFetchError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return ApiResponse(code=0, message="success", data=data)


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


@router.get(
    "/trend",
    response_model=ApiResponse[JdTrendResponse],
    summary="Count submitted JDs by day",
)
async def get_jd_trend(
    days: int = Query(30, ge=7, le=90),
    repository: JdReadRepository = Depends(get_jd_read_repository),
) -> ApiResponse[JdTrendResponse]:
    return ApiResponse(
        code=0,
        message="success",
        data=await repository.get_jd_trend(days=days),
    )


@router.get(
    "/market-trend",
    response_model=ApiResponse[JobMarketTrendResponse],
    summary="Count matching job descriptions by year",
)
async def get_job_market_trend(
    keyword: str = Query(..., min_length=2, max_length=100),
    years: int = Query(5, ge=2, le=10),
    source_url: str | None = Query(None, max_length=2000),
    fetcher: PublicJobTrendFetcher = Depends(get_public_job_trend_fetcher),
) -> ApiResponse[JobMarketTrendResponse]:
    try:
        data = await fetcher.fetch(keyword=keyword, years=years, source_url=source_url)
    except PublicJdFetchError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return ApiResponse(code=0, message="success", data=data)


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
