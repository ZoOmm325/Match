"""create skill table

Revision ID: 003_create_skill_table
Revises: 002_create_jd_table
Create Date: 2026-06-20
"""
from typing import Sequence, Union

from alembic import op
from pgvector.sqlalchemy import Vector
import sqlalchemy as sa


revision: str = "003_create_skill_table"
down_revision: Union[str, None] = "002_create_jd_table"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "skills",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("normalized_name", sa.String(length=255), nullable=False),
        sa.Column("category", sa.String(length=100), nullable=True),
        sa.Column("embedding", Vector(1024), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_skills")),
        sa.UniqueConstraint("normalized_name", name=op.f("uq_skills_normalized_name")),
    )
    op.create_index(op.f("ix_skills_id"), "skills", ["id"], unique=False)
    op.create_index(op.f("ix_skills_name"), "skills", ["name"], unique=False)
    op.create_index(op.f("ix_skills_normalized_name"), "skills", ["normalized_name"], unique=False)
    op.create_index(op.f("ix_skills_category"), "skills", ["category"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_skills_category"), table_name="skills")
    op.drop_index(op.f("ix_skills_normalized_name"), table_name="skills")
    op.drop_index(op.f("ix_skills_name"), table_name="skills")
    op.drop_index(op.f("ix_skills_id"), table_name="skills")
    op.drop_table("skills")
