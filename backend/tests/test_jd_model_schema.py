from datetime import datetime, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from backend import schemas
from backend.schemas.jd import JdCreate, JdResponse

ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_jd_create_trims_and_validates_input():
    schema = JdCreate(
        raw_text="  Need Python, FastAPI, PostgreSQL, and Docker for backend service work.  ",
        title="  Backend Engineer  ",
        company="  Example Inc  ",
        source="  manual  ",
    )

    assert schema.raw_text.startswith("Need Python")
    assert schema.title == "Backend Engineer"
    assert schema.company == "Example Inc"
    assert schema.source == "manual"


def test_jd_create_rejects_too_short_raw_text():
    with pytest.raises(ValidationError):
        JdCreate(raw_text="too short")


def test_jd_response_supports_from_attributes():
    class JdOrm:
        id = 1
        raw_text = "Need Python, FastAPI, PostgreSQL, and Docker for backend service work."
        title = "Backend Engineer"
        company = "Example Inc"
        source = "manual"
        created_at = datetime(2026, 6, 20, tzinfo=timezone.utc)
        updated_at = datetime(2026, 6, 20, tzinfo=timezone.utc)

    schema = JdResponse.model_validate(JdOrm())

    assert schema.id == 1
    assert schema.title == "Backend Engineer"
    assert schema.created_at.tzinfo == timezone.utc


def test_jd_model_declares_required_columns():
    model = read("backend/models/jd.py")

    for expected in (
        '__tablename__ = "jds"',
        "raw_text: Mapped[str]",
        "title: Mapped[str | None]",
        "company: Mapped[str | None]",
        "source: Mapped[str | None]",
        "created_at: Mapped[datetime]",
        "updated_at: Mapped[datetime]",
    ):
        assert expected in model


def test_jd_migration_creates_and_drops_jds_table():
    migration = read("backend/migrations/versions/002_create_jd_table.py")

    assert 'revision: str = "002_create_jd_table"' in migration
    assert 'down_revision: Union[str, None] = "001_enable_pgvector"' in migration
    assert 'op.create_table(\n        "jds",' in migration
    assert 'sa.Column("raw_text", sa.Text(), nullable=False)' in migration
    assert 'sa.Column("source", sa.String(length=100), nullable=True)' in migration
    assert 'op.drop_table("jds")' in migration


def test_schema_package_exports_jd_and_extraction_schemas():
    expected = {
        "ApiResponse",
        "JdSkillExtractionData",
        "JdSkillExtractionRequest",
        "JdCreate",
        "JdResponse",
        "SkillExtractionItem",
    }

    assert expected.issubset(set(schemas.__all__))
    for name in expected:
        assert hasattr(schemas, name)
