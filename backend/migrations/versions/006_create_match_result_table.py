"""create match result table

Revision ID: 006_create_match_result_table
Revises: 005_create_jd_skill_table
Create Date: 2026-06-20
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "006_create_match_result_table"
down_revision: Union[str, None] = "005_create_jd_skill_table"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "match_results",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("jd_id", sa.Integer(), nullable=False),
        sa.Column("major_id", sa.Integer(), nullable=False),
        sa.Column("similarity_score", sa.Float(), nullable=False),
        sa.Column("final_score", sa.Float(), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("match_details", sa.JSON(), nullable=True),
        sa.CheckConstraint(
            "similarity_score >= 0 AND similarity_score <= 1",
            name=op.f("ck_match_results_similarity_score_range"),
        ),
        sa.CheckConstraint(
            "final_score >= 0 AND final_score <= 1",
            name=op.f("ck_match_results_final_score_range"),
        ),
        sa.CheckConstraint("rank > 0", name=op.f("ck_match_results_rank_positive")),
        sa.ForeignKeyConstraint(
            ["jd_id"], ["jds.id"], name=op.f("fk_match_results_jd_id_jds"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["major_id"],
            ["majors.id"],
            name=op.f("fk_match_results_major_id_majors"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_match_results")),
        sa.UniqueConstraint("jd_id", "major_id", name=op.f("uq_match_results_jd_id_major_id")),
    )
    op.create_index(op.f("ix_match_results_id"), "match_results", ["id"], unique=False)
    op.create_index(op.f("ix_match_results_jd_id"), "match_results", ["jd_id"], unique=False)
    op.create_index(op.f("ix_match_results_major_id"), "match_results", ["major_id"], unique=False)
    op.create_index(op.f("ix_match_results_rank"), "match_results", ["rank"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_match_results_rank"), table_name="match_results")
    op.drop_index(op.f("ix_match_results_major_id"), table_name="match_results")
    op.drop_index(op.f("ix_match_results_jd_id"), table_name="match_results")
    op.drop_index(op.f("ix_match_results_id"), table_name="match_results")
    op.drop_table("match_results")
