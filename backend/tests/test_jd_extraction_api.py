from datetime import datetime, timezone

from starlette.testclient import TestClient

from backend.main import app
from backend.routers.jd import (
    get_jd_read_repository,
    get_jd_service,
    get_public_job_fetcher,
    get_public_job_trend_fetcher,
)
from backend.schemas.jd import (
    ExtractedJdSkillResponse,
    JdFetchResponse,
    JdDetailResponse,
    JdListItemResponse,
    JdListResponse,
    JdTrendPointResponse,
    JdTrendResponse,
    JobMarketTrendPointResponse,
    JobMarketTrendResponse,
)
from backend.services.jd_service import ExtractedSkillResult, JdExtractionResult
from backend.services.job_fetcher import PublicJdFetchError

client = TestClient(app)


class FakeJdService:
    def __init__(self):
        self.calls = []

    async def extract_skills(self, jd_text, *, title=None, company=None, source=None):
        self.calls.append(
            {
                "jd_text": jd_text,
                "title": title,
                "company": company,
                "source": source,
            }
        )
        return JdExtractionResult(
            jd_id=42,
            skills=[
                ExtractedSkillResult(
                    name="Python",
                    normalized_name="Python",
                    category="programming_language",
                    proficiency_required="intermediate",
                    embedding=[0.1] * 1024,
                ),
                ExtractedSkillResult(
                    name="FastAPI",
                    normalized_name="FastAPI",
                    category="framework",
                    proficiency_required="advanced",
                    embedding=[0.2] * 1024,
                ),
            ],
        )


class FakeJdReadRepository:
    def __init__(self):
        now = datetime(2026, 6, 21, tzinfo=timezone.utc)
        skill = ExtractedJdSkillResponse(
            id=1,
            skill_id=10,
            name="Python",
            normalized_name="Python",
            category="programming_language",
            proficiency_required="intermediate",
            relevance_score=0.8,
            extraction_method="llm",
        )
        self.detail = JdDetailResponse(
            id=42,
            raw_text="Need Python and FastAPI for backend API development.",
            title="Backend Engineer",
            company="Example Inc",
            source=None,
            created_at=now,
            updated_at=now,
            skills=[skill],
        )
        self.deleted = []

    async def get_jd_detail(self, jd_id):
        if jd_id == self.detail.id:
            return self.detail
        return None

    async def list_jds(self, *, limit, offset):
        return JdListResponse(
            items=[
                JdListItemResponse(
                    id=self.detail.id,
                    raw_text=self.detail.raw_text,
                    title=self.detail.title,
                    company=self.detail.company,
                    source=self.detail.source,
                    created_at=self.detail.created_at,
                    updated_at=self.detail.updated_at,
                    skill_count=len(self.detail.skills),
                )
            ],
            total=1,
            limit=limit,
            offset=offset,
        )

    async def get_jd_trend(self, *, days):
        return JdTrendResponse(
            days=days,
            total=1,
            points=[
                JdTrendPointResponse(date="2026-06-21", count=1),
            ],
        )


    async def delete_jd(self, jd_id):
        if jd_id != self.detail.id:
            return False
        self.deleted.append(jd_id)
        return True


class FakePublicJobTrendFetcher:
    def __init__(self, *, fail=False):
        self.fail = fail
        self.calls = []

    async def fetch(self, *, keyword, years, source_url=None):
        self.calls.append({"keyword": keyword, "years": years, "source_url": source_url})
        if self.fail:
            raise PublicJdFetchError("public job trend search is temporarily unavailable")
        return JobMarketTrendResponse(
            keyword=keyword,
            years=years,
            total=3,
            source_url=source_url,
            points=[
                JobMarketTrendPointResponse(year=2022, count=0),
                JobMarketTrendPointResponse(year=2023, count=1),
                JobMarketTrendPointResponse(year=2024, count=2),
            ],
        )


class FakePublicJobFetcher:
    def __init__(self, *, fail=False):
        self.fail = fail
        self.calls = []

    async def fetch(self, payload):
        self.calls.append(payload)
        if self.fail:
            raise PublicJdFetchError("未找到可公开访问且允许抓取的岗位 JD")
        return JdFetchResponse(
            keyword=payload.keyword,
            title="机械设计工程师",
            source_url="https://example.com/jobs/1",
            source_domain="example.com",
            jd_text="岗位职责：负责机械结构设计、工程图绘制和量产问题分析。任职要求：熟悉机械原理、材料力学和 SolidWorks。",
            inspected_urls=["https://example.com/jobs/1"],
        )


def setup_function():
    app.dependency_overrides.clear()


def teardown_function():
    app.dependency_overrides.clear()


def test_health_check():
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"code": 0, "data": {"status": "ok"}, "message": "OK"}


def test_extract_jd_skills_api_success_persists_jd():
    service = FakeJdService()
    app.dependency_overrides[get_jd_service] = lambda: service

    response = client.post(
        "/api/jd/extract",
        json={
            "title": "Backend Engineer",
            "company": "Example Inc",
            "jd_text": "Need Python, FastAPI, PostgreSQL, and Docker for backend API development.",
        },
    )

    body = response.json()

    assert response.status_code == 200
    assert body["code"] == 0
    assert body["data"]["jd_id"] == 42
    assert body["data"]["skill_count"] == 2
    assert body["data"]["extraction_method"] == "llm"
    assert [skill["name"] for skill in body["data"]["skills"]] == ["Python", "FastAPI"]
    assert service.calls[0]["title"] == "Backend Engineer"


def test_extract_jd_skills_api_validation_error():
    app.dependency_overrides[get_jd_service] = lambda: FakeJdService()

    response = client.post("/api/jd/extract", json={"jd_text": "too short"})

    body = response.json()

    assert response.status_code == 422
    assert body["code"] == 422
    assert body["message"] == "Validation failed"


def test_extract_jd_skills_legacy_api_still_works():
    response = client.post(
        "/api/jd/extract-skills",
        json={
            "jd_text": "Need Python, FastAPI, PostgreSQL, and Docker experience for backend APIs.",
        },
    )

    assert response.status_code == 200
    assert response.json()["code"] == 0


def test_fetch_public_jd_api_returns_public_jd_text():
    fetcher = FakePublicJobFetcher()
    app.dependency_overrides[get_public_job_fetcher] = lambda: fetcher

    response = client.post("/api/jd/fetch", json={"keyword": "机械设计工程师"})

    body = response.json()

    assert response.status_code == 200
    assert body["code"] == 0
    assert body["data"]["title"] == "机械设计工程师"
    assert "机械结构设计" in body["data"]["jd_text"]
    assert body["data"]["source_domain"] == "example.com"
    assert fetcher.calls[0].keyword == "机械设计工程师"


def test_fetch_public_jd_api_returns_404_when_no_public_page_found():
    app.dependency_overrides[get_public_job_fetcher] = lambda: FakePublicJobFetcher(fail=True)

    response = client.post("/api/jd/fetch", json={"keyword": "不存在岗位"})

    assert response.status_code == 404
    assert response.json()["message"] == "未找到可公开访问且允许抓取的岗位 JD"


def test_fetch_public_jd_api_rejects_invalid_public_url():
    class InvalidUrlFetcher:
        async def fetch(self, payload):
            raise ValueError("source_url 必须是 http 或 https 开头的公开页面地址")

    app.dependency_overrides[get_public_job_fetcher] = lambda: InvalidUrlFetcher()

    response = client.post(
        "/api/jd/fetch",
        json={"keyword": "机械设计工程师", "source_url": "not-a-url"},
    )

    assert response.status_code == 400
    assert response.json()["message"] == "source_url 必须是 http 或 https 开头的公开页面地址"


def test_get_jd_detail_api_returns_skills():
    repository = FakeJdReadRepository()
    app.dependency_overrides[get_jd_read_repository] = lambda: repository

    response = client.get("/api/jd/42")

    body = response.json()

    assert response.status_code == 200
    assert body["code"] == 0
    assert body["data"]["id"] == 42
    assert body["data"]["skills"][0]["name"] == "Python"


def test_get_jd_detail_api_returns_404():
    repository = FakeJdReadRepository()
    app.dependency_overrides[get_jd_read_repository] = lambda: repository

    response = client.get("/api/jd/404")

    assert response.status_code == 404


def test_list_jds_api_supports_pagination():
    repository = FakeJdReadRepository()
    app.dependency_overrides[get_jd_read_repository] = lambda: repository

    response = client.get("/api/jd?limit=5&offset=10")

    body = response.json()

    assert response.status_code == 200
    assert body["data"]["total"] == 1
    assert body["data"]["limit"] == 5
    assert body["data"]["offset"] == 10
    assert body["data"]["items"][0]["skill_count"] == 1


def test_get_jd_trend_api_returns_daily_counts():
    repository = FakeJdReadRepository()
    app.dependency_overrides[get_jd_read_repository] = lambda: repository

    response = client.get("/api/jd/trend?days=7")

    body = response.json()

    assert response.status_code == 200
    assert body["data"]["days"] == 7
    assert body["data"]["total"] == 1
    assert body["data"]["points"][0] == {"date": "2026-06-21", "count": 1}


def test_get_job_market_trend_api_returns_yearly_keyword_counts():
    fetcher = FakePublicJobTrendFetcher()
    app.dependency_overrides[get_public_job_trend_fetcher] = lambda: fetcher

    response = client.get(
        "/api/jd/market-trend?keyword=Backend%20Engineer&years=3&source_url=https%3A%2F%2Fexample.com%2Fjobs%2F1"
    )

    body = response.json()

    assert response.status_code == 200
    assert body["data"]["keyword"] == "Backend Engineer"
    assert body["data"]["years"] == 3
    assert body["data"]["total"] == 3
    assert body["data"]["data_source"] == "public_web_search"
    assert body["data"]["source_url"] == "https://example.com/jobs/1"
    assert body["data"]["points"][-1] == {"year": 2024, "count": 2}
    assert fetcher.calls == [
        {
            "keyword": "Backend Engineer",
            "years": 3,
            "source_url": "https://example.com/jobs/1",
        }
    ]


def test_get_job_market_trend_api_returns_503_when_public_search_unavailable():
    app.dependency_overrides[get_public_job_trend_fetcher] = lambda: FakePublicJobTrendFetcher(
        fail=True
    )

    response = client.get("/api/jd/market-trend?keyword=Backend%20Engineer&years=3")

    assert response.status_code == 503
    assert response.json()["message"] == "public job trend search is temporarily unavailable"


def test_delete_jd_api_deletes_existing_jd():
    repository = FakeJdReadRepository()
    app.dependency_overrides[get_jd_read_repository] = lambda: repository

    response = client.delete("/api/jd/42")

    assert response.status_code == 200
    assert response.json() == {"code": 0, "data": None, "message": "success"}
    assert repository.deleted == [42]


def test_delete_jd_api_returns_404_for_missing_jd():
    repository = FakeJdReadRepository()
    app.dependency_overrides[get_jd_read_repository] = lambda: repository

    response = client.delete("/api/jd/404")

    assert response.status_code == 404
