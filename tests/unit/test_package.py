"""Unit tests for the package metadata contract."""

import ast
from importlib.metadata import version
from pathlib import Path

import pyghostboard

PACKAGE_ROOT = Path(__file__).resolve().parents[2] / "src" / "pyghostboard"


def test_public_version_matches_distribution_metadata() -> None:
    assert pyghostboard.__version__ == version("pyghostboard")


def test_public_api_is_explicit() -> None:
    assert "Match" in pyghostboard.__all__
    assert "RuleSet" in pyghostboard.__all__
    assert "MatchService" in pyghostboard.__all__
    assert "__version__" in pyghostboard.__all__


def test_internal_modules_do_not_import_public_reexport_facades() -> None:
    violations: list[str] = []
    for path in PACKAGE_ROOT.rglob("*.py"):
        if path == PACKAGE_ROOT / "__init__.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module in {
                "pyghostboard.application",
                "pyghostboard.domain",
            }:
                violations.append(f"{path.relative_to(PACKAGE_ROOT)}:{node.lineno}")
    assert violations == []
