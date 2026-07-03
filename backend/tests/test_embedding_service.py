import asyncio
from threading import Event
from time import sleep

import pytest

from backend.services import EmbeddingService
from backend.services.embedding_service import EMBEDDING_DIMENSIONS, EmbeddingServiceError


class FakeLocalEmbeddingModel:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def encode(self, texts):
        inputs = list(texts)
        self.calls.append(inputs)
        return [[float(index)] * EMBEDDING_DIMENSIONS for index, _ in enumerate(inputs)]


def test_embed_text_returns_1024_dimension_vector():
    fake_model = FakeLocalEmbeddingModel()
    service = EmbeddingService(model=fake_model)

    vector = asyncio.run(service.embed_text(" Python FastAPI "))

    assert len(vector) == EMBEDDING_DIMENSIONS
    assert EMBEDDING_DIMENSIONS == 1024
    assert fake_model.calls == [["Python FastAPI"]]
    assert service.cache_size() == 1


def test_embed_texts_batches_missing_inputs_and_preserves_order():
    fake_model = FakeLocalEmbeddingModel()
    service = EmbeddingService(model=fake_model)

    vectors = asyncio.run(service.embed_texts(["Python", "FastAPI", "Python"]))

    assert len(vectors) == 3
    assert vectors[0] == vectors[2]
    assert fake_model.calls == [["Python", "FastAPI"]]
    assert service.cache_size() == 2


def test_embed_texts_uses_cache_to_avoid_repeated_calls():
    fake_model = FakeLocalEmbeddingModel()
    service = EmbeddingService(model=fake_model)

    first = asyncio.run(service.embed_text("Python"))
    second = asyncio.run(service.embed_text(" Python "))

    assert first == second
    assert fake_model.calls == [["Python"]]
    assert service.cache_size() == 1


def test_embed_texts_can_disable_cache():
    fake_model = FakeLocalEmbeddingModel()
    service = EmbeddingService(model=fake_model, cache_enabled=False)

    asyncio.run(service.embed_text("Python"))
    asyncio.run(service.embed_text("Python"))

    assert fake_model.calls == [["Python"], ["Python"]]
    assert service.cache_size() == 0


def test_concurrent_requests_share_inflight_embedding_work():
    class SlowModel(FakeLocalEmbeddingModel):
        def encode(self, texts):
            sleep(0.02)
            return super().encode(texts)

    async def run():
        model = SlowModel()
        service = EmbeddingService(model=model)
        vectors = await asyncio.gather(
            service.embed_text("Python"),
            service.embed_text("Python"),
        )
        return model, vectors

    model, vectors = asyncio.run(run())

    assert model.calls == [["Python"]]
    assert vectors[0] == vectors[1]


def test_embedding_cache_enforces_size_limit():
    service = EmbeddingService(model=FakeLocalEmbeddingModel(), cache_max_size=1)

    asyncio.run(service.embed_texts(["Python", "FastAPI"]))

    assert service.cache_size() == 1


def test_cache_size_does_not_mutate_expired_entries():
    service = EmbeddingService(model=FakeLocalEmbeddingModel(), cache_ttl_seconds=1)
    service._cache["expired"] = (0.0, [0.0] * EMBEDDING_DIMENSIONS)

    assert service.cache_size() == 0
    assert "expired" in service._cache


def test_cancelled_embedding_cleans_inflight_work():
    started = Event()
    release = Event()

    class BlockingModel(FakeLocalEmbeddingModel):
        def encode(self, texts):
            started.set()
            release.wait(timeout=2)
            return super().encode(texts)

    async def run():
        service = EmbeddingService(model=BlockingModel())
        task = asyncio.create_task(service.embed_text("Python"))
        await asyncio.to_thread(started.wait, 2)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        release.set()
        return service

    service = asyncio.run(run())

    assert service._inflight == {}


def test_embed_text_rejects_empty_text():
    service = EmbeddingService(model=FakeLocalEmbeddingModel())

    with pytest.raises(ValueError, match="text cannot be empty"):
        asyncio.run(service.embed_text("   "))


def test_embed_texts_accepts_single_vector_from_model():
    class SingleVectorModel:
        def encode(self, texts):
            return [0.25] * EMBEDDING_DIMENSIONS

    service = EmbeddingService(model=SingleVectorModel())

    vectors = asyncio.run(service.embed_texts(["Python"]))

    assert len(vectors) == 1
    assert vectors[0][0] == 0.25


def test_embed_texts_rejects_wrong_vector_dimension():
    class BadDimensionModel:
        def encode(self, texts):
            return [[0.1, 0.2]]

    service = EmbeddingService(model=BadDimensionModel())

    with pytest.raises(EmbeddingServiceError, match="1024"):
        asyncio.run(service.embed_text("Python"))


def test_embed_texts_rejects_mismatched_response_count():
    class MissingVectorModel:
        def encode(self, texts):
            return []

    service = EmbeddingService(model=MissingVectorModel())

    with pytest.raises(EmbeddingServiceError, match="expected 1"):
        asyncio.run(service.embed_text("Python"))


def test_service_package_exports_embedding_service():
    import backend.services as services

    assert "EmbeddingService" in services.__all__
    assert services.EmbeddingService is EmbeddingService
