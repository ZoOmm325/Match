from pathlib import Path

from fastapi.testclient import TestClient
import pytest
from pydantic import ValidationError

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
                "DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/testdb",
                "OPENAI_MODEL=gpt-4o",
                "EMBEDDING_MODEL=text-embedding-3-small",
            ]
        ),
        encoding="utf-8",
    )

    settings = Settings(_env_file=env_file)

    assert settings.app_name == "Env Loaded Match API"
    assert settings.api_prefix == "/v1"
    assert settings.database_url.endswith("/testdb")
    assert settings.openai_model == "gpt-4o"


def test_settings_reject_empty_openai_api_key(tmp_path: Path):
    env_file = tmp_path / ".env"
    env_file.write_text("OPENAI_API_KEY=   \n", encoding="utf-8")

    with pytest.raises(ValidationError, match="OPENAI_API_KEY cannot be empty"):
        Settings(_env_file=env_file)
