"""Deterministic arena planning, storage, and analysis tests."""

import stat
from io import StringIO
from pathlib import Path

import pytest
from rich.console import Console

from pyghostboard.adapters.arena import ArenaOutput, load_arena_config, read_arena_results
from pyghostboard.application.arena import (
    ArenaAgentSpec,
    ArenaConfig,
    ArenaExecutionLimits,
    ArenaManifest,
    ArenaMatchResult,
    ArenaSearchSettings,
    analyze_results,
    build_match_plans,
    derive_agent_seed,
)
from pyghostboard.cli.commands import _render_analysis
from pyghostboard.domain import OutcomeReason, Player, RuleSet

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def _config(rounds: int = 2) -> ArenaConfig:
    return ArenaConfig(
        rounds=rounds,
        root_seed=19,
        watch_agent="alpha",
        agents=(
            ArenaAgentSpec(id="alpha", policy="random"),
            ArenaAgentSpec(id="beta", policy="mcts"),
        ),
        rules=RuleSet.standard(),
        search=ArenaSearchSettings(
            iterations=2,
            exploration_weight=1.0,
            rollout_plies=4,
            setup_candidate_limit=16,
        ),
        limits=ArenaExecutionLimits(
            agent_timeout=2,
            agent_max_message_bytes=4_096,
            agent_max_stderr_bytes=1_024,
            max_plies=1_000,
        ),
    )


def _completed(plan_index: int = 1) -> ArenaMatchResult:
    plan = build_match_plans(_config())[plan_index - 1]
    return ArenaMatchResult(
        **plan.model_dump(),
        status="completed",
        winner_agent=plan.player_one_agent,
        winner_player=Player.ONE,
        reason=OutcomeReason.ESCAPE,
        plies=21,
        record=f"matches/{plan.match_index:06d}.jsonl",
    )


def test_arena_plans_swap_sides_and_derive_stable_agent_seeds() -> None:
    config = _config()
    plans = build_match_plans(config)

    assert len(plans) == 4
    assert (plans[0].player_one_agent, plans[0].player_two_agent) == ("alpha", "beta")
    assert (plans[1].player_one_agent, plans[1].player_two_agent) == ("beta", "alpha")
    assert plans[0].player_one_seed == plans[1].player_two_seed
    assert plans[0].player_two_seed == plans[1].player_one_seed
    assert plans == build_match_plans(config)
    assert derive_agent_seed(19, 1, "alpha") != derive_agent_seed(19, 2, "alpha")


def test_arena_config_requires_two_unique_unambiguous_agents() -> None:
    with pytest.raises(ValueError, match="exactly one"):
        ArenaAgentSpec(id="broken")
    with pytest.raises(ValueError, match="exactly one"):
        ArenaAgentSpec(id="broken", policy="random", command=("agent",))

    document = load_arena_config(REPOSITORY_ROOT / "examples/arena.toml")
    assert document.watch_agent == "mcts"
    assert len(document.agents) == 2


def test_arena_persisted_models_reject_inconsistent_metadata() -> None:
    with pytest.raises(ValueError, match="two matches per round"):
        ArenaManifest(
            status="running",
            root_seed=1,
            rounds=1,
            agent_ids=("alpha", "beta"),
            planned_matches=4,
            completed_matches=0,
            failed_matches=0,
        )

    completed = _completed()
    with pytest.raises(ValueError, match="winning player"):
        ArenaMatchResult.model_validate(
            {**completed.model_dump(), "winner_agent": completed.player_two_agent}
        )


def test_analysis_reports_agent_side_reason_and_ply_descriptives() -> None:
    first = _completed(1)
    second_plan = build_match_plans(_config())[1]
    second = ArenaMatchResult(
        **second_plan.model_dump(),
        status="completed",
        winner_agent=second_plan.player_two_agent,
        winner_player=Player.TWO,
        reason=OutcomeReason.CAPTURE_GOOD,
        plies=31,
        record="matches/000002.jsonl",
    )
    failed_plan = build_match_plans(_config())[2]
    failed = ArenaMatchResult(
        **failed_plan.model_dump(),
        status="failed",
        error_code="agent_failure",
        error_detail="agent exited",
    )

    analysis = analyze_results(("alpha", "beta"), (first, second, failed))

    assert analysis.attempted_matches == 3
    assert analysis.completed_matches == 2
    assert analysis.failed_matches == 1
    assert analysis.player_one_win_rate == 0.5
    assert analysis.player_two_win_rate == 0.5
    assert analysis.victory_reasons[OutcomeReason.ESCAPE] == 1
    assert analysis.victory_reasons[OutcomeReason.CAPTURE_GOOD] == 1
    assert analysis.average_plies == 26
    alpha = analysis.agents[0]
    assert alpha.games == 2 and alpha.wins == 2
    assert alpha.player_one_win_rate == 1 and alpha.player_two_win_rate == 1

    stream = StringIO()
    _render_analysis(Console(file=stream, color_system=None), analysis)
    rendered = stream.getvalue()
    assert "Arena summary" in rendered
    assert "AI results" in rendered
    assert "Victory reasons" in rendered
    assert "alpha" in rendered and "capture_good" in rendered


def test_arena_output_is_private_incremental_and_never_overwritten(tmp_path: Path) -> None:
    root = tmp_path / "results"
    output = ArenaOutput.create(root, _config())

    assert stat.S_IMODE(root.stat().st_mode) == 0o700
    assert stat.S_IMODE(output.matches.stat().st_mode) == 0o700
    assert stat.S_IMODE(output.manifest_path.stat().st_mode) == 0o600
    assert stat.S_IMODE(output.results.stat().st_mode) == 0o600

    output.append(_completed())
    running, results = read_arena_results(root)
    assert running.status == "running"
    assert running.completed_matches == 1
    assert len(results) == 1

    output.finish("interrupted")
    interrupted, _ = read_arena_results(root)
    assert interrupted.status == "interrupted"

    with pytest.raises(FileExistsError):
        ArenaOutput.create(root, _config())


def test_arena_output_rejects_incomplete_completion_and_out_of_order_results(
    tmp_path: Path,
) -> None:
    output = ArenaOutput.create(tmp_path / "results", _config(rounds=1))

    with pytest.raises(ValueError, match="expected arena match index 1"):
        output.append(_completed(2))
    inconsistent = ArenaMatchResult.model_validate(
        {
            **_completed(1).model_dump(),
            "player_two_agent": "gamma",
            "winner_agent": "alpha",
        }
    )
    with pytest.raises(ValueError, match="do not match the manifest"):
        output.append(inconsistent)
    with pytest.raises(ValueError, match="every planned result"):
        output.finish()

    output.append(_completed(1))
    output.append(_completed(2))
    with pytest.raises(ValueError, match="already contains every planned result"):
        output.append(_completed(3))
    output.finish()
    with pytest.raises(ValueError, match="only be appended while running"):
        output.append(_completed(1))
