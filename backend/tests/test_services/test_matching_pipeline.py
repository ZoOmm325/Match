from collections.abc import Callable

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import Jd, Major, MatchResult, Skill
from backend.services.jd_service import JdService
from backend.services.matching import MajorMatcher, MatchingPipeline, SkillMatcher
from backend.services.matching.pipeline import SqlAlchemyMatchResultRepository
from backend.services.vector_service import VectorSearchResult


class DeterministicVectorService:
    def __init__(self, *, skill: Skill, major: Major) -> None:
        self.skill = skill
        self.major = major
        self.skill_calls = []
        self.major_calls = []

    async def search_skills(self, query_embedding, *, top_k=10):
        self.skill_calls.append({"embedding": query_embedding, "top_k": top_k})
        return [
            VectorSearchResult(
                item=self.skill,
                similarity_score=0.96,
                table="skills",
                id=self.skill.id,
                name=self.skill.normalized_name,
                category=self.skill.category,
            )
        ]

    async def search_majors(self, query_embedding, *, top_k=10):
        self.major_calls.append({"embedding": query_embedding, "top_k": top_k})
        return [
            VectorSearchResult(
                item=self.major,
                similarity_score=0.9,
                table="majors",
                id=self.major.id,
                name=self.major.name,
                category=self.major.category,
            )
        ]


@pytest.mark.asyncio
async def test_matching_pipeline_runs_end_to_end_and_persists_results(
    db_session: AsyncSession,
    deepseek_client,
    embedding_service,
    make_embedding: Callable[[int], list[float]],
):
    seed_skill = Skill(
        name="Python",
        normalized_name="Python",
        category="programming_language",
        embedding=make_embedding(0),
    )
    major = Major(
        name="软件工程",
        code="080902",
        category="工学",
        description="培养 Python 软件开发、数据库与系统设计能力。",
        curriculum={"core": ["Python", "FastAPI", "程序设计", "数据库系统"]},
        embedding=make_embedding(0),
    )
    db_session.add_all([seed_skill, major])
    await db_session.commit()

    vector_service = DeterministicVectorService(skill=seed_skill, major=major)
    jd_service = JdService(
        deepseek_client=deepseek_client,
        embedding_service=embedding_service,
        session=db_session,
    )
    pipeline = MatchingPipeline(
        jd_service=jd_service,
        skill_matcher=SkillMatcher(
            jd_service=jd_service,
            vector_service=vector_service,
        ),
        major_matcher=MajorMatcher(
            jd_service=jd_service,
            vector_service=vector_service,
        ),
        repository=SqlAlchemyMatchResultRepository(db_session),
    )

    result = await pipeline.run(
        "负责 Python 与 FastAPI 后端服务开发，需要数据库和接口设计经验。",
        skill_top_k=5,
        major_top_n=3,
        skill_threshold=0.7,
    )

    assert result.jd_id is not None
    assert [skill.normalized_name for skill in result.extracted_skills] == [
        "Python",
        "FastAPI",
    ]
    assert len(result.skill_matches) == 1
    assert result.skill_matches[0].matched_seed_skill == "Python"
    assert len(result.major_matches) == 1
    assert result.major_matches[0].major_name == "软件工程"
    assert result.major_matches[0].matched_skills == ["Python", "FastAPI"]
    assert result.persisted_count == 1
    assert len(vector_service.skill_calls) == 2
    assert len(vector_service.major_calls) == 1

    stored_result = await db_session.scalar(select(MatchResult))
    assert stored_result is not None
    assert stored_result.jd_id == result.jd_id
    assert stored_result.major_id == major.id
    assert stored_result.rank == 1
    assert stored_result.match_details["major_name"] == "软件工程"
    assert stored_result.match_details["matched_skills"] == ["Python", "FastAPI"]
    assert await db_session.scalar(select(func.count()).select_from(Jd)) == 1


@pytest.mark.asyncio
async def test_matching_pipeline_empty_extraction_stops_before_vector_search(
    db_session: AsyncSession,
    embedding_service,
    make_embedding,
    deepseek_client_factory,
):
    seed_skill = Skill(
        name="Python",
        normalized_name="Python",
        category="programming_language",
        embedding=make_embedding(0),
    )
    major = Major(
        name="软件工程",
        code="080902",
        category="工学",
        embedding=make_embedding(0),
    )
    db_session.add_all([seed_skill, major])
    await db_session.commit()
    vector_service = DeterministicVectorService(skill=seed_skill, major=major)
    jd_service = JdService(
        deepseek_client=deepseek_client_factory([]),
        embedding_service=embedding_service,
        session=db_session,
    )
    pipeline = MatchingPipeline(
        jd_service=jd_service,
        skill_matcher=SkillMatcher(
            jd_service=jd_service,
            vector_service=vector_service,
        ),
        major_matcher=MajorMatcher(vector_service=vector_service),
        repository=SqlAlchemyMatchResultRepository(db_session),
    )

    result = await pipeline.run("这是一个不包含明确技能要求的完整岗位描述文本。")

    assert result.extracted_skills == []
    assert result.skill_matches == []
    assert result.major_matches == []
    assert result.persisted_count == 0
    assert vector_service.skill_calls == []
    assert vector_service.major_calls == []
