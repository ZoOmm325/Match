from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_ci_runs_for_pushes_and_pull_requests_with_limited_permissions():
    workflow = read(".github/workflows/test.yml")

    assert "name: Test" in workflow
    assert "push:" in workflow
    assert "pull_request:" in workflow
    assert workflow.count('      - "**.md"') == 2
    assert workflow.count('      - "docs/**"') == 2
    assert "permissions:\n  contents: read" in workflow
    assert "group: ${{ github.workflow }}-${{ github.ref }}" in workflow
    assert "group: test-${{ github.workflow }}" not in workflow
    assert "cancel-in-progress: true" in workflow


def test_backend_job_uses_healthy_pgvector_and_required_environment():
    workflow = read(".github/workflows/test.yml")

    assert "image: pgvector/pgvector:pg16" in workflow
    assert 'pg_isready -U postgres -d match_test' in workflow
    assert "DATABASE_URL: postgresql+asyncpg://postgres:postgres@localhost:5432/match_test" in workflow
    assert (
        "TEST_PGVECTOR_DATABASE_URL: "
        "postgresql+asyncpg://postgres:postgres@localhost:5432/match_test"
    ) in workflow
    assert "DEEPSEEK_API_KEY: ci-test-key" in workflow


def test_backend_job_installs_dependencies_migrates_and_enforces_coverage():
    workflow = read(".github/workflows/test.yml")

    expected_steps = (
        "uses: actions/checkout@v4",
        "uses: actions/setup-python@v5",
        "python -m pip install -r backend/requirements.txt",
        "working-directory: backend",
        "python -m alembic upgrade head",
        "python -m pytest backend/tests tests",
        "--cov=backend",
        "--cov-config=.coveragerc",
        "--cov-report=xml:coverage.xml",
        "--cov-fail-under=80",
        "uses: actions/upload-artifact@v4",
    )
    for expected in expected_steps:
        assert expected in workflow


def test_coverage_configuration_excludes_tests_and_migrations():
    coverage_config = read(".coveragerc")

    assert "source = backend" in coverage_config
    assert "backend/tests/*" in coverage_config
    assert "backend/migrations/*" in coverage_config
    assert "show_missing = True" in coverage_config


def test_frontend_job_runs_tests_types_and_production_build():
    workflow = read(".github/workflows/test.yml")

    assert "uses: actions/setup-node@v4" in workflow
    assert 'node-version: "22"' in workflow
    assert "cache-dependency-path: frontend/package-lock.json" in workflow
    assert "run: npm ci" in workflow
    assert "run: npm test" in workflow
    assert "run: npx tsc --noEmit" in workflow
    assert "run: npm run build" in workflow
