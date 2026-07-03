from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any, Protocol

from fastapi import APIRouter, Depends, HTTPException, Query, status

from backend.schemas.jd_extraction import ApiResponse
from backend.schemas.major import (
    MajorListResponse,
    MajorResponse,
    MajorSearchRequest,
    MajorSearchResponse,
    MajorSearchResultResponse,
)
from backend.services.embedding_service import EmbeddingService, EmbeddingServiceError
from backend.services.vector_service import VectorSearchResult, VectorService

router = APIRouter(prefix="/majors", tags=["Major"])


class MajorRepository(Protocol):
    async def list_majors(
        self,
        *,
        category: str | None,
        keyword: str | None,
        limit: int,
        offset: int,
    ) -> MajorListResponse: ...

    async def get_major(self, major_id: int) -> MajorResponse | None: ...


class SqlAlchemyMajorRepository:
    def __init__(self, session: Any) -> None:
        self.session = session

    async def list_majors(
        self,
        *,
        category: str | None,
        keyword: str | None,
        limit: int,
        offset: int,
    ) -> MajorListResponse:
        from sqlalchemy import func, or_, select

        from backend.models.major import Major

        filters = []
        if category:
            filters.append(Major.category == category)
        if keyword:
            pattern = f"%{keyword}%"
            filters.append(
                or_(
                    Major.name.ilike(pattern),
                    Major.code.ilike(pattern),
                    Major.description.ilike(pattern),
                )
            )

        total_statement = select(func.count()).select_from(Major)
        list_statement = (
            select(Major).order_by(Major.name.asc(), Major.id.asc()).offset(offset).limit(limit)
        )
        if filters:
            total_statement = total_statement.where(*filters)
            list_statement = list_statement.where(*filters)

        total_result = await self.session.execute(total_statement)
        result = await self.session.execute(list_statement)
        return MajorListResponse(
            items=[MajorResponse.model_validate(major) for major in result.scalars().all()],
            total=int(total_result.scalar_one()),
            limit=limit,
            offset=offset,
        )

    async def get_major(self, major_id: int) -> MajorResponse | None:
        from sqlalchemy import select

        from backend.models.major import Major

        result = await self.session.execute(select(Major).where(Major.id == major_id))
        major = result.scalar_one_or_none()
        if major is None:
            return None
        return MajorResponse.model_validate(major)


async def get_session() -> AsyncIterator[Any]:
    from backend.core.database import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        yield session


def get_major_repository(session: Any = Depends(get_session)) -> MajorRepository:
    return SqlAlchemyMajorRepository(session)


def get_vector_service(session: Any = Depends(get_session)) -> VectorService:
    return VectorService(session)


def get_embedding_service() -> EmbeddingService:
    return EmbeddingService()


@router.get("", response_model=ApiResponse[MajorListResponse], summary="List majors")
async def list_majors(
    category: str | None = Query(None, min_length=1, max_length=100),
    keyword: str | None = Query(None, min_length=1, max_length=100),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    repository: MajorRepository = Depends(get_major_repository),
) -> ApiResponse[MajorListResponse]:
    return ApiResponse(
        code=0,
        message="success",
        data=await repository.list_majors(
            category=_normalize_optional_query(category),
            keyword=_normalize_optional_query(keyword),
            limit=limit,
            offset=offset,
        ),
    )


@router.get(
    "/search", response_model=ApiResponse[MajorSearchResponse], summary="Semantic major search"
)
async def search_majors(
    query: str = Query(..., min_length=1, max_length=1000),
    top_k: int = Query(10, ge=1, le=50),
    embedding_service: EmbeddingService = Depends(get_embedding_service),
    vector_service: VectorService = Depends(get_vector_service),
) -> ApiResponse[MajorSearchResponse]:
    payload = MajorSearchRequest(query=query, top_k=top_k)
    try:
        embedding = await embedding_service.embed_text(payload.query)
        results = await vector_service.search_majors(embedding, top_k=payload.top_k)
    except (ValueError, EmbeddingServiceError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return ApiResponse(
        code=0,
        message="success",
        data=MajorSearchResponse(
            query=payload.query,
            results=[_vector_result_to_major_search_result(result) for result in results],
        ),
    )


@router.get("/{major_id}", response_model=ApiResponse[MajorResponse], summary="Get major detail")
async def get_major(
    major_id: int,
    repository: MajorRepository = Depends(get_major_repository),
) -> ApiResponse[MajorResponse]:
    major = await repository.get_major(major_id)
    if major is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Major not found")
    return ApiResponse(code=0, message="success", data=major)


def _normalize_optional_query(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _vector_result_to_major_search_result(result: VectorSearchResult) -> MajorSearchResultResponse:
    item = result.item
    return MajorSearchResultResponse(
        id=result.id or getattr(item, "id"),
        name=result.name or getattr(item, "name"),
        code=getattr(item, "code", None),
        category=result.category or getattr(item, "category", None),
        description=getattr(item, "description", None),
        curriculum=getattr(item, "curriculum", None),
        embedding=getattr(item, "embedding", None),
        created_at=getattr(item, "created_at"),
        similarity_score=result.similarity_score,
    )
