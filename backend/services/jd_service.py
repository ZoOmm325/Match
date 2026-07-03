from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from backend.core.deepseek_client import DeepSeekClient, get_deepseek_client
from backend.services.embedding_service import EmbeddingService
from backend.services.prompts.jd_extraction import (
    ExtractedSkill,
    ExtractedSkillsPayload,
    build_jd_extraction_messages,
    parse_jd_extraction_response,
)
from backend.services.skill_normalizer import SkillNormalizer

PROFICIENCY_SCORE_MAP: dict[str, float] = {
    "basic": 0.6,
    "intermediate": 0.8,
    "advanced": 0.95,
}


@dataclass(frozen=True)
class ExtractedSkillResult:
    name: str
    normalized_name: str
    category: str
    proficiency_required: str
    embedding: list[float]


@dataclass(frozen=True)
class JdExtractionResult:
    jd_id: int | None
    skills: list[ExtractedSkillResult]
    already_processed: bool = False


class JdSkillRepository(Protocol):
    async def get_or_create_jd(
        self,
        *,
        raw_text: str,
        title: str | None = None,
        company: str | None = None,
        source: str | None = None,
    ) -> Any: ...

    async def has_processed_jd(self, jd_id: int) -> bool: ...

    async def list_jd_skills(self, jd_id: int) -> list[ExtractedSkillResult]: ...

    async def get_or_create_skill(
        self,
        *,
        name: str,
        normalized_name: str,
        category: str,
        embedding: list[float],
    ) -> Any: ...

    async def link_jd_skill(
        self,
        *,
        jd_id: int,
        skill_id: int,
        relevance_score: float,
        extraction_method: str,
    ) -> Any: ...

    async def commit(self) -> None: ...


class SqlAlchemyJdSkillRepository:
    def __init__(self, session: Any) -> None:
        self.session = session

    async def get_or_create_jd(
        self,
        *,
        raw_text: str,
        title: str | None = None,
        company: str | None = None,
        source: str | None = None,
    ) -> Any:
        from sqlalchemy import select

        from backend.models.jd import Jd

        result = await self.session.execute(select(Jd).where(Jd.raw_text == raw_text))
        jd = result.scalar_one_or_none()
        if jd is not None:
            return jd

        jd = Jd(raw_text=raw_text, title=title, company=company, source=source)
        self.session.add(jd)
        await self.session.flush()
        return jd

    async def has_processed_jd(self, jd_id: int) -> bool:
        from sqlalchemy import select

        from backend.models.jd_skill import JdSkill

        result = await self.session.execute(
            select(JdSkill.id).where(JdSkill.jd_id == jd_id).limit(1)
        )
        return result.scalar_one_or_none() is not None

    async def list_jd_skills(self, jd_id: int) -> list[ExtractedSkillResult]:
        from sqlalchemy import select

        from backend.models.jd_skill import JdSkill
        from backend.models.skill import Skill

        result = await self.session.execute(
            select(Skill, JdSkill)
            .join(JdSkill, JdSkill.skill_id == Skill.id)
            .where(JdSkill.jd_id == jd_id)
        )
        rows = result.all()
        return [
            ExtractedSkillResult(
                name=skill.name,
                normalized_name=skill.normalized_name,
                category=skill.category or "other",
                proficiency_required=JdService.proficiency_for_score(jd_skill.relevance_score),
                embedding=list(skill.embedding) if skill.embedding is not None else [],
            )
            for skill, jd_skill in rows
        ]

    async def get_or_create_skill(
        self,
        *,
        name: str,
        normalized_name: str,
        category: str,
        embedding: list[float],
    ) -> Any:
        from sqlalchemy import select

        from backend.models.skill import Skill

        result = await self.session.execute(
            select(Skill).where(Skill.normalized_name == normalized_name)
        )
        skill = result.scalar_one_or_none()
        if skill is not None:
            return skill

        skill = Skill(
            name=name,
            normalized_name=normalized_name,
            category=category,
            embedding=embedding,
        )
        self.session.add(skill)
        await self.session.flush()
        return skill

    async def link_jd_skill(
        self,
        *,
        jd_id: int,
        skill_id: int,
        relevance_score: float,
        extraction_method: str,
    ) -> Any:
        from sqlalchemy import select

        from backend.models.jd_skill import JdSkill

        result = await self.session.execute(
            select(JdSkill).where(JdSkill.jd_id == jd_id, JdSkill.skill_id == skill_id)
        )
        jd_skill = result.scalar_one_or_none()
        if jd_skill is not None:
            return jd_skill

        jd_skill = JdSkill(
            jd_id=jd_id,
            skill_id=skill_id,
            relevance_score=relevance_score,
            extraction_method=extraction_method,
        )
        self.session.add(jd_skill)
        await self.session.flush()
        return jd_skill

    async def commit(self) -> None:
        await self.session.commit()


class JdService:
    def __init__(
        self,
        *,
        deepseek_client: DeepSeekClient | None = None,
        embedding_service: EmbeddingService | None = None,
        skill_normalizer: SkillNormalizer | None = None,
        repository: JdSkillRepository | None = None,
        session: Any | None = None,
    ) -> None:
        self.deepseek_client = deepseek_client or get_deepseek_client()
        self.embedding_service = embedding_service or EmbeddingService()
        self.skill_normalizer = skill_normalizer or SkillNormalizer()
        self.repository: JdSkillRepository | None
        if repository is not None:
            self.repository = repository
        elif session is not None:
            self.repository = SqlAlchemyJdSkillRepository(session)
        else:
            self.repository = None

    async def extract_skills(
        self,
        jd_text: str,
        *,
        title: str | None = None,
        company: str | None = None,
        source: str | None = None,
    ) -> JdExtractionResult:
        normalized_jd_text = jd_text.strip()
        if not normalized_jd_text:
            raise ValueError("jd_text cannot be empty")

        jd = await self._get_or_create_jd(
            raw_text=normalized_jd_text,
            title=title,
            company=company,
            source=source,
        )
        jd_id = getattr(jd, "id", None)

        if jd_id is not None and await self._has_processed_jd(jd_id):
            return JdExtractionResult(
                jd_id=jd_id,
                skills=await self._list_jd_skills(jd_id),
                already_processed=True,
            )

        extracted_payload = await self._extract_with_deepseek(normalized_jd_text)
        extracted_skills = extracted_payload["skills"]
        if not extracted_skills:
            await self._commit()
            return JdExtractionResult(jd_id=jd_id, skills=[])

        skill_texts = [self._embedding_text(skill) for skill in extracted_skills]
        embeddings = await self.embedding_service.embed_texts(skill_texts)

        results: list[ExtractedSkillResult] = []
        for skill, embedding in zip(extracted_skills, embeddings):
            normalized = await self.skill_normalizer.normalize_skill(
                skill["name"],
                category=skill["category"],
            )
            saved_skill = await self._get_or_create_skill(
                name=skill["name"],
                normalized_name=normalized.normalized_name,
                category=normalized.category,
                embedding=embedding,
            )
            saved_skill_id = getattr(saved_skill, "id", None)
            if jd_id is not None and saved_skill_id is not None:
                await self._link_jd_skill(
                    jd_id=jd_id,
                    skill_id=saved_skill_id,
                    relevance_score=self._score_for_proficiency(skill["proficiency_required"]),
                    extraction_method="llm",
                )

            results.append(
                ExtractedSkillResult(
                    name=skill["name"],
                    normalized_name=normalized.normalized_name,
                    category=normalized.category,
                    proficiency_required=skill["proficiency_required"],
                    embedding=embedding,
                )
            )

        await self._commit()
        return JdExtractionResult(jd_id=jd_id, skills=results)

    async def _extract_with_deepseek(self, jd_text: str) -> ExtractedSkillsPayload:
        response = await self.deepseek_client.create_chat_completion(
            build_jd_extraction_messages(jd_text),
            response_format={"type": "json_object"},
        )
        return parse_jd_extraction_response(self._response_content(response))

    def _response_content(self, response: Any) -> str:
        if isinstance(response, dict):
            return response["choices"][0]["message"]["content"]
        return response.choices[0].message.content

    def _embedding_text(self, skill: ExtractedSkill) -> str:
        return (
            f"{skill['name']} | category: {skill['category']} | "
            f"proficiency: {skill['proficiency_required']}"
        )

    def _score_for_proficiency(self, proficiency: str) -> float:
        return self.score_for_proficiency(proficiency)

    @staticmethod
    def score_for_proficiency(proficiency: str) -> float:
        return PROFICIENCY_SCORE_MAP.get(proficiency, PROFICIENCY_SCORE_MAP["intermediate"])

    @staticmethod
    def proficiency_for_score(score: float) -> str:
        rounded_score = round(score, 2)
        for proficiency, mapped_score in PROFICIENCY_SCORE_MAP.items():
            if rounded_score == mapped_score:
                return proficiency
        return "intermediate"

    async def _get_or_create_jd(self, **kwargs: Any) -> Any:
        if self.repository is None:
            return None
        return await self.repository.get_or_create_jd(**kwargs)

    async def _has_processed_jd(self, jd_id: int) -> bool:
        return self.repository is not None and await self.repository.has_processed_jd(jd_id)

    async def _list_jd_skills(self, jd_id: int) -> list[ExtractedSkillResult]:
        if self.repository is None:
            return []
        return await self.repository.list_jd_skills(jd_id)

    async def _get_or_create_skill(self, **kwargs: Any) -> Any:
        if self.repository is None:
            return None
        return await self.repository.get_or_create_skill(**kwargs)

    async def _link_jd_skill(self, **kwargs: Any) -> Any:
        if self.repository is None:
            return None
        return await self.repository.link_jd_skill(**kwargs)

    async def _commit(self) -> None:
        if self.repository is not None:
            await self.repository.commit()
