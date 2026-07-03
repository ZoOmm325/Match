from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any, Sequence

from backend.core.deepseek_client import DeepSeekClient, get_deepseek_client
from backend.services.jd_service import ExtractedSkillResult
from backend.services.matching.major_matcher import MajorMatchResult
from backend.services.recommendation.scorer import (
    EmploymentEvaluator,
    RecommendationScore,
    RecommendationScorer,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RankedRecommendation:
    rank: int
    major_id: int | None
    major_name: str
    major_code: str | None
    final_score: float
    skill_similarity_score: float
    skill_coverage_score: float
    employment_alignment_score: float
    matched_skills: list[str]
    missing_skills: list[str]
    recommendation_reason: str
    score_details: dict[str, Any]


class RecommendationRanker:
    def __init__(
        self,
        *,
        scorer: RecommendationScorer | None = None,
        deepseek_client: DeepSeekClient | None = None,
    ) -> None:
        self.scorer = scorer or RecommendationScorer()
        self.deepseek_client = deepseek_client

    async def rank_major_matches(
        self,
        major_matches: Sequence[MajorMatchResult],
        *,
        skills: Sequence[ExtractedSkillResult],
        top_n: int = 5,
        generate_reasons: bool = True,
        employment_evaluator: EmploymentEvaluator | None = None,
    ) -> list[RankedRecommendation]:
        scores = await self.scorer.score_major_matches(
            major_matches,
            skills=skills,
            employment_evaluator=employment_evaluator,
        )
        return await self.rank_scores(
            scores,
            top_n=top_n,
            generate_reasons=generate_reasons,
        )

    async def rank_scores(
        self,
        scores: Sequence[RecommendationScore],
        *,
        top_n: int = 5,
        generate_reasons: bool = True,
    ) -> list[RankedRecommendation]:
        limit = self._validate_top_n(top_n)
        ranked_scores = sorted(
            scores,
            key=lambda score: (-score.final_score, score.major_name.casefold()),
        )[:limit]
        if generate_reasons:
            generated = await asyncio.gather(
                *[
                    self._generate_reason(score, rank=index)
                    for index, score in enumerate(ranked_scores, start=1)
                ],
                return_exceptions=True,
            )
            reasons = []
            for index, (score, reason) in enumerate(
                zip(ranked_scores, generated),
                start=1,
            ):
                if isinstance(reason, BaseException):
                    logger.warning(
                        "Recommendation reason generation failed major=%s",
                        score.major_name,
                        exc_info=(type(reason), reason, reason.__traceback__),
                    )
                    reasons.append(self._fallback_reason(score, rank=index))
                else:
                    reasons.append(reason)
        else:
            reasons = [
                self._fallback_reason(score, rank=index)
                for index, score in enumerate(ranked_scores, start=1)
            ]
        return [
            self._to_ranked_recommendation(score, rank=index, reason=reason)
            for index, (score, reason) in enumerate(zip(ranked_scores, reasons), start=1)
        ]

    async def _generate_reason(self, score: RecommendationScore, *, rank: int) -> str:
        response = await self._client().create_chat_completion(
            self._build_reason_messages(score, rank=rank),
            temperature=0.2,
        )
        reason = self._response_content(response).strip()
        return reason or self._fallback_reason(score, rank=rank)

    def _build_reason_messages(
        self, score: RecommendationScore, *, rank: int
    ) -> list[dict[str, str]]:
        return [
            {
                "role": "system",
                "content": (
                    "You generate concise Chinese recommendation explanations for "
                    "university major matching. Mention matched skills, missing skills, "
                    "and why the major is recommended. Keep it under 120 Chinese characters."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"排名: {rank}\n"
                    f"专业: {score.major_name}\n"
                    f"最终得分: {score.final_score:.4f}\n"
                    f"技能相似度: {score.skill_similarity_score:.4f}\n"
                    f"技能覆盖率: {score.skill_coverage_score:.4f}\n"
                    f"就业方向匹配度: {score.employment_alignment_score:.4f}\n"
                    f"匹配技能: {', '.join(score.matched_skills) or '无'}\n"
                    f"缺失技能: {', '.join(score.missing_skills) or '无'}"
                ),
            },
        ]

    def _to_ranked_recommendation(
        self,
        score: RecommendationScore,
        *,
        rank: int,
        reason: str,
    ) -> RankedRecommendation:
        return RankedRecommendation(
            rank=rank,
            major_id=score.major_id,
            major_name=score.major_name,
            major_code=score.major_code,
            final_score=score.final_score,
            skill_similarity_score=score.skill_similarity_score,
            skill_coverage_score=score.skill_coverage_score,
            employment_alignment_score=score.employment_alignment_score,
            matched_skills=list(score.matched_skills),
            missing_skills=list(score.missing_skills),
            recommendation_reason=reason,
            score_details=dict(score.score_details),
        )

    def _fallback_reason(self, score: RecommendationScore, *, rank: int) -> str:
        matched = "、".join(score.matched_skills) if score.matched_skills else "岗位核心技能"
        missing = "、".join(score.missing_skills) if score.missing_skills else "暂无明显缺口"
        return (
            f"第{rank}推荐{score.major_name}，匹配{matched}，"
            f"缺口为{missing}，综合得分{score.final_score:.2f}。"
        )

    def _response_content(self, response: Any) -> str:
        if isinstance(response, dict):
            return str(response["choices"][0]["message"]["content"])
        return str(response.choices[0].message.content)

    def _client(self) -> DeepSeekClient:
        if self.deepseek_client is None:
            self.deepseek_client = get_deepseek_client()
        return self.deepseek_client

    def _validate_top_n(self, top_n: int) -> int:
        if top_n < 1:
            raise ValueError("top_n must be at least 1")
        return top_n
