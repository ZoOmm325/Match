from datetime import datetime, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from backend import schemas
from backend.schemas.major import MajorCreate, MajorResponse


ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_major_create_trims_and_validates_input():
    schema = MajorCreate(
        name="  Software Engineering  ",
        code="  080902  ",
        category="  Engineering  ",
        description="  Builds software systems.  ",
        curriculum={"core": ["Programming", "Databases"]},
        embedding=[0.1] * 1024,
    )

    assert schema.name == "Software Engineering"
    assert schema.code == "080902"
    assert schema.category == "Engineering"
    assert schema.description == "Builds software systems."
    assert schema.curriculum == {"core": ["Programming", "Databases"]}
    assert len(schema.embedding or []) == 1024


def test_major_create_rejects_empty_name():
    with pytest.raises(ValidationError):
        MajorCreate(name="  ")


def test_major_create_rejects_wrong_embedding_dimension():
    with pytest.raises(ValidationError, match="1024"):
        MajorCreate(name="Software Engineering", embedding=[0.1, 0.2])


def test_major_response_supports_from_attributes():
    class MajorOrm:
        id = 1
        name = "Software Engineering"
        code = "080902"
        category = "Engineering"
        description = "Builds software systems."
        curriculum = {"core": ["Programming", "Databases"]}
        embedding = [0.1] * 1024
        created_at = datetime(2026, 6, 20, tzinfo=timezone.utc)

    schema = MajorResponse.model_validate(MajorOrm())

    assert schema.id == 1
    assert schema.name == "Software Engineering"
    assert schema.created_at.tzinfo == timezone.utc


def test_major_model_declares_json_and_pgvector_fields():
    model = read("backend/models/major.py")

    for expected in (
        '__tablename__ = "majors"',
        "from pgvector.sqlalchemy import Vector",
        "from sqlalchemy import DateTime, JSON, String, Text, func",
        "name: Mapped[str]",
        "code: Mapped[str | None]",
        "category: Mapped[str | None]",
        "description: Mapped[str | None]",
        "curriculum: Mapped[dict[str, Any] | list[Any] | None]",
        "embedding: Mapped[list[float] | None]",
        "Vector(1024)",
    ):
        assert expected in model


def test_major_migration_creates_and_drops_majors_table():
    migration = read("backend/migrations/versions/004_create_major_table.py")

    assert 'revision: str = "004_create_major_table"' in migration
    assert 'down_revision: Union[str, None] = "003_create_skill_table"' in migration
    assert 'op.create_table(\n        "majors",' in migration
    assert 'sa.Column("curriculum", sa.JSON(), nullable=True)' in migration
    assert 'sa.Column("embedding", Vector(1024), nullable=True)' in migration
    assert 'op.drop_table("majors")' in migration


def test_schema_package_exports_major_schemas():
    assert "MajorCreate" in schemas.__all__
    assert "MajorResponse" in schemas.__all__
    assert schemas.MajorCreate is MajorCreate
    assert schemas.MajorResponse is MajorResponse
