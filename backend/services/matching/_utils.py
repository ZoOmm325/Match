from __future__ import annotations


def aggregate_embedding(embeddings: list[list[float]]) -> list[float]:
    if not embeddings:
        raise ValueError("at least one embedding is required for aggregation")
    dim = len(embeddings[0])
    if dim == 0:
        raise ValueError("embedding vectors cannot be empty")
    if any(len(embedding) != dim for embedding in embeddings):
        raise ValueError("all embedding vectors must have the same dimension")

    aggregated = [0.0] * dim
    for embedding in embeddings:
        for index, value in enumerate(embedding):
            aggregated[index] += float(value)
    norm = sum(value * value for value in aggregated) ** 0.5
    if norm == 0.0:
        return aggregated
    return [value / norm for value in aggregated]
