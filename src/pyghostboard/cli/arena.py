"""AI experiment orchestration built from application and adapter contracts."""

from __future__ import annotations

import sys
from pathlib import Path
from uuid import uuid4

from rich.console import Console

from pyghostboard.adapters.ai import SubprocessAgentController
from pyghostboard.adapters.arena import ArenaOutput, read_arena_results
from pyghostboard.adapters.config import RuntimeSettings
from pyghostboard.adapters.recording import MatchRecorder
from pyghostboard.application.arena import (
    ArenaAgentSpec,
    ArenaAnalysis,
    ArenaConfig,
    ArenaManifest,
    ArenaMatchPlan,
    ArenaMatchResult,
    analyze_results,
    build_match_plans,
)
from pyghostboard.application.runner import (
    MatchObserver,
    MatchResult,
    MatchRunner,
    MatchSpec,
    PlayerController,
    PrivateEventSink,
)
from pyghostboard.application.service import InMemoryMatchStore, MatchAborted, MatchService
from pyghostboard.cli.display import MatchDisplay, supports_live
from pyghostboard.domain.models import Player, RuleSet


async def run_arena(config: ArenaConfig, root: Path) -> ArenaManifest:
    """Run every planned game and durably append each completed attempt."""
    output = ArenaOutput.create(root, config)
    agents = {agent.id: agent for agent in config.agents}
    try:
        for plan in build_match_plans(config):
            recorder = MatchRecorder(output.record_path(plan.match_index))
            try:
                result = await _run_plan(config, plan, agents, private_events=recorder)
                destination = recorder.finalize()
                assert destination is not None
                winner_agent = (
                    plan.player_one_agent
                    if result.outcome.winner is Player.ONE
                    else plan.player_two_agent
                )
                persisted = ArenaMatchResult(
                    **plan.model_dump(),
                    status="completed",
                    winner_agent=winner_agent,
                    winner_player=result.outcome.winner,
                    reason=result.outcome.reason,
                    plies=result.plies,
                    record=f"matches/{destination.name}",
                )
            except MatchAborted as error:
                recorder.discard()
                persisted = ArenaMatchResult(
                    **plan.model_dump(),
                    status="failed",
                    error_code=error.reason.value,
                    error_detail=str(error),
                )
            output.append(persisted)
    except BaseException:
        output.finish("interrupted")
        raise
    output.finish("completed")
    return output.manifest


async def watch_match(config: ArenaConfig, console: Console) -> None:
    """Run one planned game while displaying only the configured agent's view."""
    plan = build_match_plans(config)[0]
    agents = {agent.id: agent for agent in config.agents}
    observer_player = Player.ONE if plan.player_one_agent == config.watch_agent else Player.TWO
    display = MatchDisplay(console, supports_live(console))
    display.start()
    try:
        await _run_plan(
            config,
            plan,
            agents,
            observer=display,
            observer_player=observer_player,
        )
    finally:
        display.close()


async def check_external_agent(command: list[str], settings: RuntimeSettings) -> None:
    """Connect one external AI to a full lifecycle against the bundled baseline."""
    rules = RuleSet.standard()
    controllers: dict[Player, PlayerController] = {
        Player.ONE: SubprocessAgentController(
            command,
            timeout=settings.agent_timeout,
            max_message_bytes=settings.agent_max_message_bytes,
            max_stderr_bytes=settings.agent_max_stderr_bytes,
        ),
        Player.TWO: SubprocessAgentController(
            [sys.executable, "-m", "pyghostboard.agent_runner", "--policy", "random"],
            timeout=settings.agent_timeout,
            max_message_bytes=settings.agent_max_message_bytes,
            max_stderr_bytes=settings.agent_max_stderr_bytes,
        ),
    }
    await MatchRunner(MatchService(InMemoryMatchStore())).run(
        MatchSpec(
            match_id=uuid4(),
            rules=rules,
            player_one_seed=0,
            player_two_seed=1,
            max_plies=settings.max_plies,
        ),
        controllers,
    )


def analyze_directory(root: Path) -> ArenaAnalysis:
    manifest, results = read_arena_results(root)
    return analyze_results(manifest.agent_ids, results)


async def _run_plan(
    config: ArenaConfig,
    plan: ArenaMatchPlan,
    agents: dict[str, ArenaAgentSpec],
    *,
    observer: MatchObserver | None = None,
    observer_player: Player = Player.ONE,
    private_events: PrivateEventSink | None = None,
) -> MatchResult:
    limits = config.limits
    controllers: dict[Player, PlayerController] = {
        Player.ONE: _controller(agents[plan.player_one_agent], config),
        Player.TWO: _controller(agents[plan.player_two_agent], config),
    }
    return await MatchRunner(MatchService(InMemoryMatchStore())).run(
        MatchSpec(
            match_id=plan.match_id,
            rules=config.rules,
            player_one_seed=plan.player_one_seed,
            player_two_seed=plan.player_two_seed,
            max_plies=limits.max_plies,
            observer_player=observer_player,
        ),
        controllers,
        observer=observer,
        private_events=private_events,
    )


def _controller(agent: ArenaAgentSpec, config: ArenaConfig) -> SubprocessAgentController:
    command = list(agent.command) if agent.command is not None else _policy_command(agent, config)
    limits = config.limits
    return SubprocessAgentController(
        command,
        timeout=limits.agent_timeout,
        max_message_bytes=limits.agent_max_message_bytes,
        max_stderr_bytes=limits.agent_max_stderr_bytes,
    )


def _policy_command(agent: ArenaAgentSpec, config: ArenaConfig) -> list[str]:
    assert agent.policy is not None
    search = config.search
    return [
        sys.executable,
        "-m",
        "pyghostboard.agent_runner",
        "--policy",
        agent.policy,
        "--iterations",
        str(search.iterations),
        "--exploration-weight",
        str(search.exploration_weight),
        "--rollout-plies",
        str(search.rollout_plies),
        "--setup-candidate-limit",
        str(search.setup_candidate_limit),
    ]


__all__ = ["analyze_directory", "check_external_agent", "run_arena", "watch_match"]
