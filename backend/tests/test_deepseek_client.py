import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest

import backend.core.deepseek_client as deepseek_client_module
from backend.core.config import Settings
from backend.core.deepseek_client import AsyncRateLimiter, DeepSeekClient
from backend.core.deepseek_client import DeepSeekClientConfigurationError


ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


class FakeCompletions:
    def __init__(self) -> None:
        self.payloads = []

    async def create(self, **kwargs):
        self.payloads.append(kwargs)
        return {"choices": [{"message": {"content": "ok"}}]}


class FakeDeepSeekSDK:
    def __init__(self) -> None:
        self.completions = FakeCompletions()
        self.chat = SimpleNamespace(completions=self.completions)


def make_settings() -> Settings:
    return Settings(
        deepseek_api_key="sk-test",
        deepseek_model="deepseek-chat",
        deepseek_base_url="https://api.deepseek.com",
        embedding_model="BAAI/bge-m3",
        deepseek_timeout_seconds=5,
        deepseek_max_retries=2,
        deepseek_rate_limit_per_minute=120,
    )


def test_deepseek_client_sends_chat_completion_with_configured_model():
    fake_sdk = FakeDeepSeekSDK()
    client = DeepSeekClient(settings=make_settings(), client=fake_sdk)

    response = asyncio.run(
        client.create_chat_completion(
            [{"role": "user", "content": "Extract skills"}],
            response_format={"type": "json_object"},
        )
    )

    assert response["choices"][0]["message"]["content"] == "ok"
    assert fake_sdk.completions.payloads == [
        {
            "model": "deepseek-chat",
            "messages": [{"role": "user", "content": "Extract skills"}],
            "temperature": 0,
            "response_format": {"type": "json_object"},
        }
    ]


def test_deepseek_client_requires_api_key_when_building_real_sdk_client():
    with pytest.raises(DeepSeekClientConfigurationError, match="DEEPSEEK_API_KEY is required"):
        DeepSeekClient(settings=Settings(deepseek_api_key=None))


def test_rate_limiter_allows_calls_within_limit():
    limiter = AsyncRateLimiter(max_calls=2, window_seconds=60)

    asyncio.run(limiter.acquire())
    asyncio.run(limiter.acquire())

    assert limiter.max_calls == 2


def test_deepseek_client_uses_lazy_official_sdk_and_tenacity_imports():
    source = read("backend/core/deepseek_client.py")

    assert "from openai import AsyncOpenAI" in source
    assert "base_url=self.settings.deepseek_base_url" in source
    assert "from openai import APIConnectionError, APITimeoutError, InternalServerError" in source
    assert "from openai import RateLimitError" in source
    assert "from tenacity import AsyncRetrying" in source
    assert "stop_after_attempt(self.settings.deepseek_max_retries)" in source
    assert "retry_if_exception_type(_get_retryable_deepseek_errors())" in source
    assert "retry_if_exception_type(Exception)" not in source
    assert "wait_exponential(" in source
    assert "max_retries=0" in source
    assert "DeepSeek request retry loop exited unexpectedly" not in source


def test_get_deepseek_client_reuses_single_instance(monkeypatch):
    created_clients = []

    class FakeClient:
        def __init__(self):
            created_clients.append(self)

    monkeypatch.setattr(deepseek_client_module, "_client", None)
    monkeypatch.setattr(deepseek_client_module, "DeepSeekClient", FakeClient)

    first = deepseek_client_module.get_deepseek_client()
    second = deepseek_client_module.get_deepseek_client()

    assert first is second
    assert len(created_clients) == 1


def test_settings_expose_deepseek_runtime_controls():
    settings = make_settings()

    assert settings.deepseek_base_url == "https://api.deepseek.com"
    assert settings.deepseek_timeout_seconds == 5
    assert settings.deepseek_max_retries == 2
    assert settings.deepseek_rate_limit_per_minute == 120
