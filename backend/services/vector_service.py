from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Callable, Literal

from backend.services.embedding_service import EMBEDDING_DIMENSIONS

VectorTable = Literal["skills", "skill", "majors", "major"]
TableResolver = Callable[[str], tuple[str, type[Any]]]
StatementBuilder = Callable[[type[Any], list[float], int], Any]


@dataclass(frozen=True)
class VectorSearchResult:
    item: Any
    similarity_score: float
    table: str
    id: int | None = None
    name: str | None = None
    category: str | None = None


class VectorService:
    def __init__(
        self,
        session: Any,
        *,
        table_resolver: TableResolver | None = None,
        statement_builder: StatementBuilder | None = None,
    ) -> None:
        self.session = session
        self._table_resolver = table_resolver or self._resolve_table
        self._statement_builder = statement_builder or self._build_search_statement

    async def search_similar(
        self,
        query_embedding: list[float],
        *,
        table: VectorTable = "skills",
        top_k: int = 10,
    ) -> list[VectorSearchResult]:
        vector = self._validate_query_embedding(query_embedding)
        limit = self._validate_top_k(top_k)
        table_name, model = self._table_resolver(table)
        statement = self._statement_builder(model, vector, limit)
        result = await self.session.execute(statement)
        return [self._row_to_result(row, table=table_name) for row in result.all()]

    async def search_skills(
        self,
        query_embedding: list[float],
        *,
        top_k: int = 10,
    ) -> list[VectorSearchResult]:
        return await self.search_similar(query_embedding, table="skills", top_k=top_k)

    async def search_majors(
        self,
        query_embedding: list[float],
        *,
        top_k: int = 10,
    ) -> list[VectorSearchResult]:
        return await self.search_similar(query_embedding, table="majors", top_k=top_k)

    def _validate_query_embedding(self, query_embedding: list[float]) -> list[float]:
        if len(query_embedding) != EMBEDDING_DIMENSIONS:
            raise ValueError(
                f"query_embedding must contain exactly {EMBEDDING_DIMENSIONS} dimensions"
            )
        converted: list[float] = []
        for value in query_embedding:
            if isinstance(value, (bool, str, bytes)):
                raise ValueError("query_embedding must contain only numeric values")
            try:
                numeric_value = float(value)
            except (TypeError, ValueError, OverflowError) as exc:
                raise ValueError("query_embedding must contain only numeric values") from exc
            if not math.isfinite(numeric_value):
                raise ValueError("query_embedding must contain only finite numeric values")
            converted.append(numeric_value)
        return converted

    def _validate_top_k(self, top_k: int) -> int:
        if top_k < 1:
            raise ValueError("top_k must be at least 1")
        return top_k

    def _resolve_table(self, table: str) -> tuple[str, type[Any]]:
        normalized = table.strip().casefold()
        if normalized in {"skill", "skills"}:
            from backend.models.skill import Skill

            return "skills", Skill
        if normalized in {"major", "majors"}:
            from backend.models.major import Major

            return "majors", Major
        raise ValueError("table must be one of: skills, skill, majors, major")

    def _build_search_statement(
        self,
        model: type[Any],
        query_embedding: list[float],
        top_k: int,
    ) -> Any:
        from sqlalchemy import select

        distance = model.embedding.cosine_distance(query_embedding)
        similarity_score = (1 - distance).label("similarity_score")
        return (
            select(model, similarity_score)
            .where(model.embedding.is_not(None))
            .order_by(distance)
            .limit(top_k)
        )

    def _row_to_result(self, row: Any, *, table: str) -> VectorSearchResult:
        item, similarity_score = row
        return VectorSearchResult(
            item=item,
            similarity_score=self._normalize_similarity_score(similarity_score),
            table=table,
            id=getattr(item, "id", None),
            name=self._display_name(item),
            category=getattr(item, "category", None),
        )

    def _normalize_similarity_score(self, value: Any) -> float:
        score = float(value)
        if math.isnan(score):
            return 0.0
        return round(max(0.0, min(1.0, score)), 4)

    def _display_name(self, item: Any) -> str | None:
        normalized_name = getattr(item, "normalized_name", None)
        if normalized_name:
            return str(normalized_name)
        name = getattr(item, "name", None)
        return str(name) if name else None
