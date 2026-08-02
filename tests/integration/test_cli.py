"""Command-line flows and complete bundled-agent match tests."""

import sys
from io import StringIO
from pathlib import Path

import pytest
from rich.console import Console
from typer.testing import CliRunner

from pyghostboard.adapters.config import RuntimeSettings
from pyghostboard.adapters.recording import read_record
from pyghostboard.cli import commands, create_app
from pyghostboard.cli.commands import replay_match, run_human_match
from pyghostboard.domain import Placement, Player, RuleSet

runner = CliRunner()
REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def _console(stream: StringIO) -> Console:
    return Console(file=stream, color_system=None, force_terminal=False, width=100)


def test_cli_help_is_available_in_both_languages() -> None:
    english = runner.invoke(create_app("en"), ["--help"])
    japanese = runner.invoke(create_app("ja"), ["--help"])

    assert english.exit_code == 0
    assert "play" in english.stdout and "replay" in english.stdout
    assert japanese.exit_code == 0
    assert "独立したAIプロセスと対局" in japanese.stdout


def test_bundled_rule_example_is_valid() -> None:
    stream = StringIO()
    result = runner.invoke(
        create_app("en", console=_console(stream)),
        ["rules", "validate", str(REPOSITORY_ROOT / "examples/rules.toml")],
    )

    assert result.exit_code == 0
    assert "Valid rules: 6x6" in stream.getvalue()


@pytest.mark.asyncio
async def test_complete_match_with_bundled_agent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    rules = RuleSet.standard()
    starts = rules.start_squares(Player.ONE)
    placement = Placement(good=starts[:4], bad=starts[4:])
    monkeypatch.setattr(commands, "prompt_placement", lambda *_: placement)
    monkeypatch.setattr(commands, "prompt_action", lambda _console, view: view.legal_actions[0])
    record = tmp_path / "match.jsonl"
    stream = StringIO()
    console = _console(stream)

    await run_human_match(
        rules,
        record,
        5,
        [sys.executable, "-m", "pyghostboard.agent_runner", "--policy", "random"],
        RuntimeSettings(max_plies=1_000),
        console,
    )

    assert record.exists()
    persisted = read_record(record)
    assert len(persisted.header.main_commit_sha) == 40
    assert persisted.events[0].type == "match_started"
    replay_stream = StringIO()
    replay_match(
        record,
        Player.TWO,
        step=False,
        delay=0,
        console=_console(replay_stream),
    )
    assert "Replayed" in replay_stream.getvalue()

    prompts: list[str] = []

    def prompt_next(prompt: str, **_kwargs: object) -> str:
        prompts.append(prompt)
        return ""

    monkeypatch.setattr("pyghostboard.cli.commands.Prompt.ask", prompt_next)
    replay_match(record, Player.ONE, step=True, delay=0, console=_console(StringIO()))
    assert len(prompts) == len(persisted.events) - 2

    delays: list[float] = []
    monkeypatch.setattr("pyghostboard.cli.commands.time.sleep", delays.append)
    replay_match(record, Player.ONE, step=False, delay=0.01, console=_console(StringIO()))
    assert delays == [0.01] * (len(persisted.events) - 2)
