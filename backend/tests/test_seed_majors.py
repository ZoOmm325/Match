import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

from backend.scripts.seed_majors import build_major_embedding_text
from backend.scripts.seed_majors import load_major_seed_data
from backend.scripts.seed_majors import seed_majors


ROOT = Path(__file__).resolve().parents[2]
DATA_PATH = ROOT / "backend" / "scripts" / "data" / "majors.json"


class FakeEmbeddingService:
    def __init__(self) -> None:
        self.calls = []

    async def embed_texts(self, texts):
        self.calls.append(list(texts))
        return [[float(index)] * 1024 for index, _ in enumerate(texts)]


class FakeScalarResult:
    def __init__(self, item):
        self.item = item

    def scalar_one_or_none(self):
        return self.item


class FakeSession:
    def __init__(self, existing=None) -> None:
        self.existing = existing
        self.added = []
        self.executed = []
        self.commits = 0

    async def execute(self, statement):
        self.executed.append(statement)
        return FakeScalarResult(self.existing)

    def add(self, item):
        self.added.append(item)

    async def commit(self):
        self.commits += 1


class FakeMajor(SimpleNamespace):
    pass


def fake_statement_factory(model, code):
    return {"model": model, "code": code}


def test_major_seed_json_contains_at_least_50_complete_records():
    records = load_major_seed_data(DATA_PATH)

    assert len(records) >= 50
    assert len({record["code"] for record in records}) == len(records)
    assert all(record["curriculum"]["core"] for record in records)


def test_major_seed_json_is_valid_utf8_json():
    records = json.loads(DATA_PATH.read_text(encoding="utf-8"))

    assert records[0]["name"] == "计算机科学与技术"
    assert records[0]["code"] == "080901"


def test_build_major_embedding_text_includes_description_and_courses():
    record = load_major_seed_data(DATA_PATH)[0]

    text = build_major_embedding_text(record)

    assert "专业名称: 计算机科学与技术" in text
    assert "专业描述:" in text
    assert "核心课程:" in text
    assert "数据结构" in text


def test_seed_majors_inserts_records_with_1024_dimensional_embeddings():
    records = load_major_seed_data(DATA_PATH)[:2]
    session = FakeSession()
    embedder = FakeEmbeddingService()

    count = asyncio.run(
        seed_majors(
            session,
            records=records,
            embedding_service=embedder,
            major_model=FakeMajor,
            statement_factory=fake_statement_factory,
        )
    )

    assert count == 2
    assert len(session.added) == 2
    assert session.added[0].name == records[0]["name"]
    assert session.added[0].code == records[0]["code"]
    assert len(session.added[0].embedding) == 1024
    assert len(embedder.calls[0]) == 2
    assert session.commits == 1


def test_seed_majors_updates_existing_major_by_code():
    records = load_major_seed_data(DATA_PATH)[:1]
    existing = SimpleNamespace(
        name="旧名称",
        code=records[0]["code"],
        category=None,
        description=None,
        curriculum=None,
        embedding=None,
    )
    session = FakeSession(existing=existing)

    count = asyncio.run(
        seed_majors(
            session,
            records=records,
            embedding_service=FakeEmbeddingService(),
            major_model=FakeMajor,
            statement_factory=fake_statement_factory,
        )
    )

    assert count == 1
    assert session.added == []
    assert existing.name == records[0]["name"]
    assert existing.category == records[0]["category"]
    assert len(existing.embedding) == 1024
    assert session.commits == 1
