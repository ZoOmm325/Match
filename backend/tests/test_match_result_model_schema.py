from pathlib import Path

import pytest
from pydantic import ValidationError

from backend import schemas
from backend.schemas.match_result import MatchResultCreate, MatchResultResponse

ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_match_result_create_validates_fields():
    schema = MatchResultCreate(
        jd_id=1,
        major_id=2,
        similarity_score=0.82,
        final_score=0.9,
        rank=1,
        match_details={"matched_skills": ["Python"], "missing_skills": ["MLOps"]},
    )

    assert schema.jd_id == 1
    assert schema.major_id == 2
    assert schema.similarity_score == 0.82
    assert schema.final_score == 0.9
    assert schema.rank == 1
    assert schema.match_details == {"matched_skills": ["Python"], "missing_skills": ["MLOps"]}


def test_match_result_create_rejects_out_of_range_scores():
    with pytest.raises(ValidationError):
        MatchResultCreate(jd_id=1, major_id=2, similarity_score=-0.1, final_score=0.8, rank=1)

    with pytest.raises(ValidationError):
        MatchResultCreate(jd_id=1, major_id=2, similarity_score=0.8, final_score=1.1, rank=1)


def test_match_result_create_rejects_non_positive_rank():
    with pytest.raises(ValidationError):
        MatchResultCreate(jd_id=1, major_id=2, similarity_score=0.8, final_score=0.8, rank=0)


def test_match_result_response_supports_from_attributes():
    class MatchResultOrm:
        id = 1
        jd_id = 10
        major_id = 20
        similarity_score = 0.75
        final_score = 0.88
        rank = 3
        match_details = {"matched_skills": ["Python"], "missing_skills": []}

    schema = MatchResultResponse.model_validate(MatchResultOrm())

    assert schema.id == 1
    assert schema.major_id == 20
    assert schema.rank == 3


def test_match_result_model_declares_relationships_and_constraints():
    model = read("backend/models/match_result.py")
    jd_model = read("backend/models/jd.py")
    major_model = read("backend/models/major.py")

    for expected in (
        '__tablename__ = "match_results"',
        'ForeignKey("jds.id", ondelete="CASCADE")',
        'ForeignKey("majors.id", ondelete="CASCADE")',
        "similarity_score: Mapped[float]",
        "final_score: Mapped[float]",
        "rank: Mapped[int]",
        "match_details: Mapped[dict[str, Any] | list[Any] | None]",
        "similarity_score >= 0 AND similarity_score <= 1",
        "final_score >= 0 AND final_score <= 1",
        "rank > 0",
        'UniqueConstraint("jd_id", "major_id"',
        'relationship(back_populates="match_results")',
    ):
        assert expected in model

    assert 'match_results: Mapped[list["MatchResult"]]' in jd_model
    assert 'match_results: Mapped[list["MatchResult"]]' in major_model


def test_match_result_migration_creates_result_table():
    migration = read("backend/migrations/versions/006_create_match_result_table.py")

    assert 'revision: str = "006_create_match_result_table"' in migration
    assert 'down_revision: Union[str, None] = "005_create_jd_skill_table"' in migration
    assert 'op.create_table(\n        "match_results",' in migration
    assert 'sa.Column("match_details", sa.JSON(), nullable=True)' in migration
    assert "similarity_score >= 0 AND similarity_score <= 1" in migration
    assert "final_score >= 0 AND final_score <= 1" in migration
    assert "rank > 0" in migration
    assert 'sa.UniqueConstraint("jd_id", "major_id"' in migration
    assert 'op.drop_table("match_results")' in migration


def test_schema_package_exports_match_result_schemas():
    assert "MatchResultCreate" in schemas.__all__
    assert "MatchResultResponse" in schemas.__all__
    assert schemas.MatchResultCreate is MatchResultCreate
    assert schemas.MatchResultResponse is MatchResultResponse
