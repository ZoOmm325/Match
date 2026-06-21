import asyncio
from types import SimpleNamespace

import pytest

from backend.services.jd_service import ExtractedSkillResult, JdExtractionResult
from backend.services.matching import SkillMatchResult, SkillMatcher
from backend.services.vector_service import VectorSearchResult


class FakeJdService:
    def __init__(self, extraction):
        self.extraction = extraction
        self.calls = []

    async def extract_skills(self, jd_text):
        self.calls.append(jd_text)
        return self.extraction


class FakeVectorService:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    async def search_skills(self, query_embedding, *, top_k):
        self.calls.append({"query_embedding": query_embedding, "top_k": top_k})
        return self.responses.pop(0) if self.responses else []


def extracted_skill(name, *, category="programming_language", embedding=None):
    return ExtractedSkillResult(
        name=name,
        normalized_name=name,
        category=category,
        proficiency_required="intermediate",
        embedding=embedding or [0.1] * 1024,
    )


def candidate(name, score, *, skill_id=1, category="programming_language"):
    return VectorSearchResult(
        item=SimpleNamespace(id=skill_id, normalized_name=name, category=category),
        similarity_score=score,
        table="skills",
        id=skill_id,
        name=name,
        category=category,
    )


def make_matcher(extraction, responses):
    return SkillMatcher(
        jd_service=FakeJdService(extraction),
        vector_service=FakeVectorService(responses),
    )


def test_match_aggregates_embeddings_and_preserves_extracted_skill_names():
    extraction = JdExtractionResult(
        jd_id=1,
        skills=[
            extracted_skill("Python", embedding=[1.0, 0.0]),
            extracted_skill("FastAPI", category="framework", embedding=[0.0, 1.0]),
        ],
    )
    matcher = make_matcher(
        extraction,
        [[candidate("Python", 0.92), candidate("Old Skill", 0.3)]],
    )

    results = asyncio.run(matcher.match("Need Python and FastAPI.", top_k=10, threshold=0.5))

    assert results == [
        SkillMatchResult(
            extracted_skill_name="Python, FastAPI",
            matched_seed_skill="Python",
            matched_category="programming_language",
            similarity_score=0.92,
        )
    ]
    assert matcher.vector_service.calls[0]["top_k"] == 10
    assert matcher.vector_service.calls[0]["query_embedding"] == pytest.approx(
        [0.70710678, 0.70710678]
    )


def test_match_per_skill_deduplicates_and_keeps_best_score():
    extraction = JdExtractionResult(
        jd_id=1,
        skills=[
            extracted_skill("Python", embedding=[1.0] * 1024),
            extracted_skill("Python Programming", embedding=[0.5] * 1024),
        ],
    )
    matcher = make_matcher(
        extraction,
        [
            [candidate("Python", 0.82, skill_id=10)],
            [candidate("Python", 0.95, skill_id=10)],
        ],
    )

    results = asyncio.run(
        matcher.match_per_skill("Need Python.", per_skill_k=3, top_k=20, threshold=0.5)
    )

    assert len(results) == 1
    assert results[0].extracted_skill_name == "Python Programming"
    assert results[0].matched_seed_skill == "Python"
    assert results[0].similarity_score == 0.95
    assert [call["top_k"] for call in matcher.vector_service.calls] == [3, 3]


def test_match_per_skill_applies_threshold_and_top_k():
    extraction = JdExtractionResult(
        jd_id=2,
        skills=[extracted_skill("Backend", category="backend")],
    )
    matcher = make_matcher(
        extraction,
        [
            [
                candidate("REST API", 0.91, skill_id=1, category="backend"),
                candidate("GraphQL", 0.89, skill_id=2, category="backend"),
                candidate("COBOL", 0.4, skill_id=3),
            ]
        ],
    )

    results = asyncio.run(
        matcher.match_per_skill("Need backend API experience.", per_skill_k=5, top_k=1, threshold=0.8)
    )

    assert [result.matched_seed_skill for result in results] == ["REST API"]


def test_match_returns_empty_list_when_jd_has_no_extracted_skills():
    extraction = JdExtractionResult(jd_id=3, skills=[])
    matcher = make_matcher(extraction, [])

    assert asyncio.run(matcher.match("No concrete skill.")) == []
    assert asyncio.run(matcher.match_per_skill("No concrete skill.")) == []
    assert matcher.vector_service.calls == []


def test_aggregate_embedding_rejects_empty_or_mismatched_vectors():
    matcher = make_matcher(JdExtractionResult(jd_id=None, skills=[]), [])

    with pytest.raises(ValueError, match="at least one embedding"):
        matcher._aggregate_embedding([])

    with pytest.raises(ValueError, match="cannot be empty"):
        matcher._aggregate_embedding([[]])

    with pytest.raises(ValueError, match="same dimension"):
        matcher._aggregate_embedding([[1.0, 2.0], [1.0]])


def test_matcher_rejects_invalid_inputs_and_missing_vector_service():
    matcher = make_matcher(JdExtractionResult(jd_id=None, skills=[]), [])

    with pytest.raises(ValueError, match="jd_text cannot be empty"):
        asyncio.run(matcher.match("   "))

    with pytest.raises(ValueError, match="top_k"):
        asyncio.run(matcher.match("Need Python.", top_k=0))

    with pytest.raises(RuntimeError, match="vector_service is required"):
        asyncio.run(
            SkillMatcher(
                jd_service=FakeJdService(
                    JdExtractionResult(jd_id=None, skills=[extracted_skill("Python")])
                )
            ).match(
                "Need Python."
            )
        )


def test_matching_and_service_packages_export_skill_matcher():
    import backend.services as services
    import backend.services.matching as matching

    assert "SkillMatcher" in matching.__all__
    assert "SkillMatchResult" in matching.__all__
    assert "MatchedSkill" not in services.__all__
    assert services.SkillMatcher is SkillMatcher
