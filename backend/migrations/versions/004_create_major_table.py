"""create major table

Revision ID: 004_create_major_table
Revises: 003_create_skill_table
Create Date: 2026-06-20
"""
from typing import Sequence, Union

from alembic import op
from pgvector.sqlalchemy import Vector
import sqlalchemy as sa


revision: str = "004_create_major_table"
down_revision: Union[str, None] = "003_create_skill_table"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "majors",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("code", sa.String(length=50), nullable=True),
        sa.Column("category", sa.String(length=100), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("curriculum", sa.JSON(), nullable=True),
        sa.Column("embedding", Vector(1536), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_majors")),
    )
    op.create_index(op.f("ix_majors_id"), "majors", ["id"], unique=False)
    op.create_index(op.f("ix_majors_name"), "majors", ["name"], unique=False)
    op.create_index(op.f("ix_majors_code"), "majors", ["code"], unique=False)
    op.create_index(op.f("ix_majors_category"), "majors", ["category"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_majors_category"), table_name="majors")
    op.drop_index(op.f("ix_majors_code"), table_name="majors")
    op.drop_index(op.f("ix_majors_name"), table_name="majors")
    op.drop_index(op.f("ix_majors_id"), table_name="majors")
    op.drop_table("majors")
