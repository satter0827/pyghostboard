"""Focused tests for interactive CLI behavior."""

from collections.abc import Coroutine
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from typer.testing import CliRunner

from pyghostboard.application import AbortReason, MatchAborted
from pyghostboard.cli import _prompt_action, _prompt_placement, _render_view, app
from pyghostboard.domain import Escape, Match, Placement, Player, RuleSet

runner = CliRunner()


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
    monkeypatch.setattr("pyghostboard.cli.Prompt.ask", lambda *args, **kwargs: next(answers))
    placement = _prompt_placement(RuleSet.standard(), Player.ONE)
    assert len(placement.good) == 4
    assert len(placement.bad) == 4


def test_prompt_action_and_board_render_cover_move_and_escape(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    view = _match().view_for(Player.ONE)
    monkeypatch.setattr("pyghostboard.cli.Prompt.ask", lambda *args, **kwargs: "1")
    assert _prompt_action(view) == view.legal_actions[0]
    _render_view(view)

    escape_view = view.model_copy(
        update={"legal_actions": (Escape(source=view.own_pieces[0].square),)}
    )
    assert _prompt_action(escape_view) == escape_view.legal_actions[0]


def test_play_command_builds_default_agent_command(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(coroutine: Coroutine[Any, Any, None]) -> None:
        coroutine.close()

    monkeypatch.setattr("pyghostboard.cli.asyncio.run", fake_run)
    result = runner.invoke(app, ["play", "--seed", "9"])
    assert result.exit_code == 0


def test_play_command_rejects_combined_agent_selectors() -> None:
    result = runner.invoke(
        app,
        ["play", "--agent", "random", "--ai-command", "external-agent"],
    )
    assert result.exit_code == 2
    assert "cannot be combined" in result.stdout


def test_play_command_reports_agent_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(coroutine: Coroutine[Any, Any, None]) -> None:
        coroutine.close()
        raise MatchAborted(AbortReason.AGENT_FAILURE, "broken")

    monkeypatch.setattr("pyghostboard.cli.asyncio.run", fail)
    result = runner.invoke(app, ["play"])
    assert result.exit_code == 1
    assert "Match aborted" in result.stdout
    assert '"event": "match_aborted"' in result.stderr
    assert '"reason": "agent_failure"' in result.stderr


def test_replay_rejects_empty_record(tmp_path: Path) -> None:
    record = tmp_path / "empty.jsonl"
    record.write_text("", encoding="utf-8")
    result = runner.invoke(app, ["replay", str(record)])
    assert result.exit_code != 0
    assert "record_header" in result.stderr
