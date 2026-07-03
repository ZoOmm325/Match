from sqlalchemy import CheckConstraint, Float, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.core.database import Base


class JdSkill(Base):
    __tablename__ = "jd_skills"
    __table_args__ = (
        CheckConstraint(
            "relevance_score >= 0 AND relevance_score <= 1",
            name="ck_jd_skills_relevance_score_range",
        ),
        CheckConstraint(
            "extraction_method IN ('llm', 'manual', 'keyword_rules')",
            name="ck_jd_skills_extraction_method",
        ),
        UniqueConstraint("jd_id", "skill_id", name="uq_jd_skills_jd_id_skill_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    jd_id: Mapped[int] = mapped_column(
        ForeignKey("jds.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    skill_id: Mapped[int] = mapped_column(
        ForeignKey("skills.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    relevance_score: Mapped[float] = mapped_column(Float, nullable=False)
    extraction_method: Mapped[str] = mapped_column(String(20), nullable=False)

    jd: Mapped["Jd"] = relationship(back_populates="skills")
    skill: Mapped["Skill"] = relationship(back_populates="jd_links")


from backend.models.jd import Jd  # noqa: E402
from backend.models.skill import Skill  # noqa: E402
