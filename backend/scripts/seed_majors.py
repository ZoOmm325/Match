from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any, Callable

if __package__ in (None, ""):
    sys.path.append(str(Path(__file__).resolve().parents[2]))

from backend.services.embedding_service import EmbeddingService

DATA_PATH = Path(__file__).resolve().parent / "data" / "majors.json"
MIN_MAJOR_COUNT = 50


def load_major_seed_data(path: Path = DATA_PATH) -> list[dict[str, Any]]:
    records = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(records, list):
        raise ValueError("major seed data must be a JSON array")
    if len(records) < MIN_MAJOR_COUNT:
        raise ValueError(f"major seed data must contain at least {MIN_MAJOR_COUNT} records")

    seen_codes: set[str] = set()
    for index, record in enumerate(records):
        validate_major_record(record, index=index)
        code = record["code"]
        if code in seen_codes:
            raise ValueError(f"duplicate major code: {code}")
        seen_codes.add(code)
    return records


def validate_major_record(record: Any, *, index: int) -> None:
    if not isinstance(record, dict):
        raise ValueError(f"major record at index {index} must be an object")

    for field in ("name", "code", "category", "description", "curriculum"):
        if field not in record:
            raise ValueError(f"major record at index {index} is missing {field}")

    for field in ("name", "code", "category", "description"):
        if not isinstance(record[field], str) or not record[field].strip():
            raise ValueError(f"major record at index {index} has invalid {field}")

    curriculum = record["curriculum"]
    if not isinstance(curriculum, dict) or not curriculum.get("core"):
        raise ValueError(f"major record at index {index} must define curriculum.core")
    if not all(isinstance(course, str) and course.strip() for course in curriculum["core"]):
        raise ValueError(f"major record at index {index} has invalid core courses")


def build_major_embedding_text(record: dict[str, Any]) -> str:
    core_courses = ", ".join(record["curriculum"].get("core", []))
    practice_courses = ", ".join(record["curriculum"].get("practice", []))
    parts = [
        f"专业名称: {record['name']}",
        f"专业代码: {record['code']}",
        f"学科门类: {record['category']}",
        f"专业描述: {record['description']}",
        f"核心课程: {core_courses}",
    ]
    if practice_courses:
        parts.append(f"实践课程: {practice_courses}")
    return " | ".join(parts)


async def seed_majors(
    session: Any,
    *,
    records: list[dict[str, Any]] | None = None,
    embedding_service: EmbeddingService | None = None,
    major_model: type[Any] | None = None,
    statement_factory: Callable[[type[Any], str], Any] | None = None,
) -> int:
    majors = records or load_major_seed_data()
    embedder = embedding_service or EmbeddingService()
    model = major_model or _major_model()
    make_statement = statement_factory or _major_lookup_statement
    embedding_texts = [build_major_embedding_text(record) for record in majors]
    embeddings = await embedder.embed_texts(embedding_texts)

    for record, embedding in zip(majors, embeddings):
        result = await session.execute(make_statement(model, record["code"]))
        major = result.scalar_one_or_none()
        values = {
            "name": record["name"],
            "code": record["code"],
            "category": record["category"],
            "description": record["description"],
            "curriculum": record["curriculum"],
            "embedding": embedding,
        }
        if major is None:
            session.add(model(**values))
        else:
            for key, value in values.items():
                setattr(major, key, value)

    await session.commit()
    return len(majors)


async def run_seed(path: Path = DATA_PATH) -> int:
    from backend.core.database import AsyncSessionLocal

    records = load_major_seed_data(path)
    async with AsyncSessionLocal() as session:
        return await seed_majors(session, records=records)


def _major_model() -> type[Any]:
    from backend.models.major import Major

    return Major


def _major_lookup_statement(major_model: type[Any], code: str) -> Any:
    from sqlalchemy import select

    return select(major_model).where(major_model.code == code)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed Major knowledge base data with embeddings.")
    parser.add_argument(
        "--data",
        type=Path,
        default=DATA_PATH,
        help="Path to majors seed JSON file.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    count = asyncio.run(run_seed(args.data))
    print(f"Seeded {count} majors with embeddings.")


if __name__ == "__main__":
    main()
