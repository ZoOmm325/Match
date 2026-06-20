from datetime import datetime

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.core.database import Base


class Jd(Base):
    __tablename__ = "jds"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    company: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    skills: Mapped[list["JdSkill"]] = relationship(
        back_populates="jd",
        cascade="all, delete-orphan",
    )
    match_results: Mapped[list["MatchResult"]] = relationship(
        back_populates="jd",
        cascade="all, delete-orphan",
    )


from backend.models.jd_skill import JdSkill  # noqa: E402
from backend.models.match_result import MatchResult  # noqa: E402
