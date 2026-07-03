import json

import pytest

from backend.services.prompts import (
    JD_EXTRACTION_JSON_SCHEMA,
    JD_EXTRACTION_SYSTEM_PROMPT,
    build_jd_extraction_messages,
    parse_jd_extraction_response,
)


def test_build_jd_extraction_messages_contains_few_shot_examples():
    messages = build_jd_extraction_messages(
        "招聘后端工程师，要求熟练掌握 Python、FastAPI、PostgreSQL 和 Docker。"
    )

    assert messages[0]["role"] == "system"
    assert "只输出 JSON" in messages[0]["content"]
    assert len(messages) == 6
    assert messages[-1]["role"] == "user"
    assert "Python" in messages[-1]["content"]
    assert any(
        message["role"] == "assistant" and '"skills"' in message["content"] for message in messages
    )


def test_build_jd_extraction_messages_rejects_empty_jd():
    with pytest.raises(ValueError, match="jd_text cannot be empty"):
        build_jd_extraction_messages("   ")


def test_prompt_schema_requires_structured_skill_output():
    skill_schema = JD_EXTRACTION_JSON_SCHEMA["properties"]["skills"]["items"]

    assert JD_EXTRACTION_JSON_SCHEMA["required"] == ["skills"]
    assert skill_schema["required"] == ["name", "category", "proficiency_required"]
    assert "programming_language" in skill_schema["properties"]["category"]["enum"]
    assert "operating_system" in skill_schema["properties"]["category"]["enum"]
    assert "architecture" in skill_schema["properties"]["category"]["enum"]
    assert skill_schema["properties"]["proficiency_required"]["enum"] == [
        "basic",
        "intermediate",
        "advanced",
    ]


def test_system_prompt_documents_extraction_rules():
    assert "去重" in JD_EXTRACTION_SYSTEM_PROMPT
    assert "不要臆造" in JD_EXTRACTION_SYSTEM_PROMPT
    assert "advanced" in JD_EXTRACTION_SYSTEM_PROMPT


def test_parse_jd_extraction_response_validates_and_deduplicates():
    payload = {
        "skills": [
            {
                "name": "Python",
                "category": "programming_language",
                "proficiency_required": "intermediate",
            },
            {
                "name": "python",
                "category": "programming_language",
                "proficiency_required": "basic",
            },
        ]
    }

    parsed = parse_jd_extraction_response(json.dumps(payload))

    assert parsed == {
        "skills": [
            {
                "name": "Python",
                "category": "programming_language",
                "proficiency_required": "intermediate",
            }
        ]
    }


def test_parse_jd_extraction_response_rejects_invalid_json():
    with pytest.raises(ValueError, match="not valid JSON"):
        parse_jd_extraction_response("not-json")


def test_parse_jd_extraction_response_accepts_unknown_category():
    payload = {
        "skills": [
            {
                "name": "Python",
                "category": "unknown",
                "proficiency_required": "intermediate",
            }
        ]
    }

    result = parse_jd_extraction_response(json.dumps(payload))
    assert result["skills"][0]["category"] == "unknown"


def test_parse_jd_extraction_response_accepts_extractor_categories():
    payload = {
        "skills": [
            {
                "name": "Linux",
                "category": "operating_system",
                "proficiency_required": "intermediate",
            },
            {
                "name": "Microservices",
                "category": "architecture",
                "proficiency_required": "advanced",
            },
        ]
    }

    parsed = parse_jd_extraction_response(json.dumps(payload))

    assert [skill["category"] for skill in parsed["skills"]] == [
        "operating_system",
        "architecture",
    ]


def test_parse_jd_extraction_response_rejects_invalid_proficiency():
    payload = {
        "skills": [
            {
                "name": "Python",
                "category": "programming_language",
                "proficiency_required": "expert",
            }
        ]
    }

    with pytest.raises(ValueError, match="unsupported proficiency_required"):
        parse_jd_extraction_response(json.dumps(payload))
