import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import Jd, JdSkill, Skill
from backend.services.jd_service import JdService


@pytest.mark.asyncio
async def test_extract_skills_with_mock_deepseek_persists_and_reuses_results(
    db_session: AsyncSession,
    deepseek_client,
    embedding_service,
):
    service = JdService(
        deepseek_client=deepseek_client,
        embedding_service=embedding_service,
        session=db_session,
    )
    jd_text = "负责 Python 与 FastAPI 后端服务开发，需要数据库和接口设计经验。"

    first = await service.extract_skills(
        jd_text,
        title="后端工程师",
        company="示例科技",
        source="unit-test",
    )
    second = await service.extract_skills(jd_text)

    assert first.jd_id is not None
    assert first.already_processed is False
    assert second.jd_id == first.jd_id
    assert second.already_processed is True
    assert [skill.normalized_name for skill in first.skills] == ["Python", "FastAPI"]
    assert [skill.normalized_name for skill in second.skills] == ["Python", "FastAPI"]
    assert [skill.proficiency_required for skill in second.skills] == [
        "advanced",
        "intermediate",
    ]
    assert len(deepseek_client.calls) == 1
    assert deepseek_client.calls[0]["kwargs"]["response_format"] == {"type": "json_object"}
    assert len(embedding_service.calls) == 1
    assert await db_session.scalar(select(func.count()).select_from(Jd)) == 1
    assert await db_session.scalar(select(func.count()).select_from(Skill)) == 2
    assert await db_session.scalar(select(func.count()).select_from(JdSkill)) == 2


@pytest.mark.asyncio
async def test_extract_skills_handles_empty_deepseek_result(
    db_session: AsyncSession,
    embedding_service,
    deepseek_client_factory,
):
    deepseek_client = deepseek_client_factory([])
    service = JdService(
        deepseek_client=deepseek_client,
        embedding_service=embedding_service,
        session=db_session,
    )

    result = await service.extract_skills("这是一个不包含明确技能要求的完整岗位描述文本。")

    assert result.jd_id is not None
    assert result.skills == []
    assert embedding_service.calls == []
    assert await db_session.scalar(select(func.count()).select_from(Jd)) == 1
    assert await db_session.scalar(select(func.count()).select_from(JdSkill)) == 0


@pytest.mark.asyncio
async def test_extract_skills_rejects_blank_jd_before_calling_deepseek(
    deepseek_client,
    embedding_service,
):
    service = JdService(
        deepseek_client=deepseek_client,
        embedding_service=embedding_service,
    )

    with pytest.raises(ValueError, match="jd_text cannot be empty"):
        await service.extract_skills("   ")

    assert deepseek_client.calls == []
    assert embedding_service.calls == []
