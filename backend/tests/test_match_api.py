import asyncio
from types import SimpleNamespace

from starlette.testclient import TestClient

from backend.main import app
from backend.routers.match import (
    SqlAlchemyRankedMatchResultRepository,
    _history_row_to_recommendation,
    get_embedding_service,
    get_major_matcher,
    get_match_history_repository,
    get_matching_pipeline,
    get_ranked_match_result_repository,
    get_recommendation_ranker,
)
from backend.schemas.match_result import MatchHistoryResponseData, MatchRecommendationResponse
from backend.services.jd_service import ExtractedSkillResult
from backend.services.matching.major_matcher import MajorMatchResult
from backend.services.matching.pipeline import MatchingPipelineResult
from backend.services.recommendation.ranker import RankedRecommendation

client = TestClient(app)


def extracted_skill(name="Python", embedding=None):
    return ExtractedSkillResult(
        name=name,
        normalized_name=name,
        category="programming_language",
        proficiency_required="intermediate",
        embedding=embedding or [0.1] * 1024,
    )


def major_match():
    return MajorMatchResult(
        major_id=7,
        major_name="软件工程",
        major_code="080902",
        major_category="工学",
        similarity_score=0.88,
        coverage_score=0.75,
        final_score=0.84,
        matched_skills=["Python"],
        missing_skills=["Docker"],
        match_details={"source": "test"},
    )


def ranked_recommendation(rank=1):
    return RankedRecommendation(
        rank=rank,
        major_id=7,
        major_name="软件工程",
        major_code="080902",
        final_score=0.84,
        skill_similarity_score=0.88,
        skill_coverage_score=0.75,
        employment_alignment_score=0.5,
        matched_skills=["Python"],
        missing_skills=["Docker"],
        recommendation_reason="技能匹配度较高，适合软件工程方向。",
        score_details={"weights": {"skill_similarity": 0.5}},
    )


class FakePipeline:
    def __init__(self):
        self.calls = []

    async def run(self, jd_text, **kwargs):
        self.calls.append({"jd_text": jd_text, **kwargs})
        return MatchingPipelineResult(
            jd_id=42,
            extracted_skills=[extracted_skill()],
            skill_matches=[],
            major_matches=[major_match()],
            persisted_count=1,
        )


class FakeMajorMatcher:
    def __init__(self):
        self.calls = []

    async def match_skills_to_majors(self, skills, *, top_n):
        self.calls.append({"skills": list(skills), "top_n": top_n})
        return [major_match()]


class FakeRanker:
    def __init__(self):
        self.calls = []

    async def rank_major_matches(
        self, major_matches, *, skills, top_n, generate_reasons, employment_evaluator=None
    ):
        self.calls.append(
            {
                "major_matches": list(major_matches),
                "skills": list(skills),
                "top_n": top_n,
                "generate_reasons": generate_reasons,
                "employment_evaluator": employment_evaluator,
            }
        )
        return [ranked_recommendation()]


class FakeEmbeddingService:
    def __init__(self):
        self.calls = []

    async def embed_texts(self, texts):
        self.calls.append(list(texts))
        return [[0.2] * 1024 for _ in texts]


class MismatchedEmbeddingService:
    async def embed_texts(self, texts):
        return []


class FakeRankedMatchResultRepository:
    def __init__(self):
        self.calls = []

    async def save_ranked_recommendations(self, *, jd_id, recommendations):
        self.calls.append({"jd_id": jd_id, "recommendations": list(recommendations)})
        return len([item for item in recommendations if item.major_id is not None])


class FakeScalarResult:
    def __init__(self, item):
        self.item = item

    def scalar_one_or_none(self):
        return self.item


class FakeSession:
    def __init__(self, existing=None):
        self.existing = existing
        self.added = []
        self.commits = 0

    async def execute(self, statement):
        return FakeScalarResult(self.existing)

    def add(self, item):
        self.added.append(item)

    async def commit(self):
        self.commits += 1


class FakeHistoryRepository:
    async def get_match_history(self, jd_id):
        if jd_id != 42:
            return None
        return MatchHistoryResponseData(
            jd_id=42,
            recommendations=[
                MatchRecommendationResponse(
                    rank=1,
                    major_id=7,
                    major_name="软件工程",
                    major_code="080902",
                    final_score=0.84,
                    skill_similarity_score=0.88,
                    skill_coverage_score=0.75,
                    employment_alignment_score=0.5,
                    matched_skills=["Python"],
                    missing_skills=["Docker"],
                    recommendation_reason="历史匹配结果",
                    score_details={"source": "history"},
                )
            ],
        )


def setup_function():
    app.dependency_overrides.clear()


def teardown_function():
    app.dependency_overrides.clear()


def test_match_jd_runs_pipeline_and_returns_recommendations():
    pipeline = FakePipeline()
    ranker = FakeRanker()
    repository = FakeRankedMatchResultRepository()
    app.dependency_overrides[get_matching_pipeline] = lambda: pipeline
    app.dependency_overrides[get_recommendation_ranker] = lambda: ranker
    app.dependency_overrides[get_ranked_match_result_repository] = lambda: repository

    response = client.post(
        "/api/match",
        json={
            "jd_text": "Need Python, FastAPI, PostgreSQL and Docker for backend API development.",
            "major_top_n": 3,
            "generate_reasons": False,
        },
    )

    body = response.json()

    assert response.status_code == 200
    assert body["code"] == 0
    assert body["data"]["jd_id"] == 42
    assert body["data"]["persisted_count"] == 1
    assert body["data"]["recommendations"][0]["major_name"] == "软件工程"
    assert pipeline.calls[0]["major_top_n"] == 3
    assert pipeline.calls[0]["persist"] is False
    assert ranker.calls[0]["generate_reasons"] is False
    assert repository.calls[0]["jd_id"] == 42
    assert repository.calls[0]["recommendations"][0].recommendation_reason


def test_match_jd_validation_error():
    app.dependency_overrides[get_matching_pipeline] = lambda: FakePipeline()
    app.dependency_overrides[get_recommendation_ranker] = lambda: FakeRanker()
    app.dependency_overrides[get_ranked_match_result_repository] = (
        lambda: FakeRankedMatchResultRepository()
    )

    response = client.post("/api/match", json={"jd_text": "too short"})

    assert response.status_code == 422
    assert response.json()["message"] == "Validation failed"


def test_match_by_skills_embeds_missing_vectors_and_returns_recommendations():
    matcher = FakeMajorMatcher()
    ranker = FakeRanker()
    embedding_service = FakeEmbeddingService()
    app.dependency_overrides[get_major_matcher] = lambda: matcher
    app.dependency_overrides[get_recommendation_ranker] = lambda: ranker
    app.dependency_overrides[get_embedding_service] = lambda: embedding_service

    response = client.post(
        "/api/match/by-skills",
        json={
            "top_n": 2,
            "skills": [
                {
                    "name": "Python",
                    "category": "programming_language",
                    "proficiency_required": "intermediate",
                },
                {
                    "name": "Docker",
                    "category": "devops",
                    "proficiency_required": "basic",
                    "embedding": [0.3] * 1024,
                },
            ],
        },
    )

    body = response.json()

    assert response.status_code == 200
    assert body["data"]["jd_id"] is None
    assert body["data"]["extracted_skill_count"] == 2
    assert body["data"]["recommendations"][0]["recommendation_reason"]
    assert embedding_service.calls == [
        ["Python | category: programming_language | proficiency: intermediate"]
    ]
    assert matcher.calls[0]["top_n"] == 2
    assert [skill.name for skill in matcher.calls[0]["skills"]] == ["Python", "Docker"]


def test_match_by_skills_rejects_mismatched_embedding_count():
    app.dependency_overrides[get_major_matcher] = lambda: FakeMajorMatcher()
    app.dependency_overrides[get_recommendation_ranker] = lambda: FakeRanker()
    app.dependency_overrides[get_embedding_service] = lambda: MismatchedEmbeddingService()

    response = client.post(
        "/api/match/by-skills",
        json={"skills": [{"name": "Python"}]},
    )

    assert response.status_code == 400
    assert "unexpected number" in response.json()["message"]


def test_match_by_skills_validates_embedding_dimensions():
    response = client.post(
        "/api/match/by-skills",
        json={"skills": [{"name": "Python", "embedding": [0.1, 0.2]}]},
    )

    assert response.status_code == 422
    assert response.json()["message"] == "Validation failed"


def test_get_match_history_returns_saved_recommendations():
    app.dependency_overrides[get_match_history_repository] = lambda: FakeHistoryRepository()

    response = client.get("/api/match/42")

    body = response.json()

    assert response.status_code == 200
    assert body["code"] == 0
    assert body["data"]["jd_id"] == 42
    assert body["data"]["recommendations"][0]["score_details"] == {"source": "history"}


def test_get_match_history_returns_404():
    app.dependency_overrides[get_match_history_repository] = lambda: FakeHistoryRepository()

    response = client.get("/api/match/404")

    assert response.status_code == 404


def test_ranked_match_repository_persists_recommendation_details(monkeypatch):
    created_rows = []

    class FakeColumn:
        def __init__(self, name):
            self.name = name

        def __eq__(self, other):
            return (self.name, other)

    class FakeMatchResult(SimpleNamespace):
        jd_id = FakeColumn("jd_id")
        major_id = FakeColumn("major_id")

        def __init__(self, **kwargs):
            created_rows.append(kwargs)
            super().__init__(**kwargs)

    monkeypatch.setitem(
        __import__("sys").modules,
        "backend.models.match_result",
        SimpleNamespace(MatchResult=FakeMatchResult),
    )
    monkeypatch.setitem(
        __import__("sys").modules,
        "sqlalchemy",
        SimpleNamespace(
            select=lambda model: SimpleNamespace(where=lambda *args: ("select", model, args))
        ),
    )

    session = FakeSession()
    repository = SqlAlchemyRankedMatchResultRepository(session)

    count = asyncio.run(
        repository.save_ranked_recommendations(
            jd_id=42,
            recommendations=[ranked_recommendation()],
        )
    )

    details = created_rows[0]["match_details"]

    assert count == 1
    assert created_rows[0]["similarity_score"] == 0.88
    assert created_rows[0]["final_score"] == 0.84
    assert details["skill_coverage_score"] == 0.75
    assert details["employment_alignment_score"] == 0.5
    assert details["recommendation_reason"]
    assert session.commits == 1

    restored = _history_row_to_recommendation(
        SimpleNamespace(
            rank=1,
            major_id=7,
            final_score=0.84,
            similarity_score=0.88,
            match_details=details,
        ),
        SimpleNamespace(name="fallback", code="fallback"),
    )

    assert restored.skill_coverage_score == 0.75
    assert restored.employment_alignment_score == 0.5
    assert restored.recommendation_reason == details["recommendation_reason"]


def test_match_router_is_registered_on_app():
    paths = set(client.get("/openapi.json").json()["paths"])

    assert "/api/match" in paths
    assert "/api/match/by-skills" in paths
    assert "/api/match/{jd_id}" in paths
