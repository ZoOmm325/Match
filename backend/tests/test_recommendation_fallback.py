import asyncio
from types import SimpleNamespace

import pytest

from backend.services.matching import MajorMatchResult
from backend.services.recommendation import RecommendationFallbackService
from backend.services.vector_service import VectorSearchResult


class FakeEmbeddingService:
    def __init__(self):
        self.calls = []

    async def embed_text(self, text):
        self.calls.append(text)
        return [0.1] * 1024


class FakeVectorService:
    def __init__(self, results):
        self.results = results
        self.calls = []

    async def search_majors(self, embedding, *, top_k):
        self.calls.append({"embedding": embedding, "top_k": top_k})
        return self.results


def vector_candidate(name, score, *, major_id=1, code="080902", category="工学"):
    item = SimpleNamespace(id=major_id, name=name, code=code, category=category)
    return VectorSearchResult(
        item=item,
        similarity_score=score,
        table="majors",
        id=major_id,
        name=name,
        category=category,
    )


def major_match(name="软件工程", final_score=0.8):
    return MajorMatchResult(
        major_id=1,
        major_name=name,
        major_code="080902",
        major_category="工学",
        similarity_score=final_score,
        coverage_score=0.5,
        final_score=final_score,
        matched_skills=["Python"],
        missing_skills=[],
        match_details={},
    )


def test_full_text_embedding_fallback_searches_majors():
    embedding = FakeEmbeddingService()
    vector = FakeVectorService([vector_candidate("软件工程", 0.82)])
    service = RecommendationFallbackService(
        embedding_service=embedding,
        vector_service=vector,
    )

    results = asyncio.run(service.match_by_full_text_embedding("  Need Python backend.  ", top_n=3))

    assert embedding.calls == ["Need Python backend."]
    assert vector.calls == [{"embedding": [0.1] * 1024, "top_k": 3}]
    assert results[0].major_name == "软件工程"
    assert results[0].final_score == 0.82
    assert results[0].match_details["fallback"] == "full_text_embedding"


def test_low_score_or_empty_matches_use_popular_fallback():
    service = RecommendationFallbackService()

    assert service.should_use_popular_fallback([]) is True
    assert (
        service.should_use_popular_fallback([major_match(final_score=0.2)], min_final_score=0.35)
        is True
    )
    assert (
        service.should_use_popular_fallback([major_match(final_score=0.6)], min_final_score=0.35)
        is False
    )

    results = service.popular_recommendations(top_n=2)

    assert [item.major_name for item in results] == ["计算机科学与技术", "软件工程"]
    assert all(item.match_details["fallback"] == "popular" for item in results)


def test_keyword_fallback_uses_jd_keywords_when_deepseek_unavailable():
    service = RecommendationFallbackService()

    results = service.keyword_recommendations(
        "需要 Python API 后端开发，并熟悉软件工程实践", top_n=2
    )

    assert results[0].major_name == "软件工程"
    assert results[0].match_details["fallback"] == "keyword"
    assert {"python", "api", "后端", "软件", "开发"}.intersection(results[0].matched_skills)


def test_keyword_fallback_returns_popular_when_no_keyword_matches():
    service = RecommendationFallbackService()

    results = service.keyword_recommendations("岗位要求积极主动，学习能力强", top_n=1)

    assert len(results) == 1
    assert results[0].match_details["fallback"] == "popular"


def test_recover_selects_expected_fallback_strategy():
    embedding = FakeEmbeddingService()
    vector = FakeVectorService([vector_candidate("人工智能", 0.78, major_id=2, code="080717T")])
    service = RecommendationFallbackService(embedding_service=embedding, vector_service=vector)

    keyword_results = asyncio.run(
        service.recover(
            "需要机器学习算法工程师",
            extracted_skill_count=3,
            deepseek_available=False,
        )
    )
    assert keyword_results[0].major_name == "人工智能"

    full_text_results = asyncio.run(
        service.recover(
            "泛技术岗位描述",
            extracted_skill_count=0,
            top_n=1,
        )
    )
    assert full_text_results[0].major_name == "人工智能"

    popular_results = asyncio.run(
        service.recover(
            "Need something.",
            extracted_skill_count=2,
            current_matches=[major_match(final_score=0.1)],
            min_final_score=0.35,
            top_n=1,
        )
    )
    assert popular_results[0].match_details["fallback"] == "popular"

    current = [major_match(final_score=0.9)]
    assert (
        asyncio.run(
            service.recover(
                "Need Python.",
                extracted_skill_count=2,
                current_matches=current,
            )
        )
        == current
    )


def test_fallback_validates_inputs_and_dependencies():
    service = RecommendationFallbackService()

    with pytest.raises(ValueError, match="jd_text"):
        service.keyword_recommendations("   ")

    with pytest.raises(ValueError, match="top_n"):
        service.popular_recommendations(top_n=0)

    with pytest.raises(RuntimeError, match="embedding_service"):
        asyncio.run(service.match_by_full_text_embedding("Need Python."))


def test_recommendation_package_exports_fallback_service():
    import backend.services as services
    import backend.services.recommendation as recommendation

    assert "RecommendationFallbackService" in recommendation.__all__
    assert "PopularMajor" in recommendation.__all__
    assert services.RecommendationFallbackService is RecommendationFallbackService
