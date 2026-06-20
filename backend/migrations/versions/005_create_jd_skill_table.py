"""create jd skill table

Revision ID: 005_create_jd_skill_table
Revises: 004_create_major_table
Create Date: 2026-06-20
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "005_create_jd_skill_table"
down_revision: Union[str, None] = "004_create_major_table"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "jd_skills",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("jd_id", sa.Integer(), nullable=False),
        sa.Column("skill_id", sa.Integer(), nullable=False),
        sa.Column("relevance_score", sa.Float(), nullable=False),
        sa.Column("extraction_method", sa.String(length=20), nullable=False),
        sa.CheckConstraint(
            "relevance_score >= 0 AND relevance_score <= 1",
            name=op.f("ck_jd_skills_relevance_score_range"),
        ),
        sa.CheckConstraint(
            "extraction_method IN ('llm', 'manual')",
            name=op.f("ck_jd_skills_extraction_method"),
        ),
        sa.ForeignKeyConstraint(["jd_id"], ["jds.id"], name=op.f("fk_jd_skills_jd_id_jds"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["skill_id"],
            ["skills.id"],
            name=op.f("fk_jd_skills_skill_id_skills"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_jd_skills")),
        sa.UniqueConstraint("jd_id", "skill_id", name=op.f("uq_jd_skills_jd_id_skill_id")),
    )
    op.create_index(op.f("ix_jd_skills_id"), "jd_skills", ["id"], unique=False)
    op.create_index(op.f("ix_jd_skills_jd_id"), "jd_skills", ["jd_id"], unique=False)
    op.create_index(op.f("ix_jd_skills_skill_id"), "jd_skills", ["skill_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_jd_skills_skill_id"), table_name="jd_skills")
    op.drop_index(op.f("ix_jd_skills_jd_id"), table_name="jd_skills")
    op.drop_index(op.f("ix_jd_skills_id"), table_name="jd_skills")
    op.drop_table("jd_skills")
