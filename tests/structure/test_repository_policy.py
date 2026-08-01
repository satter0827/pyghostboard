"""Executable repository and release-policy constraints."""

from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_ROOT = ROOT / ".github" / "workflows"
PACKAGE_ROOT = ROOT / "src" / "pyghostboard"


def test_workflow_actions_are_pinned_to_complete_commits() -> None:
    violations: list[str] = []
    for workflow in WORKFLOW_ROOT.glob("*.yml"):
        for line_number, line in enumerate(workflow.read_text(encoding="utf-8").splitlines(), 1):
            stripped = line.strip()
            if not stripped.startswith("- uses:"):
                continue
            action = stripped.removeprefix("- uses:").split("#", maxsplit=1)[0].strip()
            if re.fullmatch(r"[^\s@]+@[0-9a-f]{40}", action) is None:
                violations.append(f"{workflow.name}:{line_number}: {action}")
    assert violations == []


def test_release_workflow_builds_artifacts_without_registry_publication() -> None:
    workflow = (WORKFLOW_ROOT / "release.yml").read_text(encoding="utf-8")
    lowered = workflow.lower()
    assert "tools/verify_distribution.py" in workflow
    assert "git rev-parse origin/main" in workflow
    assert "actions/upload-artifact@" in workflow
    assert "pypi" not in lowered
    assert "id-token: write" not in lowered
    assert "gh-action-pypi-publish" not in lowered


def test_process_adapters_never_enable_a_shell() -> None:
    violations: list[str] = []
    for path in PACKAGE_ROOT.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if any(
                keyword.arg == "shell"
                and isinstance(keyword.value, ast.Constant)
                and keyword.value.value is True
                for keyword in node.keywords
            ):
                violations.append(f"{path.relative_to(ROOT)}:{node.lineno}")
            if isinstance(node.func, ast.Attribute) and node.func.attr in {
                "create_subprocess_shell",
                "getoutput",
                "getstatusoutput",
            }:
                violations.append(f"{path.relative_to(ROOT)}:{node.lineno}")
    assert violations == []
