"""Command-line flows and complete bundled-agent match tests."""

import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

from pyghostboard.adapters.config import RuntimeSettings
from pyghostboard.adapters.recording import read_record
from pyghostboard.cli import _play, app
from pyghostboard.domain import Placement, Player, RuleSet

runner = CliRunner()
REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def test_cli_help_is_available() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "play" in result.stdout
    assert "replay" in result.stdout


def test_bundled_rule_example_is_valid() -> None:
    result = runner.invoke(app, ["rules", "validate", str(REPOSITORY_ROOT / "examples/rules.toml")])

    assert result.exit_code == 0
    assert "Valid rules: 6x6" in result.stdout


@pytest.mark.asyncio
async def test_complete_match_with_bundled_agent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    rules = RuleSet.standard()
    starts = rules.start_squares(Player.ONE)
    placement = Placement(good=starts[:4], bad=starts[4:])
    monkeypatch.setattr("pyghostboard.cli._prompt_placement", lambda *_: placement)
    monkeypatch.setattr("pyghostboard.cli._prompt_action", lambda view: view.legal_actions[0])
    monkeypatch.setattr("pyghostboard.cli._render_view", lambda *_: None)
    record = tmp_path / "match.jsonl"

    await _play(
        rules,
        record,
        5,
        [sys.executable, "-m", "pyghostboard.agent_runner", "--policy", "random"],
        RuntimeSettings(max_plies=1_000),
    )

    assert record.exists()
    persisted = read_record(record)
    assert len(persisted.header.main_commit_sha) == 40
    assert persisted.events[0].type == "match_started"
    replay = runner.invoke(app, ["replay", str(record)])
    assert replay.exit_code == 0
    assert "Replayed" in replay.stdout
