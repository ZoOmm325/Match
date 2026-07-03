import json
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_pre_commit_config_registers_all_required_quality_hooks():
    config = read(".pre-commit-config.yaml")

    for hook in ("black", "isort", "flake8", "mypy", "eslint", "prettier"):
        assert f"- id: {hook}" in config

    assert "files: ^backend/.*\\.py$" in config
    assert "files: ^frontend/.*\\.(js|mjs|ts|tsx)$" in config
    assert "exclude: ^results\\.json$" in config
    assert "--config=backend/pyproject.toml" in config
    assert "--settings-path=backend/pyproject.toml" in config
    assert "pass_filenames: false" in config
    assert "flake8-pyproject==1.2.3" in config
    assert "--toml-config=backend/pyproject.toml" in config
    assert "entry: python -m mypy" in config
    assert "mypy==1.13.0" in config
    assert "eslint-config-next@15.5.19" in config
    assert "typescript@5.9.3" in config
    assert "rev: v3.1.0" in config


def test_python_quality_tools_share_pyproject_configuration():
    config = tomllib.loads(read("backend/pyproject.toml"))

    assert config["tool"]["black"]["line-length"] == 100
    assert config["tool"]["isort"]["profile"] == "black"
    assert config["tool"]["isort"]["line_length"] == 100
    assert config["tool"]["flake8"]["max-line-length"] == 100
    assert config["tool"]["mypy"]["python_version"] == "3.12"
    assert config["tool"]["mypy"]["check_untyped_defs"] is True


def test_frontend_eslint_and_prettier_configs_are_valid_json():
    eslint = json.loads(read("frontend/.eslintrc.json"))
    prettier = json.loads(read("frontend/.prettierrc"))

    assert eslint["extends"] == ["next/core-web-vitals", "next/typescript"]
    assert "next-env.d.ts" in eslint["ignorePatterns"]
    assert prettier["printWidth"] == 100
    assert prettier["semi"] is True
    assert prettier["trailingComma"] == "es5"


def test_frontend_package_exposes_compatible_local_lint_commands():
    package = json.loads(read("frontend/package.json"))

    assert package["scripts"]["lint"] == "eslint . --max-warnings=0"
    assert package["devDependencies"]["eslint"] == "8.57.1"
    assert package["devDependencies"]["eslint-config-next"] == "15.5.19"
    assert package["devDependencies"]["prettier"] == "3.1.0"
    assert package["devDependencies"]["typescript"] == "5.9.3"
