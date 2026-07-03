from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Sequence

from backend.services.jd_service import ExtractedSkillResult, JdService
from backend.services.matching._utils import aggregate_embedding
from backend.services.vector_service import VectorService


@dataclass(frozen=True)
class SkillMatchResult:
    extracted_skill_name: str
    matched_seed_skill: str
    matched_category: str
    similarity_score: float = field(compare=True)

    @property
    def name(self) -> str:
        return self.matched_seed_skill

    @property
    def category(self) -> str:
        return self.matched_category


class SkillMatcher:
    """Match JD-extracted skills to canonical seed skills via vector similarity.

    Two strategies are exposed:

    * ``match()``          – aggregate extracted-skill embeddings into a
                             single centroid vector, then query the seed
                             skill knowledge base once (fast, holistic).
    * ``match_per_skill()`` – query per extracted-skill embedding; tracks
                              which extracted skill produced each match
                              (higher precision, traceable).
    """

    def __init__(
        self,
        *,
        jd_service: JdService | None = None,
        vector_service: VectorService | None = None,
    ) -> None:
        self.jd_service = jd_service or JdService()
        self.vector_service = vector_service

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def match(
        self,
        jd_text: str,
        *,
        top_k: int = 20,
        threshold: float = 0.5,
    ) -> list[SkillMatchResult]:
        """Aggregate extracted-skill embeddings and return top-k seed matches."""
        self._validate_input(jd_text, top_k)
        extraction = await self.jd_service.extract_skills(jd_text)
        if not extraction.skills:
            return []

        aggregated = self._aggregate_embedding([skill.embedding for skill in extraction.skills])
        extracted_skill_name = ", ".join(skill.name for skill in extraction.skills)
        return await self._search_and_merge(
            query_embedding=aggregated,
            extracted_skill_name=extracted_skill_name,
            top_k=top_k,
            threshold=threshold,
        )

    async def match_per_skill(
        self,
        jd_text: str,
        *,
        per_skill_k: int = 5,
        top_k: int = 20,
        threshold: float = 0.5,
    ) -> list[SkillMatchResult]:
        """Search seed skills per extracted-skill embedding; merge with best-score dedup."""
        self._validate_input(jd_text, top_k)
        extraction = await self.jd_service.extract_skills(jd_text)
        return await self.match_extracted_skills(
            extraction.skills,
            per_skill_k=per_skill_k,
            top_k=top_k,
            threshold=threshold,
        )

    async def match_extracted_skills(
        self,
        skills: Sequence[ExtractedSkillResult],
        *,
        per_skill_k: int = 5,
        top_k: int = 20,
        threshold: float = 0.5,
    ) -> list[SkillMatchResult]:
        if top_k < 1:
            raise ValueError("top_k must be at least 1")
        if per_skill_k < 1:
            raise ValueError("per_skill_k must be at least 1")
        extracted_skills = list(skills)
        if not extracted_skills:
            return []

        merged: dict[str, SkillMatchResult] = {}
        for skill in extracted_skills:
            results = await self._search_skills(skill.embedding, top_k=per_skill_k)
            for result in results:
                if result.similarity_score < threshold:
                    continue
                key = result.name.casefold() if result.name else None
                if not key:
                    continue
                if key in merged and merged[key].similarity_score >= result.similarity_score:
                    continue
                merged[key] = SkillMatchResult(
                    extracted_skill_name=skill.name,
                    matched_seed_skill=result.name or "",
                    matched_category=result.category or "other",
                    similarity_score=result.similarity_score,
                )

        ranked = sorted(merged.values(), key=lambda m: m.similarity_score, reverse=True)
        return ranked[:top_k]

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _validate_input(self, jd_text: str, top_k: int) -> None:
        if not jd_text.strip():
            raise ValueError("jd_text cannot be empty")
        if top_k < 1:
            raise ValueError("top_k must be at least 1")

    async def _search_skills(self, query_embedding: list[float], *, top_k: int) -> list[Any]:
        if self.vector_service is None:
            raise RuntimeError("vector_service is required for skill matching")
        return await self.vector_service.search_skills(query_embedding, top_k=top_k)

    async def _search_and_merge(
        self,
        query_embedding: list[float],
        *,
        extracted_skill_name: str,
        top_k: int,
        threshold: float,
    ) -> list[SkillMatchResult]:
        results = await self._search_skills(query_embedding, top_k=max(top_k, 1))
        matches: list[SkillMatchResult] = []
        for result in results:
            if result.similarity_score < threshold:
                continue
            matches.append(
                SkillMatchResult(
                    extracted_skill_name=extracted_skill_name,
                    matched_seed_skill=result.name or "",
                    matched_category=result.category or "other",
                    similarity_score=result.similarity_score,
                )
            )
        return matches

    def _aggregate_embedding(self, embeddings: list[list[float]]) -> list[float]:
        return aggregate_embedding(embeddings)
