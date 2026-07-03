import asyncio

import pytest

from backend.services.jd_service import ExtractedSkillResult
from backend.services.matching import MajorMatchResult
from backend.services.recommendation import (
    RankedRecommendation,
    RecommendationRanker,
    RecommendationScore,
    RecommendationScorer,
)


class FakeDeepSeekClient:
    def __init__(self):
        self.calls = []

    async def create_chat_completion(self, messages, **kwargs):
        self.calls.append({"messages": messages, "kwargs": kwargs})
        major_line = messages[1]["content"].splitlines()[1]
        major_name = major_line.split(": ", 1)[1]
        return {
            "choices": [
                {
                    "message": {
                        "content": f"推荐{major_name}，因为技能覆盖较好，后续补齐缺失技能即可。"
                    }
                }
            ]
        }


def recommendation_score(name, final_score, *, major_id=1):
    return RecommendationScore(
        major_id=major_id,
        major_name=name,
        major_code="080902",
        skill_similarity_score=0.8,
        skill_coverage_score=0.7,
        employment_alignment_score=0.6,
        final_score=final_score,
        matched_skills=["Python", "FastAPI"],
        missing_skills=["MLOps"],
        score_details={"source": "test"},
    )


def major_match(name, final_score):
    return MajorMatchResult(
        major_id=1,
        major_name=name,
        major_code="080902",
        major_category="工学",
        similarity_score=final_score,
        coverage_score=0.8,
        final_score=final_score,
        matched_skills=["Python"],
        missing_skills=[],
        match_details={},
    )


def skill(name="Python"):
    return ExtractedSkillResult(
        name=name,
        normalized_name=name,
        category="programming_language",
        proficiency_required="intermediate",
        embedding=[0.1] * 1024,
    )


def test_rank_scores_returns_top_5_with_llm_reasons():
    client = FakeDeepSeekClient()
    ranker = RecommendationRanker(deepseek_client=client)
    scores = [
        recommendation_score(f"Major {index}", final_score=1 - index * 0.05, major_id=index)
        for index in range(7)
    ]

    results = asyncio.run(ranker.rank_scores(scores, top_n=5))

    assert len(results) == 5
    assert all(isinstance(item, RankedRecommendation) for item in results)
    assert [item.rank for item in results] == [1, 2, 3, 4, 5]
    assert [item.major_name for item in results] == [f"Major {index}" for index in range(5)]
    assert all("推荐" in item.recommendation_reason for item in results)
    assert len(client.calls) == 5
    assert client.calls[0]["kwargs"]["temperature"] == 0.2
    assert "匹配技能: Python, FastAPI" in client.calls[0]["messages"][1]["content"]


def test_rank_scores_can_use_deterministic_fallback_reasons():
    ranker = RecommendationRanker()

    results = asyncio.run(
        ranker.rank_scores(
            [recommendation_score("软件工程", 0.9)],
            generate_reasons=False,
        )
    )

    assert results[0].recommendation_reason.startswith("第1推荐软件工程")
    assert results[0].matched_skills == ["Python", "FastAPI"]
    assert results[0].missing_skills == ["MLOps"]


def test_rank_scores_sorts_by_score_then_name_and_validates_top_n():
    ranker = RecommendationRanker()
    scores = [
        recommendation_score("B Major", 0.8),
        recommendation_score("A Major", 0.8),
        recommendation_score("C Major", 0.7),
    ]

    results = asyncio.run(ranker.rank_scores(scores, generate_reasons=False))

    assert [item.major_name for item in results] == ["A Major", "B Major", "C Major"]

    with pytest.raises(ValueError, match="top_n"):
        asyncio.run(ranker.rank_scores(scores, top_n=0, generate_reasons=False))


def test_rank_major_matches_scores_then_ranks():
    def evaluator(skills, match):
        return 0.9

    class FakeScorer(RecommendationScorer):
        async def score_major_matches(self, major_matches, *, skills, employment_evaluator=None):
            assert [skill.name for skill in skills] == ["Python"]
            assert employment_evaluator is evaluator
            return [
                recommendation_score(match.major_name, match.final_score, major_id=match.major_id)
                for match in major_matches
            ]

    ranker = RecommendationRanker(scorer=FakeScorer())

    results = asyncio.run(
        ranker.rank_major_matches(
            [major_match("软件工程", 0.8), major_match("人工智能", 0.9)],
            skills=[skill()],
            generate_reasons=False,
            employment_evaluator=evaluator,
        )
    )

    assert [item.major_name for item in results] == ["人工智能", "软件工程"]


def test_ranker_falls_back_when_llm_returns_empty_reason():
    class EmptyClient:
        async def create_chat_completion(self, messages, **kwargs):
            return {"choices": [{"message": {"content": "   "}}]}

    ranker = RecommendationRanker(deepseek_client=EmptyClient())

    results = asyncio.run(ranker.rank_scores([recommendation_score("软件工程", 0.9)]))

    assert results[0].recommendation_reason.startswith("第1推荐软件工程")


def test_ranker_falls_back_only_for_failed_reason_generation():
    class PartiallyFailingClient:
        async def create_chat_completion(self, messages, **kwargs):
            if "Broken Major" in messages[1]["content"]:
                raise RuntimeError("upstream failure")
            return {"choices": [{"message": {"content": "generated reason"}}]}

    ranker = RecommendationRanker(deepseek_client=PartiallyFailingClient())
    results = asyncio.run(
        ranker.rank_scores(
            [
                recommendation_score("Healthy Major", 0.9),
                recommendation_score("Broken Major", 0.8),
            ]
        )
    )

    assert results[0].recommendation_reason == "generated reason"
    assert results[1].recommendation_reason != "generated reason"


def test_recommendation_package_exports_ranker():
    import backend.services as services
    import backend.services.recommendation as recommendation

    assert "RecommendationRanker" in recommendation.__all__
    assert "RankedRecommendation" in recommendation.__all__
    assert services.RecommendationRanker is RecommendationRanker
