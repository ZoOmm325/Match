from __future__ import annotations

import asyncio
import inspect
from collections import deque
from collections.abc import Awaitable, Callable, Sequence
from threading import Lock
from time import monotonic
from typing import Any

from backend.core.config import Settings, get_settings

Message = dict[str, Any]
_client: DeepSeekClient | None = None
_client_lock = Lock()


class DeepSeekClientConfigurationError(RuntimeError):
    """Raised when the DeepSeek client cannot be configured."""


def _get_retryable_deepseek_errors() -> tuple[type[BaseException], ...]:
    try:
        from openai import APIConnectionError, APITimeoutError, InternalServerError, RateLimitError
    except ModuleNotFoundError:
        return ()

    return (APITimeoutError, APIConnectionError, RateLimitError, InternalServerError)


class AsyncRateLimiter:
    """Small in-process rolling-window limiter for DeepSeek API calls."""

    def __init__(self, max_calls: int, window_seconds: float = 60.0) -> None:
        if max_calls < 1:
            raise ValueError("max_calls must be at least 1")
        self.max_calls = max_calls
        self.window_seconds = window_seconds
        self._calls: deque[float] = deque()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        while True:
            async with self._lock:
                now = monotonic()
                while self._calls and now - self._calls[0] >= self.window_seconds:
                    self._calls.popleft()

                if len(self._calls) < self.max_calls:
                    self._calls.append(now)
                    return

                sleep_for = self.window_seconds - (now - self._calls[0])

            await asyncio.sleep(max(sleep_for, 0.0))


class DeepSeekClient:
    """Async DeepSeek SDK wrapper with config, retry, timeout, and rate limiting."""

    def __init__(
        self,
        settings: Settings | None = None,
        client: Any | None = None,
        rate_limiter: AsyncRateLimiter | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.model = self.settings.deepseek_model
        self._client = client or self._build_sdk_client()
        self._rate_limiter = rate_limiter or AsyncRateLimiter(
            self.settings.deepseek_rate_limit_per_minute
        )

    def _build_sdk_client(self) -> Any:
        if not self.settings.deepseek_api_key:
            raise DeepSeekClientConfigurationError("DEEPSEEK_API_KEY is required")

        try:
            from openai import AsyncOpenAI
        except ModuleNotFoundError as exc:
            raise DeepSeekClientConfigurationError(
                "openai package is not installed; run `pip install -r requirements.txt`"
            ) from exc

        return AsyncOpenAI(
            api_key=self.settings.deepseek_api_key,
            base_url=self.settings.deepseek_base_url,
            timeout=self.settings.deepseek_timeout_seconds,
            max_retries=0,
        )

    async def create_chat_completion(
        self,
        messages: Sequence[Message],
        *,
        model: str | None = None,
        temperature: float = 0,
        response_format: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> Any:
        payload: dict[str, Any] = {
            "model": model or self.model,
            "messages": list(messages),
            "temperature": temperature,
            **kwargs,
        }
        if response_format is not None:
            payload["response_format"] = response_format

        return await self._request_with_retry(
            lambda: self._client.chat.completions.create(**payload)
        )

    async def close(self) -> None:
        close = getattr(self._client, "close", None) or getattr(self._client, "aclose", None)
        if close is None:
            return
        result = close()
        if inspect.isawaitable(result):
            await result

    async def _request_with_retry(self, request: Callable[[], Awaitable[Any]]) -> Any:
        await self._rate_limiter.acquire()

        try:
            from tenacity import (
                AsyncRetrying,
                retry_if_exception_type,
                stop_after_attempt,
                wait_exponential,
            )
        except ModuleNotFoundError:
            return await request()

        retrying = AsyncRetrying(
            stop=stop_after_attempt(self.settings.deepseek_max_retries),
            wait=wait_exponential(multiplier=1, min=1, max=10),
            retry=retry_if_exception_type(_get_retryable_deepseek_errors()),
            reraise=True,
        )

        async for attempt in retrying:
            with attempt:
                return await request()


def get_deepseek_client() -> DeepSeekClient:
    global _client
    if _client is None:
        with _client_lock:
            if _client is None:
                _client = DeepSeekClient()
    return _client


async def close_deepseek_client() -> None:
    global _client
    with _client_lock:
        client = _client
        _client = None
    if client is not None:
        await client.close()
