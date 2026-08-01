"""Localized pyghostboard command-line entry point."""

from __future__ import annotations

import sys
from collections.abc import Sequence
from typing import TYPE_CHECKING

from pyghostboard.cli.i18n import resolve_language

if TYPE_CHECKING:
    import typer
    from rich.console import Console


def create_app(language: str, *, console: Console | None = None) -> typer.Typer:
    """Lazily build the command tree after the caller resolves language."""
    from pyghostboard.cli.commands import create_app as build_app

    return build_app(language, console=console)


def main(arguments: Sequence[str] | None = None) -> None:
    """Resolve language before constructing and invoking the command tree."""
    selected_arguments = list(sys.argv[1:] if arguments is None else arguments)
    app = create_app(resolve_language(selected_arguments))
    app(args=selected_arguments, prog_name="pyghostboard")


__all__ = ["create_app", "main"]
