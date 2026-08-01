"""End-to-end arena, watch, analysis, and external-agent command tests."""

import json
import stat
import sys
from io import StringIO
from pathlib import Path

import pytest
from rich.console import Console
from typer.testing import CliRunner

from pyghostboard.adapters.arena import load_arena_config, read_arena_results
from pyghostboard.application.arena import (
    ArenaAgentSpec,
    ArenaConfig,
    ArenaExecutionLimits,
    ArenaSearchSettings,
)
from pyghostboard.cli import create_app
from pyghostboard.cli.arena import run_arena
from pyghostboard.domain import RuleSet

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
runner = CliRunner()


def _console(stream: StringIO) -> Console:
    return Console(file=stream, color_system=None, force_terminal=False, width=100)


def _write_fast_config(path: Path) -> None:
    source = (REPOSITORY_ROOT / "examples/arena.toml").read_text(encoding="utf-8")
    source = source.replace("rounds = 2", "rounds = 1")
    source = source.replace('policy = "mcts"', 'policy = "random"')
    source = source.replace("iterations = 64", "iterations = 2")
    source = source.replace("rollout_plies = 48", "rollout_plies = 4")
    path.write_text(source, encoding="utf-8")


def test_arena_watch_analyze_and_agent_check_commands(tmp_path: Path) -> None:
    config = tmp_path / "arena.toml"
    _write_fast_config(config)
    results = tmp_path / "results"
    arena_stream = StringIO()

    arena_result = runner.invoke(
        create_app("en", console=_console(arena_stream)),
        ["arena", str(config), "--output", str(results)],
    )

    assert arena_result.exit_code == 0
    assert "2 completed, 0 failed" in arena_stream.getvalue()
    manifest, matches = read_arena_results(results)
    assert manifest.status == "completed"
    assert len(matches) == 2
    assert tuple(match.player_one_agent for match in matches) == ("mcts", "random")
    assert tuple(match.player_two_agent for match in matches) == ("random", "mcts")
    assert len(tuple((results / "matches").glob("*.jsonl"))) == 2
    assert all(
        stat.S_IMODE(path.stat().st_mode) == 0o600 for path in (results / "matches").glob("*.jsonl")
    )

    english_json = StringIO()
    japanese_json = StringIO()
    for language, stream in (("en", english_json), ("ja", japanese_json)):
        analyzed = runner.invoke(
            create_app(language, console=_console(stream)),
            ["analyze", str(results), "--format", "json"],
        )
        assert analyzed.exit_code == 0
    assert english_json.getvalue() == japanese_json.getvalue()
    assert json.loads(english_json.getvalue())["completed_matches"] == 2

    watch_stream = StringIO()
    watched = runner.invoke(
        create_app("en", console=_console(watch_stream)),
        ["watch", str(config)],
    )
    assert watched.exit_code == 0
    assert "Board" in watch_stream.getvalue()

    checked_stream = StringIO()
    checked = runner.invoke(
        create_app("en", console=_console(checked_stream)),
        [
            "agent",
            "check",
            "--command",
            sys.executable,
            "--command",
            str(REPOSITORY_ROOT / "examples/external_agent.py"),
        ],
    )
    assert checked.exit_code == 0
    assert "full match successfully" in checked_stream.getvalue()


@pytest.mark.asyncio
async def test_arena_persists_each_agent_failure_and_completes_schedule(tmp_path: Path) -> None:
    config = ArenaConfig(
        rounds=1,
        root_seed=8,
        watch_agent="broken",
        agents=(
            ArenaAgentSpec(
                id="broken",
                command=(sys.executable, "-c", "raise SystemExit(7)"),
            ),
            ArenaAgentSpec(id="baseline", policy="random"),
        ),
        rules=RuleSet.standard(),
        search=ArenaSearchSettings(
            iterations=1,
            exploration_weight=1,
            rollout_plies=1,
            setup_candidate_limit=8,
        ),
        limits=ArenaExecutionLimits(
            agent_timeout=1,
            agent_max_message_bytes=4_096,
            agent_max_stderr_bytes=1_024,
            max_plies=100,
        ),
    )
    root = tmp_path / "failed-results"

    manifest = await run_arena(config, root)
    persisted, results = read_arena_results(root)

    assert manifest.status == persisted.status == "completed"
    assert manifest.completed_matches == 0
    assert manifest.failed_matches == 2
    assert tuple(result.error_code for result in results) == (
        "agent_failure",
        "agent_failure",
    )
    assert tuple((root / "matches").iterdir()) == ()


@pytest.mark.asyncio
async def test_unexpected_arena_interruption_is_recorded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_path = tmp_path / "arena.toml"
    _write_fast_config(config_path)

    async def interrupt(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("host interrupted")

    monkeypatch.setattr("pyghostboard.cli.arena._run_plan", interrupt)
    root = tmp_path / "interrupted"

    with pytest.raises(RuntimeError, match="host interrupted"):
        await run_arena(load_arena_config(config_path), root)

    manifest, results = read_arena_results(root)
    assert manifest.status == "interrupted"
    assert results == ()
