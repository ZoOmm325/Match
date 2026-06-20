from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_compose_declares_required_services_and_ports():
    compose = read("docker-compose.yml")

    for service in ("db:", "backend:", "frontend:"):
        assert service in compose

    assert "pgvector/pgvector:pg16" in compose
    assert "${POSTGRES_PORT:-5432}:5432" in compose
    assert "${BACKEND_PORT:-8000}:8000" in compose
    assert "${FRONTEND_PORT:-3000}:3000" in compose


def test_compose_wires_backend_to_pgvector_database():
    compose = read("docker-compose.yml")

    assert "env_file:" in compose
    assert "path: .env" in compose
    assert "required: false" in compose
    assert "DATABASE_URL: ${DATABASE_URL:-postgresql+asyncpg://postgres:postgres@db:5432/match}" in compose
    assert "OPENAI_API_KEY:" not in compose
    assert "condition: service_healthy" in compose
    assert "pg_isready" in compose
    assert "uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload" in compose


def test_dockerfiles_match_backend_and_next_standalone_runtime():
    backend_dockerfile = read("backend/Dockerfile")
    frontend_dockerfile = read("frontend/Dockerfile")
    next_config = read("frontend/next.config.mjs")

    assert "FROM python:3.12-slim AS base" in backend_dockerfile
    assert "pip install -r /app/backend/requirements.txt" in backend_dockerfile
    assert "backend.main:app" in backend_dockerfile
    assert 'ENTRYPOINT ["/app/backend/docker-entrypoint.sh"]' in backend_dockerfile

    assert 'output: "standalone"' in next_config
    assert "FROM node:22-alpine AS prod" in frontend_dockerfile
    assert "COPY --from=builder /app/.next/standalone ./" in frontend_dockerfile
    assert 'CMD ["node", "server.js"]' in frontend_dockerfile


def test_env_example_contains_required_runtime_settings():
    env_example = read(".env.example")

    for key in (
        "POSTGRES_DB=match",
        "DATABASE_URL=postgresql+asyncpg://postgres:postgres@db:5432/match",
        "RUN_MIGRATIONS=true",
        "# OPENAI_API_KEY=sk-your-api-key",
        "NEXT_PUBLIC_API_BASE_URL=http://localhost:8000/api",
    ):
        assert key in env_example


def test_backend_entrypoint_runs_migrations_when_alembic_exists():
    entrypoint = read("backend/docker-entrypoint.sh")

    assert 'RUN_MIGRATIONS:-true' in entrypoint
    assert '[ -f "/app/backend/alembic.ini" ]' in entrypoint
    assert "alembic upgrade head" in entrypoint
    assert "cd /app\n" not in entrypoint
    assert 'exec "$@"' in entrypoint
