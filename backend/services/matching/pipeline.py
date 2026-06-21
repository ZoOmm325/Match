from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from backend.services.jd_service import ExtractedSkillResult, JdExtractionResult, JdService
from backend.services.matching.major_matcher import MajorMatcher, MajorMatchResult
from backend.services.matching.skill_matcher import SkillMatcher, SkillMatchResult
from backend.services.vector_service import VectorService


@dataclass(frozen=True)
class MatchingPipelineResult:
    jd_id: int | None
    extracted_skills: list[ExtractedSkillResult]
    skill_matches: list[SkillMatchResult]
    major_matches: list[MajorMatchResult]
    persisted_count: int = 0
    already_processed: bool = False


class MatchResultRepository(Protocol):
    async def save_match_results(
        self,
        *,
        jd_id: int,
        major_matches: list[MajorMatchResult],
    ) -> int:
        ...


class SqlAlchemyMatchResultRepository:
    def __init__(self, session: Any) -> None:
        self.session = session

    async def save_match_results(
        self,
        *,
        jd_id: int,
        major_matches: list[MajorMatchResult],
    ) -> int:
        from sqlalchemy import select

        from backend.models.match_result import MatchResult

        saved_count = 0
        for rank, match in enumerate(major_matches, start=1):
            if match.major_id is None:
                continue
            result = await self.session.execute(
                select(MatchResult).where(
                    MatchResult.jd_id == jd_id,
                    MatchResult.major_id == match.major_id,
                )
            )
            row = result.scalar_one_or_none()
            values = {
                "jd_id": jd_id,
                "major_id": match.major_id,
                "similarity_score": match.similarity_score,
                "final_score": match.final_score,
                "rank": rank,
                "match_details": self._match_details(match),
            }
            if row is None:
                self.session.add(MatchResult(**values))
            else:
                for key, value in values.items():
                    setattr(row, key, value)
            saved_count += 1

        await self.session.commit()
        return saved_count

    def _match_details(self, match: MajorMatchResult) -> dict[str, Any]:
        details = dict(match.match_details)
        details.update(
            {
                "major_name": match.major_name,
                "major_code": match.major_code,
                "major_category": match.major_category,
                "matched_skills": match.matched_skills,
                "missing_skills": match.missing_skills,
                "coverage_score": match.coverage_score,
            }
        )
        return details


class MatchingPipeline:
    def __init__(
        self,
        *,
        jd_service: JdService | None = None,
        skill_matcher: SkillMatcher | None = None,
        major_matcher: MajorMatcher | None = None,
        repository: MatchResultRepository | None = None,
        session: Any | None = None,
    ) -> None:
        vector_service = VectorService(session) if session is not None else None
        self.jd_service = jd_service or JdService(session=session)
        self.skill_matcher = skill_matcher or SkillMatcher(
            jd_service=self.jd_service,
            vector_service=vector_service,
        )
        self.major_matcher = major_matcher or MajorMatcher(
            jd_service=self.jd_service,
            vector_service=vector_service,
        )
        self.repository = repository
        if self.repository is None and session is not None:
            self.repository = SqlAlchemyMatchResultRepository(session)

    async def run(
        self,
        jd_text: str,
        *,
        skill_top_k: int = 20,
        major_top_n: int = 10,
        skill_threshold: float = 0.5,
        persist: bool = True,
    ) -> MatchingPipelineResult:
        normalized_jd_text = jd_text.strip()
        if not normalized_jd_text:
            raise ValueError("jd_text cannot be empty")
        if skill_top_k < 1:
            raise ValueError("skill_top_k must be at least 1")
        if major_top_n < 1:
            raise ValueError("major_top_n must be at least 1")

        extraction = await self.jd_service.extract_skills(normalized_jd_text)
        skill_matches = await self.skill_matcher.match_extracted_skills(
            extraction.skills,
            top_k=skill_top_k,
            threshold=skill_threshold,
        )
        major_matches = await self.major_matcher.match_skills_to_majors(
            extraction.skills,
            top_n=major_top_n,
        )
        persisted_count = await self._persist_results(extraction, major_matches, persist=persist)
        return MatchingPipelineResult(
            jd_id=extraction.jd_id,
            extracted_skills=extraction.skills,
            skill_matches=skill_matches,
            major_matches=major_matches,
            persisted_count=persisted_count,
            already_processed=extraction.already_processed,
        )

    async def _persist_results(
        self,
        extraction: JdExtractionResult,
        major_matches: list[MajorMatchResult],
        *,
        persist: bool,
    ) -> int:
        if not persist or self.repository is None or extraction.jd_id is None:
            return 0
        return await self.repository.save_match_results(
            jd_id=extraction.jd_id,
            major_matches=major_matches,
        )
