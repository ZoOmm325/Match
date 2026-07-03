import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.models import Jd, JdSkill, Major, MatchResult, Skill

EMBEDDING_DIMENSIONS = 1024


def make_embedding(seed: float) -> list[float]:
    return [seed + index / 100_000 for index in range(EMBEDDING_DIMENSIONS)]


def test_model_columns_expose_required_database_contracts():
    assert Jd.__table__.c.raw_text.nullable is False
    assert Jd.__table__.c.created_at.server_default is not None
    assert Skill.__table__.c.normalized_name.nullable is False
    assert Skill.__table__.c.embedding.type.dim == EMBEDDING_DIMENSIONS
    assert Major.__table__.c.embedding.type.dim == EMBEDDING_DIMENSIONS
    assert JdSkill.__table__.c.jd_id.foreign_keys
    assert JdSkill.__table__.c.skill_id.foreign_keys
    assert MatchResult.__table__.c.jd_id.foreign_keys
    assert MatchResult.__table__.c.major_id.foreign_keys


@pytest.mark.asyncio
async def test_crud_and_relationship_joins(db_session: AsyncSession):
    jd = Jd(
        raw_text="需要 Python、FastAPI、PostgreSQL 和 Docker 后端开发经验。",
        title="后端工程师",
        company="示例科技",
        source="unit-test",
    )
    skill = Skill(
        name="Python",
        normalized_name="python",
        category="programming_language",
    )
    major = Major(
        name="软件工程",
        code="080902",
        category="工学",
        description="培养软件系统分析、设计、开发与管理能力。",
        curriculum={"core": ["程序设计", "数据库系统"]},
    )
    db_session.add_all([jd, skill, major])
    await db_session.flush()

    jd_skill = JdSkill(
        jd_id=jd.id,
        skill_id=skill.id,
        relevance_score=0.95,
        extraction_method="llm",
    )
    match_result = MatchResult(
        jd_id=jd.id,
        major_id=major.id,
        similarity_score=0.88,
        final_score=0.91,
        rank=1,
        match_details={"matched_skills": ["Python"], "missing_skills": []},
    )
    db_session.add_all([jd_skill, match_result])
    await db_session.commit()

    loaded_jd = await db_session.scalar(
        select(Jd)
        .where(Jd.id == jd.id)
        .options(
            selectinload(Jd.skills).selectinload(JdSkill.skill),
            selectinload(Jd.match_results).selectinload(MatchResult.major),
        )
    )
    assert loaded_jd is not None
    assert loaded_jd.skills[0].skill.normalized_name == "python"
    assert loaded_jd.match_results[0].major.code == "080902"

    joined_skill = await db_session.scalar(
        select(Skill)
        .join(JdSkill, JdSkill.skill_id == Skill.id)
        .join(Jd, Jd.id == JdSkill.jd_id)
        .where(Jd.title == "后端工程师")
    )
    assert joined_skill is skill

    major.description = "更新后的软件工程培养目标。"
    major.curriculum = {"core": ["程序设计"], "practice": ["工程实训"]}
    await db_session.commit()
    await db_session.refresh(major)
    assert major.description == "更新后的软件工程培养目标。"
    assert major.curriculum["practice"] == ["工程实训"]

    await db_session.delete(match_result)
    await db_session.commit()
    assert await db_session.get(MatchResult, match_result.id) is None


@pytest.mark.asyncio
async def test_embedding_vectors_round_trip_without_dimension_loss(
    db_session: AsyncSession,
):
    skill_vector = make_embedding(0.1)
    major_vector = make_embedding(0.2)
    skill = Skill(
        name="向量数据库",
        normalized_name="vector database",
        category="database",
        embedding=skill_vector,
    )
    major = Major(
        name="数据科学与大数据技术",
        code="080910T",
        category="工学",
        embedding=major_vector,
    )
    db_session.add_all([skill, major])
    await db_session.commit()
    skill_id = skill.id
    major_id = major.id
    db_session.expire_all()

    stored_skill = await db_session.get(Skill, skill_id)
    stored_major = await db_session.get(Major, major_id)

    assert stored_skill is not None
    assert stored_major is not None
    assert stored_skill.embedding is not None
    assert stored_major.embedding is not None
    assert len(stored_skill.embedding) == EMBEDDING_DIMENSIONS
    assert len(stored_major.embedding) == EMBEDDING_DIMENSIONS
    assert list(stored_skill.embedding) == pytest.approx(skill_vector)
    assert list(stored_major.embedding) == pytest.approx(major_vector)


@pytest.mark.asyncio
async def test_deleting_jd_cascades_links_but_keeps_reference_data(
    db_session: AsyncSession,
):
    jd = Jd(raw_text="需要数据分析、SQL 和机器学习能力的完整岗位描述。")
    skill = Skill(name="SQL", normalized_name="sql", category="database")
    major = Major(name="数据科学与大数据技术", code="080910T", category="工学")
    db_session.add_all([jd, skill, major])
    await db_session.flush()
    db_session.add(
        JdSkill(
            jd_id=jd.id,
            skill_id=skill.id,
            relevance_score=0.8,
            extraction_method="manual",
        )
    )
    db_session.add(
        MatchResult(
            jd_id=jd.id,
            major_id=major.id,
            similarity_score=0.8,
            final_score=0.82,
            rank=1,
        )
    )
    await db_session.commit()
    skill_id = skill.id
    major_id = major.id

    await db_session.delete(jd)
    await db_session.commit()

    assert await db_session.scalar(select(func.count()).select_from(JdSkill)) == 0
    assert await db_session.scalar(select(func.count()).select_from(MatchResult)) == 0
    assert await db_session.get(Skill, skill_id) is not None
    assert await db_session.get(Major, major_id) is not None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("relevance_score", "extraction_method"),
    [
        (-0.01, "llm"),
        (1.01, "manual"),
        (0.8, "rules"),
    ],
)
async def test_jd_skill_database_constraints_reject_invalid_values(
    db_session: AsyncSession,
    relevance_score: float,
    extraction_method: str,
):
    jd = Jd(raw_text="用于验证技能关联数据库约束的完整岗位描述文本。")
    skill = Skill(name="Python", normalized_name="python", category="programming_language")
    db_session.add_all([jd, skill])
    await db_session.flush()
    db_session.add(
        JdSkill(
            jd_id=jd.id,
            skill_id=skill.id,
            relevance_score=relevance_score,
            extraction_method=extraction_method,
        )
    )

    with pytest.raises(IntegrityError):
        await db_session.commit()


@pytest.mark.asyncio
async def test_jd_skill_database_accepts_keyword_rules_method(
    db_session: AsyncSession,
):
    jd = Jd(raw_text="用于验证规则提取方式数据库约束的完整岗位描述文本。")
    skill = Skill(
        name="Python",
        normalized_name="python-keyword-rules",
        category="programming_language",
    )
    db_session.add_all([jd, skill])
    await db_session.flush()
    link = JdSkill(
        jd_id=jd.id,
        skill_id=skill.id,
        relevance_score=0.8,
        extraction_method="keyword_rules",
    )
    db_session.add(link)

    await db_session.commit()

    assert link.id is not None
    assert link.extraction_method == "keyword_rules"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("similarity_score", "final_score", "rank"),
    [
        (-0.01, 0.8, 1),
        (0.8, 1.01, 1),
        (0.8, 0.9, 0),
    ],
)
async def test_match_result_database_constraints_reject_invalid_values(
    db_session: AsyncSession,
    similarity_score: float,
    final_score: float,
    rank: int,
):
    jd = Jd(raw_text="用于验证专业匹配结果数据库约束的完整岗位描述文本。")
    major = Major(name="计算机科学与技术", code="080901", category="工学")
    db_session.add_all([jd, major])
    await db_session.flush()
    db_session.add(
        MatchResult(
            jd_id=jd.id,
            major_id=major.id,
            similarity_score=similarity_score,
            final_score=final_score,
            rank=rank,
        )
    )

    with pytest.raises(IntegrityError):
        await db_session.commit()


@pytest.mark.asyncio
async def test_skill_unique_constraint_prevents_duplicate_normalized_names(
    db_session: AsyncSession,
):
    db_session.add_all(
        [
            Skill(name="Python", normalized_name="python"),
            Skill(name="Python 语言", normalized_name="python"),
        ]
    )

    with pytest.raises(IntegrityError):
        await db_session.commit()


@pytest.mark.asyncio
async def test_major_unique_constraint_prevents_duplicate_codes(
    db_session: AsyncSession,
):
    db_session.add_all(
        [
            Major(name="软件工程", code="080902"),
            Major(name="软件工程（实验班）", code="080902"),
        ]
    )

    with pytest.raises(IntegrityError):
        await db_session.commit()


@pytest.mark.asyncio
async def test_jd_skill_unique_constraint_prevents_duplicate_links(
    db_session: AsyncSession,
):
    jd = Jd(raw_text="用于验证岗位技能唯一关联约束的完整岗位描述文本。")
    skill = Skill(name="Python", normalized_name="python")
    db_session.add_all([jd, skill])
    await db_session.flush()
    db_session.add_all(
        [
            JdSkill(
                jd_id=jd.id,
                skill_id=skill.id,
                relevance_score=0.8,
                extraction_method="llm",
            ),
            JdSkill(
                jd_id=jd.id,
                skill_id=skill.id,
                relevance_score=0.95,
                extraction_method="manual",
            ),
        ]
    )

    with pytest.raises(IntegrityError):
        await db_session.commit()


@pytest.mark.asyncio
async def test_match_result_unique_constraint_prevents_duplicate_major_results(
    db_session: AsyncSession,
):
    jd = Jd(raw_text="用于验证专业匹配唯一关联约束的完整岗位描述文本。")
    major = Major(name="软件工程", code="080902")
    db_session.add_all([jd, major])
    await db_session.flush()
    db_session.add_all(
        [
            MatchResult(
                jd_id=jd.id,
                major_id=major.id,
                similarity_score=0.8,
                final_score=0.85,
                rank=1,
            ),
            MatchResult(
                jd_id=jd.id,
                major_id=major.id,
                similarity_score=0.75,
                final_score=0.8,
                rank=2,
            ),
        ]
    )

    with pytest.raises(IntegrityError):
        await db_session.commit()
