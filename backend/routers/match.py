from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any, Protocol

from fastapi import APIRouter, Depends, HTTPException, status

from backend.schemas.jd_extraction import ApiResponse
from backend.schemas.match_result import (
    MatchBySkillsRequest,
    MatchHistoryResponseData,
    MatchRecommendationResponse,
    MatchRequest,
    MatchResponseData,
    SkillMatchInput,
)
from backend.services.embedding_service import EmbeddingService, EmbeddingServiceError
from backend.services.jd_service import ExtractedSkillResult
from backend.services.matching.major_matcher import MajorMatcher
from backend.services.matching.pipeline import MatchingPipeline
from backend.services.recommendation.ranker import RankedRecommendation, RecommendationRanker
from backend.services.vector_service import VectorService

router = APIRouter(prefix="/match", tags=["Match"])


class MatchHistoryRepository(Protocol):
    async def get_match_history(self, jd_id: int) -> MatchHistoryResponseData | None: ...


class RankedMatchResultRepository(Protocol):
    async def save_ranked_recommendations(
        self,
        *,
        jd_id: int | None,
        recommendations: list[RankedRecommendation],
    ) -> int: ...


class SqlAlchemyMatchHistoryRepository:
    def __init__(self, session: Any) -> None:
        self.session = session

    async def get_match_history(self, jd_id: int) -> MatchHistoryResponseData | None:
        from sqlalchemy import select

        from backend.models.jd import Jd
        from backend.models.major import Major
        from backend.models.match_result import MatchResult

        jd_result = await self.session.execute(select(Jd.id).where(Jd.id == jd_id))
        if jd_result.scalar_one_or_none() is None:
            return None

        result = await self.session.execute(
            select(MatchResult, Major)
            .join(Major, MatchResult.major_id == Major.id)
            .where(MatchResult.jd_id == jd_id)
            .order_by(MatchResult.rank.asc())
        )
        recommendations = [
            _history_row_to_recommendation(match_result, major)
            for match_result, major in result.all()
        ]
        return MatchHistoryResponseData(jd_id=jd_id, recommendations=recommendations)


class SqlAlchemyRankedMatchResultRepository:
    def __init__(self, session: Any) -> None:
        self.session = session

    async def save_ranked_recommendations(
        self,
        *,
        jd_id: int | None,
        recommendations: list[RankedRecommendation],
    ) -> int:
        if jd_id is None:
            return 0

        from sqlalchemy import select

        from backend.models.match_result import MatchResult

        saved_count = 0
        for recommendation in recommendations:
            if recommendation.major_id is None:
                continue
            result = await self.session.execute(
                select(MatchResult).where(
                    MatchResult.jd_id == jd_id,
                    MatchResult.major_id == recommendation.major_id,
                )
            )
            row = result.scalar_one_or_none()
            values = {
                "jd_id": jd_id,
                "major_id": recommendation.major_id,
                "similarity_score": recommendation.skill_similarity_score,
                "final_score": recommendation.final_score,
                "rank": recommendation.rank,
                "match_details": _ranked_match_details(recommendation),
            }
            if row is None:
                self.session.add(MatchResult(**values))
            else:
                for key, value in values.items():
                    setattr(row, key, value)
            saved_count += 1

        await self.session.commit()
        return saved_count


async def get_session() -> AsyncIterator[Any]:
    from backend.core.database import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        yield session


def get_matching_pipeline(session: Any = Depends(get_session)) -> MatchingPipeline:
    return MatchingPipeline(session=session)


def get_major_matcher(session: Any = Depends(get_session)) -> MajorMatcher:
    return MajorMatcher(vector_service=VectorService(session))


def get_recommendation_ranker() -> RecommendationRanker:
    return RecommendationRanker()


def get_embedding_service() -> EmbeddingService:
    return EmbeddingService()


def get_match_history_repository(session: Any = Depends(get_session)) -> MatchHistoryRepository:
    return SqlAlchemyMatchHistoryRepository(session)


def get_ranked_match_result_repository(
    session: Any = Depends(get_session),
) -> RankedMatchResultRepository:
    return SqlAlchemyRankedMatchResultRepository(session)


@router.post(
    "", response_model=ApiResponse[MatchResponseData], summary="Run full JD matching pipeline"
)
async def match_jd(
    payload: MatchRequest,
    pipeline: MatchingPipeline = Depends(get_matching_pipeline),
    ranker: RecommendationRanker = Depends(get_recommendation_ranker),
    repository: RankedMatchResultRepository = Depends(get_ranked_match_result_repository),
) -> ApiResponse[MatchResponseData]:
    try:
        result = await pipeline.run(
            payload.jd_text,
            skill_top_k=payload.skill_top_k,
            major_top_n=payload.major_top_n,
            skill_threshold=payload.skill_threshold,
            persist=False,
        )
        recommendations = await ranker.rank_major_matches(
            result.major_matches,
            skills=result.extracted_skills,
            top_n=payload.major_top_n,
            generate_reasons=payload.generate_reasons,
        )
        persisted_count = await repository.save_ranked_recommendations(
            jd_id=result.jd_id,
            recommendations=recommendations,
        )
    except (ValueError, EmbeddingServiceError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return ApiResponse(
        code=0,
        message="success",
        data=MatchResponseData(
            jd_id=result.jd_id,
            extracted_skill_count=len(result.extracted_skills),
            persisted_count=persisted_count,
            already_processed=result.already_processed,
            recommendations=[_ranked_to_response(item) for item in recommendations],
        ),
    )


@router.post(
    "/by-skills",
    response_model=ApiResponse[MatchResponseData],
    summary="Match majors from an explicit skill list",
)
async def match_by_skills(
    payload: MatchBySkillsRequest,
    matcher: MajorMatcher = Depends(get_major_matcher),
    ranker: RecommendationRanker = Depends(get_recommendation_ranker),
    embedding_service: EmbeddingService = Depends(get_embedding_service),
) -> ApiResponse[MatchResponseData]:
    try:
        skills = await _build_extracted_skills(payload.skills, embedding_service)
        major_matches = await matcher.match_skills_to_majors(skills, top_n=payload.top_n)
        recommendations = await ranker.rank_major_matches(
            major_matches,
            skills=skills,
            top_n=payload.top_n,
            generate_reasons=payload.generate_reasons,
        )
    except (ValueError, EmbeddingServiceError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return ApiResponse(
        code=0,
        message="success",
        data=MatchResponseData(
            jd_id=None,
            extracted_skill_count=len(skills),
            persisted_count=0,
            already_processed=False,
            recommendations=[_ranked_to_response(item) for item in recommendations],
        ),
    )


@router.get(
    "/{jd_id}",
    response_model=ApiResponse[MatchHistoryResponseData],
    summary="Get historical match results by JD id",
)
async def get_match_history(
    jd_id: int,
    repository: MatchHistoryRepository = Depends(get_match_history_repository),
) -> ApiResponse[MatchHistoryResponseData]:
    history = await repository.get_match_history(jd_id)
    if history is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Match history not found")
    return ApiResponse(code=0, message="success", data=history)


async def _build_extracted_skills(
    skills: list[SkillMatchInput],
    embedding_service: EmbeddingService,
) -> list[ExtractedSkillResult]:
    missing_embedding_inputs = [
        _embedding_text(skill) for skill in skills if skill.embedding is None
    ]
    generated_embeddings = (
        await embedding_service.embed_texts(missing_embedding_inputs)
        if missing_embedding_inputs
        else []
    )
    if len(generated_embeddings) != len(missing_embedding_inputs):
        raise EmbeddingServiceError("embedding service returned an unexpected number of vectors")
    generated_index = 0
    results: list[ExtractedSkillResult] = []
    for skill in skills:
        if skill.embedding is not None:
            embedding = skill.embedding
        else:
            embedding = generated_embeddings[generated_index]
            generated_index += 1
        results.append(
            ExtractedSkillResult(
                name=skill.name,
                normalized_name=skill.name,
                category=skill.category,
                proficiency_required=skill.proficiency_required,
                embedding=[float(v) for v in embedding],
            )
        )
    return results


def _embedding_text(skill: SkillMatchInput) -> str:
    return (
        f"{skill.name} | category: {skill.category} | " f"proficiency: {skill.proficiency_required}"
    )


def _ranked_to_response(item: RankedRecommendation) -> MatchRecommendationResponse:
    return MatchRecommendationResponse(
        rank=item.rank,
        major_id=item.major_id,
        major_name=item.major_name,
        major_code=item.major_code,
        final_score=item.final_score,
        skill_similarity_score=item.skill_similarity_score,
        skill_coverage_score=item.skill_coverage_score,
        employment_alignment_score=item.employment_alignment_score,
        matched_skills=item.matched_skills,
        missing_skills=item.missing_skills,
        recommendation_reason=item.recommendation_reason,
        score_details=item.score_details,
    )


def _ranked_match_details(item: RankedRecommendation) -> dict[str, Any]:
    details = dict(item.score_details)
    details.update(
        {
            "major_name": item.major_name,
            "major_code": item.major_code,
            "matched_skills": list(item.matched_skills),
            "missing_skills": list(item.missing_skills),
            "skill_similarity_score": item.skill_similarity_score,
            "skill_coverage_score": item.skill_coverage_score,
            "employment_alignment_score": item.employment_alignment_score,
            "recommendation_reason": item.recommendation_reason,
        }
    )
    return details


def _history_row_to_recommendation(match_result: Any, major: Any) -> MatchRecommendationResponse:
    details = match_result.match_details if isinstance(match_result.match_details, dict) else {}
    return MatchRecommendationResponse(
        rank=match_result.rank,
        major_id=match_result.major_id,
        major_name=str(details.get("major_name") or major.name),
        major_code=details.get("major_code") or getattr(major, "code", None),
        final_score=match_result.final_score,
        skill_similarity_score=float(
            details.get("skill_similarity_score", match_result.similarity_score)
        ),
        skill_coverage_score=float(
            details.get("skill_coverage_score", details.get("coverage_score", 0.0))
        ),
        employment_alignment_score=float(details.get("employment_alignment_score", 0.0)),
        matched_skills=list(details.get("matched_skills", [])),
        missing_skills=list(details.get("missing_skills", [])),
        recommendation_reason=str(details.get("recommendation_reason") or "历史匹配结果"),
        score_details=details,
    )
