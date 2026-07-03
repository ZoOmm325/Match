import logging

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from starlette.testclient import TestClient

from backend.core.config import Settings
from backend.core.exceptions import install_exception_handlers
from backend.core.middleware import RequestLoggingMiddleware
from backend.main import create_app


def make_test_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(RequestLoggingMiddleware)
    install_exception_handlers(app)

    @app.get("/ok")
    async def ok():
        return {"ok": True}

    @app.get("/http-error")
    async def http_error():
        raise HTTPException(status_code=403, detail="Forbidden")

    @app.get("/validate/{value}")
    async def validate(value: int):
        return {"value": value}

    @app.get("/pydantic-error")
    async def pydantic_error():
        class Payload(BaseModel):
            value: int

        Payload.model_validate({"value": "not-an-integer"})

    @app.get("/unexpected")
    async def unexpected():
        raise RuntimeError("sensitive internal detail")

    return app


def test_request_logging_middleware_adds_request_id_and_timing(caplog):
    client = TestClient(make_test_app())

    with caplog.at_level(logging.INFO, logger="backend.core.middleware"):
        response = client.get("/ok", headers={"X-Request-ID": "request-123"})

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "request-123"
    assert float(response.headers["X-Process-Time-Ms"]) >= 0
    assert "Request completed method=GET path=/ok status_code=200" in caplog.text
    assert "request_id=request-123" in caplog.text


def test_http_exception_uses_standard_response_format():
    client = TestClient(make_test_app())

    response = client.get("/http-error")

    assert response.status_code == 403
    assert response.json() == {"code": 403, "data": None, "message": "Forbidden"}


def test_request_validation_exception_uses_standard_response_format():
    client = TestClient(make_test_app())

    response = client.get("/validate/not-an-integer")

    body = response.json()

    assert response.status_code == 422
    assert body["code"] == 422
    assert body["message"] == "Validation failed"
    assert body["data"]["errors"]


def test_pydantic_validation_exception_uses_standard_response_format():
    client = TestClient(make_test_app())

    response = client.get("/pydantic-error")

    body = response.json()

    assert response.status_code == 422
    assert body["code"] == 422
    assert body["message"] == "Validation failed"
    assert body["data"]["errors"][0]["type"] == "int_parsing"


def test_unhandled_exception_is_logged_and_hides_internal_detail(caplog):
    client = TestClient(make_test_app(), raise_server_exceptions=False)

    with caplog.at_level(logging.ERROR):
        response = client.get("/unexpected")

    assert response.status_code == 500
    assert response.json() == {
        "code": 500,
        "data": None,
        "message": "Internal server error",
    }
    assert "Unhandled exception method=GET path=/unexpected" in caplog.text
    assert "sensitive internal detail" not in response.text


def test_create_app_uses_configured_api_prefix_for_health_and_routes():
    app = create_app(
        Settings(
            api_prefix="/v1",
            cors_origins=["https://example.com"],
            _env_file=None,
        )
    )
    client = TestClient(app)

    health_response = client.get("/v1/health")
    openapi_paths = set(client.get("/openapi.json").json()["paths"])

    assert health_response.status_code == 200
    assert health_response.json()["data"]["status"] == "ok"
    assert "/v1/jd/extract" in openapi_paths
    assert "/v1/majors" in openapi_paths
    assert "/v1/match" in openapi_paths
    assert "/v1/skills" in openapi_paths


def test_create_app_applies_cors_settings():
    app = create_app(
        Settings(
            cors_origins=["https://frontend.example.com"],
            _env_file=None,
        )
    )
    client = TestClient(app)

    response = client.options(
        "/api/health",
        headers={
            "Origin": "https://frontend.example.com",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "https://frontend.example.com"


def test_create_app_enables_request_info_logging():
    create_app(Settings(_env_file=None))

    assert logging.getLogger("backend.core.middleware").isEnabledFor(logging.INFO)
