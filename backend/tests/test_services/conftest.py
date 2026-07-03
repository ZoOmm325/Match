import json
from collections.abc import Callable
from typing import Any

import pytest


class FakeDeepSeekClient:
    def __init__(self, skills: list[dict[str, str]]) -> None:
        self.skills = skills
        self.calls: list[dict[str, Any]] = []

    async def create_chat_completion(
        self,
        messages: list[dict[str, str]],
        **kwargs: Any,
    ) -> dict[str, Any]:
        self.calls.append({"messages": messages, "kwargs": kwargs})
        return {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {"skills": self.skills},
                            ensure_ascii=False,
                        )
                    }
                }
            ]
        }


class FakeEmbeddingService:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(list(texts))
        vectors: list[list[float]] = []
        for index, _text in enumerate(texts):
            vector = [0.0] * 1024
            vector[index] = 1.0
            vectors.append(vector)
        return vectors


@pytest.fixture
def extracted_skill_payload() -> list[dict[str, str]]:
    return [
        {
            "name": "python开发",
            "category": "programming_language",
            "proficiency_required": "advanced",
        },
        {
            "name": "Fast API",
            "category": "framework",
            "proficiency_required": "intermediate",
        },
    ]


@pytest.fixture
def deepseek_client(
    extracted_skill_payload: list[dict[str, str]],
) -> FakeDeepSeekClient:
    return FakeDeepSeekClient(extracted_skill_payload)


@pytest.fixture
def deepseek_client_factory() -> Callable[[list[dict[str, str]]], FakeDeepSeekClient]:
    return FakeDeepSeekClient


@pytest.fixture
def embedding_service() -> FakeEmbeddingService:
    return FakeEmbeddingService()


@pytest.fixture
def make_embedding() -> Callable[[int], list[float]]:
    def factory(index: int = 0) -> list[float]:
        vector = [0.0] * 1024
        vector[index] = 1.0
        return vector

    return factory
