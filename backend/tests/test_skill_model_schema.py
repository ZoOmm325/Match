from datetime import datetime, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from backend import schemas
from backend.schemas.skill import SkillCreate, SkillResponse


ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_skill_create_trims_and_validates_input():
    schema = SkillCreate(
        name="  Python Programming  ",
        normalized_name="  Python  ",
        category="  programming_language  ",
        embedding=[0.1] * 1024,
    )

    assert schema.name == "Python Programming"
    assert schema.normalized_name == "Python"
    assert schema.category == "programming_language"
    assert len(schema.embedding or []) == 1024


def test_skill_create_rejects_empty_required_text():
    with pytest.raises(ValidationError):
        SkillCreate(name="  ", normalized_name="Python")


def test_skill_create_rejects_wrong_embedding_dimension():
    with pytest.raises(ValidationError, match="1024"):
        SkillCreate(name="Python", normalized_name="Python", embedding=[0.1, 0.2])


def test_skill_response_supports_from_attributes():
    class SkillOrm:
        id = 1
        name = "Python Programming"
        normalized_name = "Python"
        category = "programming_language"
        embedding = [0.1] * 1024
        created_at = datetime(2026, 6, 20, tzinfo=timezone.utc)

    schema = SkillResponse.model_validate(SkillOrm())

    assert schema.id == 1
    assert schema.normalized_name == "Python"
    assert schema.created_at.tzinfo == timezone.utc


def test_skill_model_declares_pgvector_embedding():
    model = read("backend/models/skill.py")

    for expected in (
        '__tablename__ = "skills"',
        "from pgvector.sqlalchemy import Vector",
        "name: Mapped[str]",
        "normalized_name: Mapped[str]",
        "category: Mapped[str | None]",
        "embedding: Mapped[list[float] | None]",
        "Vector(1024)",
        "created_at: Mapped[datetime]",
    ):
        assert expected in model


def test_skill_migration_creates_and_drops_skills_table():
    migration = read("backend/migrations/versions/003_create_skill_table.py")

    assert 'revision: str = "003_create_skill_table"' in migration
    assert 'down_revision: Union[str, None] = "002_create_jd_table"' in migration
    assert 'op.create_table(\n        "skills",' in migration
    assert 'sa.Column("embedding", Vector(1024), nullable=True)' in migration
    assert 'op.drop_table("skills")' in migration


def test_schema_package_exports_skill_schemas():
    assert "SkillCreate" in schemas.__all__
    assert "SkillResponse" in schemas.__all__
    assert schemas.SkillCreate is SkillCreate
    assert schemas.SkillResponse is SkillResponse
