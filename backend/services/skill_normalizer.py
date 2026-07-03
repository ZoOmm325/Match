from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from backend.core.deepseek_client import DeepSeekClient


@dataclass(frozen=True)
class NormalizedSkill:
    name: str
    normalized_name: str
    category: str
    source: str = "dictionary"


SKILL_SYNONYMS: dict[str, tuple[str, str]] = {
    "python": ("Python", "programming_language"),
    "python编程": ("Python", "programming_language"),
    "python开发": ("Python", "programming_language"),
    "python programming": ("Python", "programming_language"),
    "java": ("Java", "programming_language"),
    "javascript": ("JavaScript", "programming_language"),
    "js": ("JavaScript", "programming_language"),
    "typescript": ("TypeScript", "programming_language"),
    "ts": ("TypeScript", "programming_language"),
    "fastapi": ("FastAPI", "framework"),
    "fast api": ("FastAPI", "framework"),
    "django": ("Django", "framework"),
    "flask": ("Flask", "framework"),
    "react": ("React", "framework"),
    "reactjs": ("React", "framework"),
    "nextjs": ("Next.js", "framework"),
    "next.js": ("Next.js", "framework"),
    "vue": ("Vue", "framework"),
    "sql": ("SQL", "database"),
    "postgres": ("PostgreSQL", "database"),
    "postgresql": ("PostgreSQL", "database"),
    "mysql": ("MySQL", "database"),
    "redis": ("Redis", "database"),
    "docker": ("Docker", "devops"),
    "容器化": ("Docker", "devops"),
    "k8s": ("Kubernetes", "devops"),
    "kubernetes": ("Kubernetes", "devops"),
    "linux": ("Linux", "operating_system"),
    "git": ("Git", "tool"),
    "machine learning": ("Machine Learning", "ai"),
    "机器学习": ("Machine Learning", "ai"),
    "deep learning": ("Deep Learning", "ai"),
    "深度学习": ("Deep Learning", "ai"),
    "nlp": ("NLP", "ai"),
    "natural language processing": ("NLP", "ai"),
    "自然语言处理": ("NLP", "ai"),
    "pytorch": ("PyTorch", "ai"),
    "tensorflow": ("TensorFlow", "ai"),
    "rag": ("Retrieval-Augmented Generation", "ai"),
    "retrieval augmented generation": ("Retrieval-Augmented Generation", "ai"),
    "prompt engineering": ("Prompt Engineering", "ai"),
    "data analysis": ("Data Analysis", "data"),
    "数据分析": ("Data Analysis", "data"),
    "communication": ("Communication", "soft_skill"),
    "沟通": ("Communication", "soft_skill"),
    "团队协作": ("Teamwork", "soft_skill"),
}


CATEGORY_ALIASES: dict[str, str] = {
    "language": "programming_language",
    "programming": "programming_language",
    "programming_language": "programming_language",
    "framework": "framework",
    "database": "database",
    "db": "database",
    "devops": "devops",
    "ai": "ai",
    "ml": "ai",
    "data": "data",
    "backend": "backend",
    "frontend": "frontend",
    "cloud": "cloud",
    "testing": "testing",
    "tool": "tool",
    "operating_system": "operating_system",
    "operating system": "operating_system",
    "os": "operating_system",
    "architecture": "architecture",
    "soft_skill": "soft_skill",
    "soft skill": "soft_skill",
    "domain_knowledge": "domain_knowledge",
    "protocol": "protocol",
}


class SkillNormalizer:
    def __init__(
        self,
        *,
        deepseek_client: DeepSeekClient | None = None,
        use_llm_fallback: bool = False,
        synonyms: dict[str, tuple[str, str]] | None = None,
    ) -> None:
        self.deepseek_client = deepseek_client
        self.use_llm_fallback = use_llm_fallback
        self.synonyms = dict(SKILL_SYNONYMS)
        if synonyms:
            self.synonyms.update(
                {self._canonical_key(key): value for key, value in synonyms.items()}
            )

    async def normalize_skill(
        self,
        name: str,
        *,
        category: str | None = None,
    ) -> NormalizedSkill:
        raw_name = self._clean_name(name)
        key = self._canonical_key(raw_name)
        if key in self.synonyms:
            normalized_name, normalized_category = self.synonyms[key]
            return NormalizedSkill(
                name=raw_name,
                normalized_name=normalized_name,
                category=normalized_category,
                source="dictionary",
            )

        if self.use_llm_fallback and self.deepseek_client is not None:
            llm_result = await self._normalize_with_llm(raw_name, category)
            if llm_result is not None:
                return llm_result

        return NormalizedSkill(
            name=raw_name,
            normalized_name=self._title_preserving_acronyms(raw_name),
            category=self._normalize_category(category),
            source="fallback",
        )

    async def normalize_skills(
        self,
        skills: list[dict[str, Any]] | list[str],
    ) -> list[NormalizedSkill]:
        results: list[NormalizedSkill] = []
        seen: set[str] = set()
        for item in skills:
            if isinstance(item, str):
                normalized = await self.normalize_skill(item)
            else:
                normalized = await self.normalize_skill(
                    str(item.get("name", "")),
                    category=item.get("category"),
                )

            dedupe_key = normalized.normalized_name.casefold()
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            results.append(normalized)
        return results

    async def _normalize_with_llm(
        self,
        name: str,
        category: str | None,
    ) -> NormalizedSkill | None:
        assert self.deepseek_client is not None

        response = await self.deepseek_client.create_chat_completion(
            [
                {
                    "role": "system",
                    "content": (
                        "You normalize skill names. Return only JSON with "
                        "normalized_name and category."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {"name": name, "category": category},
                        ensure_ascii=False,
                    ),
                },
            ],
            response_format={"type": "json_object"},
        )
        try:
            payload = json.loads(self._response_content(response))
        except (json.JSONDecodeError, TypeError):
            return None
        if not isinstance(payload, dict):
            return None
        normalized_name = self._clean_name(str(payload.get("normalized_name", "")))
        if not normalized_name:
            return None

        return NormalizedSkill(
            name=name,
            normalized_name=normalized_name,
            category=self._normalize_category(payload.get("category") or category),
            source="llm",
        )

    def _response_content(self, response: Any) -> str:
        if isinstance(response, dict):
            return response["choices"][0]["message"]["content"]
        return response.choices[0].message.content

    def _clean_name(self, name: str) -> str:
        normalized = re.sub(r"\s+", " ", name.strip())
        if not normalized:
            raise ValueError("skill name cannot be empty")
        return normalized

    def _canonical_key(self, name: str) -> str:
        key = self._clean_name(name).casefold()
        key = key.replace("-", " ").replace("_", " ")
        key = re.sub(r"\s+", " ", key)
        return key.strip()

    def _normalize_category(self, category: str | None) -> str:
        if not category:
            return "other"
        return CATEGORY_ALIASES.get(self._canonical_key(category), self._canonical_key(category))

    def _title_preserving_acronyms(self, name: str) -> str:
        if name.isupper() and len(name) <= 5:
            return name
        return " ".join(part if part.isupper() else part.capitalize() for part in name.split())
