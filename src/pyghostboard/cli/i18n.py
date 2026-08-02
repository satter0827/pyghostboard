"""Language resolution and GNU gettext activation for the CLI."""

from __future__ import annotations

import gettext
import locale
import os
from collections.abc import Sequence
from pathlib import Path

DEFAULT_LANGUAGE = "en"
SUPPORTED_LANGUAGES = frozenset({"en", "ja"})
LANGUAGE_ENV = "PYGHOSTBOARD_LANGUAGE"
LOCALE_DIRECTORY = Path(__file__).resolve().parents[1] / "locale"

_translation: gettext.NullTranslations = gettext.NullTranslations()


def tr(message: str) -> str:
    """Translate one human-facing CLI message."""
    return _translation.gettext(message)


def resolve_language(arguments: Sequence[str], environment: dict[str, str] | None = None) -> str:
    """Resolve CLI, environment, OS locale, then English in precedence order."""
    explicit = _language_argument(arguments)
    values = environment if environment is not None else os.environ
    candidate = explicit or values.get(LANGUAGE_ENV) or _os_language() or DEFAULT_LANGUAGE
    normalized = candidate.replace("-", "_").split("_", maxsplit=1)[0].lower()
    return normalized if normalized in SUPPORTED_LANGUAGES else DEFAULT_LANGUAGE


def activate_language(language: str) -> None:
    """Activate the selected catalog before constructing the Typer application."""
    global _translation
    if language not in SUPPORTED_LANGUAGES:
        raise ValueError(f"unsupported language: {language}")
    gettext.bindtextdomain("pyghostboard", LOCALE_DIRECTORY)
    gettext.textdomain("pyghostboard")
    _translation = gettext.translation(
        "pyghostboard",
        localedir=LOCALE_DIRECTORY,
        languages=[language],
        fallback=True,
    )
    _translation.install()
    _translate_typer_constants()


def _language_argument(arguments: Sequence[str]) -> str | None:
    for index, argument in enumerate(arguments):
        if argument.startswith("--language="):
            return argument.partition("=")[2]
        if argument == "--language" and index + 1 < len(arguments):
            return arguments[index + 1]
    return None


def _os_language() -> str | None:
    language, _ = locale.getlocale()
    return language


def _translate_typer_constants() -> None:
    # Typer resolves these strings during import, before main() can select a catalog.
    from typer import rich_utils

    rich_utils.DEFAULT_STRING = tr("[default: {}]")
    rich_utils.ENVVAR_STRING = tr("[env var: {}]")
    rich_utils.REQUIRED_LONG_STRING = tr("[required]")
    rich_utils.ARGUMENTS_PANEL_TITLE = tr("Arguments")
    rich_utils.OPTIONS_PANEL_TITLE = tr("Options")
    rich_utils.COMMANDS_PANEL_TITLE = tr("Commands")
    rich_utils.ERRORS_PANEL_TITLE = tr("Error")
    rich_utils.ABORTED_TEXT = tr("Aborted.")
    rich_utils.RICH_HELP = tr("Try [blue]'{command_path} {help_option}'[/] for help.")


__all__ = [
    "DEFAULT_LANGUAGE",
    "LANGUAGE_ENV",
    "SUPPORTED_LANGUAGES",
    "activate_language",
    "resolve_language",
    "tr",
]
