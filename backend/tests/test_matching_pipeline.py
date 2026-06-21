import asyncio
from types import SimpleNamespace

import pytest

from backend.services.jd_service import ExtractedSkillResult, JdExtractionResult
from backend.services.matching import (
    MajorMatchResult,
    MatchingPipeline,
    MatchingPipelineResult,
    SkillMatchResult,
)
from backend.services.matching.pipeline import SqlAlchemyMatchResultRepository


class FakeJdService:
    def __init__(self, extraction):
        self.extraction = extraction
        self.calls = []

    async def extract_skills(self, jd_text):
        self.calls.append(jd_text)
        return self.extraction


class FakeSkillMatcher:
    def __init__(self, matches):
        self.matches = matches
        self.calls = []

    async def match_extracted_skills(self, skills, **kwargs):
        self.calls.append({"skills": list(skills), "kwargs": kwargs})
        return self.matches


class FakeMajorMatcher:
    def __init__(self, matches):
        self.matches = matches
        self.calls = []

    async def match_skills_to_majors(self, skills, **kwargs):
        self.calls.append({"skills": list(skills), "kwargs": kwargs})
        return self.matches


class FakeRepository:
    def __init__(self):
        self.calls = []

    async def save_match_results(self, **kwargs):
        self.calls.append(kwargs)
        return len(kwargs["major_matches"])


class FakeScalarResult:
    def __init__(self, item):
        self.item = item

    def scalar_one_or_none(self):
        return self.item


class FakeSession:
    def __init__(self, existing=None):
        self.existing = existing
        self.added = []
        self.executed = []
        self.commits = 0

    async def execute(self, statement):
        self.executed.append(statement)
        return FakeScalarResult(self.existing)

    def add(self, item):
        self.added.append(item)

    async def commit(self):
        self.commits += 1


def skill(name="Python"):
    return ExtractedSkillResult(
        name=name,
        normalized_name=name,
        category="programming_language",
        proficiency_required="intermediate",
        embedding=[0.1] * 1024,
    )


def skill_match():
    return SkillMatchResult(
        extracted_skill_name="Python",
        matched_seed_skill="Python",
        matched_category="programming_language",
        similarity_score=0.9,
    )


def major_match(major_id=10, name="软件工程", final_score=0.88):
    return MajorMatchResult(
        major_id=major_id,
        major_name=name,
        major_code="080902",
        major_category="工学",
        similarity_score=0.8,
        coverage_score=1.0,
        final_score=final_score,
        matched_skills=["Python"],
        missing_skills=[],
        match_details={"skill_count": 1, "matched_skill_count": 1},
    )


def make_pipeline(extraction, skill_matches=None, major_matches=None, repository=None):
    return MatchingPipeline(
        jd_service=FakeJdService(extraction),
        skill_matcher=FakeSkillMatcher(skill_matches or []),
        major_matcher=FakeMajorMatcher(major_matches or []),
        repository=repository,
    )


def test_pipeline_runs_end_to_end_and_persists_match_results():
    extraction = JdExtractionResult(jd_id=1, skills=[skill()])
    repository = FakeRepository()
    pipeline = make_pipeline(
        extraction,
        skill_matches=[skill_match()],
        major_matches=[major_match()],
        repository=repository,
    )

    result = asyncio.run(
        pipeline.run(
            "  Need Python developer.  ",
            skill_top_k=5,
            major_top_n=3,
            skill_threshold=0.75,
        )
    )

    assert isinstance(result, MatchingPipelineResult)
    assert result.jd_id == 1
    assert result.extracted_skills == extraction.skills
    assert result.skill_matches == [skill_match()]
    assert result.major_matches == [major_match()]
    assert result.persisted_count == 1
    assert pipeline.jd_service.calls == ["Need Python developer."]
    assert pipeline.skill_matcher.calls[0]["kwargs"] == {"top_k": 5, "threshold": 0.75}
    assert pipeline.major_matcher.calls[0]["kwargs"] == {"top_n": 3}
    assert repository.calls == [{"jd_id": 1, "major_matches": [major_match()]}]


def test_pipeline_does_not_persist_without_jd_id_or_when_disabled():
    no_jd_pipeline = make_pipeline(
        JdExtractionResult(jd_id=None, skills=[skill()]),
        major_matches=[major_match()],
        repository=FakeRepository(),
    )

    no_jd_result = asyncio.run(no_jd_pipeline.run("Need Python."))

    assert no_jd_result.persisted_count == 0
    assert no_jd_pipeline.repository.calls == []

    disabled_pipeline = make_pipeline(
        JdExtractionResult(jd_id=2, skills=[skill()]),
        major_matches=[major_match()],
        repository=FakeRepository(),
    )

    disabled_result = asyncio.run(disabled_pipeline.run("Need Python.", persist=False))

    assert disabled_result.persisted_count == 0
    assert disabled_pipeline.repository.calls == []


def test_pipeline_handles_empty_extracted_skills():
    pipeline = make_pipeline(JdExtractionResult(jd_id=3, skills=[], already_processed=True))

    result = asyncio.run(pipeline.run("No concrete skills."))

    assert result.extracted_skills == []
    assert result.skill_matches == []
    assert result.major_matches == []
    assert result.persisted_count == 0
    assert result.already_processed is True


def test_pipeline_validates_inputs():
    pipeline = make_pipeline(JdExtractionResult(jd_id=None, skills=[]))

    with pytest.raises(ValueError, match="jd_text"):
        asyncio.run(pipeline.run("   "))

    with pytest.raises(ValueError, match="skill_top_k"):
        asyncio.run(pipeline.run("Need Python.", skill_top_k=0))

    with pytest.raises(ValueError, match="major_top_n"):
        asyncio.run(pipeline.run("Need Python.", major_top_n=0))


def test_sqlalchemy_repository_inserts_and_updates_match_results(monkeypatch):
    created_rows = []

    class FakeColumn:
        def __init__(self, name):
            self.name = name

        def __eq__(self, other):
            return (self.name, other)

    class FakeMatchResult(SimpleNamespace):
        jd_id = FakeColumn("jd_id")
        major_id = FakeColumn("major_id")

        def __init__(self, **kwargs):
            created_rows.append(kwargs)
            super().__init__(**kwargs)

    monkeypatch.setitem(
        __import__("sys").modules,
        "backend.models.match_result",
        SimpleNamespace(MatchResult=FakeMatchResult),
    )
    monkeypatch.setitem(
        __import__("sys").modules,
        "sqlalchemy",
        SimpleNamespace(select=lambda model: SimpleNamespace(where=lambda *args: ("select", model, args))),
    )

    session = FakeSession()
    repository = SqlAlchemyMatchResultRepository(session)

    count = asyncio.run(repository.save_match_results(jd_id=1, major_matches=[major_match()]))

    assert count == 1
    assert len(session.added) == 1
    assert created_rows[0]["jd_id"] == 1
    assert created_rows[0]["major_id"] == 10
    assert created_rows[0]["rank"] == 1
    assert created_rows[0]["match_details"]["matched_skills"] == ["Python"]
    assert session.commits == 1

    existing = SimpleNamespace(
        jd_id=1,
        major_id=10,
        similarity_score=0,
        final_score=0,
        rank=99,
        match_details={},
    )
    session = FakeSession(existing=existing)
    repository = SqlAlchemyMatchResultRepository(session)

    count = asyncio.run(repository.save_match_results(jd_id=1, major_matches=[major_match(final_score=0.91)]))

    assert count == 1
    assert session.added == []
    assert existing.final_score == 0.91
    assert existing.rank == 1
    assert session.commits == 1


def test_matching_package_exports_pipeline():
    import backend.services as services
    import backend.services.matching as matching

    assert "MatchingPipeline" in matching.__all__
    assert "MatchingPipelineResult" in matching.__all__
    assert services.MatchingPipeline is MatchingPipeline
