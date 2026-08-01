"""Repository structure and dependency-boundary tests."""

from __future__ import annotations

import ast
import graphlib
import json
from collections.abc import Iterator
from pathlib import Path

import pyghostboard.application as application_api
import pyghostboard.domain as domain_api
from pyghostboard.protocol import request_adapter, response_adapter

PACKAGE_ROOT = Path(__file__).resolve().parents[2] / "src" / "pyghostboard"
PUBLIC_FACADES = {"pyghostboard.application", "pyghostboard.domain"}
DOMAIN_FORBIDDEN_IMPORTS = {
    "asyncio",
    "logging",
    "os",
    "pathlib",
    "pydantic_settings",
    "rich",
    "structlog",
    "subprocess",
    "typer",
}


def _modules() -> dict[str, Path]:
    modules: dict[str, Path] = {}
    for path in PACKAGE_ROOT.rglob("*.py"):
        relative = path.relative_to(PACKAGE_ROOT)
        parts = relative.with_suffix("").parts
        if parts[-1] == "__init__":
            parts = parts[:-1]
        name = ".".join(("pyghostboard", *parts))
        modules[name] = path
    return modules


def _imports(path: Path) -> Iterator[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            yield from (alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            yield node.module


def _internal_target(imported: str, modules: dict[str, Path]) -> str | None:
    candidates = (
        module for module in modules if imported == module or imported.startswith(f"{module}.")
    )
    return max(candidates, key=len, default=None)


def _layer(module: str) -> int | None:
    if module == "pyghostboard.domain" or module.startswith("pyghostboard.domain."):
        return 0
    if module == "pyghostboard.application" or module.startswith("pyghostboard.application."):
        return 1
    if module == "pyghostboard.protocol":
        return 1
    if module == "pyghostboard.adapters" or module.startswith("pyghostboard.adapters."):
        return 2
    if module == "pyghostboard.random_agent":
        return 2
    if module == "pyghostboard.cli":
        return 3
    return None


def test_internal_dependency_graph_is_acyclic_and_points_inward() -> None:
    modules = _modules()
    graph: dict[str, set[str]] = {module: set() for module in modules}
    violations: list[str] = []
    for source, path in modules.items():
        for imported in _imports(path):
            target = _internal_target(imported, modules)
            if target is None or target == source:
                continue
            graph[source].add(target)
            source_layer = _layer(source)
            target_layer = _layer(target)
            if (
                source_layer is not None
                and target_layer is not None
                and target_layer > source_layer
            ):
                violations.append(f"{source} -> {target}")
    assert violations == []
    tuple(graphlib.TopologicalSorter(graph).static_order())


def test_package_imports_are_absolute_and_never_wildcarded() -> None:
    violations: list[str] = []
    for module, path in _modules().items():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom):
                continue
            if node.level:
                violations.append(f"{module}:{node.lineno} uses a relative import")
            if any(alias.name == "*" for alias in node.names):
                violations.append(f"{module}:{node.lineno} uses a wildcard import")
    assert violations == []


def test_adapter_modules_do_not_import_sibling_adapters() -> None:
    modules = _modules()
    violations: list[str] = []
    for source, path in modules.items():
        if not source.startswith("pyghostboard.adapters."):
            continue
        source_adapter = source.split(".")[2]
        for imported in _imports(path):
            if not imported.startswith("pyghostboard.adapters."):
                continue
            target_adapter = imported.split(".")[2]
            if target_adapter != source_adapter:
                violations.append(f"{source} -> {imported}")
    assert violations == []


def test_internal_modules_do_not_depend_on_public_reexport_facades() -> None:
    violations: list[str] = []
    for module, path in _modules().items():
        if module == "pyghostboard":
            continue
        for imported in _imports(path):
            if imported in PUBLIC_FACADES:
                violations.append(f"{module} -> {imported}")
    assert violations == []


def test_domain_has_no_io_process_configuration_or_logging_imports() -> None:
    violations: list[str] = []
    for module, path in _modules().items():
        if not module.startswith("pyghostboard.domain"):
            continue
        for imported in _imports(path):
            if imported.split(".", maxsplit=1)[0] in DOMAIN_FORBIDDEN_IMPORTS:
                violations.append(f"{module} -> {imported}")
    assert violations == []


def test_ai_wire_schema_cannot_contain_private_host_models() -> None:
    schemas = json.dumps(
        {
            "request": request_adapter.json_schema(),
            "response": response_adapter.json_schema(),
        },
        sort_keys=True,
    )
    assert "PrivateMatchSnapshot" not in schemas
    assert "PrivateMatchEvent" not in schemas
    assert "PrivatePiece" not in schemas


def test_public_facades_export_existing_unique_names() -> None:
    for facade in (domain_api, application_api):
        exported = facade.__all__
        assert len(exported) == len(set(exported))
        assert all(hasattr(facade, name) for name in exported)
