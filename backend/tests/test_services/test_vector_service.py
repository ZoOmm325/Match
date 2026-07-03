import os
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from pgvector.sqlalchemy import Vector
from sqlalchemy import Integer, String, text
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from backend.models import Skill
from backend.services.vector_service import VectorService


class PgVectorTestBase(DeclarativeBase):
    pass


class PgVectorRecord(PgVectorTestBase):
    __tablename__ = "test_vector_service_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(100), nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(1024), nullable=False)


@pytest_asyncio.fixture
async def pgvector_session() -> AsyncIterator[AsyncSession]:
    database_url = os.getenv("TEST_PGVECTOR_DATABASE_URL")
    if not database_url:
        pytest.skip("set TEST_PGVECTOR_DATABASE_URL to run the real pgvector integration test")

    engine = create_async_engine(database_url)
    async with engine.connect() as connection:
        transaction = await connection.begin()
        await connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await connection.run_sync(PgVectorTestBase.metadata.create_all)
        session = AsyncSession(bind=connection, expire_on_commit=False)
        try:
            yield session
        finally:
            await session.close()
            await transaction.rollback()
    await engine.dispose()


def test_vector_statement_uses_postgresql_cosine_distance(make_embedding):
    service = VectorService(session=None)

    statement = service._build_search_statement(
        Skill,
        make_embedding(0),
        5,
    )
    compiled = str(
        statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": False},
        )
    )

    assert "<=>" in compiled
    assert "ORDER BY" in compiled
    assert "LIMIT" in compiled
    assert "skills.embedding IS NOT NULL" in compiled


@pytest.mark.asyncio
async def test_vector_service_validates_dimension_and_limit(make_embedding):
    service = VectorService(session=None)

    with pytest.raises(ValueError, match="1024"):
        await service.search_skills([0.1, 0.2])
    with pytest.raises(ValueError, match="top_k"):
        await service.search_skills(make_embedding(0), top_k=0)


@pytest.mark.asyncio
@pytest.mark.pgvector
async def test_real_pgvector_search_orders_by_cosine_similarity(
    pgvector_session: AsyncSession,
    make_embedding,
):
    python = PgVectorRecord(
        name="Python",
        normalized_name="Python",
        category="programming_language",
        embedding=make_embedding(0),
    )
    java = PgVectorRecord(
        name="Java",
        normalized_name="Java",
        category="programming_language",
        embedding=make_embedding(1),
    )
    pgvector_session.add_all([java, python])
    await pgvector_session.flush()
    service = VectorService(
        pgvector_session,
        table_resolver=lambda _table: ("skills", PgVectorRecord),
    )

    results = await service.search_skills(make_embedding(0), top_k=2)

    assert [result.name for result in results] == ["Python", "Java"]
    assert results[0].similarity_score == 1.0
    assert results[0].similarity_score > results[1].similarity_score
