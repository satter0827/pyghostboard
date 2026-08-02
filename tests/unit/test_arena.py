"""Pure arena configuration, planning, and reporting tests."""

from io import StringIO
from typing import Literal

import pytest
from pydantic import TypeAdapter, ValidationError
from rich.console import Console

from pyghostboard.application.arena import (
    ArenaAgent,
    ArenaConfig,
    ArenaManifest,
    ArenaMatchResult,
    ExternalArenaAgent,
    MctsArenaAgent,
    RandomArenaAgent,
    _build_match_plans,
    _config_digest,
    build_arena_report,
)
from pyghostboard.cli.commands import _render_analysis
from pyghostboard.domain import OutcomeReason, Player, RuleSet


def _config(*, agents: tuple[ArenaAgent, ...] | None = None, rounds: int = 2) -> ArenaConfig:
    return ArenaConfig(
        rounds=rounds,
        root_seed=19,
        agents=agents
        or (
            RandomArenaAgent(id="charlie"),
            MctsArenaAgent(
                id="alpha",
                iterations=2,
                exploration_weight=1,
                rollout_plies=4,
                setup_candidate_limit=16,
            ),
            RandomArenaAgent(id="beta"),
        ),
        rules=RuleSet.standard(),
    )


def _manifest(
    config: ArenaConfig,
    status: Literal["running", "completed", "interrupted"] = "running",
) -> ArenaManifest:
    plans = _build_match_plans(config)
    return ArenaManifest(
        status=status,
        config_digest="a" * 64,
        package_version="0.1.0.dev0",
        source_commit="b" * 40,
        planned_matches=len(plans),
        completed_matches=len(plans) if status == "completed" else 0,
        failed_matches=0,
    )


def _completed(config: ArenaConfig, plan_index: int, winner: Player) -> ArenaMatchResult:
    plan = _build_match_plans(config)[plan_index - 1]
    winner_agent = plan.player_one_agent if winner is Player.ONE else plan.player_two_agent
    return ArenaMatchResult(
        **plan.model_dump(),
        status="completed",
        winner_agent=winner_agent,
        winner_player=winner,
        reason=OutcomeReason.ESCAPE,
        plies=21,
        record="match.jsonl",
    )


def test_arena_config_uses_discriminated_agents_and_rejects_ambiguous_inputs() -> None:
    adapter: TypeAdapter[ArenaAgent] = TypeAdapter(ArenaAgent)
    assert isinstance(
        adapter.validate_python({"kind": "random", "id": "baseline"}), RandomArenaAgent
    )
    assert isinstance(
        adapter.validate_python(
            {
                "kind": "external",
                "id": "candidate",
                "command": ["python", "agent.py"],
                "revision": "abc123",
            }
        ),
        ExternalArenaAgent,
    )
    with pytest.raises(ValidationError):
        adapter.validate_python({"kind": "external", "id": "candidate", "command": ["python"]})
    with pytest.raises(ValidationError):
        adapter.validate_python(
            {"kind": "external", "id": "candidate", "command": [], "revision": "abc123"}
        )
    with pytest.raises(ValidationError):
        adapter.validate_python(
            {"kind": "external", "id": "candidate", "command": ["python"], "revision": ""}
        )
    with pytest.raises(ValueError, match="empty arguments"):
        ExternalArenaAgent(id="candidate", command=("python", ""), revision="abc123")
    with pytest.raises(ValueError, match="unique"):
        _config(agents=(RandomArenaAgent(id="same"), RandomArenaAgent(id="same")))
    with pytest.raises(ValidationError):
        ArenaConfig.model_validate({**_config().model_dump(), "watch_agent": "alpha"})


def test_arena_plans_every_pair_in_stable_order_and_swaps_sides() -> None:
    config = _config()
    plans = _build_match_plans(config)

    assert len(plans) == 12
    assert tuple((plan.player_one_agent, plan.player_two_agent) for plan in plans[:4]) == (
        ("alpha", "beta"),
        ("beta", "alpha"),
        ("alpha", "beta"),
        ("beta", "alpha"),
    )
    assert plans[0].player_one_seed == plans[1].player_two_seed
    assert plans[0].player_two_seed == plans[1].player_one_seed

    reordered = _config(agents=tuple(reversed(config.agents)))
    assert _build_match_plans(reordered) == plans
    assert _config_digest(reordered) == _config_digest(config)
    assert plans[0].player_one_seed != plans[2].player_one_seed
    assert plans[0].player_one_seed != plans[4].player_one_seed


def test_arena_result_rejects_status_and_plan_inconsistency() -> None:
    config = _config(rounds=1)
    completed = _completed(config, 1, Player.ONE)
    with pytest.raises(ValueError, match="winning player"):
        ArenaMatchResult.model_validate(
            {**completed.model_dump(), "winner_agent": completed.player_two_agent}
        )
    with pytest.raises(ValueError, match="failure fields"):
        ArenaMatchResult.model_validate(
            {**completed.model_dump(), "status": "failed", "error_code": "failure"}
        )


def test_report_describes_agents_pairs_failures_and_incomplete_rounds() -> None:
    config = _config(
        agents=(RandomArenaAgent(id="alpha"), RandomArenaAgent(id="beta")),
        rounds=2,
    )
    first = _completed(config, 1, Player.ONE)
    second = _completed(config, 2, Player.TWO)
    third_plan = _build_match_plans(config)[2]
    failed = ArenaMatchResult(
        **third_plan.model_dump(),
        status="failed",
        error_code="agent_failure",
        error_detail="private command detail",
    )
    manifest = ArenaManifest(
        **{
            **_manifest(config).model_dump(),
            "completed_matches": 2,
            "failed_matches": 1,
        }
    )

    report = build_arena_report(config, manifest, (first, second, failed))

    assert report.completed_matches == 2
    assert report.failed_matches == 1
    assert report.error_codes == {"agent_failure": 1}
    assert report.incomplete_rounds == 1
    assert report.pairs[0].first_sweeps == 1
    assert report.pairs[0].split_rounds == 0
    assert report.pairs[0].incomplete_rounds == 1
    assert "private command detail" not in report.model_dump_json()

    stream = StringIO()
    _render_analysis(Console(file=stream, color_system=None), report)
    rendered = stream.getvalue()
    assert "Arena summary" in rendered
    assert "Pair results" in rendered
    assert "Failure reasons" in rendered
    assert "agent_failure" in rendered
