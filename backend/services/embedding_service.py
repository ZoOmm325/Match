from __future__ import annotations

import asyncio
from collections.abc import Sequence
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
    ) -> None:
        self.model_name = model_name or get_settings().embedding_model
        self._model = model
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
            fetched_vectors = await asyncio.to_thread(self._encode_texts, missing_texts)

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
                "sentence-transformers package is not installed; run `pip install -r requirements.txt`"
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
            and all(isinstance(item, (int, float)) for item in value)
        )
