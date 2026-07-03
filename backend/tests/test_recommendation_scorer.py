import asyncio

import pytest

from backend.services.jd_service import ExtractedSkillResult
from backend.services.matching import MajorMatchResult
from backend.services.recommendation import RecommendationScore, RecommendationScorer, ScoreWeights


def major_match(name="软件工程", *, similarity=0.8, coverage=0.75, final=0.785):
    return MajorMatchResult(
        major_id=1,
        major_name=name,
        major_code="080902",
        major_category="工学",
        similarity_score=similarity,
        coverage_score=coverage,
        final_score=final,
        matched_skills=["Python", "FastAPI"],
        missing_skills=["MLOps"],
        match_details={"skill_count": 3, "matched_skill_count": 2},
    )


def skill(name="Python"):
    return ExtractedSkillResult(
        name=name,
        normalized_name=name,
        category="programming_language",
        proficiency_required="intermediate",
        embedding=[0.1] * 1024,
    )


def test_score_dimensions_uses_default_weights():
    scorer = RecommendationScorer()

    result = scorer.score_dimensions(
        skill_similarity_score=0.8,
        skill_coverage_score=0.5,
        employment_alignment_score=0.25,
    )

    assert result == {
        "skill_similarity_score": 0.8,
        "skill_coverage_score": 0.5,
        "employment_alignment_score": 0.25,
        "final_score": 0.6,
    }


def test_score_dimensions_clamps_scores_to_zero_one():
    scorer = RecommendationScorer()

    result = scorer.score_dimensions(
        skill_similarity_score=1.2,
        skill_coverage_score=-0.5,
        employment_alignment_score=float("nan"),
    )

    assert result == {
        "skill_similarity_score": 1.0,
        "skill_coverage_score": 0.0,
        "employment_alignment_score": 0.0,
        "final_score": 0.5,
    }


def test_score_major_match_returns_breakdown_and_metadata():
    scorer = RecommendationScorer()

    result = scorer.score_major_match(major_match(), employment_alignment_score=0.6)

    assert result == RecommendationScore(
        major_id=1,
        major_name="软件工程",
        major_code="080902",
        skill_similarity_score=0.8,
        skill_coverage_score=0.75,
        employment_alignment_score=0.6,
        final_score=0.745,
        matched_skills=["Python", "FastAPI"],
        missing_skills=["MLOps"],
        score_details={
            "weights": {
                "skill_similarity": 0.5,
                "skill_coverage": 0.3,
                "employment_alignment": 0.2,
            },
            "source_major_score": 0.785,
            "major_match_details": {"skill_count": 3, "matched_skill_count": 2},
        },
    )


def test_custom_weights_are_normalized():
    scorer = RecommendationScorer(weights=ScoreWeights(5, 3, 2))

    result = scorer.score_dimensions(
        skill_similarity_score=1.0,
        skill_coverage_score=0.0,
        employment_alignment_score=0.0,
    )

    assert result["final_score"] == 0.5
    assert scorer.weights == ScoreWeights(0.5, 0.3, 0.2)


def test_invalid_weights_are_rejected():
    with pytest.raises(ValueError, match="negative"):
        RecommendationScorer(weights=ScoreWeights(-1, 1, 1))

    with pytest.raises(ValueError, match="positive"):
        RecommendationScorer(weights=ScoreWeights(0, 0, 0))


def test_score_major_match_with_async_evaluator():
    async def evaluator(skills, match):
        assert [item.name for item in skills] == ["Python"]
        assert match.major_name == "软件工程"
        return 0.9

    scorer = RecommendationScorer(employment_evaluator=evaluator)

    result = asyncio.run(
        scorer.score_major_match_with_evaluator(
            major_match(),
            skills=[skill()],
        )
    )

    assert result.employment_alignment_score == 0.9
    assert result.final_score == 0.805


def test_score_major_matches_sorts_by_final_score():
    def evaluator(skills, match):
        return 1.0 if match.major_name == "人工智能" else 0.0

    scorer = RecommendationScorer(employment_evaluator=evaluator)
    matches = [
        major_match("软件工程", similarity=0.8, coverage=0.5, final=0.71),
        major_match("人工智能", similarity=0.75, coverage=0.7, final=0.735),
    ]

    results = asyncio.run(scorer.score_major_matches(matches, skills=[skill()]))

    assert [result.major_name for result in results] == ["人工智能", "软件工程"]


def test_score_major_matches_runs_async_evaluators_concurrently():
    started = 0
    release = asyncio.Event()

    async def evaluator(skills, match):
        nonlocal started
        started += 1
        if started == 2:
            release.set()
        await release.wait()
        return 0.5

    async def run():
        scorer = RecommendationScorer(employment_evaluator=evaluator)
        matches = [
            major_match("A", similarity=0.8, coverage=0.5, final=0.7),
            major_match("B", similarity=0.7, coverage=0.6, final=0.68),
        ]
        return await scorer.score_major_matches(matches, skills=[skill()])

    results = asyncio.run(run())

    assert started == 2
    assert len(results) == 2


def test_score_major_matches_falls_back_only_for_failed_evaluator():
    async def evaluator(skills, match):
        if match.major_name == "Broken":
            raise RuntimeError("evaluation failed")
        return 0.8

    scorer = RecommendationScorer(employment_evaluator=evaluator)
    results = asyncio.run(
        scorer.score_major_matches(
            [
                major_match("Healthy", similarity=0.8),
                major_match("Broken", similarity=0.7),
            ],
            skills=[skill()],
        )
    )
    by_name = {result.major_name: result for result in results}

    assert by_name["Healthy"].employment_alignment_score == 0.8
    assert by_name["Broken"].employment_alignment_score == 0.0


def test_recommendation_package_exports_scorer():
    import backend.services as services
    import backend.services.recommendation as recommendation

    assert "RecommendationScorer" in recommendation.__all__
    assert "RecommendationScore" in recommendation.__all__
    assert services.RecommendationScorer is RecommendationScorer
