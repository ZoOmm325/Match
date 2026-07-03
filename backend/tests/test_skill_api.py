from datetime import datetime, timezone

from starlette.testclient import TestClient

from backend.main import app
from backend.routers.skill import get_skill_repository
from backend.schemas.skill import (
    SkillCategoriesResponse,
    SkillListResponse,
    SkillResponse,
    SkillSummaryResponse,
)

client = TestClient(app)


def make_skill_response(skill_id=1):
    return SkillResponse(
        id=skill_id,
        name="Python Programming",
        normalized_name="Python",
        category="programming_language",
        embedding=[0.1] * 1024,
        created_at=datetime(2026, 7, 1, tzinfo=timezone.utc),
    )


class FakeSkillRepository:
    def __init__(self):
        self.calls = []
        self.skill = make_skill_response()

    async def list_skills(self, *, category, keyword, limit, offset):
        self.calls.append(
            {
                "category": category,
                "keyword": keyword,
                "limit": limit,
                "offset": offset,
            }
        )
        return SkillListResponse(
            items=[
                SkillSummaryResponse(
                    id=self.skill.id,
                    name=self.skill.name,
                    normalized_name=self.skill.normalized_name,
                    category=self.skill.category,
                    created_at=self.skill.created_at,
                )
            ],
            total=1,
            limit=limit,
            offset=offset,
        )

    async def get_skill(self, skill_id):
        if skill_id == self.skill.id:
            return self.skill
        return None

    async def list_categories(self):
        return SkillCategoriesResponse(categories=["database", "framework", "programming_language"])


def setup_function():
    app.dependency_overrides.clear()


def teardown_function():
    app.dependency_overrides.clear()


def test_list_skills_supports_category_search_and_pagination():
    repository = FakeSkillRepository()
    app.dependency_overrides[get_skill_repository] = lambda: repository

    response = client.get(
        "/api/skills?category=programming_language&keyword=python&limit=5&offset=10"
    )

    body = response.json()

    assert response.status_code == 200
    assert body["code"] == 0
    assert body["data"]["total"] == 1
    assert body["data"]["items"][0]["normalized_name"] == "Python"
    assert "embedding" not in body["data"]["items"][0]
    assert repository.calls == [
        {
            "category": "programming_language",
            "keyword": "python",
            "limit": 5,
            "offset": 10,
        }
    ]


def test_get_skill_detail_returns_embedding():
    repository = FakeSkillRepository()
    app.dependency_overrides[get_skill_repository] = lambda: repository

    response = client.get("/api/skills/1")

    body = response.json()

    assert response.status_code == 200
    assert body["data"]["id"] == 1
    assert len(body["data"]["embedding"]) == 1024


def test_get_skill_detail_returns_404():
    repository = FakeSkillRepository()
    app.dependency_overrides[get_skill_repository] = lambda: repository

    response = client.get("/api/skills/404")

    assert response.status_code == 404


def test_list_skill_categories_returns_sorted_unique_categories():
    repository = FakeSkillRepository()
    app.dependency_overrides[get_skill_repository] = lambda: repository

    response = client.get("/api/skills/categories")

    assert response.status_code == 200
    assert response.json()["data"]["categories"] == [
        "database",
        "framework",
        "programming_language",
    ]


def test_list_skills_validation_error():
    app.dependency_overrides[get_skill_repository] = lambda: FakeSkillRepository()

    response = client.get("/api/skills?limit=0")

    assert response.status_code == 422
    assert response.json()["message"] == "Validation failed"


def test_skill_router_is_registered_on_app():
    paths = set(client.get("/openapi.json").json()["paths"])

    assert "/api/skills" in paths
    assert "/api/skills/categories" in paths
    assert "/api/skills/{skill_id}" in paths
