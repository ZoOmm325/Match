import asyncio
import json

import pytest

from backend.services import SkillNormalizer
from backend.services.skill_normalizer import NormalizedSkill


class FakeDeepSeekClient:
    def __init__(self):
        self.calls = []

    async def create_chat_completion(self, messages, **kwargs):
        self.calls.append({"messages": messages, "kwargs": kwargs})
        return {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "normalized_name": "Prompt Engineering",
                                "category": "ai",
                            }
                        )
                    }
                }
            ]
        }


def test_normalize_python_aliases_to_python():
    normalizer = SkillNormalizer()

    names = ["Python编程", "Python开发", "Python"]
    results = [asyncio.run(normalizer.normalize_skill(name)) for name in names]

    assert [result.normalized_name for result in results] == ["Python", "Python", "Python"]
    assert all(result.category == "programming_language" for result in results)
    assert all(result.source == "dictionary" for result in results)


def test_normalize_skills_deduplicates_aliases():
    normalizer = SkillNormalizer()

    results = asyncio.run(
        normalizer.normalize_skills(
            [
                {"name": "Python编程", "category": "language"},
                {"name": "python开发", "category": "programming"},
                {"name": "Fast API", "category": "framework"},
            ]
        )
    )

    assert [result.normalized_name for result in results] == ["Python", "FastAPI"]


def test_normalize_unknown_skill_uses_fallback_formatting_and_category():
    normalizer = SkillNormalizer()

    result = asyncio.run(normalizer.normalize_skill("  product analytics  ", category="data"))

    assert result == NormalizedSkill(
        name="product analytics",
        normalized_name="Product Analytics",
        category="data",
        source="fallback",
    )


def test_normalize_category_aliases():
    normalizer = SkillNormalizer()

    result = asyncio.run(normalizer.normalize_skill("Unknown Skill", category="soft skill"))

    assert result.category == "soft_skill"


def test_normalize_operating_system_and_architecture_categories():
    normalizer = SkillNormalizer()

    linux = asyncio.run(normalizer.normalize_skill("Linux", category="operating system"))
    architecture = asyncio.run(normalizer.normalize_skill("Microservices", category="architecture"))

    assert linux.normalized_name == "Linux"
    assert linux.category == "operating_system"
    assert architecture.category == "architecture"


def test_normalize_nlp_alias_from_seed_data():
    normalizer = SkillNormalizer()

    result = asyncio.run(normalizer.normalize_skill("Natural Language Processing"))

    assert result.normalized_name == "NLP"
    assert result.category == "ai"


def test_normalize_empty_skill_rejected():
    normalizer = SkillNormalizer()

    with pytest.raises(ValueError, match="skill name cannot be empty"):
        asyncio.run(normalizer.normalize_skill("   "))


def test_llm_fallback_used_when_dictionary_misses():
    client = FakeDeepSeekClient()
    normalizer = SkillNormalizer(deepseek_client=client, use_llm_fallback=True)

    result = asyncio.run(normalizer.normalize_skill("prompt设计", category="ai"))

    assert result.normalized_name == "Prompt Engineering"
    assert result.category == "ai"
    assert result.source == "llm"
    assert client.calls[0]["kwargs"]["response_format"] == {"type": "json_object"}


def test_dictionary_prevents_unnecessary_llm_call():
    client = FakeDeepSeekClient()
    normalizer = SkillNormalizer(deepseek_client=client, use_llm_fallback=True)

    result = asyncio.run(normalizer.normalize_skill("K8s"))

    assert result.normalized_name == "Kubernetes"
    assert client.calls == []


def test_custom_synonyms_extend_dictionary():
    normalizer = SkillNormalizer(synonyms={"prompt设计": ("Prompt Engineering", "ai")})

    result = asyncio.run(normalizer.normalize_skill("Prompt设计"))

    assert result.normalized_name == "Prompt Engineering"
    assert result.category == "ai"


def test_service_package_exports_skill_normalizer():
    import backend.services as services

    assert "SkillNormalizer" in services.__all__
    assert services.SkillNormalizer is SkillNormalizer
