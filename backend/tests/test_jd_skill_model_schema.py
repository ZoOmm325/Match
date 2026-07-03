from pathlib import Path

import pytest
from pydantic import ValidationError

from backend import schemas
from backend.schemas.jd_skill import JdSkillCreate, JdSkillResponse

ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_jd_skill_create_validates_fields():
    schema = JdSkillCreate(
        jd_id=1,
        skill_id=2,
        relevance_score=0.86,
        extraction_method="llm",
    )

    assert schema.jd_id == 1
    assert schema.skill_id == 2
    assert schema.relevance_score == 0.86
    assert schema.extraction_method == "llm"


def test_jd_skill_create_rejects_out_of_range_score():
    with pytest.raises(ValidationError):
        JdSkillCreate(jd_id=1, skill_id=2, relevance_score=1.1, extraction_method="llm")


def test_jd_skill_create_rejects_invalid_method():
    with pytest.raises(ValidationError):
        JdSkillCreate(jd_id=1, skill_id=2, relevance_score=0.5, extraction_method="rules")


def test_jd_skill_create_accepts_keyword_rules_method():
    schema = JdSkillCreate(
        jd_id=1,
        skill_id=2,
        relevance_score=0.8,
        extraction_method="keyword_rules",
    )

    assert schema.extraction_method == "keyword_rules"


def test_jd_skill_response_supports_from_attributes():
    class JdSkillOrm:
        id = 1
        jd_id = 10
        skill_id = 20
        relevance_score = 0.75
        extraction_method = "manual"

    schema = JdSkillResponse.model_validate(JdSkillOrm())

    assert schema.id == 1
    assert schema.jd_id == 10
    assert schema.extraction_method == "manual"


def test_jd_skill_model_declares_relationships_and_constraints():
    model = read("backend/models/jd_skill.py")
    jd_model = read("backend/models/jd.py")
    skill_model = read("backend/models/skill.py")

    for expected in (
        '__tablename__ = "jd_skills"',
        'ForeignKey("jds.id", ondelete="CASCADE")',
        'ForeignKey("skills.id", ondelete="CASCADE")',
        "relevance_score: Mapped[float]",
        "extraction_method: Mapped[str]",
        "CheckConstraint(",
        "extraction_method IN ('llm', 'manual', 'keyword_rules')",
        "ck_jd_skills_extraction_method",
        'UniqueConstraint("jd_id", "skill_id"',
        'relationship(back_populates="skills")',
        'relationship(back_populates="jd_links")',
    ):
        assert expected in model

    assert 'skills: Mapped[list["JdSkill"]]' in jd_model
    assert 'jd_links: Mapped[list["JdSkill"]]' in skill_model


def test_jd_skill_migration_creates_join_table():
    migration = read("backend/migrations/versions/005_create_jd_skill_table.py")

    assert 'revision: str = "005_create_jd_skill_table"' in migration
    assert 'down_revision: Union[str, None] = "004_create_major_table"' in migration
    assert 'op.create_table(\n        "jd_skills",' in migration
    assert "sa.ForeignKeyConstraint(" in migration
    assert '["jd_id"]' in migration
    assert '["jds.id"]' in migration
    assert '["skill_id"],' in migration
    assert '["skills.id"],' in migration
    assert "relevance_score >= 0 AND relevance_score <= 1" in migration
    assert "extraction_method IN ('llm', 'manual', 'keyword_rules')" in migration
    assert 'name=op.f("ck_jd_skills_extraction_method")' in migration
    assert 'sa.UniqueConstraint("jd_id", "skill_id"' in migration
    assert 'op.drop_table("jd_skills")' in migration


def test_keyword_rules_migration_updates_existing_constraint():
    migration = read("backend/migrations/versions/007_keyword_rules.py")

    assert 'down_revision: Union[str, None] = "006_create_match_result_table"' in migration
    assert "extraction_method IN ('llm', 'manual', 'keyword_rules')" in migration
    assert "op.drop_constraint(" in migration


def test_schema_package_exports_jd_skill_schemas():
    assert "JdSkillCreate" in schemas.__all__
    assert "JdSkillResponse" in schemas.__all__
    assert schemas.JdSkillCreate is JdSkillCreate
    assert schemas.JdSkillResponse is JdSkillResponse
