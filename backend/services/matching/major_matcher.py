from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Sequence

from backend.services.jd_service import ExtractedSkillResult, JdService
from backend.services.matching._utils import aggregate_embedding
from backend.services.vector_service import VectorSearchResult, VectorService


MAJOR_CATEGORY_TO_SKILL_OVERLAP: dict[str, set[str]] = {
    "工学": {
        "programming_language",
        "framework",
        "database",
        "devops",
        "ai",
        "data",
        "backend",
        "frontend",
        "cloud",
        "testing",
        "tool",
        "operating_system",
        "architecture",
        "domain_knowledge",
    },
    "管理学": {"soft_skill", "domain_knowledge", "data", "tool"},
    "经济学": {"data", "domain_knowledge", "soft_skill"},
    "理学": {"data", "ai", "programming_language", "domain_knowledge"},
    "医学": {"domain_knowledge", "data", "soft_skill"},
    "文学": {"soft_skill", "domain_knowledge", "tool"},
    "法学": {"soft_skill", "domain_knowledge", "data"},
    "教育学": {"soft_skill", "domain_knowledge", "data"},
    "艺术学": {"frontend", "tool", "soft_skill", "domain_knowledge"},
    "农学": {"domain_knowledge", "data", "ai", "tool"},
}


@dataclass(frozen=True)
class MajorMatchResult:
    major_id: int | None
    major_name: str
    major_code: str | None
    major_category: str | None
    similarity_score: float
    coverage_score: float
    final_score: float
    matched_skills: list[str]
    missing_skills: list[str]
    match_details: dict[str, Any]


class MajorMatcher:
    def __init__(
        self,
        *,
        vector_service: VectorService | None = None,
        jd_service: JdService | None = None,
        similarity_weight: float = 0.7,
        coverage_weight: float = 0.3,
    ) -> None:
        self.vector_service = vector_service
        self.jd_service = jd_service
        self.similarity_weight = float(similarity_weight)
        self.coverage_weight = float(coverage_weight)
        self._validate_weights()

    async def match_skills_to_majors(
        self,
        skills: Sequence[ExtractedSkillResult],
        *,
        top_n: int = 10,
        candidate_multiplier: int = 3,
    ) -> list[MajorMatchResult]:
        limit = self._validate_positive_int(top_n, "top_n")
        multiplier = self._validate_positive_int(candidate_multiplier, "candidate_multiplier")
        normalized_skills = list(skills)
        if not normalized_skills:
            return []
        if self.vector_service is None:
            raise RuntimeError("vector_service is required for major matching")

        query_embedding = self._aggregate_embedding([skill.embedding for skill in normalized_skills])
        candidates = await self.vector_service.search_majors(
            query_embedding,
            top_k=max(limit, limit * multiplier),
        )
        results = [
            self._to_major_match(candidate, normalized_skills)
            for candidate in candidates
        ]
        return sorted(results, key=lambda item: (-item.final_score, item.major_name.casefold()))[:limit]

    async def match_jd_to_majors(
        self,
        jd_text: str,
        *,
        top_n: int = 10,
        candidate_multiplier: int = 3,
    ) -> list[MajorMatchResult]:
        if self.jd_service is None:
            raise RuntimeError("jd_service is required for JD major matching")
        extraction = await self.jd_service.extract_skills(jd_text)
        return await self.match_skills_to_majors(
            extraction.skills,
            top_n=top_n,
            candidate_multiplier=candidate_multiplier,
        )

    def _to_major_match(
        self,
        candidate: VectorSearchResult,
        skills: list[ExtractedSkillResult],
    ) -> MajorMatchResult:
        matched_skills, missing_skills = self._split_covered_skills(candidate.item, skills)
        coverage_score = round(len(matched_skills) / len(skills), 4) if skills else 0.0
        similarity_score = candidate.similarity_score
        final_score = round(
            similarity_score * self.similarity_weight
            + coverage_score * self.coverage_weight,
            4,
        )
        major_code = getattr(candidate.item, "code", None)
        major_category = candidate.category or getattr(candidate.item, "category", None)
        major_name = candidate.name or getattr(candidate.item, "name", "") or ""
        return MajorMatchResult(
            major_id=candidate.id,
            major_name=major_name,
            major_code=major_code,
            major_category=major_category,
            similarity_score=similarity_score,
            coverage_score=coverage_score,
            final_score=final_score,
            matched_skills=matched_skills,
            missing_skills=missing_skills,
            match_details={
                "similarity_weight": self.similarity_weight,
                "coverage_weight": self.coverage_weight,
                "skill_count": len(skills),
                "matched_skill_count": len(matched_skills),
            },
        )

    def _split_covered_skills(
        self,
        major: Any,
        skills: list[ExtractedSkillResult],
    ) -> tuple[list[str], list[str]]:
        matched: list[str] = []
        missing: list[str] = []
        major_text = self._major_search_text(major)
        allowed_categories = MAJOR_CATEGORY_TO_SKILL_OVERLAP.get(
            str(getattr(major, "category", "") or ""),
            set(),
        )
        for skill in skills:
            skill_name = skill.normalized_name or skill.name
            if (
                skill.category in allowed_categories
                or self._contains_skill_name(major_text, skill_name)
                or self._contains_skill_name(major_text, skill.name)
            ):
                matched.append(skill_name)
            else:
                missing.append(skill_name)
        return matched, missing

    def _major_search_text(self, major: Any) -> str:
        parts: list[str] = []
        for attr in ("name", "category", "description"):
            value = getattr(major, attr, None)
            if value:
                parts.append(str(value))
        curriculum = getattr(major, "curriculum", None)
        if isinstance(curriculum, dict):
            for value in curriculum.values():
                if isinstance(value, list):
                    parts.extend(str(item) for item in value)
                elif value:
                    parts.append(str(value))
        elif isinstance(curriculum, list):
            parts.extend(str(item) for item in curriculum)
        elif curriculum:
            parts.append(str(curriculum))
        return " ".join(parts).casefold()

    def _contains_skill_name(self, major_text: str, skill_name: str) -> bool:
        normalized_name = skill_name.strip()
        if not normalized_name:
            return False
        pattern = rf"(?<![A-Za-z0-9_+#.]){re.escape(normalized_name)}(?![A-Za-z0-9_+#.])"
        return re.search(pattern, major_text, flags=re.IGNORECASE) is not None

    def _aggregate_embedding(self, embeddings: list[list[float]]) -> list[float]:
        return aggregate_embedding(embeddings)

    def _validate_weights(self) -> None:
        if self.similarity_weight < 0 or self.coverage_weight < 0:
            raise ValueError("matcher weights cannot be negative")
        total = self.similarity_weight + self.coverage_weight
        if total <= 0:
            raise ValueError("matcher weights must sum to a positive value")
        self.similarity_weight = self.similarity_weight / total
        self.coverage_weight = self.coverage_weight / total

    def _validate_positive_int(self, value: int, name: str) -> int:
        if value < 1:
            raise ValueError(f"{name} must be at least 1")
        return value
