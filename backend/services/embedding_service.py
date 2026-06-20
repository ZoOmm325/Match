from __future__ import annotations

import asyncio
from collections.abc import Sequence
from typing import Any

from backend.core.openai_client import OpenAIClient, get_openai_client


EMBEDDING_DIMENSIONS = 1536


class EmbeddingServiceError(RuntimeError):
    """Raised when an embedding response is malformed."""


class EmbeddingService:
    def __init__(
        self,
        openai_client: OpenAIClient | None = None,
        *,
        cache_enabled: bool = True,
    ) -> None:
        self.openai_client = openai_client or get_openai_client()
        self.cache_enabled = cache_enabled
        self._cache: dict[str, list[float]] = {}
        self._lock = asyncio.Lock()

    async def embed_text(self, text: str) -> list[float]:
        vectors = await self.embed_texts([text])
        return vectors[0]

    async def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        normalized_texts = [self._normalize_text(text) for text in texts]
        if not normalized_texts:
            return []

        async with self._lock:
            cached_vectors = {
                text: self._cache[text]
                for text in normalized_texts
                if self.cache_enabled and text in self._cache
            }

        missing_texts = self._unique_missing_texts(normalized_texts, cached_vectors)
        if missing_texts:
            response = await self.openai_client.create_embedding(missing_texts)
            fetched_vectors = self._extract_vectors(response, expected_count=len(missing_texts))

            async with self._lock:
                for text, vector in zip(missing_texts, fetched_vectors):
                    if self.cache_enabled:
                        self._cache[text] = vector
                    cached_vectors[text] = vector

        return [list(cached_vectors[text]) for text in normalized_texts]

    def clear_cache(self) -> None:
        self._cache.clear()

    def cache_size(self) -> int:
        return len(self._cache)

    def _normalize_text(self, text: str) -> str:
        normalized = text.strip()
        if not normalized:
            raise ValueError("text cannot be empty")
        return normalized

    def _unique_missing_texts(
        self,
        texts: Sequence[str],
        cached_vectors: dict[str, list[float]],
    ) -> list[str]:
        seen: set[str] = set()
        missing: list[str] = []
        for text in texts:
            if text in cached_vectors or text in seen:
                continue
            seen.add(text)
            missing.append(text)
        return missing

    def _extract_vectors(self, response: Any, *, expected_count: int) -> list[list[float]]:
        data = self._get_response_data(response)
        if len(data) != expected_count:
            raise EmbeddingServiceError(
                f"expected {expected_count} embedding vectors, got {len(data)}"
            )

        vectors = [self._get_embedding_vector(item) for item in data]
        for vector in vectors:
            if len(vector) != EMBEDDING_DIMENSIONS:
                raise EmbeddingServiceError(
                    f"embedding must contain {EMBEDDING_DIMENSIONS} dimensions"
                )
        return vectors

    def _get_response_data(self, response: Any) -> list[Any]:
        if isinstance(response, dict):
            data = response.get("data")
        else:
            data = getattr(response, "data", None)

        if not isinstance(data, list):
            raise EmbeddingServiceError("embedding response data must be a list")
        return data

    def _get_embedding_vector(self, item: Any) -> list[float]:
        if isinstance(item, dict):
            vector = item.get("embedding")
        else:
            vector = getattr(item, "embedding", None)

        if not isinstance(vector, list):
            raise EmbeddingServiceError("embedding item must contain an embedding list")
        return [float(value) for value in vector]
