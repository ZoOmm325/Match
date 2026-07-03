import asyncio
import json
from types import SimpleNamespace

import pytest

from backend.services.jd_service import PROFICIENCY_SCORE_MAP, ExtractedSkillResult, JdService


class FakeDeepSeekClient:
    def __init__(self, skills):
        self.skills = skills
        self.calls = []

    async def create_chat_completion(self, messages, **kwargs):
        self.calls.append({"messages": messages, "kwargs": kwargs})
        return {
            "choices": [
                {"message": {"content": json.dumps({"skills": self.skills}, ensure_ascii=False)}}
            ]
        }


class FakeEmbeddingService:
    def __init__(self):
        self.calls = []

    async def embed_texts(self, texts):
        self.calls.append(list(texts))
        return [[float(index)] * 1024 for index, _ in enumerate(texts)]


class FakeRepository:
    def __init__(self, *, processed=False):
        self.processed = processed
        self.jd = SimpleNamespace(id=1)
        self.skills = {}
        self.links = []
        self.commits = 0
        self.existing_results = [
            ExtractedSkillResult(
                name="Python",
                normalized_name="Python",
                category="programming_language",
                proficiency_required="intermediate",
                embedding=[0.1] * 1024,
            )
        ]

    async def get_or_create_jd(self, **kwargs):
        self.jd.raw_text = kwargs["raw_text"]
        self.jd.title = kwargs.get("title")
        return self.jd

    async def has_processed_jd(self, jd_id):
        return self.processed

    async def list_jd_skills(self, jd_id):
        return self.existing_results

    async def get_or_create_skill(self, **kwargs):
        normalized_name = kwargs["normalized_name"]
        if normalized_name not in self.skills:
            self.skills[normalized_name] = SimpleNamespace(
                id=len(self.skills) + 10,
                **kwargs,
            )
        return self.skills[normalized_name]

    async def link_jd_skill(self, **kwargs):
        self.links.append(kwargs)
        return SimpleNamespace(id=len(self.links), **kwargs)

    async def commit(self):
        self.commits += 1


def test_jd_service_extracts_embeds_and_persists_skills():
    deepseek = FakeDeepSeekClient(
        [
            {
                "name": "Python",
                "category": "programming_language",
                "proficiency_required": "intermediate",
            },
            {
                "name": "FastAPI",
                "category": "framework",
                "proficiency_required": "advanced",
            },
        ]
    )
    embedding_service = FakeEmbeddingService()
    repository = FakeRepository()
    service = JdService(
        deepseek_client=deepseek,
        embedding_service=embedding_service,
        repository=repository,
    )

    result = asyncio.run(
        service.extract_skills(
            " Need Python and FastAPI for backend APIs. ",
            title="Backend Engineer",
        )
    )

    assert result.jd_id == 1
    assert result.already_processed is False
    assert [skill.name for skill in result.skills] == ["Python", "FastAPI"]
    assert result.skills[0].embedding == [0.0] * 1024
    assert result.skills[1].embedding == [1.0] * 1024
    assert len(deepseek.calls) == 1
    assert deepseek.calls[0]["kwargs"]["response_format"] == {"type": "json_object"}
    assert embedding_service.calls == [
        [
            "Python | category: programming_language | proficiency: intermediate",
            "FastAPI | category: framework | proficiency: advanced",
        ]
    ]
    assert set(repository.skills) == {"Python", "FastAPI"}
    assert repository.links == [
        {
            "jd_id": 1,
            "skill_id": 10,
            "relevance_score": 0.8,
            "extraction_method": "llm",
        },
        {
            "jd_id": 1,
            "skill_id": 11,
            "relevance_score": 0.95,
            "extraction_method": "llm",
        },
    ]
    assert repository.commits == 1


def test_jd_service_returns_cached_result_for_processed_jd():
    deepseek = FakeDeepSeekClient([])
    embedding_service = FakeEmbeddingService()
    repository = FakeRepository(processed=True)
    service = JdService(
        deepseek_client=deepseek,
        embedding_service=embedding_service,
        repository=repository,
    )

    result = asyncio.run(service.extract_skills("Need Python and FastAPI."))

    assert result.already_processed is True
    assert result.skills == repository.existing_results
    assert deepseek.calls == []
    assert embedding_service.calls == []
    assert repository.commits == 0


def test_jd_service_handles_empty_extraction_payload():
    deepseek = FakeDeepSeekClient([])
    repository = FakeRepository()
    service = JdService(
        deepseek_client=deepseek,
        embedding_service=FakeEmbeddingService(),
        repository=repository,
    )

    result = asyncio.run(service.extract_skills("This JD has no concrete technical skill."))

    assert result.jd_id == 1
    assert result.skills == []
    assert repository.links == []
    assert repository.commits == 1


def test_jd_service_can_run_without_repository_for_prompt_only_extraction():
    deepseek = FakeDeepSeekClient(
        [
            {
                "name": "Python",
                "category": "programming_language",
                "proficiency_required": "basic",
            }
        ]
    )
    service = JdService(deepseek_client=deepseek, embedding_service=FakeEmbeddingService())

    result = asyncio.run(service.extract_skills("Python is a plus."))

    assert result.jd_id is None
    assert result.skills[0].normalized_name == "Python"
    assert result.skills[0].category == "programming_language"
    assert result.skills[0].embedding == [0.0] * 1024


def test_jd_service_rejects_empty_jd_text():
    service = JdService(
        deepseek_client=FakeDeepSeekClient([]),
        embedding_service=FakeEmbeddingService(),
        repository=FakeRepository(),
    )

    with pytest.raises(ValueError, match="jd_text cannot be empty"):
        asyncio.run(service.extract_skills("   "))


def test_jd_service_uses_skill_normalizer_for_canonical_names():
    deepseek = FakeDeepSeekClient(
        [
            {
                "name": "python",
                "category": "programming_language",
                "proficiency_required": "intermediate",
            }
        ]
    )
    repository = FakeRepository()
    service = JdService(
        deepseek_client=deepseek,
        embedding_service=FakeEmbeddingService(),
        repository=repository,
    )

    result = asyncio.run(service.extract_skills("Need python development experience."))

    assert result.skills[0].normalized_name == "Python"
    assert result.skills[0].category == "programming_language"
    assert repository.skills["Python"].normalized_name == "Python"
    assert repository.skills["Python"].category == "programming_language"


def test_jd_service_reuses_canonical_skill_across_case_variants():
    repository = FakeRepository()
    first_service = JdService(
        deepseek_client=FakeDeepSeekClient(
            [
                {
                    "name": "Python",
                    "category": "programming_language",
                    "proficiency_required": "intermediate",
                }
            ]
        ),
        embedding_service=FakeEmbeddingService(),
        repository=repository,
    )
    second_service = JdService(
        deepseek_client=FakeDeepSeekClient(
            [
                {
                    "name": "python",
                    "category": "programming_language",
                    "proficiency_required": "intermediate",
                }
            ]
        ),
        embedding_service=FakeEmbeddingService(),
        repository=repository,
    )

    first_result = asyncio.run(first_service.extract_skills("Need Python backend experience."))
    second_result = asyncio.run(second_service.extract_skills("Need python data experience."))

    assert first_result.skills[0].normalized_name == "Python"
    assert second_result.skills[0].normalized_name == "Python"
    assert list(repository.skills) == ["Python"]
    assert len(repository.skills) == 1


def test_jd_service_maps_relevance_score_back_to_proficiency():
    assert JdService.proficiency_for_score(0.6) == "basic"
    assert JdService.proficiency_for_score(0.8) == "intermediate"
    assert JdService.proficiency_for_score(0.95) == "advanced"
    assert JdService.proficiency_for_score(0.799) == "intermediate"


def test_jd_service_uses_shared_proficiency_score_mapping():
    for proficiency, score in PROFICIENCY_SCORE_MAP.items():
        assert JdService.score_for_proficiency(proficiency) == score
        assert JdService.proficiency_for_score(score) == proficiency

    assert JdService.score_for_proficiency("unknown") == PROFICIENCY_SCORE_MAP["intermediate"]


def test_service_package_exports_jd_service():
    import backend.services as services

    assert "JdService" in services.__all__
    assert services.JdService is JdService
