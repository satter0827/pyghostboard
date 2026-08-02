"""End-to-end arena filesystem, subprocess, and CLI tests."""

from __future__ import annotations

import asyncio
import json
import stat
import sys
from io import StringIO
from pathlib import Path

import pytest
from rich.console import Console
from typer.testing import CliRunner

from pyghostboard.adapters.arena import ArenaOutput, read_arena
from pyghostboard.adapters.recording import MatchRecorder
from pyghostboard.application.arena import (
    ArenaConfig,
    ArenaExecutionLimits,
    ArenaRunner,
    ExternalArenaAgent,
    RandomArenaAgent,
)
from pyghostboard.cli import create_app
from pyghostboard.cli.arena import run_new_arena
from pyghostboard.domain import RuleSet

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
runner = CliRunner()


def _console(stream: StringIO) -> Console:
    return Console(file=stream, color_system=None, force_terminal=False, width=100)


def _write_fast_config(path: Path) -> None:
    source = (REPOSITORY_ROOT / "examples/arena.toml").read_text(encoding="utf-8")
    source = source.replace("rounds = 2", "rounds = 1")
    source = source.replace("iterations = 64", "iterations = 2")
    source = source.replace("rollout_plies = 48", "rollout_plies = 4")
    path.write_text(source, encoding="utf-8")


def _random_config(rounds: int = 1) -> ArenaConfig:
    return ArenaConfig(
        rounds=rounds,
        root_seed=8,
        agents=(RandomArenaAgent(id="alpha"), RandomArenaAgent(id="beta")),
        rules=RuleSet.standard(),
        limits=ArenaExecutionLimits(
            agent_timeout=2,
            agent_max_message_bytes=4_096,
            agent_max_stderr_bytes=1_024,
            max_plies=1_000,
        ),
    )


def test_arena_run_analyze_watch_and_agent_check_commands(tmp_path: Path) -> None:
    config = tmp_path / "arena.toml"
    _write_fast_config(config)
    results = tmp_path / "results"
    arena_stream = StringIO()

    arena_result = runner.invoke(
        create_app("en", console=_console(arena_stream)),
        ["arena", "run", str(config), "--output", str(results)],
    )

    assert arena_result.exit_code == 0, arena_result.exception
    assert "2 completed, 0 failed" in arena_stream.getvalue()
    stored, manifest, matches = read_arena(results)
    assert manifest.status == "completed"
    assert len(matches) == 2
    assert stored.config.recording == "all"
    attempt_paths = tuple(sorted((results / "attempts").iterdir()))
    assert tuple(path.name for path in attempt_paths) == ("000001", "000002")
    assert all((path / "result.json").is_file() for path in attempt_paths)
    assert all((path / "match.jsonl").is_file() for path in attempt_paths)
    assert stat.S_IMODE(results.stat().st_mode) == 0o700
    assert all(stat.S_IMODE(path.stat().st_mode) == 0o700 for path in attempt_paths)
    assert all(
        stat.S_IMODE((path / "result.json").stat().st_mode) == 0o600 for path in attempt_paths
    )

    english_json = StringIO()
    japanese_json = StringIO()
    for language, stream in (("en", english_json), ("ja", japanese_json)):
        analyzed = runner.invoke(
            create_app(language, console=_console(stream)),
            ["arena", "analyze", str(results), "--format", "json"],
        )
        assert analyzed.exit_code == 0, analyzed.exception
    assert english_json.getvalue() == japanese_json.getvalue()
    document = json.loads(english_json.getvalue())
    assert document["completed_matches"] == 2
    assert "command" not in english_json.getvalue()
    assert "error_detail" not in english_json.getvalue()

    watch_stream = StringIO()
    watched = runner.invoke(
        create_app("en", console=_console(watch_stream)),
        [
            "arena",
            "watch",
            str(config),
            "--agent",
            "mcts",
            "--opponent",
            "random",
        ],
    )
    assert watched.exit_code == 0, watched.exception
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
    assert checked.exit_code == 0, checked.exception
    assert "full match successfully" in checked_stream.getvalue()


@pytest.mark.asyncio
async def test_arena_persists_failures_without_private_records(tmp_path: Path) -> None:
    config = ArenaConfig(
        rounds=1,
        root_seed=8,
        recording="none",
        agents=(
            ExternalArenaAgent(
                id="broken",
                command=(sys.executable, "-c", "raise SystemExit(7)"),
                revision="test-fixture",
            ),
            RandomArenaAgent(id="baseline"),
        ),
        rules=RuleSet.standard(),
        limits=ArenaExecutionLimits(
            agent_timeout=1,
            agent_max_message_bytes=4_096,
            agent_max_stderr_bytes=1_024,
            max_plies=100,
        ),
    )
    root = tmp_path / "failed-results"

    report = await run_new_arena(config, root)
    _, manifest, results = read_arena(root)

    assert report.status == manifest.status == "completed"
    assert report.completed_matches == 0
    assert report.failed_matches == 2
    assert tuple(result.error_code for result in results) == (
        "agent_failure",
        "agent_failure",
    )
    assert not tuple(root.glob("attempts/*/match.jsonl"))
    assert "raise SystemExit" not in report.model_dump_json()


def test_interrupted_arena_resumes_only_missing_attempts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _random_config()
    root = tmp_path / "interrupted"
    original = ArenaRunner._run_plan
    calls = 0

    async def interrupt_once(*args: object, **kwargs: object) -> object:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("host interrupted")
        return await original(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(ArenaRunner, "_run_plan", interrupt_once)
    with pytest.raises(RuntimeError, match="host interrupted"):
        asyncio.run(run_new_arena(config, root))

    _, interrupted, before = read_arena(root)
    assert interrupted.status == "interrupted"
    assert tuple(result.match_index for result in before) == (1,)

    monkeypatch.setattr(ArenaRunner, "_run_plan", original)
    stream = StringIO()
    resumed = runner.invoke(
        create_app("en", console=_console(stream)),
        ["arena", "resume", str(root)],
    )
    assert resumed.exit_code == 0, resumed.exception
    _, completed, after = read_arena(root)
    assert completed.status == "completed"
    assert tuple(result.match_index for result in after) == (1, 2)
    assert (root / "attempts" / "000001").is_dir()


def test_arena_lock_and_completed_resume_are_rejected(tmp_path: Path) -> None:
    config = _random_config()
    root = tmp_path / "locked"
    with (
        ArenaOutput.create(root, config, MatchRecorder),
        pytest.raises(ValueError, match="already running"),
    ):
        ArenaOutput.resume(root, MatchRecorder)

    with ArenaOutput.resume(root, MatchRecorder) as output:
        output.update_status("interrupted")

    completed_root = tmp_path / "completed"
    asyncio.run(run_new_arena(config, completed_root))
    with pytest.raises(ValueError, match="completed arena cannot be resumed"):
        ArenaOutput.resume(completed_root, MatchRecorder)


def test_resume_rebuilds_a_stale_manifest_from_attempts(tmp_path: Path) -> None:
    config = _random_config()
    root = tmp_path / "stale-manifest"
    original = ArenaRunner._run_plan
    calls = 0

    async def interrupt_once(*args: object, **kwargs: object) -> object:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("host interrupted")
        return await original(*args, **kwargs)  # type: ignore[arg-type]

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(ArenaRunner, "_run_plan", interrupt_once)
        with pytest.raises(RuntimeError, match="host interrupted"):
            asyncio.run(run_new_arena(config, root))

    manifest_path = root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["completed_matches"] = 0
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with ArenaOutput.resume(root, MatchRecorder) as output:
        assert output.manifest.completed_matches == 1
        assert tuple(result.match_index for result in output.results()) == (1,)
