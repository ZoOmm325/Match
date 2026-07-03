from types import SimpleNamespace

import pytest

from backend.services.jd_service import ExtractedSkillResult
from backend.services.matching import MajorMatchResult
from backend.services.recommendation import (
    RankedRecommendation,
    RecommendationFallbackService,
    RecommendationRanker,
    RecommendationScore,
    RecommendationScorer,
    ScoreWeights,
)
from backend.services.recommendation.fallback import POPULAR_MAJORS
from backend.services.vector_service import VectorSearchResult


def make_skill(
    name: str = "Python",
    *,
    category: str = "programming_language",
) -> ExtractedSkillResult:
    return ExtractedSkillResult(
        name=name,
        normalized_name=name,
        category=category,
        proficiency_required="intermediate",
        embedding=[0.1] * 1024,
    )


def make_major_match(
    name: str = "软件工程",
    *,
    major_id: int = 1,
    similarity: float = 0.8,
    coverage: float = 0.75,
    final_score: float = 0.785,
) -> MajorMatchResult:
    return MajorMatchResult(
        major_id=major_id,
        major_name=name,
        major_code=f"08090{major_id}",
        major_category="工学",
        similarity_score=similarity,
        coverage_score=coverage,
        final_score=final_score,
        matched_skills=["Python", "FastAPI"],
        missing_skills=["MLOps"],
        match_details={"skill_count": 3, "matched_skill_count": 2},
    )


def make_score(
    name: str,
    final_score: float,
    *,
    major_id: int = 1,
) -> RecommendationScore:
    return RecommendationScore(
        major_id=major_id,
        major_name=name,
        major_code=f"08090{major_id}",
        skill_similarity_score=0.8,
        skill_coverage_score=0.7,
        employment_alignment_score=0.6,
        final_score=final_score,
        matched_skills=["Python", "FastAPI"],
        missing_skills=["MLOps"],
        score_details={"source": "task-9.4"},
    )


class ReasonDeepSeekClient:
    def __init__(self, *, content: str | None = None) -> None:
        self.content = content
        self.calls = []

    async def create_chat_completion(self, messages, **kwargs):
        self.calls.append({"messages": messages, "kwargs": kwargs})
        major_name = messages[1]["content"].splitlines()[1].split(": ", 1)[1]
        content = self.content
        if content is None:
            content = f"推荐{major_name}，核心技能覆盖充分，可重点补齐 MLOps。"
        return {"choices": [{"message": {"content": content}}]}


class FakeEmbeddingService:
    def __init__(self) -> None:
        self.calls = []

    async def embed_text(self, text: str) -> list[float]:
        self.calls.append(text)
        return [0.2] * 1024


class FakeVectorService:
    def __init__(self) -> None:
        self.calls = []

    async def search_majors(
        self,
        embedding: list[float],
        *,
        top_k: int,
    ) -> list[VectorSearchResult]:
        self.calls.append({"embedding": embedding, "top_k": top_k})
        item = SimpleNamespace(
            id=4,
            name="人工智能",
            code="080717T",
            category="工学",
        )
        return [
            VectorSearchResult(
                item=item,
                similarity_score=0.82,
                table="majors",
                id=item.id,
                name=item.name,
                category=item.category,
            )
        ]


@pytest.mark.parametrize(
    ("weights", "expected_weights", "expected_final"),
    [
        (
            ScoreWeights(),
            ScoreWeights(0.5, 0.3, 0.2),
            0.66,
        ),
        (
            ScoreWeights(1, 0, 0),
            ScoreWeights(1.0, 0.0, 0.0),
            0.8,
        ),
        (
            ScoreWeights(0, 1, 0),
            ScoreWeights(0.0, 1.0, 0.0),
            0.6,
        ),
        (
            ScoreWeights(5, 3, 2),
            ScoreWeights(0.5, 0.3, 0.2),
            0.66,
        ),
    ],
)
def test_multidimensional_scores_respect_weight_configuration(
    weights: ScoreWeights,
    expected_weights: ScoreWeights,
    expected_final: float,
):
    scorer = RecommendationScorer(weights=weights)

    result = scorer.score_dimensions(
        skill_similarity_score=0.8,
        skill_coverage_score=0.6,
        employment_alignment_score=0.4,
    )

    assert scorer.weights == expected_weights
    assert result == {
        "skill_similarity_score": 0.8,
        "skill_coverage_score": 0.6,
        "employment_alignment_score": 0.4,
        "final_score": expected_final,
    }


def test_scoring_clamps_dimensions_and_preserves_match_metadata():
    scorer = RecommendationScorer()
    result = scorer.score_major_match(
        make_major_match(similarity=1.5, coverage=-0.2),
        employment_alignment_score=float("nan"),
    )

    assert result.skill_similarity_score == 1.0
    assert result.skill_coverage_score == 0.0
    assert result.employment_alignment_score == 0.0
    assert result.final_score == 0.5
    assert result.matched_skills == ["Python", "FastAPI"]
    assert result.missing_skills == ["MLOps"]
    assert result.score_details["weights"] == {
        "skill_similarity": 0.5,
        "skill_coverage": 0.3,
        "employment_alignment": 0.2,
    }
    assert result.score_details["major_match_details"]["skill_count"] == 3


@pytest.mark.parametrize(
    "weights",
    [
        ScoreWeights(-1, 1, 1),
        ScoreWeights(0, 0, 0),
    ],
)
def test_invalid_weight_configurations_are_rejected(weights: ScoreWeights):
    with pytest.raises(ValueError, match="negative|positive"):
        RecommendationScorer(weights=weights)


@pytest.mark.asyncio
async def test_employment_evaluator_changes_ranking_and_supports_override():
    async def default_evaluator(_skills, _match):
        return 0.0

    async def override_evaluator(_skills, match):
        return 1.0 if match.major_name == "人工智能" else 0.0

    scorer = RecommendationScorer(
        weights=ScoreWeights(0.4, 0.2, 0.4),
        employment_evaluator=default_evaluator,
    )
    matches = [
        make_major_match(
            "软件工程",
            major_id=1,
            similarity=0.9,
            coverage=0.9,
        ),
        make_major_match(
            "人工智能",
            major_id=2,
            similarity=0.7,
            coverage=0.7,
        ),
    ]

    results = await scorer.score_major_matches(
        matches,
        skills=[make_skill()],
        employment_evaluator=override_evaluator,
    )

    assert [result.major_name for result in results] == ["人工智能", "软件工程"]
    assert results[0].employment_alignment_score == 1.0
    assert results[0].final_score == 0.82


@pytest.mark.asyncio
async def test_ranker_sorts_by_score_then_name_and_applies_top_n():
    ranker = RecommendationRanker()
    scores = [
        make_score("B 专业", 0.9, major_id=2),
        make_score("A 专业", 0.9, major_id=1),
        make_score("C 专业", 0.8, major_id=3),
    ]

    results = await ranker.rank_scores(
        scores,
        top_n=2,
        generate_reasons=False,
    )

    assert [result.major_name for result in results] == ["A 专业", "B 专业"]
    assert [result.rank for result in results] == [1, 2]
    assert all(isinstance(result, RankedRecommendation) for result in results)
    assert results[0].recommendation_reason.startswith("第1推荐A 专业")


@pytest.mark.asyncio
async def test_rank_major_matches_combines_scoring_and_reason_generation():
    client = ReasonDeepSeekClient()
    ranker = RecommendationRanker(
        scorer=RecommendationScorer(weights=ScoreWeights(0.6, 0.3, 0.1)),
        deepseek_client=client,
    )

    results = await ranker.rank_major_matches(
        [
            make_major_match(
                "软件工程",
                similarity=0.9,
                coverage=0.8,
            )
        ],
        skills=[make_skill(), make_skill("FastAPI", category="framework")],
        top_n=1,
        employment_evaluator=lambda _skills, _match: 0.7,
    )

    assert results[0].final_score == 0.85
    assert results[0].recommendation_reason.startswith("推荐软件工程")
    assert results[0].score_details["weights"]["skill_similarity"] == pytest.approx(0.6)


@pytest.mark.asyncio
async def test_llm_reason_generation_uses_expected_prompt_and_parameters():
    client = ReasonDeepSeekClient()
    ranker = RecommendationRanker(deepseek_client=client)

    results = await ranker.rank_scores([make_score("软件工程", 0.9)])

    assert results[0].recommendation_reason == (
        "推荐软件工程，核心技能覆盖充分，可重点补齐 MLOps。"
    )
    assert len(client.calls) == 1
    call = client.calls[0]
    assert call["kwargs"]["temperature"] == 0.2
    assert "最终得分: 0.9000" in call["messages"][1]["content"]
    assert "匹配技能: Python, FastAPI" in call["messages"][1]["content"]
    assert "缺失技能: MLOps" in call["messages"][1]["content"]


@pytest.mark.asyncio
async def test_empty_llm_reason_falls_back_to_deterministic_text():
    ranker = RecommendationRanker(
        deepseek_client=ReasonDeepSeekClient(content="   "),
    )

    results = await ranker.rank_scores([make_score("软件工程", 0.9)])

    assert results[0].recommendation_reason.startswith("第1推荐软件工程")
    assert "综合得分0.90" in results[0].recommendation_reason


@pytest.mark.asyncio
async def test_cold_start_recovery_selects_each_expected_strategy():
    embedding = FakeEmbeddingService()
    vector = FakeVectorService()
    fallback = RecommendationFallbackService(
        embedding_service=embedding,
        vector_service=vector,
    )

    keyword_results = await fallback.recover(
        "需要 Python API 后端开发经验",
        extracted_skill_count=2,
        deepseek_available=False,
        top_n=2,
    )
    full_text_results = await fallback.recover(
        "泛技术岗位，要求学习能力和工程实践能力",
        extracted_skill_count=0,
        top_n=1,
    )
    popular_results = await fallback.recover(
        "需要通用技术能力",
        extracted_skill_count=2,
        current_matches=[make_major_match(final_score=0.2)],
        min_final_score=0.35,
        top_n=2,
    )
    current = [make_major_match(final_score=0.8)]
    retained_results = await fallback.recover(
        "需要 Python 开发经验",
        extracted_skill_count=2,
        current_matches=current,
        min_final_score=0.35,
    )

    assert keyword_results[0].major_name == "软件工程"
    assert keyword_results[0].match_details["fallback"] == "keyword"
    assert full_text_results[0].major_name == "人工智能"
    assert full_text_results[0].match_details["fallback"] == "full_text_embedding"
    assert embedding.calls == ["泛技术岗位，要求学习能力和工程实践能力"]
    assert popular_results[0].major_name == POPULAR_MAJORS[0].name
    assert popular_results[0].match_details["fallback"] == "popular"
    assert retained_results == current


def test_keyword_fallback_uses_boundaries_deduplication_and_popular_default():
    fallback = RecommendationFallbackService()

    results = fallback.keyword_recommendations(
        "负责 Python API 后端开发、机器学习算法和数据分析",
        top_n=5,
    )
    no_false_positive = fallback.keyword_recommendations(
        "负责 ambition 品牌运营与客户沟通",
        top_n=1,
    )
    no_keywords = fallback.keyword_recommendations(
        "要求积极主动并具备良好学习能力",
        top_n=1,
    )

    assert [result.major_name for result in results[:3]] == [
        "软件工程",
        "人工智能",
        "数据科学与大数据技术",
    ]
    assert len({result.major_code for result in results}) == len(results)
    assert "bi" not in no_false_positive[0].matched_skills
    assert no_keywords[0].match_details["fallback"] == "popular"


@pytest.mark.asyncio
async def test_fallback_and_ranker_validate_inputs_and_dependencies():
    fallback = RecommendationFallbackService()

    with pytest.raises(ValueError, match="jd_text"):
        fallback.keyword_recommendations("   ")
    with pytest.raises(ValueError, match="top_n"):
        fallback.popular_recommendations(top_n=0)
    with pytest.raises(ValueError, match="top_n"):
        await RecommendationRanker().rank_scores([], top_n=0)


@pytest.mark.asyncio
async def test_full_text_fallback_requires_embedding_and_vector_services():
    with pytest.raises(RuntimeError, match="embedding_service and vector_service"):
        await RecommendationFallbackService().match_by_full_text_embedding(
            "Need Python backend experience."
        )
