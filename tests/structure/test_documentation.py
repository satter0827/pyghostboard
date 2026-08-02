"""Executable documentation-organization constraints."""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[2]
DOCS_ROOT = ROOT / "docs"
DESIGN_ROOT = DOCS_ROOT / "design"
NOTES_ROOT = DOCS_ROOT / "notes"
MARKDOWN_LINK = re.compile(r"!?(?:\[[^\]]*\])\(([^)]+)\)")
NOTE_NAME = re.compile(r"\d{4}-\d{2}-\d{2}-[a-z0-9]+(?:-[a-z0-9]+)*\.md")


def _markdown_files() -> Iterator[Path]:
    yield from ROOT.glob("*.md")
    yield from DOCS_ROOT.rglob("*.md")
    yield from (ROOT / ".github").rglob("*.md")


def _link_targets(path: Path) -> Iterator[str]:
    text = path.read_text(encoding="utf-8")
    for match in MARKDOWN_LINK.finditer(text):
        value = match.group(1).strip()
        if value.startswith("<") and ">" in value:
            yield value[1 : value.index(">")]
        else:
            yield value.split(maxsplit=1)[0]


def _resolve_local_link(source: Path, target: str) -> Path | None:
    parsed = urlsplit(target)
    if parsed.scheme or parsed.netloc or not parsed.path:
        return None
    return (source.parent / unquote(parsed.path)).resolve()


def test_documentation_is_separated_by_authority() -> None:
    assert {path.name for path in DOCS_ROOT.glob("*.md")} == {"README.md"}
    assert DESIGN_ROOT.is_dir()
    assert NOTES_ROOT.is_dir()


def test_design_index_references_every_design_document() -> None:
    index = DESIGN_ROOT / "README.md"
    linked = {
        resolved
        for target in _link_targets(index)
        if (resolved := _resolve_local_link(index, target)) is not None
    }
    design_documents = set(DESIGN_ROOT.glob("*.md")) - {index}
    assert design_documents <= linked


def test_local_markdown_links_resolve() -> None:
    missing: list[str] = []
    for source in _markdown_files():
        for target in _link_targets(source):
            resolved = _resolve_local_link(source, target)
            if resolved is not None and not resolved.exists():
                missing.append(f"{source.relative_to(ROOT)}: {target}")
    assert missing == []


def test_temporary_notes_use_dated_names() -> None:
    invalid = [
        path.name
        for path in NOTES_ROOT.glob("*.md")
        if path.name != "README.md" and NOTE_NAME.fullmatch(path.name) is None
    ]
    assert invalid == []


def test_vscode_launches_supported_cli_workflows_in_an_integrated_terminal() -> None:
    document = json.loads((ROOT / ".vscode" / "launch.json").read_text(encoding="utf-8"))
    configurations = {item["name"]: item for item in document["configurations"]}
    expected_prefixes = {
        "App: Play": ["play"],
        "Arena: Watch Example": ["arena", "watch"],
        "Arena: Run Example": ["arena", "run"],
        "Arena: Resume": ["arena", "resume"],
    }
    for name, prefix in expected_prefixes.items():
        configuration = configurations[name]
        assert configuration["module"] == "pyghostboard.cli"
        assert configuration["console"] == "integratedTerminal"
        assert configuration["args"][: len(prefix)] == prefix
