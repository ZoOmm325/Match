from datetime import datetime, timezone
from types import SimpleNamespace

from starlette.testclient import TestClient

from backend.main import app
from backend.routers.major import get_embedding_service, get_major_repository, get_vector_service
from backend.schemas.major import MajorListResponse, MajorResponse
from backend.services.embedding_service import EmbeddingServiceError
from backend.services.vector_service import VectorSearchResult

client = TestClient(app)


def make_major_response(major_id=1, name="软件工程", category="工学"):
    return MajorResponse(
        id=major_id,
        name=name,
        code="080902",
        category=category,
        description="培养软件开发和工程实践能力。",
        curriculum={"core": ["程序设计", "数据库"]},
        embedding=[0.1] * 1024,
        created_at=datetime(2026, 6, 21, tzinfo=timezone.utc),
    )


class FakeMajorRepository:
    def __init__(self):
        self.calls = []
        self.major = make_major_response()

    async def list_majors(self, *, category, keyword, limit, offset):
        self.calls.append(
            {
                "category": category,
                "keyword": keyword,
                "limit": limit,
                "offset": offset,
            }
        )
        return MajorListResponse(items=[self.major], total=1, limit=limit, offset=offset)

    async def get_major(self, major_id):
        if major_id == self.major.id:
            return self.major
        return None


class FakeEmbeddingService:
    def __init__(self):
        self.calls = []

    async def embed_text(self, text):
        self.calls.append(text)
        return [0.2] * 1024


class FakeVectorService:
    def __init__(self):
        self.calls = []

    async def search_majors(self, embedding, *, top_k):
        self.calls.append({"embedding": embedding, "top_k": top_k})
        item = SimpleNamespace(
            id=2,
            name="人工智能",
            code="080717T",
            category="工学",
            description="面向机器学习和智能系统。",
            curriculum={"core": ["机器学习"]},
            embedding=[0.3] * 1024,
            created_at=datetime(2026, 6, 21, tzinfo=timezone.utc),
        )
        return [
            VectorSearchResult(
                item=item,
                similarity_score=0.91,
                table="majors",
                id=item.id,
                name=item.name,
                category=item.category,
            )
        ]


def setup_function():
    app.dependency_overrides.clear()


def teardown_function():
    app.dependency_overrides.clear()


def test_list_majors_supports_filters_and_pagination():
    repository = FakeMajorRepository()
    app.dependency_overrides[get_major_repository] = lambda: repository

    response = client.get("/api/majors?category=工学&keyword=软件&limit=5&offset=10")

    body = response.json()

    assert response.status_code == 200
    assert body["code"] == 0
    assert body["data"]["total"] == 1
    assert body["data"]["items"][0]["name"] == "软件工程"
    assert repository.calls == [{"category": "工学", "keyword": "软件", "limit": 5, "offset": 10}]


def test_get_major_detail_returns_curriculum():
    repository = FakeMajorRepository()
    app.dependency_overrides[get_major_repository] = lambda: repository

    response = client.get("/api/majors/1")

    body = response.json()

    assert response.status_code == 200
    assert body["data"]["id"] == 1
    assert body["data"]["curriculum"] == {"core": ["程序设计", "数据库"]}


def test_get_major_detail_returns_404():
    repository = FakeMajorRepository()
    app.dependency_overrides[get_major_repository] = lambda: repository

    response = client.get("/api/majors/404")

    assert response.status_code == 404


def test_search_majors_embeds_query_and_uses_vector_service():
    embedding_service = FakeEmbeddingService()
    vector_service = FakeVectorService()
    app.dependency_overrides[get_embedding_service] = lambda: embedding_service
    app.dependency_overrides[get_vector_service] = lambda: vector_service

    response = client.get("/api/majors/search?query=机器学习算法工程师&top_k=3")

    body = response.json()

    assert response.status_code == 200
    assert body["code"] == 0
    assert body["data"]["query"] == "机器学习算法工程师"
    assert body["data"]["results"][0]["name"] == "人工智能"
    assert body["data"]["results"][0]["similarity_score"] == 0.91
    assert embedding_service.calls == ["机器学习算法工程师"]
    assert vector_service.calls == [{"embedding": [0.2] * 1024, "top_k": 3}]


def test_search_majors_validation_error():
    app.dependency_overrides[get_embedding_service] = lambda: FakeEmbeddingService()
    app.dependency_overrides[get_vector_service] = lambda: FakeVectorService()

    response = client.get("/api/majors/search?query=&top_k=0")

    assert response.status_code == 422
    assert response.json()["message"] == "Validation failed"


def test_search_majors_returns_400_for_embedding_errors():
    class FailingEmbeddingService:
        async def embed_text(self, text):
            raise EmbeddingServiceError("embedding unavailable")

    app.dependency_overrides[get_embedding_service] = lambda: FailingEmbeddingService()
    app.dependency_overrides[get_vector_service] = lambda: FakeVectorService()

    response = client.get("/api/majors/search?query=machine-learning")

    assert response.status_code == 400
    assert response.json()["message"] == "embedding unavailable"


def test_major_router_is_registered_on_app():
    paths = set(client.get("/openapi.json").json()["paths"])

    assert "/api/majors" in paths
    assert "/api/majors/search" in paths
    assert "/api/majors/{major_id}" in paths
