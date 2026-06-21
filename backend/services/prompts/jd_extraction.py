from __future__ import annotations

import json
from typing import Any, Literal, TypedDict


Proficiency = Literal["basic", "intermediate", "advanced"]


class ExtractedSkill(TypedDict):
    name: str
    category: str
    proficiency_required: Proficiency


class ExtractedSkillsPayload(TypedDict):
    skills: list[ExtractedSkill]


JD_EXTRACTION_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["skills"],
    "additionalProperties": False,
    "properties": {
        "skills": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["name", "category", "proficiency_required"],
                "additionalProperties": False,
                "properties": {
                    "name": {"type": "string"},
                    "category": {
                        "type": "string",
                        "enum": [
                            "programming_language",
                            "framework",
                            "database",
                            "devops",
                            "ai",
                            "data",
                            "backend",
                            "frontend",
                            "cloud",
                            "testing",
                            "tool",
                            "operating_system",
                            "architecture",
                            "soft_skill",
                            "domain_knowledge",
                            "other",
                        ],
                    },
                    "proficiency_required": {
                        "type": "string",
                        "enum": ["basic", "intermediate", "advanced"],
                    },
                },
            },
        }
    },
}


JD_EXTRACTION_SYSTEM_PROMPT = """你是招聘 JD 技能抽取专家。

任务：从用户提供的岗位 JD 中抽取可用于大学专业匹配的技能列表。

输出要求：
- 只输出 JSON，不要 Markdown，不要解释。
- JSON 顶层格式必须是 {"skills": [...]}。
- skills 中每一项必须包含 name、category、proficiency_required。
- name 使用标准技能名，例如 Python、FastAPI、PostgreSQL、Machine Learning。
- category 必须从 schema enum 中选择。
- proficiency_required 只能是 basic、intermediate、advanced。
- 去重：同义或大小写不同的技能只保留一个标准名称。
- 只抽取 JD 明确要求或强相关的技能，不要臆造。
- 如果没有可抽取技能，返回 {"skills": []}。

熟练度判断：
- basic：了解、接触过、加分项、优先。
- intermediate：熟悉、熟练、掌握、有经验、能够独立完成。
- advanced：精通、深入理解、专家、架构经验、主导或负责复杂系统。
"""


FEW_SHOT_EXAMPLES: list[dict[str, str]] = [
    {
        "jd": (
            "我们招聘后端工程师，要求熟练掌握 Python 和 FastAPI，熟悉 PostgreSQL、Redis，"
            "有 Docker 容器化部署经验，了解 Kubernetes 优先。"
        ),
        "json": json.dumps(
            {
                "skills": [
                    {
                        "name": "Python",
                        "category": "programming_language",
                        "proficiency_required": "intermediate",
                    },
                    {
                        "name": "FastAPI",
                        "category": "framework",
                        "proficiency_required": "intermediate",
                    },
                    {
                        "name": "PostgreSQL",
                        "category": "database",
                        "proficiency_required": "intermediate",
                    },
                    {
                        "name": "Redis",
                        "category": "database",
                        "proficiency_required": "intermediate",
                    },
                    {
                        "name": "Docker",
                        "category": "devops",
                        "proficiency_required": "intermediate",
                    },
                    {
                        "name": "Kubernetes",
                        "category": "devops",
                        "proficiency_required": "basic",
                    },
                ]
            },
            ensure_ascii=False,
        ),
    },
    {
        "jd": (
            "AI 算法岗位，需要深入理解机器学习、深度学习和自然语言处理，"
            "精通 PyTorch，能够独立完成模型训练、评估和部署。"
        ),
        "json": json.dumps(
            {
                "skills": [
                    {
                        "name": "Machine Learning",
                        "category": "ai",
                        "proficiency_required": "advanced",
                    },
                    {
                        "name": "Deep Learning",
                        "category": "ai",
                        "proficiency_required": "advanced",
                    },
                    {
                        "name": "NLP",
                        "category": "ai",
                        "proficiency_required": "advanced",
                    },
                    {
                        "name": "PyTorch",
                        "category": "ai",
                        "proficiency_required": "advanced",
                    },
                    {
                        "name": "Model Training",
                        "category": "ai",
                        "proficiency_required": "intermediate",
                    },
                    {
                        "name": "Model Deployment",
                        "category": "devops",
                        "proficiency_required": "intermediate",
                    },
                ]
            },
            ensure_ascii=False,
        ),
    },
]


def build_jd_extraction_messages(jd_text: str) -> list[dict[str, str]]:
    normalized = jd_text.strip()
    if not normalized:
        raise ValueError("jd_text cannot be empty")

    messages = [{"role": "system", "content": JD_EXTRACTION_SYSTEM_PROMPT}]
    for example in FEW_SHOT_EXAMPLES:
        messages.append({"role": "user", "content": _format_user_prompt(example["jd"])})
        messages.append({"role": "assistant", "content": example["json"]})
    messages.append({"role": "user", "content": _format_user_prompt(normalized)})
    return messages


def parse_jd_extraction_response(content: str) -> ExtractedSkillsPayload:
    try:
        payload = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValueError("DeepSeek response is not valid JSON") from exc

    return validate_extracted_skills_payload(payload)


def validate_extracted_skills_payload(payload: Any) -> ExtractedSkillsPayload:
    if not isinstance(payload, dict):
        raise ValueError("extraction payload must be a JSON object")

    skills = payload.get("skills")
    if not isinstance(skills, list):
        raise ValueError("extraction payload must contain a skills list")

    normalized_skills: list[ExtractedSkill] = []
    seen: set[str] = set()
    for item in skills:
        if not isinstance(item, dict):
            raise ValueError("each skill must be a JSON object")

        name = _required_string(item, "name")
        category = _required_string(item, "category")
        proficiency = _required_string(item, "proficiency_required")

        if category not in JD_EXTRACTION_JSON_SCHEMA["properties"]["skills"]["items"]["properties"]["category"]["enum"]:
            raise ValueError(f"unsupported skill category: {category}")
        if proficiency not in ("basic", "intermediate", "advanced"):
            raise ValueError(f"unsupported proficiency_required: {proficiency}")

        key = name.casefold()
        if key in seen:
            continue
        seen.add(key)
        normalized_skills.append(
            {
                "name": name,
                "category": category,
                "proficiency_required": proficiency,  # type: ignore[typeddict-item]
            }
        )

    return {"skills": normalized_skills}


def _format_user_prompt(jd_text: str) -> str:
    return (
        "请从以下 JD 中抽取技能，并严格输出 JSON：\n\n"
        f"<jd>\n{jd_text}\n</jd>"
    )


def _required_string(item: dict[str, Any], field: str) -> str:
    value = item.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"skill field {field} must be a non-empty string")
    return value.strip()
