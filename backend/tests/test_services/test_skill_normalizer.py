import json

import pytest

from backend.services.skill_normalizer import SkillNormalizer


class NormalizationDeepSeekClient:
    def __init__(self) -> None:
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


@pytest.mark.asyncio
async def test_dictionary_normalization_deduplicates_aliases_and_categories():
    normalizer = SkillNormalizer()

    results = await normalizer.normalize_skills(
        [
            {"name": "Python编程", "category": "language"},
            {"name": "python开发", "category": "programming"},
            {"name": "Natural-Language_Processing", "category": "ml"},
            {"name": "K8s", "category": "devops"},
        ]
    )

    assert [(result.normalized_name, result.category, result.source) for result in results] == [
        ("Python", "programming_language", "dictionary"),
        ("NLP", "ai", "dictionary"),
        ("Kubernetes", "devops", "dictionary"),
    ]


@pytest.mark.asyncio
async def test_unknown_skill_uses_clean_fallback_and_category_alias():
    normalizer = SkillNormalizer()

    result = await normalizer.normalize_skill(
        "  product   analytics  ",
        category="soft skill",
    )

    assert result.name == "product analytics"
    assert result.normalized_name == "Product Analytics"
    assert result.category == "soft_skill"
    assert result.source == "fallback"


@pytest.mark.asyncio
async def test_llm_fallback_is_only_used_for_unknown_skills():
    client = NormalizationDeepSeekClient()
    normalizer = SkillNormalizer(
        deepseek_client=client,
        use_llm_fallback=True,
    )

    known = await normalizer.normalize_skill("Python")
    unknown = await normalizer.normalize_skill("提示词设计", category="ai")

    assert known.normalized_name == "Python"
    assert unknown.normalized_name == "Prompt Engineering"
    assert unknown.source == "llm"
    assert len(client.calls) == 1
    assert client.calls[0]["kwargs"]["response_format"] == {"type": "json_object"}


@pytest.mark.asyncio
async def test_blank_skill_name_is_rejected():
    with pytest.raises(ValueError, match="skill name cannot be empty"):
        await SkillNormalizer().normalize_skill("  ")
