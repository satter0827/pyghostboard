"""Executable repository and release-policy constraints."""

from __future__ import annotations

import ast
import json
import re
import tomllib
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
    assert "workflow_dispatch:" in workflow
    assert "scripts/release_gate.py release" in workflow
    assert "git rev-parse origin/main" in workflow
    assert "gh run list" in workflow
    assert "actions/upload-artifact@" in workflow
    assert "git push origin" in workflow
    assert "VERSION: ${{ inputs.version }}" in workflow
    assert '--version "${{ inputs.version }}"' not in workflow
    assert "pypi" not in lowered
    assert "id-token: write" not in lowered
    assert "gh-action-pypi-publish" not in lowered


def test_ci_checks_branch_tips_and_exposes_stable_gate_names() -> None:
    workflow = (WORKFLOW_ROOT / "ci.yml").read_text(encoding="utf-8")
    assert "branches: [develop, main]" in workflow
    assert "scripts/release_gate.py check quality" in workflow
    assert "scripts/release_gate.py check integration" in workflow
    assert "scripts/release_gate.py check package" in workflow
    assert "name: Develop Gate" in workflow
    assert "name: Release Gate" in workflow


def test_rulesets_require_only_the_stable_aggregate_gates() -> None:
    expected = {"develop": ["Develop Gate"], "main": ["Release Gate"]}
    for branch, contexts in expected.items():
        ruleset = json.loads((ROOT / ".github" / "rulesets" / f"{branch}.json").read_text())
        status_rule = next(
            rule for rule in ruleset["rules"] if rule["type"] == "required_status_checks"
        )
        assert [
            entry["context"] for entry in status_rule["parameters"]["required_status_checks"]
        ] == contexts


def test_supported_python_configuration_matches_project_metadata() -> None:
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    configured = set(re.findall(r'python-version = "(3\.\d+)"', pyproject))
    classifiers = set(re.findall(r'Programming Language :: Python :: (3\.\d+)"', pyproject))
    assert configured == classifiers == {"3.11", "3.12", "3.13", "3.14"}


def test_local_tool_state_is_grouped_under_one_private_directory() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    tools = pyproject["tool"]
    assert tools["pytest"]["ini_options"]["cache_dir"] == ".pyghostboard/cache/pytest"
    assert tools["ruff"]["cache-dir"] == ".pyghostboard/cache/ruff"
    assert tools["mypy"]["cache_dir"] == ".pyghostboard/cache/mypy"
    assert tools["coverage"]["run"]["data_file"] == ".pyghostboard/coverage/data"
    assert tools["coverage"]["html"]["directory"] == ".pyghostboard/coverage/html"
    assert tools["coverage"]["json"]["output"] == ".pyghostboard/coverage/coverage.json"
    assert tools["coverage"]["lcov"]["output"] == ".pyghostboard/coverage/coverage.lcov"
    assert tools["coverage"]["xml"]["output"] == ".pyghostboard/coverage/coverage.xml"

    release_gate = (ROOT / "scripts" / "release_gate.py").read_text(encoding="utf-8")
    assert 'CACHE_ROOT / "import-linter"' in release_gate
    hypothesis_config = (ROOT / "tests" / "conftest.py").read_text(encoding="utf-8")
    assert '".pyghostboard" / "cache" / "hypothesis"' in hypothesis_config
    tasks = json.loads((ROOT / ".vscode" / "tasks.json").read_text(encoding="utf-8"))
    import_task = next(task for task in tasks["tasks"] if task["label"] == "Check: Imports")
    assert import_task["args"] == [
        "run",
        "lint-imports",
        "--cache-dir",
        ".pyghostboard/cache/import-linter",
    ]


def test_review_policy_is_the_single_agent_review_source() -> None:
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    review_gate = (ROOT / "scripts" / "review_gate.md").read_text(encoding="utf-8")
    assert "scripts/review_gate.md" in agents
    assert "## Review scope" in review_gate
    assert "## Review-only constraints" not in agents


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
