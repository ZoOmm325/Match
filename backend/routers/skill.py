from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any, Protocol

from fastapi import APIRouter, Depends, HTTPException, Query, status

from backend.schemas.jd_extraction import ApiResponse
from backend.schemas.skill import (
    SkillCategoriesResponse,
    SkillListResponse,
    SkillResponse,
    SkillSummaryResponse,
)

router = APIRouter(prefix="/skills", tags=["Skill"])


class SkillRepository(Protocol):
    async def list_skills(
        self,
        *,
        category: str | None,
        keyword: str | None,
        limit: int,
        offset: int,
    ) -> SkillListResponse: ...

    async def get_skill(self, skill_id: int) -> SkillResponse | None: ...

    async def list_categories(self) -> SkillCategoriesResponse: ...


class SqlAlchemySkillRepository:
    def __init__(self, session: Any) -> None:
        self.session = session

    async def list_skills(
        self,
        *,
        category: str | None,
        keyword: str | None,
        limit: int,
        offset: int,
    ) -> SkillListResponse:
        from sqlalchemy import func, or_, select

        from backend.models.skill import Skill

        filters = []
        if category:
            filters.append(Skill.category == category)
        if keyword:
            pattern = f"%{keyword}%"
            filters.append(
                or_(
                    Skill.name.ilike(pattern),
                    Skill.normalized_name.ilike(pattern),
                )
            )

        total_statement = select(func.count()).select_from(Skill)
        list_statement = (
            select(Skill)
            .order_by(Skill.normalized_name.asc(), Skill.id.asc())
            .offset(offset)
            .limit(limit)
        )
        if filters:
            total_statement = total_statement.where(*filters)
            list_statement = list_statement.where(*filters)

        total_result = await self.session.execute(total_statement)
        result = await self.session.execute(list_statement)
        return SkillListResponse(
            items=[SkillSummaryResponse.model_validate(skill) for skill in result.scalars().all()],
            total=int(total_result.scalar_one()),
            limit=limit,
            offset=offset,
        )

    async def get_skill(self, skill_id: int) -> SkillResponse | None:
        from sqlalchemy import select

        from backend.models.skill import Skill

        result = await self.session.execute(select(Skill).where(Skill.id == skill_id))
        skill = result.scalar_one_or_none()
        if skill is None:
            return None
        return SkillResponse.model_validate(skill)

    async def list_categories(self) -> SkillCategoriesResponse:
        from sqlalchemy import select

        from backend.models.skill import Skill

        result = await self.session.execute(
            select(Skill.category)
            .where(Skill.category.is_not(None))
            .distinct()
            .order_by(Skill.category.asc())
        )
        categories = [
            category for category in result.scalars().all() if category and category.strip()
        ]
        return SkillCategoriesResponse(categories=categories)


async def get_session() -> AsyncIterator[Any]:
    from backend.core.database import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        yield session


def get_skill_repository(session: Any = Depends(get_session)) -> SkillRepository:
    return SqlAlchemySkillRepository(session)


@router.get("", response_model=ApiResponse[SkillListResponse], summary="List skills")
async def list_skills(
    category: str | None = Query(None, min_length=1, max_length=100),
    keyword: str | None = Query(None, min_length=1, max_length=100),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    repository: SkillRepository = Depends(get_skill_repository),
) -> ApiResponse[SkillListResponse]:
    return ApiResponse(
        code=0,
        message="success",
        data=await repository.list_skills(
            category=_normalize_optional_query(category),
            keyword=_normalize_optional_query(keyword),
            limit=limit,
            offset=offset,
        ),
    )


@router.get(
    "/categories",
    response_model=ApiResponse[SkillCategoriesResponse],
    summary="List skill categories",
)
async def list_skill_categories(
    repository: SkillRepository = Depends(get_skill_repository),
) -> ApiResponse[SkillCategoriesResponse]:
    return ApiResponse(
        code=0,
        message="success",
        data=await repository.list_categories(),
    )


@router.get("/{skill_id}", response_model=ApiResponse[SkillResponse], summary="Get skill detail")
async def get_skill(
    skill_id: int,
    repository: SkillRepository = Depends(get_skill_repository),
) -> ApiResponse[SkillResponse]:
    skill = await repository.get_skill(skill_id)
    if skill is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Skill not found")
    return ApiResponse(code=0, message="success", data=skill)


def _normalize_optional_query(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None
