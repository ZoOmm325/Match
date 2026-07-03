from __future__ import annotations

import asyncio
import inspect
import logging
import math
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from typing import Any

from backend.services.jd_service import ExtractedSkillResult
from backend.services.matching.major_matcher import MajorMatchResult

EmploymentEvaluator = Callable[
    [Sequence[ExtractedSkillResult], MajorMatchResult],
    float | Awaitable[float],
]

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ScoreWeights:
    skill_similarity: float = 0.5
    skill_coverage: float = 0.3
    employment_alignment: float = 0.2

    def normalized(self) -> "ScoreWeights":
        for value in (self.skill_similarity, self.skill_coverage, self.employment_alignment):
            if value < 0:
                raise ValueError("score weights cannot be negative")
        total = self.skill_similarity + self.skill_coverage + self.employment_alignment
        if total <= 0:
            raise ValueError("score weights must sum to a positive value")
        return ScoreWeights(
            skill_similarity=self.skill_similarity / total,
            skill_coverage=self.skill_coverage / total,
            employment_alignment=self.employment_alignment / total,
        )


@dataclass(frozen=True)
class RecommendationScore:
    major_id: int | None
    major_name: str
    major_code: str | None
    skill_similarity_score: float
    skill_coverage_score: float
    employment_alignment_score: float
    final_score: float
    matched_skills: list[str]
    missing_skills: list[str]
    score_details: dict[str, Any]


class RecommendationScorer:
    def __init__(
        self,
        *,
        weights: ScoreWeights | None = None,
        employment_evaluator: EmploymentEvaluator | None = None,
    ) -> None:
        self.weights = (weights or ScoreWeights()).normalized()
        self.employment_evaluator = employment_evaluator

    def score_dimensions(
        self,
        *,
        skill_similarity_score: float,
        skill_coverage_score: float,
        employment_alignment_score: float,
    ) -> dict[str, float]:
        similarity = self._normalize_score(skill_similarity_score)
        coverage = self._normalize_score(skill_coverage_score)
        employment = self._normalize_score(employment_alignment_score)
        final_score = round(
            similarity * self.weights.skill_similarity
            + coverage * self.weights.skill_coverage
            + employment * self.weights.employment_alignment,
            4,
        )
        return {
            "skill_similarity_score": similarity,
            "skill_coverage_score": coverage,
            "employment_alignment_score": employment,
            "final_score": final_score,
        }

    def score_major_match(
        self,
        major_match: MajorMatchResult,
        *,
        employment_alignment_score: float = 0.0,
    ) -> RecommendationScore:
        dimensions = self.score_dimensions(
            skill_similarity_score=major_match.similarity_score,
            skill_coverage_score=major_match.coverage_score,
            employment_alignment_score=employment_alignment_score,
        )
        return self._build_recommendation_score(major_match, dimensions)

    async def score_major_match_with_evaluator(
        self,
        major_match: MajorMatchResult,
        *,
        skills: Sequence[ExtractedSkillResult],
        employment_evaluator: EmploymentEvaluator | None = None,
    ) -> RecommendationScore:
        evaluator = employment_evaluator or self.employment_evaluator
        if evaluator is None:
            employment_score = 0.0
        else:
            evaluation = evaluator(skills, major_match)
            if inspect.isawaitable(evaluation):
                employment_score = float(await evaluation)
            else:
                employment_score = float(evaluation)
        return self.score_major_match(
            major_match,
            employment_alignment_score=employment_score,
        )

    async def score_major_matches(
        self,
        major_matches: Sequence[MajorMatchResult],
        *,
        skills: Sequence[ExtractedSkillResult],
        employment_evaluator: EmploymentEvaluator | None = None,
    ) -> list[RecommendationScore]:
        evaluated = await asyncio.gather(
            *[
                self.score_major_match_with_evaluator(
                    major_match,
                    skills=skills,
                    employment_evaluator=employment_evaluator,
                )
                for major_match in major_matches
            ],
            return_exceptions=True,
        )
        scores: list[RecommendationScore] = []
        for major_match, result in zip(major_matches, evaluated):
            if isinstance(result, BaseException):
                logger.warning(
                    "Employment evaluation failed major=%s",
                    major_match.major_name,
                    exc_info=(type(result), result, result.__traceback__),
                )
                scores.append(self.score_major_match(major_match))
            else:
                scores.append(result)
        return sorted(scores, key=lambda score: (-score.final_score, score.major_name.casefold()))

    def _build_recommendation_score(
        self,
        major_match: MajorMatchResult,
        dimensions: dict[str, float],
    ) -> RecommendationScore:
        return RecommendationScore(
            major_id=major_match.major_id,
            major_name=major_match.major_name,
            major_code=major_match.major_code,
            skill_similarity_score=dimensions["skill_similarity_score"],
            skill_coverage_score=dimensions["skill_coverage_score"],
            employment_alignment_score=dimensions["employment_alignment_score"],
            final_score=dimensions["final_score"],
            matched_skills=list(major_match.matched_skills),
            missing_skills=list(major_match.missing_skills),
            score_details={
                "weights": {
                    "skill_similarity": self.weights.skill_similarity,
                    "skill_coverage": self.weights.skill_coverage,
                    "employment_alignment": self.weights.employment_alignment,
                },
                "source_major_score": major_match.final_score,
                "major_match_details": dict(major_match.match_details),
            },
        )

    def _normalize_score(self, score: float) -> float:
        value = float(score)
        if math.isnan(value):
            return 0.0
        return round(max(0.0, min(1.0, value)), 4)
