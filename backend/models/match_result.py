from typing import Any

from sqlalchemy import CheckConstraint, Float, ForeignKey, Integer, JSON, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.core.database import Base


class MatchResult(Base):
    __tablename__ = "match_results"
    __table_args__ = (
        CheckConstraint(
            "similarity_score >= 0 AND similarity_score <= 1",
            name="ck_match_results_similarity_score_range",
        ),
        CheckConstraint(
            "final_score >= 0 AND final_score <= 1",
            name="ck_match_results_final_score_range",
        ),
        CheckConstraint("rank > 0", name="ck_match_results_rank_positive"),
        UniqueConstraint("jd_id", "major_id", name="uq_match_results_jd_id_major_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    jd_id: Mapped[int] = mapped_column(
        ForeignKey("jds.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    major_id: Mapped[int] = mapped_column(
        ForeignKey("majors.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    similarity_score: Mapped[float] = mapped_column(Float, nullable=False)
    final_score: Mapped[float] = mapped_column(Float, nullable=False)
    rank: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    match_details: Mapped[dict[str, Any] | list[Any] | None] = mapped_column(JSON, nullable=True)

    jd: Mapped["Jd"] = relationship(back_populates="match_results")
    major: Mapped["Major"] = relationship(back_populates="match_results")


from backend.models.jd import Jd  # noqa: E402
from backend.models.major import Major  # noqa: E402
