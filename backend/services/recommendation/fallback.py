from __future__ import annotations

import re
from dataclasses import dataclass

from backend.services.embedding_service import EmbeddingService
from backend.services.matching.major_matcher import MajorMatchResult
from backend.services.vector_service import VectorSearchResult, VectorService


@dataclass(frozen=True)
class PopularMajor:
    name: str
    code: str
    category: str
    reason: str


POPULAR_MAJORS: tuple[PopularMajor, ...] = (
    PopularMajor("计算机科学与技术", "080901", "工学", "通用技术岗位覆盖面广"),
    PopularMajor("软件工程", "080902", "工学", "适合软件开发和工程实践方向"),
    PopularMajor("数据科学与大数据技术", "080910T", "工学", "适合数据分析和智能应用方向"),
    PopularMajor("人工智能", "080717T", "工学", "适合机器学习和智能系统方向"),
    PopularMajor("信息管理与信息系统", "120102", "管理学", "兼顾业务、数据和信息系统能力"),
)


_POPULAR_MAJOR_BY_CODE = {major.code: major for major in POPULAR_MAJORS}


KEYWORD_MAJOR_RULES: tuple[tuple[tuple[str, ...], PopularMajor], ...] = (
    (
        ("python", "java", "后端", "backend", "api", "软件", "开发"),
        _POPULAR_MAJOR_BY_CODE["080902"],
    ),
    (("机器学习", "深度学习", "人工智能", "ai", "llm", "算法"), _POPULAR_MAJOR_BY_CODE["080717T"]),
    (("数据", "分析", "大数据", "bi", "etl", "统计"), _POPULAR_MAJOR_BY_CODE["080910T"]),
    (("产品", "业务", "需求", "信息系统", "项目管理"), _POPULAR_MAJOR_BY_CODE["120102"]),
    (("网络", "安全", "linux", "系统", "运维"), _POPULAR_MAJOR_BY_CODE["080901"]),
)


class RecommendationFallbackService:
    def __init__(
        self,
        *,
        embedding_service: EmbeddingService | None = None,
        vector_service: VectorService | None = None,
        popular_majors: tuple[PopularMajor, ...] = POPULAR_MAJORS,
    ) -> None:
        self.embedding_service = embedding_service
        self.vector_service = vector_service
        self.popular_majors = popular_majors

    async def match_by_full_text_embedding(
        self,
        jd_text: str,
        *,
        top_n: int = 5,
    ) -> list[MajorMatchResult]:
        normalized_text = self._validate_jd_text(jd_text)
        if self.embedding_service is None or self.vector_service is None:
            raise RuntimeError(
                "embedding_service and vector_service are required for full-text fallback"
            )
        top_n = self._validate_top_n(top_n)
        embedding = await self.embedding_service.embed_text(normalized_text)
        candidates = await self.vector_service.search_majors(embedding, top_k=top_n)
        return [
            self._from_vector_result(candidate, rank=index)
            for index, candidate in enumerate(candidates, start=1)
        ]

    def should_use_popular_fallback(
        self,
        matches: list[MajorMatchResult],
        *,
        min_final_score: float = 0.35,
    ) -> bool:
        if not matches:
            return True
        return max(match.final_score for match in matches) < min_final_score

    def popular_recommendations(self, *, top_n: int = 5) -> list[MajorMatchResult]:
        top_n = self._validate_top_n(top_n)
        return [
            self._from_popular_major(major, rank=index)
            for index, major in enumerate(self.popular_majors[:top_n], start=1)
        ]

    def keyword_recommendations(self, jd_text: str, *, top_n: int = 5) -> list[MajorMatchResult]:
        text = self._validate_jd_text(jd_text).casefold()
        top_n = self._validate_top_n(top_n)
        scored: list[tuple[int, PopularMajor, list[str]]] = []
        seen_codes: set[str] = set()
        for keywords, major in KEYWORD_MAJOR_RULES:
            matched_keywords = [
                keyword for keyword in keywords if self._contains_keyword(text, keyword)
            ]
            if matched_keywords and major.code not in seen_codes:
                scored.append((len(matched_keywords), major, matched_keywords))
                seen_codes.add(major.code)

        if not scored:
            return self.popular_recommendations(top_n=top_n)

        scored.sort(key=lambda item: (-item[0], item[1].name))
        return [
            self._from_popular_major(
                major,
                rank=index,
                matched_keywords=keywords,
                final_score=min(1.0, 0.45 + 0.1 * score),
            )
            for index, (score, major, keywords) in enumerate(scored[:top_n], start=1)
        ]

    async def recover(
        self,
        jd_text: str,
        *,
        extracted_skill_count: int,
        current_matches: list[MajorMatchResult] | None = None,
        deepseek_available: bool = True,
        top_n: int = 5,
        min_final_score: float = 0.35,
    ) -> list[MajorMatchResult]:
        if not deepseek_available:
            return self.keyword_recommendations(jd_text, top_n=top_n)
        if extracted_skill_count == 0:
            return await self.match_by_full_text_embedding(jd_text, top_n=top_n)
        matches = current_matches or []
        if self.should_use_popular_fallback(matches, min_final_score=min_final_score):
            return self.popular_recommendations(top_n=top_n)
        return matches[:top_n]

    def _from_vector_result(self, result: VectorSearchResult, *, rank: int) -> MajorMatchResult:
        major = result.item
        return MajorMatchResult(
            major_id=result.id,
            major_name=result.name or getattr(major, "name", "") or "",
            major_code=getattr(major, "code", None),
            major_category=result.category or getattr(major, "category", None),
            similarity_score=result.similarity_score,
            coverage_score=0.0,
            final_score=result.similarity_score,
            matched_skills=[],
            missing_skills=[],
            match_details={"fallback": "full_text_embedding", "rank": rank},
        )

    def _from_popular_major(
        self,
        major: PopularMajor,
        *,
        rank: int,
        matched_keywords: list[str] | None = None,
        final_score: float | None = None,
    ) -> MajorMatchResult:
        score = round(final_score if final_score is not None else max(0.4, 0.75 - rank * 0.05), 4)
        return MajorMatchResult(
            major_id=None,
            major_name=major.name,
            major_code=major.code,
            major_category=major.category,
            similarity_score=score,
            coverage_score=0.0,
            final_score=score,
            matched_skills=list(matched_keywords or []),
            missing_skills=[],
            match_details={
                "fallback": "keyword" if matched_keywords else "popular",
                "reason": major.reason,
                "rank": rank,
            },
        )

    def _contains_keyword(self, text: str, keyword: str) -> bool:
        if re.search(r"[\u4e00-\u9fff]", keyword):
            return keyword in text
        return (
            re.search(
                rf"(?<![A-Za-z0-9_+#.]){re.escape(keyword)}(?![A-Za-z0-9_+#.])", text, re.IGNORECASE
            )
            is not None
        )

    def _validate_jd_text(self, jd_text: str) -> str:
        normalized = jd_text.strip()
        if not normalized:
            raise ValueError("jd_text cannot be empty")
        return normalized

    def _validate_top_n(self, top_n: int) -> int:
        if top_n < 1:
            raise ValueError("top_n must be at least 1")
        return top_n
