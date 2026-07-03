from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

from backend.schemas.jd_extraction import SkillExtractionItem
from backend.services.prompts.jd_extraction import Proficiency


@dataclass(frozen=True)
class SkillRule:
    name: str
    category: str
    aliases: tuple[str, ...]


class JdSkillExtractor:
    """Deterministic JD skill extractor.

    This rule-based implementation keeps the API testable without network
    access. It is intentionally isolated so a DeepSeek-backed extractor can be
    added later behind the same service boundary.
    """

    PROFICIENCY_RULES: tuple[tuple[Proficiency, str], ...] = (
        ("advanced", r"(精通|专家|深入理解|深度掌握|架构经验|lead|senior|expert)"),
        ("intermediate", r"(熟悉|熟练|掌握|经验|能够|独立|proficient|familiar)"),
        ("basic", r"(了解|优先|加分|基础|接触过|basic|plus)"),
    )

    SKILL_RULES: tuple[SkillRule, ...] = (
        SkillRule("Python", "programming_language", ("Python", "python")),
        SkillRule("Java", "programming_language", ("Java", "java")),
        SkillRule("JavaScript", "programming_language", ("JavaScript", "JS", "javascript")),
        SkillRule("TypeScript", "programming_language", ("TypeScript", "TS", "typescript")),
        SkillRule("SQL", "database", ("SQL", "sql")),
        SkillRule("PostgreSQL", "database", ("PostgreSQL", "Postgres", "postgresql")),
        SkillRule("MySQL", "database", ("MySQL", "mysql")),
        SkillRule("Redis", "database", ("Redis", "redis")),
        SkillRule("FastAPI", "framework", ("FastAPI", "fastapi")),
        SkillRule("Django", "framework", ("Django", "django")),
        SkillRule("Flask", "framework", ("Flask", "flask")),
        SkillRule("React", "framework", ("React", "react")),
        SkillRule("Next.js", "framework", ("Next.js", "NextJS", "next.js", "nextjs")),
        SkillRule("Vue", "framework", ("Vue", "Vue.js", "vue")),
        SkillRule("Docker", "devops", ("Docker", "docker", "容器化")),
        SkillRule("Kubernetes", "devops", ("Kubernetes", "K8s", "k8s")),
        SkillRule("Git", "tool", ("Git", "git")),
        SkillRule("Linux", "operating_system", ("Linux", "linux")),
        SkillRule("Machine Learning", "ai", ("机器学习", "Machine Learning", "ML")),
        SkillRule("Deep Learning", "ai", ("深度学习", "Deep Learning", "DL")),
        SkillRule("NLP", "ai", ("自然语言处理", "NLP", "nlp")),
        SkillRule("Data Analysis", "data", ("数据分析", "Data Analysis")),
        SkillRule("Pandas", "data", ("Pandas", "pandas")),
        SkillRule("PyTorch", "ai", ("PyTorch", "pytorch")),
        SkillRule("TensorFlow", "ai", ("TensorFlow", "tensorflow")),
        SkillRule("REST API", "backend", ("REST", "RESTful", "API接口", "接口开发")),
        SkillRule("Microservices", "architecture", ("微服务", "Microservices")),
        SkillRule("Unit Testing", "testing", ("单元测试", "pytest", "unittest", "测试用例")),
        SkillRule("Communication", "soft_skill", ("沟通", "协作", "团队合作")),
        SkillRule("Project Management", "soft_skill", ("项目管理", "需求分析")),
    )

    def extract(self, jd_text: str) -> list[SkillExtractionItem]:
        text = jd_text.strip()
        items = [
            self._build_item(rule, alias, text) for rule, alias in self._iter_matched_rules(text)
        ]
        return sorted(items, key=lambda item: (-item.confidence, item.name.lower()))

    def _iter_matched_rules(self, text: str) -> Iterable[tuple[SkillRule, str]]:
        seen: set[str] = set()
        for rule in self.SKILL_RULES:
            matched_alias = self._find_alias(rule.aliases, text)
            if matched_alias and rule.name not in seen:
                seen.add(rule.name)
                yield rule, matched_alias

    def _find_alias(self, aliases: tuple[str, ...], text: str) -> str | None:
        for alias in aliases:
            if re.search(self._alias_pattern(alias), text, flags=re.IGNORECASE):
                return alias
        return None

    def _build_item(self, rule: SkillRule, alias: str, text: str) -> SkillExtractionItem:
        evidence = self._extract_evidence(text, alias)
        proficiency = self._infer_proficiency(evidence)
        return SkillExtractionItem(
            name=rule.name,
            category=rule.category,
            proficiency_required=proficiency,
            evidence=evidence,
            confidence=self._score_confidence(alias, evidence, proficiency),
        )

    def _extract_evidence(self, text: str, alias: str) -> str:
        match = re.search(self._alias_pattern(alias), text, flags=re.IGNORECASE)
        if not match:
            return alias
        start = max(0, match.start() - 24)
        end = min(len(text), match.end() + 32)
        return text[start:end].strip(" ，。；;、\n\t")

    def _infer_proficiency(self, evidence: str) -> Proficiency:
        for proficiency, pattern in self.PROFICIENCY_RULES:
            if re.search(pattern, evidence, flags=re.IGNORECASE):
                return proficiency
        return "intermediate"

    def _score_confidence(
        self,
        alias: str,
        evidence: str,
        proficiency: Proficiency,
    ) -> float:
        score = 0.72
        if len(alias) >= 3:
            score += 0.08
        if proficiency == "advanced":
            score += 0.08
        if proficiency == "intermediate":
            score += 0.04
        if len(evidence) > len(alias):
            score += 0.04
        return min(round(score, 2), 0.95)

    def _alias_pattern(self, alias: str) -> str:
        escaped = re.escape(alias)
        if re.search(r"[\u4e00-\u9fff]", alias):
            return escaped
        return rf"(?<![A-Za-z0-9_]){escaped}(?![A-Za-z0-9_])"
