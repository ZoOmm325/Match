import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

from backend.scripts.seed_skills import build_skill_embedding_text
from backend.scripts.seed_skills import canonical_skill_key
from backend.scripts.seed_skills import load_skill_seed_data
from backend.scripts.seed_skills import seed_skills


ROOT = Path(__file__).resolve().parents[2]
DATA_PATH = ROOT / "backend" / "scripts" / "data" / "skills.json"


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


class FakeSkill(SimpleNamespace):
    pass


def fake_statement_factory(model, normalized_name):
    return {"model": model, "normalized_name": normalized_name}


def test_skill_seed_json_contains_at_least_100_complete_records():
    records = load_skill_seed_data(DATA_PATH)

    assert len(records) >= 100
    assert len({canonical_skill_key(record["normalized_name"]) for record in records}) == len(records)
    assert {"programming_language", "framework", "database", "tool", "soft_skill"}.issubset(
        {record["category"] for record in records}
    )


def test_skill_seed_json_is_valid_utf8_json():
    records = json.loads(DATA_PATH.read_text(encoding="utf-8"))

    assert records[0] == {
        "name": "Python",
        "normalized_name": "Python",
        "category": "programming_language",
    }


def test_build_skill_embedding_text_includes_name_alias_and_category():
    record = load_skill_seed_data(DATA_PATH)[0]

    text = build_skill_embedding_text(record)

    assert "Skill: Python" in text
    assert "Alias: Python" in text
    assert "Category: programming_language" in text


def test_canonical_skill_key_matches_skill_normalizer_separator_rules():
    assert canonical_skill_key("Prompt Engineering") == "prompt engineering"
    assert canonical_skill_key("Prompt-Engineering") == "prompt engineering"
    assert canonical_skill_key("Prompt_Engineering") == "prompt engineering"


def test_seed_skills_inserts_records_with_1024_dimensional_embeddings():
    records = load_skill_seed_data(DATA_PATH)[:2]
    session = FakeSession()
    embedder = FakeEmbeddingService()

    count = asyncio.run(
        seed_skills(
            session,
            records=records,
            embedding_service=embedder,
            skill_model=FakeSkill,
            statement_factory=fake_statement_factory,
        )
    )

    assert count == 2
    assert len(session.added) == 2
    assert session.added[0].name == records[0]["name"]
    assert session.added[0].normalized_name == records[0]["normalized_name"]
    assert len(session.added[0].embedding) == 1024
    assert len(embedder.calls[0]) == 2
    assert session.commits == 1


def test_seed_skills_updates_existing_skill_by_normalized_name():
    records = load_skill_seed_data(DATA_PATH)[:1]
    existing = SimpleNamespace(
        name="Old Python",
        normalized_name=records[0]["normalized_name"],
        category=None,
        embedding=None,
    )
    session = FakeSession(existing=existing)

    count = asyncio.run(
        seed_skills(
            session,
            records=records,
            embedding_service=FakeEmbeddingService(),
            skill_model=FakeSkill,
            statement_factory=fake_statement_factory,
        )
    )

    assert count == 1
    assert session.added == []
    assert existing.name == records[0]["name"]
    assert existing.category == records[0]["category"]
    assert len(existing.embedding) == 1024
    assert session.commits == 1
