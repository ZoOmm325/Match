from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
README = (ROOT / "README.md").read_text(encoding="utf-8")


def test_readme_is_bilingual_and_describes_the_project():
    assert "# 岗位 JD → 大学专业匹配系统" in README
    assert "## 中文说明" in README
    assert "## English" in README
    assert "### 项目概述" in README
    assert "### Overview" in README
    assert "DeepSeek" in README
    assert "BAAI/bge-m3" in README
    assert "PostgreSQL 16" in README
    assert "pgvector" in README


def test_readme_documents_architecture_and_technology_stack():
    assert "```mermaid" in README
    assert "Next.js 前端" in README
    assert "FastAPI API" in README
    assert "多维评分与推荐排序" in README
    assert "### 技术栈" in README
    assert "### Technology" in README


def test_readme_docker_quick_start_includes_migrations_and_seed_data():
    required_commands = (
        "Copy-Item .env.example .env",
        "docker compose build",
        "docker compose up -d db",
        'docker compose run --rm backend sh -c "cd /app/backend && alembic upgrade head"',
        "python -m backend.scripts.seed_skills",
        "python -m backend.scripts.seed_majors",
        "docker compose up -d",
    )
    for command in required_commands:
        assert command in README

    assert "DEEPSEEK_API_KEY=sk-your-deepseek-api-key" in README
    assert '`CORS_ORIGINS` | `["http://localhost:3000"]`' in README
    assert "首次执行会下载 `BAAI/bge-m3`" in README
    assert "种子命令是幂等的" in README


def test_readme_documents_local_development_and_host_database_difference():
    assert "py -3.12 -m venv .venv" in README
    assert "pip install -r" in README
    assert "requirements.txt" in README
    assert "python -m uvicorn backend.main:app --reload" in README
    assert "npm ci" in README
    assert "npm run dev" in README
    assert "主机名 `db` 用于 Docker 网络" in README
    assert "Use `localhost` when the backend runs directly on the host." in README
    assert "#### Requirements" in README
    assert "- Python 3.12" in README
    assert "- Node.js 22 and npm" in README
    assert "- PostgreSQL 16 with the pgvector extension" in README
    assert "- A DeepSeek API key" in README


def test_readme_links_api_docs_and_lists_public_api_groups():
    assert "http://localhost:8000/docs" in README
    assert "http://localhost:8000/openapi.json" in README
    assert "/api/health" in README
    assert "/api/jd/extract" in README
    assert "/api/match/by-skills" in README
    assert "/api/skills/categories" in README
    assert "/api/majors/search" in README
    assert '"code": 0' in README
    assert '"data": {}' in README
    assert '"message": "success"' in README


def test_readme_documents_tests_and_repository_layout():
    assert "python -m pytest backend\\tests tests -q" in README
    assert "--cov-fail-under=80" in README
    assert "TEST_PGVECTOR_DATABASE_URL" in README
    assert "npm test" in README
    assert "npx tsc --noEmit" in README
    assert "npm run build" in README

    for path in (
        "backend/core",
        "backend/models",
        "backend/routers",
        "backend/services",
        "backend/scripts",
        "frontend/app",
        "frontend/components",
        ".github/workflows",
    ):
        assert path in README


def test_readme_documents_makefile_workflows():
    for command in (
        "make install",
        "make migrate",
        "make seed",
        "make dev",
        "make test",
        "make lint",
        "make build",
        "make clean",
    ):
        assert command in README

    assert "starts PostgreSQL, applies the Alembic migrations" in README
    assert "directory caches" in README
