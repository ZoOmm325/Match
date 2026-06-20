"""SQLAlchemy model package."""

from backend.models.jd import Jd
from backend.models.jd_skill import JdSkill
from backend.models.major import Major
from backend.models.match_result import MatchResult
from backend.models.skill import Skill

__all__ = ["Jd", "JdSkill", "Major", "MatchResult", "Skill"]
