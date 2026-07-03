from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

from backend.core.config import Settings
from backend.main import create_app
from backend.models import Jd, JdSkill, Major, Skill
from backend.routers import jd as jd_router
from backend.routers import major as major_router
from backend.routers import match as match_router
from backend.routers import skill as skill_router
from backend.schemas.jd import (
    ExtractedJdSkillResponse,
    JdDetailResponse,
    JdListItemResponse,
    JdListResponse,
)
from backend.schemas.major import MajorListResponse, MajorResponse
from backend.schemas.match_result import MatchHistoryResponseData, MatchRecommendationResponse
from backend.schemas.skill import (
    SkillCategoriesResponse,
    SkillListResponse,
    SkillResponse,
    SkillSummaryResponse,
)
from backend.services.jd_service import ExtractedSkillResult, JdExtractionResult
from backend.services.matching import MajorMatchResult, MatchingPipelineResult
from backend.services.recommendation.ranker import RankedRecommendation
from backend.services.vector_service import VectorSearchResult

NOW = datetime(2026, 7, 1, tzinfo=timezone.utc)
VALID_JD = "Need Python, FastAPI, PostgreSQL and Docker for backend API development."


@dataclass
class ApiState:
    deleted_jds: set[int] = field(default_factory=set)
    extraction_calls: list[str] = field(default_factory=list)
    pipeline_calls: list[str] = field(default_factory=list)
    saved_recommendations: list[RankedRecommendation] = field(default_factory=list)


def extracted_skill(name: str = "Python") -> ExtractedSkillResult:
    return ExtractedSkillResult(
        name=name,
        normalized_name=name,
        category="programming_language",
        proficiency_required="intermediate",
        embedding=[0.1] * 1024,
    )


def major_response(major_id: int = 1) -> MajorResponse:
    return MajorResponse(
        id=major_id,
        name="软件工程",
        code="080902",
        category="工学",
        description="培养软件开发和工程实践能力。",
        curriculum={"core": ["程序设计", "数据库系统"]},
        embedding=[0.2] * 1024,
        created_at=NOW,
    )


def skill_response(skill_id: int = 1) -> SkillResponse:
    return SkillResponse(
        id=skill_id,
        name="Python Programming",
        normalized_name="Python",
        category="programming_language",
        embedding=[0.1] * 1024,
        created_at=NOW,
    )


def recommendation() -> RankedRecommendation:
    return RankedRecommendation(
        rank=1,
        major_id=1,
        major_name="软件工程",
        major_code="080902",
        final_score=0.9,
        skill_similarity_score=0.92,
        skill_coverage_score=1.0,
        employment_alignment_score=0.75,
        matched_skills=["Python"],
        missing_skills=[],
        recommendation_reason="岗位技能与软件工程培养方向高度匹配。",
        score_details={"source": "api-integration-test"},
    )


def recommendation_response() -> MatchRecommendationResponse:
    item = recommendation()
    return MatchRecommendationResponse(
        rank=item.rank,
        major_id=item.major_id,
        major_name=item.major_name,
        major_code=item.major_code,
        final_score=item.final_score,
        skill_similarity_score=item.skill_similarity_score,
        skill_coverage_score=item.skill_coverage_score,
        employment_alignment_score=item.employment_alignment_score,
        matched_skills=item.matched_skills,
        missing_skills=item.missing_skills,
        recommendation_reason=item.recommendation_reason,
        score_details=item.score_details,
    )


class FakeJdService:
    def __init__(self, state: ApiState) -> None:
        self.state = state

    async def extract_skills(self, jd_text: str, **_kwargs: Any) -> JdExtractionResult:
        if "service-error" in jd_text:
            raise ValueError("JD extraction failed")
        self.state.extraction_calls.append(jd_text)
        return JdExtractionResult(jd_id=42, skills=[extracted_skill()])


class FakeJdRepository:
    def __init__(self, state: ApiState) -> None:
        self.state = state

    def detail(self) -> JdDetailResponse:
        return JdDetailResponse(
            id=42,
            raw_text=VALID_JD,
            title="Backend Engineer",
            company="Example Inc",
            source="api-test",
            created_at=NOW,
            updated_at=NOW,
            skills=[
                ExtractedJdSkillResponse(
                    id=1,
                    skill_id=1,
                    name="Python",
                    normalized_name="Python",
                    category="programming_language",
                    proficiency_required="intermediate",
                    relevance_score=0.8,
                    extraction_method="llm",
                )
            ],
        )

    async def get_jd_detail(self, jd_id: int) -> JdDetailResponse | None:
        if jd_id != 42 or jd_id in self.state.deleted_jds:
            return None
        return self.detail()

    async def list_jds(self, *, limit: int, offset: int) -> JdListResponse:
        detail = self.detail()
        items = (
            []
            if 42 in self.state.deleted_jds
            else [
                JdListItemResponse(
                    id=detail.id,
                    raw_text=detail.raw_text,
                    title=detail.title,
                    company=detail.company,
                    source=detail.source,
                    created_at=detail.created_at,
                    updated_at=detail.updated_at,
                    skill_count=len(detail.skills),
                )
            ]
        )
        return JdListResponse(
            items=items,
            total=len(items),
            limit=limit,
            offset=offset,
        )

    async def delete_jd(self, jd_id: int) -> bool:
        if jd_id != 42 or jd_id in self.state.deleted_jds:
            return False
        self.state.deleted_jds.add(jd_id)
        return True


class FakeSkillRepository:
    async def list_skills(
        self,
        *,
        category: str | None,
        keyword: str | None,
        limit: int,
        offset: int,
    ) -> SkillListResponse:
        item = skill_response()
        include = (not category or item.category == category) and (
            not keyword or keyword.casefold() in item.normalized_name.casefold()
        )
        return SkillListResponse(
            items=(
                [
                    SkillSummaryResponse(
                        id=item.id,
                        name=item.name,
                        normalized_name=item.normalized_name,
                        category=item.category,
                        created_at=item.created_at,
                    )
                ]
                if include
                else []
            ),
            total=1 if include else 0,
            limit=limit,
            offset=offset,
        )

    async def get_skill(self, skill_id: int) -> SkillResponse | None:
        return skill_response() if skill_id == 1 else None

    async def list_categories(self) -> SkillCategoriesResponse:
        return SkillCategoriesResponse(categories=["database", "framework", "programming_language"])


class FakeMajorRepository:
    async def list_majors(
        self,
        *,
        category: str | None,
        keyword: str | None,
        limit: int,
        offset: int,
    ) -> MajorListResponse:
        item = major_response()
        include = (not category or item.category == category) and (
            not keyword or keyword in item.name
        )
        return MajorListResponse(
            items=[item] if include else [],
            total=1 if include else 0,
            limit=limit,
            offset=offset,
        )

    async def get_major(self, major_id: int) -> MajorResponse | None:
        return major_response() if major_id == 1 else None


class FakeEmbeddingService:
    async def embed_text(self, _text: str) -> list[float]:
        return [0.2] * 1024

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [[0.2] * 1024 for _ in texts]


class FakeVectorService:
    async def search_majors(
        self,
        _embedding: list[float],
        *,
        top_k: int,
    ) -> list[VectorSearchResult]:
        item = major_response()
        return [
            VectorSearchResult(
                item=item,
                similarity_score=0.91,
                table="majors",
                id=item.id,
                name=item.name,
                category=item.category,
            )
        ][:top_k]


class FakePipeline:
    def __init__(self, state: ApiState) -> None:
        self.state = state

    async def run(self, jd_text: str, **_kwargs: Any) -> MatchingPipelineResult:
        if "pipeline-error" in jd_text:
            raise ValueError("Matching pipeline failed")
        self.state.pipeline_calls.append(jd_text)
        return MatchingPipelineResult(
            jd_id=42,
            extracted_skills=[extracted_skill()],
            skill_matches=[],
            major_matches=[major_match()],
        )


class FakeMajorMatcher:
    async def match_skills_to_majors(
        self,
        skills: list[ExtractedSkillResult],
        *,
        top_n: int,
    ) -> list[MajorMatchResult]:
        if skills[0].name == "RaiseError":
            raise ValueError("Invalid explicit skill")
        return [major_match()][:top_n]


class FakeRanker:
    async def rank_major_matches(self, *_args: Any, **_kwargs: Any):
        return [recommendation()]


class FakeRankedRepository:
    def __init__(self, state: ApiState) -> None:
        self.state = state

    async def save_ranked_recommendations(
        self,
        *,
        jd_id: int | None,
        recommendations: list[RankedRecommendation],
    ) -> int:
        self.state.saved_recommendations = list(recommendations)
        return len(recommendations) if jd_id is not None else 0


class FakeHistoryRepository:
    async def get_match_history(
        self,
        jd_id: int,
    ) -> MatchHistoryResponseData | None:
        if jd_id != 42:
            return None
        return MatchHistoryResponseData(
            jd_id=jd_id,
            recommendations=[recommendation_response()],
        )


def major_match() -> MajorMatchResult:
    return MajorMatchResult(
        major_id=1,
        major_name="软件工程",
        major_code="080902",
        major_category="工学",
        similarity_score=0.92,
        coverage_score=1.0,
        final_score=0.9,
        matched_skills=["Python"],
        missing_skills=[],
        match_details={"source": "api-integration-test"},
    )


@pytest.fixture
def api_state() -> ApiState:
    return ApiState()


@pytest.fixture
def api_app(api_state: ApiState) -> FastAPI:
    app = create_app(Settings(_env_file=None))
    jd_repository = FakeJdRepository(api_state)
    app.dependency_overrides.update(
        {
            jd_router.get_jd_service: lambda: FakeJdService(api_state),
            jd_router.get_jd_read_repository: lambda: jd_repository,
            skill_router.get_skill_repository: FakeSkillRepository,
            major_router.get_major_repository: FakeMajorRepository,
            major_router.get_embedding_service: FakeEmbeddingService,
            major_router.get_vector_service: FakeVectorService,
            match_router.get_matching_pipeline: lambda: FakePipeline(api_state),
            match_router.get_major_matcher: FakeMajorMatcher,
            match_router.get_recommendation_ranker: FakeRanker,
            match_router.get_embedding_service: FakeEmbeddingService,
            match_router.get_ranked_match_result_repository: lambda: FakeRankedRepository(
                api_state
            ),
            match_router.get_match_history_repository: FakeHistoryRepository,
        }
    )
    yield app
    app.dependency_overrides.clear()


@pytest.fixture
def client(api_app: FastAPI):
    with TestClient(api_app, raise_server_exceptions=False) as test_client:
        yield test_client


SUCCESS_CASES = [
    ("GET", "/api/health", None),
    ("POST", "/api/jd/extract", {"jd_text": VALID_JD}),
    ("POST", "/api/jd/extract-skills", {"jd_text": VALID_JD}),
    ("GET", "/api/jd?limit=20&offset=0", None),
    ("GET", "/api/jd/42", None),
    ("DELETE", "/api/jd/42", None),
    ("GET", "/api/skills", None),
    ("GET", "/api/skills/categories", None),
    ("GET", "/api/skills/1", None),
    ("GET", "/api/majors", None),
    ("GET", "/api/majors/search?query=Python&top_k=5", None),
    ("GET", "/api/majors/1", None),
    ("POST", "/api/match", {"jd_text": VALID_JD}),
    (
        "POST",
        "/api/match/by-skills",
        {"skills": [{"name": "Python", "category": "programming_language"}]},
    ),
    ("GET", "/api/match/42", None),
]


@pytest.mark.parametrize(("method", "url", "payload"), SUCCESS_CASES)
def test_every_api_operation_returns_standard_success_envelope(
    client: TestClient,
    method: str,
    url: str,
    payload: dict[str, Any] | None,
):
    response = client.request(method, url, json=payload)
    body = response.json()

    assert response.status_code == 200
    assert set(body) == {"code", "data", "message"}
    assert body["code"] == 0
    assert body["message"] in {"OK", "success"}
    assert body["data"] is not None or method == "DELETE"
    assert response.headers["X-Request-ID"]
    assert float(response.headers["X-Process-Time-Ms"]) >= 0


VALIDATION_CASES = [
    ("POST", "/api/health", None, 405),
    ("POST", "/api/jd/extract", {"jd_text": "short"}, 422),
    ("POST", "/api/jd/extract-skills", {"jd_text": "short"}, 422),
    ("GET", "/api/jd?limit=0", None, 422),
    ("GET", "/api/jd/not-an-id", None, 422),
    ("DELETE", "/api/jd/not-an-id", None, 422),
    ("GET", "/api/skills?limit=101", None, 422),
    ("POST", "/api/skills/categories", None, 405),
    ("GET", "/api/skills/not-an-id", None, 422),
    ("GET", "/api/majors?offset=-1", None, 422),
    ("GET", "/api/majors/search?query=&top_k=0", None, 422),
    ("GET", "/api/majors/not-an-id", None, 422),
    ("POST", "/api/match", {"jd_text": "short"}, 422),
    ("POST", "/api/match/by-skills", {"skills": []}, 422),
    ("GET", "/api/match/not-an-id", None, 422),
]


@pytest.mark.parametrize(
    ("method", "url", "payload", "expected_status"),
    VALIDATION_CASES,
)
def test_every_api_operation_handles_invalid_requests_consistently(
    client: TestClient,
    method: str,
    url: str,
    payload: dict[str, Any] | None,
    expected_status: int,
):
    response = client.request(method, url, json=payload)
    body = response.json()

    assert response.status_code == expected_status
    assert set(body) == {"code", "data", "message"}
    assert body["code"] == expected_status
    if expected_status == 422:
        assert body["message"] == "Validation failed"
        assert body["data"]["errors"]


BOUNDARY_CASES = [
    ("GET", "/api/health", None),
    ("POST", "/api/jd/extract", {"jd_text": "x" * 20}),
    ("POST", "/api/jd/extract-skills", {"jd_text": "Python Docker SQL API"}),
    ("GET", "/api/jd?limit=100&offset=0", None),
    ("GET", "/api/jd/42", None),
    ("DELETE", "/api/jd/42", None),
    (
        "GET",
        "/api/skills?category=programming_language&keyword=Python&limit=100&offset=0",
        None,
    ),
    ("GET", "/api/skills/categories?unused=value", None),
    ("GET", "/api/skills/1", None),
    ("GET", "/api/majors?category=工学&keyword=软件&limit=100&offset=0", None),
    ("GET", "/api/majors/search?query=Python&top_k=50", None),
    ("GET", "/api/majors/1", None),
    (
        "POST",
        "/api/match",
        {
            "jd_text": VALID_JD,
            "skill_top_k": 100,
            "major_top_n": 50,
            "skill_threshold": 0,
        },
    ),
    (
        "POST",
        "/api/match/by-skills",
        {
            "top_n": 50,
            "skills": [
                {
                    "name": "Python",
                    "embedding": [0.1] * 1024,
                }
            ],
        },
    ),
    ("GET", "/api/match/42", None),
]


@pytest.mark.parametrize(("method", "url", "payload"), BOUNDARY_CASES)
def test_every_api_operation_accepts_documented_boundary_values(
    client: TestClient,
    method: str,
    url: str,
    payload: dict[str, Any] | None,
):
    response = client.request(method, url, json=payload)

    assert response.status_code == 200
    assert response.json()["code"] == 0


@pytest.mark.parametrize(
    ("method", "url", "message"),
    [
        ("GET", "/api/jd/404", "JD not found"),
        ("DELETE", "/api/jd/404", "JD not found"),
        ("GET", "/api/skills/404", "Skill not found"),
        ("GET", "/api/majors/404", "Major not found"),
        ("GET", "/api/match/404", "Match history not found"),
    ],
)
def test_missing_resources_return_standard_404(
    client: TestClient,
    method: str,
    url: str,
    message: str,
):
    response = client.request(method, url)

    assert response.status_code == 404
    assert response.json() == {"code": 404, "data": None, "message": message}


def test_complete_jd_to_match_history_workflow(
    client: TestClient,
    api_state: ApiState,
):
    extraction = client.post("/api/jd/extract", json={"jd_text": VALID_JD})
    jd_id = extraction.json()["data"]["jd_id"]
    detail = client.get(f"/api/jd/{jd_id}")
    match = client.post("/api/match", json={"jd_text": VALID_JD})
    history = client.get(f"/api/match/{jd_id}")
    major = client.get("/api/majors/1")
    deleted = client.delete(f"/api/jd/{jd_id}")
    missing_after_delete = client.get(f"/api/jd/{jd_id}")

    assert extraction.json()["data"]["skills"][0]["name"] == "Python"
    assert detail.json()["data"]["skills"][0]["normalized_name"] == "Python"
    assert match.json()["data"]["recommendations"][0]["major_id"] == 1
    assert history.json()["data"]["recommendations"][0]["major_name"] == "软件工程"
    assert major.json()["data"]["curriculum"]["core"]
    assert deleted.status_code == 200
    assert missing_after_delete.status_code == 404
    assert api_state.extraction_calls == [VALID_JD]
    assert api_state.pipeline_calls == [VALID_JD]
    assert len(api_state.saved_recommendations) == 1


@pytest.mark.asyncio
async def test_async_client_uses_same_asgi_contract(api_app: FastAPI):
    transport = httpx.ASGITransport(app=api_app, raise_app_exceptions=False)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as async_client:
        health, skills, missing = await _gather_responses(
            async_client.get("/api/health"),
            async_client.get("/api/skills?limit=1"),
            async_client.get("/api/majors/404"),
        )

    assert health.json() == {"code": 0, "data": {"status": "ok"}, "message": "OK"}
    assert skills.json()["data"]["limit"] == 1
    assert missing.json() == {
        "code": 404,
        "data": None,
        "message": "Major not found",
    }


async def _gather_responses(*requests):
    import asyncio

    return await asyncio.gather(*requests)


def test_route_value_errors_and_unhandled_errors_hide_internal_details(
    client: TestClient,
    api_app: FastAPI,
):
    value_error = client.post(
        "/api/jd/extract",
        json={"jd_text": "service-error " + "x" * 20},
    )

    class ExplodingSkillRepository:
        async def list_skills(self, **_kwargs):
            raise RuntimeError("private database failure")

    api_app.dependency_overrides[skill_router.get_skill_repository] = ExplodingSkillRepository
    unexpected = client.get("/api/skills")

    assert value_error.status_code == 400
    assert value_error.json() == {
        "code": 400,
        "data": None,
        "message": "JD extraction failed",
    }
    assert unexpected.status_code == 500
    assert unexpected.json() == {
        "code": 500,
        "data": None,
        "message": "Internal server error",
    }
    assert "private database failure" not in unexpected.text


@pytest.mark.asyncio
async def test_sqlalchemy_api_read_repositories_execute_real_crud(db_session):
    jd = Jd(
        raw_text=VALID_JD,
        title="Backend Engineer",
        company="Example Inc",
        source="repository-test",
    )
    skill = Skill(
        name="Python Programming",
        normalized_name="Python",
        category="programming_language",
        embedding=[0.1] * 1024,
    )
    major = Major(
        name="软件工程",
        code="080902",
        category="工学",
        description="培养软件开发和工程实践能力。",
        curriculum={"core": ["程序设计"]},
        embedding=[0.2] * 1024,
    )
    db_session.add_all([jd, skill, major])
    await db_session.flush()
    db_session.add(
        JdSkill(
            jd_id=jd.id,
            skill_id=skill.id,
            relevance_score=0.8,
            extraction_method="llm",
        )
    )
    await db_session.commit()

    jd_repository = jd_router.SqlAlchemyJdReadRepository(db_session)
    skill_repository = skill_router.SqlAlchemySkillRepository(db_session)
    major_repository = major_router.SqlAlchemyMajorRepository(db_session)

    jd_list = await jd_repository.list_jds(limit=10, offset=0)
    jd_detail = await jd_repository.get_jd_detail(jd.id)
    skill_list = await skill_repository.list_skills(
        category="programming_language",
        keyword="Python",
        limit=10,
        offset=0,
    )
    skill_detail = await skill_repository.get_skill(skill.id)
    categories = await skill_repository.list_categories()
    major_list = await major_repository.list_majors(
        category="工学",
        keyword="软件",
        limit=10,
        offset=0,
    )
    major_detail = await major_repository.get_major(major.id)

    assert jd_list.total == 1
    assert jd_list.items[0].skill_count == 1
    assert jd_detail is not None
    assert jd_detail.skills[0].normalized_name == "Python"
    assert skill_list.total == 1
    assert skill_detail is not None
    assert len(skill_detail.embedding or []) == 1024
    assert categories.categories == ["programming_language"]
    assert major_list.total == 1
    assert major_detail is not None
    assert major_detail.curriculum == {"core": ["程序设计"]}
    assert await jd_repository.get_jd_detail(9999) is None
    assert await skill_repository.get_skill(9999) is None
    assert await major_repository.get_major(9999) is None
    assert await jd_repository.delete_jd(9999) is False
    assert await jd_repository.delete_jd(jd.id) is True
    assert await jd_repository.get_jd_detail(jd.id) is None


@pytest.mark.asyncio
async def test_sqlalchemy_match_repositories_persist_update_and_restore_history(
    db_session,
):
    jd = Jd(raw_text=VALID_JD, title="Backend Engineer")
    major = Major(
        name="软件工程",
        code="080902",
        category="工学",
    )
    db_session.add_all([jd, major])
    await db_session.commit()
    item = replace(recommendation(), major_id=major.id)
    ranked_repository = match_router.SqlAlchemyRankedMatchResultRepository(db_session)
    history_repository = match_router.SqlAlchemyMatchHistoryRepository(db_session)

    assert (
        await ranked_repository.save_ranked_recommendations(
            jd_id=None,
            recommendations=[item],
        )
        == 0
    )
    assert (
        await ranked_repository.save_ranked_recommendations(
            jd_id=jd.id,
            recommendations=[replace(item, major_id=None)],
        )
        == 0
    )
    assert (
        await ranked_repository.save_ranked_recommendations(
            jd_id=jd.id,
            recommendations=[item],
        )
        == 1
    )

    updated = replace(
        item,
        final_score=0.95,
        recommendation_reason="更新后的推荐理由。",
    )
    assert (
        await ranked_repository.save_ranked_recommendations(
            jd_id=jd.id,
            recommendations=[updated],
        )
        == 1
    )

    history = await history_repository.get_match_history(jd.id)
    missing = await history_repository.get_match_history(9999)

    assert history is not None
    assert history.recommendations[0].final_score == 0.95
    assert history.recommendations[0].recommendation_reason == "更新后的推荐理由。"
    assert missing is None


def test_router_compatibility_module_exports_current_jd_endpoints():
    from backend.routers import jd_extraction

    assert jd_extraction.router is jd_router.router
    assert jd_extraction.extract_jd_skills is jd_router.extract_jd_skills
