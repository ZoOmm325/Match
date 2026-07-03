"""allow keyword rules extraction method

Revision ID: 007_keyword_rules
Revises: 006_create_match_result_table
Create Date: 2026-07-02
"""

from typing import Sequence, Union

from alembic import op

revision: str = "007_keyword_rules"
down_revision: Union[str, None] = "006_create_match_result_table"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint(
        op.f("ck_jd_skills_extraction_method"),
        "jd_skills",
        type_="check",
    )
    op.create_check_constraint(
        op.f("ck_jd_skills_extraction_method"),
        "jd_skills",
        "extraction_method IN ('llm', 'manual', 'keyword_rules')",
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("ck_jd_skills_extraction_method"),
        "jd_skills",
        type_="check",
    )
    op.create_check_constraint(
        op.f("ck_jd_skills_extraction_method"),
        "jd_skills",
        "extraction_method IN ('llm', 'manual')",
    )
