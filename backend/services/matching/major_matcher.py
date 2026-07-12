from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Sequence

from backend.services.jd_service import ExtractedSkillResult, JdService
from backend.services.matching._utils import aggregate_embedding
from backend.services.vector_service import VectorSearchResult, VectorService


CURRICULUM_SKILL_TERMS: tuple[tuple[tuple[str, ...], tuple[str, ...]], ...] = (
    (
        ("程序设计", "编程", "软件开发", "面向对象", "programming", "software development"),
        ("Python", "Java", "C", "C++", "JavaScript", "Git", "Problem Solving"),
    ),
    (
        ("面向对象", "object-oriented"),
        ("Java", "C++", "C#", "Design Patterns"),
    ),
    (
        ("数据库", "database"),
        ("SQL", "MySQL", "PostgreSQL", "Database Design", "Data Modeling"),
    ),
    (
        ("数据结构", "算法", "algorithm", "data structure"),
        ("Problem Solving", "Data Modeling"),
    ),
    (
        ("软件工程", "软件项目", "需求工程", "software engineering", "software project"),
        ("Agile Development", "Scrum", "Project Management", "Git", "FastAPI", "CI/CD", "Docker"),
    ),
    (
        ("软件测试", "测试技术", "software testing"),
        ("Unit Testing", "Integration Testing", "End-to-End Testing", "Selenium", "Postman"),
    ),
    (
        ("计算机网络", "网络协议", "路由", "交换", "network"),
        ("Linux", "Nginx", "Cybersecurity"),
    ),
    (
        ("操作系统", "linux"),
        ("Linux", "Bash"),
    ),
    (
        ("web 开发", "web开发", "web development", "前端"),
        ("HTML", "CSS", "JavaScript", "React", "Vue"),
    ),
    (
        ("后端", "接口", "api 开发", "api development"),
        ("REST API", "GraphQL", "Node.js", "Java", "Python", "FastAPI", "Spring Boot"),
    ),
    (
        ("机器学习", "machine learning"),
        ("Machine Learning", "Scikit-learn", "Python", "Pandas", "NumPy"),
    ),
    (
        ("深度学习", "deep learning"),
        ("Deep Learning", "PyTorch", "TensorFlow", "Keras"),
    ),
    (
        ("自然语言处理", "nlp", "natural language processing"),
        ("NLP", "Natural Language Processing", "Transformers"),
    ),
    (
        ("计算机视觉", "computer vision"),
        ("Computer Vision", "OpenCV"),
    ),
    (
        ("人工智能", "智能科学"),
        ("Machine Learning", "Deep Learning", "Python", "Scikit-learn"),
    ),
    (
        ("大数据", "数据挖掘", "数据分析", "data mining", "data analysis"),
        ("Pandas", "NumPy", "ETL", "Data Warehouse", "Apache Spark", "Hadoop"),
    ),
    (
        ("数据可视化", "visualization"),
        ("Data Modeling", "Pandas"),
    ),
    (
        ("云计算", "云平台", "cloud"),
        ("Docker", "Kubernetes", "Cloud Native", "AWS", "Alibaba Cloud"),
    ),
    (
        ("物联网", "iot"),
        ("Internet of Things", "IoT", "Embedded Systems", "C", "C++"),
    ),
    (
        ("嵌入式", "embedded"),
        ("Embedded Systems", "C", "C++", "Linux"),
    ),
    (
        ("网络安全", "信息安全", "web 安全", "安全攻防", "cybersecurity", "security"),
        ("Cybersecurity", "Cryptography", "Linux"),
    ),
    (
        ("密码", "cryptography"),
        ("Cryptography",),
    ),
    (
        ("电路", "电子", "circuit"),
        ("Circuit Design",),
    ),
    (
        ("信号处理", "signal processing"),
        ("Signal Processing", "MATLAB"),
    ),
    (
        ("plc",),
        ("PLC",),
    ),
    (
        ("cad", "机械设计", "工程制图"),
        ("CAD", "AutoCAD", "SolidWorks"),
    ),
)

COMPUTER_MAJOR_TRIGGERS: tuple[str, ...] = (
    "计算机",
    "软件工程",
    "网络工程",
    "信息安全",
    "物联网",
    "智能科学",
    "人工智能",
    "数据科学",
    "大数据",
    "网络空间安全",
    "cybersecurity",
    "computer",
    "software engineering",
    "data science",
    "artificial intelligence",
)

COMPUTER_COMMON_SKILL_TERMS: tuple[str, ...] = (
    "Git",
    "Linux",
    "SQL",
    "REST API",
    "Unit Testing",
    "Docker",
    "CI/CD",
)


@dataclass(frozen=True)
class MajorMatchResult:
    major_id: int | None
    major_name: str
    major_code: str | None
    major_category: str | None
    similarity_score: float
    coverage_score: float
    final_score: float
    matched_skills: list[str]
    missing_skills: list[str]
    match_details: dict[str, Any]


class MajorMatcher:
    def __init__(
        self,
        *,
        vector_service: VectorService | None = None,
        jd_service: JdService | None = None,
        similarity_weight: float = 0.7,
        coverage_weight: float = 0.3,
    ) -> None:
        self.vector_service = vector_service
        self.jd_service = jd_service
        self.similarity_weight = float(similarity_weight)
        self.coverage_weight = float(coverage_weight)
        self._validate_weights()

    async def match_skills_to_majors(
        self,
        skills: Sequence[ExtractedSkillResult],
        *,
        top_n: int = 10,
        candidate_multiplier: int = 3,
    ) -> list[MajorMatchResult]:
        limit = self._validate_positive_int(top_n, "top_n")
        multiplier = self._validate_positive_int(candidate_multiplier, "candidate_multiplier")
        normalized_skills = list(skills)
        if not normalized_skills:
            return []
        if self.vector_service is None:
            raise RuntimeError("vector_service is required for major matching")

        query_embedding = self._aggregate_embedding(
            [skill.embedding for skill in normalized_skills]
        )
        candidates = await self.vector_service.search_majors(
            query_embedding,
            top_k=max(limit, limit * multiplier),
        )
        results = [self._to_major_match(candidate, normalized_skills) for candidate in candidates]
        return sorted(results, key=lambda item: (-item.final_score, item.major_name.casefold()))[
            :limit
        ]

    async def match_jd_to_majors(
        self,
        jd_text: str,
        *,
        top_n: int = 10,
        candidate_multiplier: int = 3,
    ) -> list[MajorMatchResult]:
        if self.jd_service is None:
            raise RuntimeError("jd_service is required for JD major matching")
        extraction = await self.jd_service.extract_skills(jd_text)
        return await self.match_skills_to_majors(
            extraction.skills,
            top_n=top_n,
            candidate_multiplier=candidate_multiplier,
        )

    def _to_major_match(
        self,
        candidate: VectorSearchResult,
        skills: list[ExtractedSkillResult],
    ) -> MajorMatchResult:
        matched_skills, missing_skills = self._split_covered_skills(candidate.item, skills)
        coverage_score = round(len(matched_skills) / len(skills), 4) if skills else 0.0
        similarity_score = candidate.similarity_score
        final_score = round(
            similarity_score * self.similarity_weight + coverage_score * self.coverage_weight,
            4,
        )
        major_code = getattr(candidate.item, "code", None)
        major_category = candidate.category or getattr(candidate.item, "category", None)
        major_name = candidate.name or getattr(candidate.item, "name", "") or ""
        return MajorMatchResult(
            major_id=candidate.id,
            major_name=major_name,
            major_code=major_code,
            major_category=major_category,
            similarity_score=similarity_score,
            coverage_score=coverage_score,
            final_score=final_score,
            matched_skills=matched_skills,
            missing_skills=missing_skills,
            match_details={
                "similarity_weight": self.similarity_weight,
                "coverage_weight": self.coverage_weight,
                "skill_count": len(skills),
                "matched_skill_count": len(matched_skills),
            },
        )

    def _split_covered_skills(
        self,
        major: Any,
        skills: list[ExtractedSkillResult],
    ) -> tuple[list[str], list[str]]:
        matched: list[str] = []
        missing: list[str] = []
        major_text = self._major_search_text(major)
        derived_skill_terms = self._derived_skill_terms(major)
        for skill in skills:
            skill_name = skill.normalized_name or skill.name
            if self._is_skill_covered(major_text, derived_skill_terms, skill):
                matched.append(skill_name)
            else:
                missing.append(skill_name)
        return matched, missing

    def _major_search_text(self, major: Any) -> str:
        parts: list[str] = []
        for attr in ("name", "category"):
            value = getattr(major, attr, None)
            if value:
                parts.append(str(value))
        curriculum = getattr(major, "curriculum", None)
        if isinstance(curriculum, dict):
            for value in curriculum.values():
                if isinstance(value, list):
                    parts.extend(str(item) for item in value)
                elif value:
                    parts.append(str(value))
        elif isinstance(curriculum, list):
            parts.extend(str(item) for item in curriculum)
        elif curriculum:
            parts.append(str(curriculum))
        return " ".join(parts).casefold()

    def _derived_skill_terms(self, major: Any) -> set[str]:
        source_text = self._major_search_text(major)
        terms: set[str] = set()
        for triggers, skill_terms in CURRICULUM_SKILL_TERMS:
            if any(trigger.casefold() in source_text for trigger in triggers):
                terms.update(term.casefold() for term in skill_terms)
        if self._is_computer_major_text(source_text):
            terms.update(term.casefold() for term in COMPUTER_COMMON_SKILL_TERMS)
        return terms

    def _is_computer_major_text(self, source_text: str) -> bool:
        return any(trigger.casefold() in source_text for trigger in COMPUTER_MAJOR_TRIGGERS)

    def _is_skill_covered(
        self,
        major_text: str,
        derived_skill_terms: set[str],
        skill: ExtractedSkillResult,
    ) -> bool:
        skill_names = {
            name.strip() for name in (skill.normalized_name, skill.name) if name and name.strip()
        }
        if any(self._contains_skill_name(major_text, name) for name in skill_names):
            return True
        return any(name.casefold() in derived_skill_terms for name in skill_names)

    def _contains_skill_name(self, major_text: str, skill_name: str) -> bool:
        normalized_name = skill_name.strip()
        if not normalized_name:
            return False
        pattern = rf"(?<![A-Za-z0-9_+#.]){re.escape(normalized_name)}(?![A-Za-z0-9_+#.])"
        return re.search(pattern, major_text, flags=re.IGNORECASE) is not None

    def _aggregate_embedding(self, embeddings: list[list[float]]) -> list[float]:
        return aggregate_embedding(embeddings)

    def _validate_weights(self) -> None:
        if self.similarity_weight < 0 or self.coverage_weight < 0:
            raise ValueError("matcher weights cannot be negative")
        total = self.similarity_weight + self.coverage_weight
        if total <= 0:
            raise ValueError("matcher weights must sum to a positive value")
        self.similarity_weight = self.similarity_weight / total
        self.coverage_weight = self.coverage_weight / total

    def _validate_positive_int(self, value: int, name: str) -> int:
        if value < 1:
            raise ValueError(f"{name} must be at least 1")
        return value
