import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MAKEFILE = (ROOT / "Makefile").read_text(encoding="utf-8")
TARGETS = ("install", "dev", "test", "lint", "migrate", "seed", "build", "clean")


def _recipe(target: str) -> str:
    match = re.search(
        rf"^{target}(?:\s*:[^\n]*)?\n(?P<recipe>(?:\t[^\n]*\n)+)",
        MAKEFILE,
        re.MULTILINE,
    )
    assert match is not None, f"missing or empty Makefile target: {target}"
    return match.group("recipe")


def test_makefile_exposes_all_required_phony_targets():
    phony_line = re.search(r"^\.PHONY:\s*(.+)$", MAKEFILE, re.MULTILINE)
    assert phony_line is not None

    phony_targets = set(phony_line.group(1).split())
    assert set(TARGETS) <= phony_targets
    for target in TARGETS:
        _recipe(target)


def test_install_target_installs_backend_frontend_and_quality_dependencies():
    recipe = _recipe("install")
    assert "-m pip install -r backend/requirements.txt" in recipe
    assert "-m pip install pre-commit" in recipe
    assert "--prefix frontend ci" in recipe
    assert (
        "-m pre_commit install --hook-type pre-commit --hook-type pre-push"
        in recipe
    )


def test_dev_target_applies_migrations_then_starts_the_stack():
    assert re.search(r"^dev:\s+migrate$", MAKEFILE, re.MULTILINE)
    assert "$(COMPOSE) up --build" in _recipe("dev")

    migrate_recipe = _recipe("migrate")
    assert "$(COMPOSE) up -d db" in migrate_recipe
    assert "$(COMPOSE) build backend" in migrate_recipe
    assert "alembic upgrade head" in migrate_recipe


def test_test_and_lint_targets_cover_both_applications():
    test_recipe = _recipe("test")
    assert "-m pytest backend/tests tests -q" in test_recipe
    assert "--prefix frontend test" in test_recipe
    assert "--prefix frontend run typecheck" in test_recipe
    assert "--project frontend/tsconfig.json" not in test_recipe
    assert "-m pre_commit run --all-files" in _recipe("lint")


def test_seed_and_build_targets_use_the_production_workflows():
    assert re.search(r"^seed:\s+migrate$", MAKEFILE, re.MULTILINE)
    seed_recipe = _recipe("seed")
    assert "python -m backend.scripts.seed_skills" in seed_recipe
    assert "python -m backend.scripts.seed_majors" in seed_recipe

    build_recipe = _recipe("build")
    assert "--target prod -f backend/Dockerfile" in build_recipe
    assert "--target prod -f frontend/Dockerfile" in build_recipe


def test_clean_target_only_removes_explicit_files():
    recipe = _recipe("clean")
    assert "Path('.coverage').unlink(missing_ok=True)" in recipe
    assert "Path('coverage.xml').unlink(missing_ok=True)" in recipe

    forbidden_commands = (
        "del /s",
        "rd /s",
        "rmdir /s",
        "remove-item -recurse",
        "rm -rf",
    )
    normalized_recipe = recipe.casefold()
    assert all(command not in normalized_recipe for command in forbidden_commands)
