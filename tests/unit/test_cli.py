"""Focused tests for localized interactive CLI behavior."""

from collections.abc import Coroutine
from io import StringIO
from typing import Any
from uuid import uuid4

import pytest
from rich.console import Console
from typer.testing import CliRunner

from pyghostboard.application import AbortReason, MatchAborted
from pyghostboard.cli import commands, create_app
from pyghostboard.cli.display import render_screen, supports_live
from pyghostboard.cli.i18n import resolve_language
from pyghostboard.cli.input import parse_action, prompt_placement
from pyghostboard.domain import Escape, Match, Move, Placement, Player, RuleSet, Square

runner = CliRunner()


def _console(stream: StringIO | None = None, *, terminal: bool = False) -> Console:
    return Console(
        file=stream or StringIO(),
        force_terminal=terminal,
        color_system="standard" if terminal else None,
        width=100,
    )


def _match() -> Match:
    rules = RuleSet.standard()
    one = rules.start_squares(Player.ONE)
    two = rules.start_squares(Player.TWO)
    return Match.start(
        uuid4(),
        rules,
        {
            Player.ONE: Placement(good=one[:4], bad=one[4:]),
            Player.TWO: Placement(good=two[:4], bad=two[4:]),
        },
    )


def test_prompt_placement_retries_invalid_input(monkeypatch: pytest.MonkeyPatch) -> None:
    answers = iter(("z9", "b1,c1,d1,e1"))
    monkeypatch.setattr("pyghostboard.cli.input.Prompt.ask", lambda *args, **kwargs: next(answers))
    placement = prompt_placement(_console(), RuleSet.standard(), Player.ONE)
    assert len(placement.good) == 4
    assert len(placement.bad) == 4


def test_action_input_accepts_number_move_and_escape() -> None:
    move = Move(source=Square.parse("b2"), destination=Square.parse("c2"))
    escape = Escape(source=Square.parse("d6"))
    legal = (move, escape)

    assert parse_action("1", legal) == move
    assert parse_action("b2 c2", legal) == move
    assert parse_action("d6 exit", legal) == escape
    assert parse_action("b2 b3", legal) is None


def test_board_screen_uses_only_player_view() -> None:
    view = _match().view_for(Player.ONE)
    stream = StringIO()
    console = _console(stream)
    console.print(render_screen(view, None))

    assert "Board" in stream.getvalue()
    assert "Last move: none" in stream.getvalue()
    assert "?" in stream.getvalue()


def test_live_mode_requires_tty_color_and_capable_terminal() -> None:
    console = _console(terminal=True)

    assert supports_live(console, {"TERM": "xterm-256color"})
    assert not supports_live(console, {"TERM": "dumb"})
    assert not supports_live(console, {"TERM": "xterm", "NO_COLOR": "1"})
    assert not supports_live(_console(), {"TERM": "xterm"})


def test_language_precedence_and_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("pyghostboard.cli.i18n._os_language", lambda: "ja_JP")

    assert resolve_language(["--language", "en"], {"PYGHOSTBOARD_LANGUAGE": "ja"}) == "en"
    assert resolve_language([], {"PYGHOSTBOARD_LANGUAGE": "ja_JP"}) == "ja"
    assert resolve_language([], {}) == "ja"
    assert resolve_language([], {"PYGHOSTBOARD_LANGUAGE": "unknown"}) == "en"


def test_help_and_usage_errors_are_localized() -> None:
    english = runner.invoke(create_app("en"), ["--help"])
    japanese = runner.invoke(create_app("ja"), ["--help"])
    usage_error = runner.invoke(create_app("ja"), ["replay"])

    assert english.exit_code == 0
    assert "Play and inspect" in english.stdout
    assert japanese.exit_code == 0
    assert "pyghostboardの対局" in japanese.stdout
    assert "使い方:" in japanese.stdout
    assert "オプション" in japanese.stdout
    assert "このメッセージを表示して終了します" in japanese.stdout
    assert usage_error.exit_code == 2
    assert "エラー" in usage_error.stderr


def test_play_uses_mcts_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    selected: list[str | None] = []

    def resolve(agent: str | None, command: list[str] | None) -> list[str]:
        selected.append(agent)
        assert command is None
        return ["agent"]

    def fake_run(coroutine: Coroutine[Any, Any, None]) -> None:
        coroutine.close()

    monkeypatch.setattr(commands, "resolve_agent_command", resolve)
    monkeypatch.setattr("pyghostboard.cli.commands.asyncio.run", fake_run)
    result = runner.invoke(create_app("en", console=_console()), ["play", "--seed", "9"])

    assert result.exit_code == 0
    assert selected == [None]


def test_play_rejects_combined_agent_selectors() -> None:
    stream = StringIO()
    result = runner.invoke(
        create_app("en", console=_console(stream)),
        ["play", "--agent", "random", "--command", "external-agent"],
    )

    assert result.exit_code == 2
    assert "cannot be combined" in stream.getvalue()


def test_play_reports_stable_agent_failure_code(monkeypatch: pytest.MonkeyPatch) -> None:
    stream = StringIO()

    def fail(coroutine: Coroutine[Any, Any, None]) -> None:
        coroutine.close()
        raise MatchAborted(AbortReason.AGENT_FAILURE, "broken")

    monkeypatch.setattr("pyghostboard.cli.commands.asyncio.run", fail)
    result = runner.invoke(create_app("ja", console=_console(stream)), ["play"])

    assert result.exit_code == 1
    assert "対局を中止しました" in stream.getvalue()
    assert "agent_failure" in stream.getvalue()
    assert '"event": "match_aborted"' in result.stderr
