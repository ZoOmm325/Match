import asyncio
from types import SimpleNamespace

import pytest

from backend.services.vector_service import VectorSearchResult, VectorService


class FakeExecuteResult:
    def __init__(self, rows):
        self.rows = rows

    def all(self):
        return self.rows


class FakeSession:
    def __init__(self, rows):
        self.rows = rows
        self.statements = []

    async def execute(self, statement):
        self.statements.append(statement)
        return FakeExecuteResult(self.rows)


class FakeModel:
    pass


def fake_table_resolver(table):
    if table in {"skills", "skill"}:
        return "skills", FakeModel
    if table in {"majors", "major"}:
        return "majors", FakeModel
    raise ValueError("bad table")


def fake_statement_builder(model, query_embedding, top_k):
    return {
        "model": model,
        "query_embedding": query_embedding,
        "top_k": top_k,
    }


def make_service(rows):
    return VectorService(
        FakeSession(rows),
        table_resolver=fake_table_resolver,
        statement_builder=fake_statement_builder,
    )


def test_search_similar_returns_similarity_results_for_skills():
    python = SimpleNamespace(
        id=1,
        name="Python Programming",
        normalized_name="Python",
        category="programming_language",
    )
    service = make_service([(python, 0.93)])

    results = asyncio.run(service.search_similar([0.1] * 1024, table="skills", top_k=5))

    assert results == [
        VectorSearchResult(
            item=python,
            similarity_score=0.93,
            table="skills",
            id=1,
            name="Python",
            category="programming_language",
        )
    ]
    assert service.session.statements == [
        {
            "model": FakeModel,
            "query_embedding": [0.1] * 1024,
            "top_k": 5,
        }
    ]


def test_search_majors_uses_major_table_and_name_fallback():
    major = SimpleNamespace(id=10, name="Software Engineering", category="工学")
    service = make_service([(major, 0.88)])

    results = asyncio.run(service.search_majors([1] * 1024, top_k=3))

    assert results[0].table == "majors"
    assert results[0].id == 10
    assert results[0].name == "Software Engineering"
    assert results[0].similarity_score == 0.88
    assert service.session.statements[0]["top_k"] == 3


def test_search_skills_shortcut_uses_skills_table():
    skill = SimpleNamespace(id=2, normalized_name="FastAPI", category="framework")
    service = make_service([(skill, 0.81)])

    results = asyncio.run(service.search_skills([0] * 1024))

    assert results[0].table == "skills"
    assert results[0].name == "FastAPI"


def test_search_clamps_and_rounds_similarity_scores():
    low = SimpleNamespace(id=1, normalized_name="Low")
    high = SimpleNamespace(id=2, normalized_name="High")
    precise = SimpleNamespace(id=3, normalized_name="Precise")
    nan_value = SimpleNamespace(id=4, normalized_name="NaN")
    service = make_service(
        [
            (low, -0.2),
            (high, 1.3),
            (precise, 0.876543),
            (nan_value, float("nan")),
        ]
    )

    results = asyncio.run(service.search_skills([0] * 1024))

    assert [result.similarity_score for result in results] == [0.0, 1.0, 0.8765, 0.0]


def test_search_rejects_wrong_embedding_dimension():
    service = make_service([])

    with pytest.raises(ValueError, match="1024"):
        asyncio.run(service.search_similar([0.1] * 2))


def test_search_rejects_non_numeric_embedding_values():
    service = make_service([])
    embedding = [0.1] * 1023 + ["bad"]

    with pytest.raises(ValueError, match="numeric"):
        asyncio.run(service.search_similar(embedding))


def test_search_rejects_boolean_embedding_values():
    service = make_service([])
    embedding = [0.1] * 1023 + [True]

    with pytest.raises(ValueError, match="numeric"):
        asyncio.run(service.search_similar(embedding))


def test_search_rejects_invalid_top_k():
    service = make_service([])

    with pytest.raises(ValueError, match="top_k"):
        asyncio.run(service.search_similar([0.1] * 1024, top_k=0))


def test_service_package_exports_vector_service():
    import backend.services as services

    assert "VectorService" in services.__all__
    assert "VectorSearchResult" in services.__all__
    assert services.VectorService is VectorService
