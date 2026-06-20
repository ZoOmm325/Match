from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_alembic_ini_points_to_migrations_directory():
    alembic_ini = read("backend/alembic.ini")

    assert "script_location = migrations" in alembic_ini
    assert "prepend_sys_path = ." in alembic_ini
    assert "The real database URL is loaded by migrations/env.py" in alembic_ini
    assert "sqlalchemy.url = driver://user:pass@localhost/dbname" in alembic_ini
    assert "sqlalchemy.url = postgresql+asyncpg://postgres:postgres@localhost:5432/match" not in alembic_ini


def test_migration_env_uses_project_settings_and_metadata():
    env_py = read("backend/migrations/env.py")

    assert "from backend.core.config import get_settings" in env_py
    assert "from backend.core.database import Base" in env_py
    assert "async_engine_from_config" in env_py
    assert "target_metadata = Base.metadata" in env_py
    assert "connection.run_sync(do_run_migrations)" in env_py


def test_initial_revision_enables_pgvector_extension():
    revision = read("backend/migrations/versions/001_enable_pgvector.py")

    assert 'revision: str = "001_enable_pgvector"' in revision
    assert 'op.execute("CREATE EXTENSION IF NOT EXISTS vector")' in revision
    assert 'op.execute("DROP EXTENSION IF EXISTS vector")' in revision
