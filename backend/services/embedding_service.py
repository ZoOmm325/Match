from __future__ import annotations

import asyncio
from collections import OrderedDict
from collections.abc import Sequence
from time import monotonic
from typing import Any

from backend.core.config import get_settings

EMBEDDING_DIMENSIONS = 1024


class EmbeddingServiceError(RuntimeError):
    """Raised when a local embedding response is malformed."""


class EmbeddingService:
    def __init__(
        self,
        model: Any | None = None,
        *,
        model_name: str | None = None,
        cache_enabled: bool = True,
        cache_max_size: int = 2048,
        cache_ttl_seconds: float = 3600.0,
    ) -> None:
        if cache_max_size < 1:
            raise ValueError("cache_max_size must be at least 1")
        if cache_ttl_seconds <= 0:
            raise ValueError("cache_ttl_seconds must be greater than 0")
        self.model_name = model_name or get_settings().embedding_model
        self._model = model
        self.cache_enabled = cache_enabled
        self.cache_max_size = cache_max_size
        self.cache_ttl_seconds = cache_ttl_seconds
        self._cache: OrderedDict[str, tuple[float, list[float]]] = OrderedDict()
        self._inflight: dict[str, asyncio.Future[list[float]]] = {}
        self._lock = asyncio.Lock()

    async def embed_text(self, text: str) -> list[float]:
        vectors = await self.embed_texts([text])
        return vectors[0]

    async def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        normalized_texts = [self._normalize_text(text) for text in texts]
        if not normalized_texts:
            return []

        unique_texts = list(dict.fromkeys(normalized_texts))
        if not self.cache_enabled:
            vectors = await asyncio.to_thread(self._encode_texts, unique_texts)
            vector_by_text = dict(zip(unique_texts, vectors))
            return [list(vector_by_text[text]) for text in normalized_texts]

        cached_vectors: dict[str, list[float]] = {}
        futures: dict[str, asyncio.Future[list[float]]] = {}
        owned_texts: list[str] = []
        async with self._lock:
            self._purge_expired_cache()
            loop = asyncio.get_running_loop()
            for text in unique_texts:
                cached = self._cache.get(text)
                if cached is not None:
                    self._cache.move_to_end(text)
                    cached_vectors[text] = cached[1]
                    continue
                future = self._inflight.get(text)
                if future is None:
                    future = loop.create_future()
                    self._inflight[text] = future
                    owned_texts.append(text)
                futures[text] = future

        if owned_texts:
            try:
                fetched_vectors = await asyncio.to_thread(self._encode_texts, owned_texts)
            except asyncio.CancelledError:
                async with self._lock:
                    for text in owned_texts:
                        future = self._inflight.pop(text, None)
                        if future is not None and not future.done():
                            future.cancel()
                raise
            except Exception as exc:
                async with self._lock:
                    for text in owned_texts:
                        future = self._inflight.pop(text, None)
                        if future is not None and not future.done():
                            future.set_exception(exc)
            else:
                now = monotonic()
                async with self._lock:
                    for text, vector in zip(owned_texts, fetched_vectors):
                        self._cache[text] = (now, vector)
                        self._cache.move_to_end(text)
                        future = self._inflight.pop(text)
                        if not future.done():
                            future.set_result(vector)
                    self._trim_cache()

        pending_texts = [text for text in unique_texts if text not in cached_vectors]
        if pending_texts:
            outcomes = await asyncio.gather(
                *(futures[text] for text in pending_texts),
                return_exceptions=True,
            )
            for text, outcome in zip(pending_texts, outcomes):
                if isinstance(outcome, BaseException):
                    raise outcome
                cached_vectors[text] = outcome

        return [list(cached_vectors[text]) for text in normalized_texts]

    def _purge_expired_cache(self) -> None:
        expires_before = monotonic() - self.cache_ttl_seconds
        expired = [
            text for text, (cached_at, _) in self._cache.items() if cached_at <= expires_before
        ]
        for text in expired:
            self._cache.pop(text, None)

    def _trim_cache(self) -> None:
        while len(self._cache) > self.cache_max_size:
            self._cache.popitem(last=False)

    def clear_cache(self) -> None:
        self._cache.clear()

    def cache_size(self) -> int:
        expires_before = monotonic() - self.cache_ttl_seconds
        return sum(cached_at > expires_before for cached_at, _ in self._cache.values())

    @property
    def model(self) -> Any:
        if self._model is None:
            self._model = self._load_model()
        return self._model

    def _load_model(self) -> Any:
        try:
            from sentence_transformers import SentenceTransformer
        except ModuleNotFoundError as exc:
            raise EmbeddingServiceError(
                "sentence-transformers package is not installed; "
                "run `pip install -r requirements.txt`"
            ) from exc

        return SentenceTransformer(self.model_name)

    def _encode_texts(self, texts: Sequence[str]) -> list[list[float]]:
        encoded = self.model.encode(list(texts))
        vectors = self._coerce_vectors(encoded, expected_count=len(texts))
        for vector in vectors:
            if len(vector) != EMBEDDING_DIMENSIONS:
                raise EmbeddingServiceError(
                    f"embedding must contain {EMBEDDING_DIMENSIONS} dimensions"
                )
        return vectors

    def _normalize_text(self, text: str) -> str:
        normalized = text.strip()
        if not normalized:
            raise ValueError("text cannot be empty")
        return normalized

    def _coerce_vectors(self, encoded: Any, *, expected_count: int) -> list[list[float]]:
        if hasattr(encoded, "tolist"):
            encoded = encoded.tolist()

        if expected_count == 1 and self._is_vector(encoded):
            encoded = [encoded]

        if not isinstance(encoded, list) or len(encoded) != expected_count:
            actual_count = len(encoded) if isinstance(encoded, list) else 0
            raise EmbeddingServiceError(
                f"expected {expected_count} embedding vectors, got {actual_count}"
            )

        vectors: list[list[float]] = []
        for item in encoded:
            if hasattr(item, "tolist"):
                item = item.tolist()
            if not self._is_vector(item):
                raise EmbeddingServiceError("embedding item must be a numeric list")
            vectors.append([float(value) for value in item])
        return vectors

    def _is_vector(self, value: Any) -> bool:
        return (
            isinstance(value, list)
            and bool(value)
            and all(isinstance(item, (int, float)) and not isinstance(item, bool) for item in value)
        )
