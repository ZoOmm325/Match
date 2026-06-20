import asyncio
from types import SimpleNamespace

import pytest

from backend.services import EmbeddingService
from backend.services.embedding_service import EMBEDDING_DIMENSIONS, EmbeddingServiceError


class FakeOpenAIClient:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    async def create_embedding(self, text):
        inputs = list(text) if isinstance(text, list) else [text]
        self.calls.append(inputs)
        return {
            "data": [
                {"embedding": [float(index)] * EMBEDDING_DIMENSIONS}
                for index, _ in enumerate(inputs)
            ]
        }


def test_embed_text_returns_1536_dimension_vector():
    fake_client = FakeOpenAIClient()
    service = EmbeddingService(openai_client=fake_client)

    vector = asyncio.run(service.embed_text(" Python FastAPI "))

    assert len(vector) == EMBEDDING_DIMENSIONS
    assert fake_client.calls == [["Python FastAPI"]]
    assert service.cache_size() == 1


def test_embed_texts_batches_missing_inputs_and_preserves_order():
    fake_client = FakeOpenAIClient()
    service = EmbeddingService(openai_client=fake_client)

    vectors = asyncio.run(service.embed_texts(["Python", "FastAPI", "Python"]))

    assert len(vectors) == 3
    assert vectors[0] == vectors[2]
    assert fake_client.calls == [["Python", "FastAPI"]]
    assert service.cache_size() == 2


def test_embed_texts_uses_cache_to_avoid_repeated_calls():
    fake_client = FakeOpenAIClient()
    service = EmbeddingService(openai_client=fake_client)

    first = asyncio.run(service.embed_text("Python"))
    second = asyncio.run(service.embed_text(" Python "))

    assert first == second
    assert fake_client.calls == [["Python"]]
    assert service.cache_size() == 1


def test_embed_texts_can_disable_cache():
    fake_client = FakeOpenAIClient()
    service = EmbeddingService(openai_client=fake_client, cache_enabled=False)

    asyncio.run(service.embed_text("Python"))
    asyncio.run(service.embed_text("Python"))

    assert fake_client.calls == [["Python"], ["Python"]]
    assert service.cache_size() == 0


def test_embed_text_rejects_empty_text():
    service = EmbeddingService(openai_client=FakeOpenAIClient())

    with pytest.raises(ValueError, match="text cannot be empty"):
        asyncio.run(service.embed_text("   "))


def test_embed_texts_accepts_sdk_object_response():
    class ObjectResponseClient:
        async def create_embedding(self, text):
            return SimpleNamespace(
                data=[
                    SimpleNamespace(embedding=[0.25] * EMBEDDING_DIMENSIONS)
                    for _ in text
                ]
            )

    service = EmbeddingService(openai_client=ObjectResponseClient())

    vectors = asyncio.run(service.embed_texts(["Python", "FastAPI"]))

    assert len(vectors) == 2
    assert vectors[0][0] == 0.25


def test_embed_texts_rejects_wrong_vector_dimension():
    class BadDimensionClient:
        async def create_embedding(self, text):
            return {"data": [{"embedding": [0.1, 0.2]}]}

    service = EmbeddingService(openai_client=BadDimensionClient())

    with pytest.raises(EmbeddingServiceError, match="1536"):
        asyncio.run(service.embed_text("Python"))


def test_embed_texts_rejects_mismatched_response_count():
    class MissingVectorClient:
        async def create_embedding(self, text):
            return {"data": []}

    service = EmbeddingService(openai_client=MissingVectorClient())

    with pytest.raises(EmbeddingServiceError, match="expected 1"):
        asyncio.run(service.embed_text("Python"))


def test_service_package_exports_embedding_service():
    import backend.services as services

    assert "EmbeddingService" in services.__all__
    assert services.EmbeddingService is EmbeddingService
