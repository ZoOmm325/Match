import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest

from backend.core.config import Settings
import backend.core.openai_client as openai_client_module
from backend.core.openai_client import AsyncRateLimiter, OpenAIClient
from backend.core.openai_client import OpenAIClientConfigurationError


ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


class FakeCompletions:
    def __init__(self) -> None:
        self.payloads = []

    async def create(self, **kwargs):
        self.payloads.append(kwargs)
        return {"choices": [{"message": {"content": "ok"}}]}


class FakeEmbeddings:
    def __init__(self) -> None:
        self.payloads = []

    async def create(self, **kwargs):
        self.payloads.append(kwargs)
        return {"data": [{"embedding": [0.0] * 1536}]}


class FakeOpenAISDK:
    def __init__(self) -> None:
        self.completions = FakeCompletions()
        self.embeddings_impl = FakeEmbeddings()
        self.chat = SimpleNamespace(completions=self.completions)
        self.embeddings = self.embeddings_impl


def make_settings() -> Settings:
    return Settings(
        openai_api_key="sk-test",
        openai_model="gpt-4o-mini",
        embedding_model="text-embedding-3-small",
        openai_timeout_seconds=5,
        openai_max_retries=2,
        openai_rate_limit_per_minute=120,
    )


def test_openai_client_sends_chat_completion_with_configured_model():
    fake_sdk = FakeOpenAISDK()
    client = OpenAIClient(settings=make_settings(), client=fake_sdk)

    response = asyncio.run(
        client.create_chat_completion(
            [{"role": "user", "content": "Extract skills"}],
            response_format={"type": "json_object"},
        )
    )

    assert response["choices"][0]["message"]["content"] == "ok"
    assert fake_sdk.completions.payloads == [
        {
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": "Extract skills"}],
            "temperature": 0,
            "response_format": {"type": "json_object"},
        }
    ]


def test_openai_client_sends_embedding_with_configured_model():
    fake_sdk = FakeOpenAISDK()
    client = OpenAIClient(settings=make_settings(), client=fake_sdk)

    response = asyncio.run(client.create_embedding("Python FastAPI"))

    assert len(response["data"][0]["embedding"]) == 1536
    assert fake_sdk.embeddings_impl.payloads == [
        {"model": "text-embedding-3-small", "input": "Python FastAPI"}
    ]


def test_openai_client_requires_api_key_when_building_real_sdk_client():
    with pytest.raises(OpenAIClientConfigurationError, match="OPENAI_API_KEY is required"):
        OpenAIClient(settings=Settings(openai_api_key=None))


def test_rate_limiter_allows_calls_within_limit():
    limiter = AsyncRateLimiter(max_calls=2, window_seconds=60)

    asyncio.run(limiter.acquire())
    asyncio.run(limiter.acquire())

    assert limiter.max_calls == 2


def test_openai_client_uses_lazy_official_sdk_and_tenacity_imports():
    source = read("backend/core/openai_client.py")

    assert "from openai import AsyncOpenAI" in source
    assert "from openai import APIConnectionError, APITimeoutError, InternalServerError" in source
    assert "from openai import RateLimitError" in source
    assert "from tenacity import AsyncRetrying" in source
    assert "stop_after_attempt(self.settings.openai_max_retries)" in source
    assert "retry_if_exception_type(_get_retryable_openai_errors())" in source
    assert "retry_if_exception_type(Exception)" not in source
    assert "wait_exponential(" in source
    assert "max_retries=0" in source
    assert "OpenAI request retry loop exited unexpectedly" not in source


def test_get_openai_client_reuses_single_instance(monkeypatch):
    created_clients = []

    class FakeClient:
        def __init__(self):
            created_clients.append(self)

    monkeypatch.setattr(openai_client_module, "_client", None)
    monkeypatch.setattr(openai_client_module, "OpenAIClient", FakeClient)

    first = openai_client_module.get_openai_client()
    second = openai_client_module.get_openai_client()

    assert first is second
    assert len(created_clients) == 1


def test_settings_expose_openai_runtime_controls():
    settings = make_settings()

    assert settings.openai_timeout_seconds == 5
    assert settings.openai_max_retries == 2
    assert settings.openai_rate_limit_per_minute == 120
