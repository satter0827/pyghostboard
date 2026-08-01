"""Build and verify deterministic GNU gettext catalogs."""

from __future__ import annotations

import argparse
import ast
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path

from babel.messages.catalog import Catalog
from babel.messages.mofile import write_mo
from babel.messages.pofile import read_po, write_po

ROOT = Path(__file__).resolve().parents[1]
CLI_SOURCE = ROOT / "src" / "pyghostboard" / "cli"
LOCALE_ROOT = ROOT / "src" / "pyghostboard" / "locale"
POT_PATH = LOCALE_ROOT / "pyghostboard.pot"
PO_PATH = LOCALE_ROOT / "ja" / "LC_MESSAGES" / "pyghostboard.po"
MO_PATH = LOCALE_ROOT / "ja" / "LC_MESSAGES" / "pyghostboard.mo"
CREATION_DATE = datetime(2026, 8, 1, tzinfo=UTC)

FRAMEWORK_MESSAGES = {
    "Aborted.",
    "Arguments",
    "Commands",
    "Error",
    "Invalid value",
    "Missing argument",
    "Missing option",
    "Options",
    "Show this message and exit.",
    "Try [blue]'{command_path} {help_option}'[/] for help.",
    "Usage:",
    "[default: {}]",
    "[env var: {}]",
    "[required]",
}


def extracted_messages() -> tuple[str, ...]:
    messages = set(FRAMEWORK_MESSAGES)
    for path in CLI_SOURCE.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "tr"
                and node.args
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)
            ):
                messages.add(node.args[0].value)
    return tuple(sorted(messages))


def source_catalog() -> Catalog:
    catalog = Catalog(
        project="pyghostboard",
        version="0.1.0",
        creation_date=CREATION_DATE,
        charset="UTF-8",
    )
    for message in extracted_messages():
        catalog.add(message)
    return catalog


def pot_bytes() -> bytes:
    output = BytesIO()
    write_po(output, source_catalog(), width=100, omit_header=False, sort_output=True)
    return output.getvalue().rstrip() + b"\n"


def mo_bytes() -> bytes:
    with PO_PATH.open("rb") as source:
        catalog = read_po(source, locale="ja")
    catalog.creation_date = CREATION_DATE
    catalog.revision_date = CREATION_DATE
    expected = set(extracted_messages())
    translated = {message.id for message in catalog if isinstance(message.id, str) and message.id}
    if translated != expected:
        missing = sorted(expected - translated)
        unexpected = sorted(translated - expected)
        raise ValueError(f"Japanese catalog differs: missing={missing}, unexpected={unexpected}")
    empty = sorted(
        message.id
        for message in catalog
        if isinstance(message.id, str) and message.id and not message.string
    )
    if empty:
        raise ValueError(f"Japanese catalog has empty translations: {empty}")
    output = BytesIO()
    write_mo(output, catalog, use_fuzzy=False)
    return output.getvalue()


def update() -> None:
    POT_PATH.parent.mkdir(parents=True, exist_ok=True)
    MO_PATH.parent.mkdir(parents=True, exist_ok=True)
    POT_PATH.write_bytes(pot_bytes())
    MO_PATH.write_bytes(mo_bytes())


def check() -> None:
    expected = {POT_PATH: pot_bytes(), MO_PATH: mo_bytes()}
    stale = [
        path
        for path, content in expected.items()
        if not path.exists() or path.read_bytes() != content
    ]
    if stale:
        paths = ", ".join(str(path.relative_to(ROOT)) for path in stale)
        raise ValueError(f"translation catalogs are stale: {paths}; run tools/i18n.py update")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("check", "update"))
    arguments = parser.parse_args()
    update() if arguments.action == "update" else check()


if __name__ == "__main__":
    main()
