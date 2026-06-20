from fastapi.testclient import TestClient

from backend.main import app


client = TestClient(app)


def test_health_check():
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"code": 0, "data": {"status": "ok"}, "message": "OK"}


def test_extract_jd_skills_api_success():
    response = client.post(
        "/api/jd/extract",
        json={
            "title": "AI 后端工程师",
            "company": "示例科技",
            "jd_text": (
                "岗位要求：熟练掌握 Python、FastAPI、SQL 和 PostgreSQL，"
                "熟悉机器学习、NLP，具备 Docker 部署经验。"
            ),
        },
    )

    body = response.json()
    names = {skill["name"] for skill in body["data"]["skills"]}

    assert response.status_code == 200
    assert body["code"] == 0
    assert body["data"]["title"] == "AI 后端工程师"
    assert {"Python", "FastAPI", "SQL", "PostgreSQL", "Machine Learning", "NLP", "Docker"}.issubset(
        names
    )


def test_extract_jd_skills_api_validation_error():
    response = client.post("/api/jd/extract", json={"jd_text": "太短"})

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
