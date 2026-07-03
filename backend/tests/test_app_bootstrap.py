from pathlib import Path

import pytest
from pydantic import ValidationError
from starlette.testclient import TestClient

from backend.core import database as database_module
from backend.core.config import Settings
from backend.main import app

client = TestClient(app)


def test_docs_and_openapi_are_available():
    docs_response = client.get("/docs")
    openapi_response = client.get("/openapi.json")

    assert docs_response.status_code == 200
    assert openapi_response.status_code == 200
    assert openapi_response.json()["info"]["title"] == "JD Major Match API"


def test_settings_can_load_from_env_file(tmp_path: Path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "APP_NAME=Env Loaded Match API",
                "API_PREFIX=/v1",
                'CORS_ORIGINS=["https://app.example.com","https://admin.example.com"]',
                "DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/testdb",
                "DEEPSEEK_API_KEY=sk-test",
                "DEEPSEEK_MODEL=deepseek-chat",
                "DEEPSEEK_BASE_URL=https://api.deepseek.com",
                "EMBEDDING_MODEL=BAAI/bge-m3",
            ]
        ),
        encoding="utf-8",
    )

    settings = Settings(_env_file=env_file)

    assert settings.app_name == "Env Loaded Match API"
    assert settings.api_prefix == "/v1"
    assert settings.cors_origins == [
        "https://app.example.com",
        "https://admin.example.com",
    ]
    assert settings.database_url.endswith("/testdb")
    assert settings.deepseek_api_key == "sk-test"
    assert settings.deepseek_model == "deepseek-chat"
    assert settings.deepseek_base_url == "https://api.deepseek.com"


def test_settings_reject_empty_deepseek_api_key(tmp_path: Path):
    env_file = tmp_path / ".env"
    env_file.write_text("DEEPSEEK_API_KEY=   \n", encoding="utf-8")

    with pytest.raises(ValidationError, match="DEEPSEEK_API_KEY cannot be empty"):
        Settings(_env_file=env_file)


def test_settings_reject_empty_cors_origin_list(tmp_path: Path):
    env_file = tmp_path / ".env"
    env_file.write_text("CORS_ORIGINS=[]\n", encoding="utf-8")

    with pytest.raises(ValidationError, match="CORS_ORIGINS must contain"):
        Settings(_env_file=env_file)


def test_database_engine_checks_pooled_connections_before_use(monkeypatch):
    captured = {}

    def fake_create_async_engine(url, **kwargs):
        captured.update({"url": url, **kwargs})
        return object()

    monkeypatch.setattr(database_module, "create_async_engine", fake_create_async_engine)

    database_module.make_engine("postgresql+asyncpg://localhost/test")

    assert captured["pool_pre_ping"] is True
