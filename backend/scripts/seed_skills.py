from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from pathlib import Path
from typing import Any, Callable

if __package__ in (None, ""):
    sys.path.append(str(Path(__file__).resolve().parents[2]))

from backend.services.embedding_service import EmbeddingService


DATA_PATH = Path(__file__).resolve().parent / "data" / "skills.json"
MIN_SKILL_COUNT = 100


def load_skill_seed_data(path: Path = DATA_PATH) -> list[dict[str, str]]:
    records = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(records, list):
        raise ValueError("skill seed data must be a JSON array")
    if len(records) < MIN_SKILL_COUNT:
        raise ValueError(f"skill seed data must contain at least {MIN_SKILL_COUNT} records")

    seen: set[str] = set()
    for index, record in enumerate(records):
        validate_skill_record(record, index=index)
        normalized_key = canonical_skill_key(record["normalized_name"])
        if normalized_key in seen:
            raise ValueError(f"duplicate normalized skill name: {record['normalized_name']}")
        seen.add(normalized_key)
    return records


def validate_skill_record(record: Any, *, index: int) -> None:
    if not isinstance(record, dict):
        raise ValueError(f"skill record at index {index} must be an object")

    for field in ("name", "normalized_name", "category"):
        if field not in record:
            raise ValueError(f"skill record at index {index} is missing {field}")
        if not isinstance(record[field], str) or not record[field].strip():
            raise ValueError(f"skill record at index {index} has invalid {field}")


def build_skill_embedding_text(record: dict[str, str]) -> str:
    return (
        f"Skill: {record['normalized_name']} | "
        f"Alias: {record['name']} | "
        f"Category: {record['category']}"
    )


def canonical_skill_key(name: str) -> str:
    key = name.strip().casefold()
    key = key.replace("-", " ").replace("_", " ")
    key = re.sub(r"\s+", " ", key)
    return key.strip()


async def seed_skills(
    session: Any,
    *,
    records: list[dict[str, str]] | None = None,
    embedding_service: EmbeddingService | None = None,
    skill_model: type[Any] | None = None,
    statement_factory: Callable[[type[Any], str], Any] | None = None,
) -> int:
    skills = records or load_skill_seed_data()
    embedder = embedding_service or EmbeddingService()
    model = skill_model or _skill_model()
    make_statement = statement_factory or _skill_lookup_statement
    embedding_texts = [build_skill_embedding_text(record) for record in skills]
    embeddings = await embedder.embed_texts(embedding_texts)

    for record, embedding in zip(skills, embeddings):
        result = await session.execute(make_statement(model, record["normalized_name"]))
        skill = result.scalar_one_or_none()
        values = {
            "name": record["name"],
            "normalized_name": record["normalized_name"],
            "category": record["category"],
            "embedding": embedding,
        }
        if skill is None:
            session.add(model(**values))
        else:
            for key, value in values.items():
                setattr(skill, key, value)

    await session.commit()
    return len(skills)


async def run_seed(path: Path = DATA_PATH) -> int:
    from backend.core.database import AsyncSessionLocal

    records = load_skill_seed_data(path)
    async with AsyncSessionLocal() as session:
        return await seed_skills(session, records=records)


def _skill_model() -> type[Any]:
    from backend.models.skill import Skill

    return Skill


def _skill_lookup_statement(skill_model: type[Any], normalized_name: str) -> Any:
    from sqlalchemy import select

    return select(skill_model).where(skill_model.normalized_name == normalized_name)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed Skill knowledge base data with embeddings.")
    parser.add_argument(
        "--data",
        type=Path,
        default=DATA_PATH,
        help="Path to skills seed JSON file.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    count = asyncio.run(run_seed(args.data))
    print(f"Seeded {count} skills with embeddings.")


if __name__ == "__main__":
    main()
