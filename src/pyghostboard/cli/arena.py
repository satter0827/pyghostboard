"""CLI assembly for arena application use cases."""

from __future__ import annotations

import sys
from pathlib import Path
from uuid import uuid4

from rich.console import Console

from pyghostboard.adapters.ai import SubprocessAgentController
from pyghostboard.adapters.arena import ArenaOutput, read_arena
from pyghostboard.adapters.config import RuntimeSettings
from pyghostboard.adapters.recording import MatchRecorder
from pyghostboard.application.arena import (
    ArenaAgent,
    ArenaConfig,
    ArenaReport,
    ArenaRunner,
    ExternalArenaAgent,
    MctsArenaAgent,
    build_arena_report,
)
from pyghostboard.application.runner import MatchRunner, MatchSpec, PlayerController
from pyghostboard.application.service import InMemoryMatchStore, MatchService
from pyghostboard.cli.display import MatchDisplay, supports_live
from pyghostboard.domain.models import Player, RuleSet


class SubprocessArenaControllerFactory:
    """Create isolated controllers from validated arena agent settings."""

    def __init__(self, config: ArenaConfig) -> None:
        self._config = config

    def create(self, agent: ArenaAgent) -> PlayerController:
        limits = self._config.limits
        return SubprocessAgentController(
            self._command(agent),
            timeout=limits.agent_timeout,
            max_message_bytes=limits.agent_max_message_bytes,
            max_stderr_bytes=limits.agent_max_stderr_bytes,
        )

    @staticmethod
    def _command(agent: ArenaAgent) -> list[str]:
        if isinstance(agent, ExternalArenaAgent):
            return list(agent.command)
        command = [
            sys.executable,
            "-m",
            "pyghostboard.agent_runner",
            "--policy",
            agent.kind,
        ]
        if isinstance(agent, MctsArenaAgent):
            command.extend(
                (
                    "--iterations",
                    str(agent.iterations),
                    "--exploration-weight",
                    str(agent.exploration_weight),
                    "--rollout-plies",
                    str(agent.rollout_plies),
                    "--setup-candidate-limit",
                    str(agent.setup_candidate_limit),
                )
            )
        return command


async def run_new_arena(config: ArenaConfig, root: Path) -> ArenaReport:
    """Create and complete one new private arena."""
    with ArenaOutput.create(root, config, MatchRecorder) as output:
        return await ArenaRunner(SubprocessArenaControllerFactory(config), output).run(config)


async def resume_arena(root: Path) -> ArenaReport:
    """Resume only the missing attempts in one interrupted arena."""
    with ArenaOutput.resume(root, MatchRecorder) as output:
        config = output.config
        return await ArenaRunner(SubprocessArenaControllerFactory(config), output).run(config)


async def watch_match(
    config: ArenaConfig,
    console: Console,
    *,
    agent_id: str,
    opponent_id: str,
    round_index: int,
    side: Player,
) -> None:
    """Run one configured pairing while displaying the selected agent view."""
    display = MatchDisplay(console, supports_live(console))
    display.start()
    try:
        await ArenaRunner(SubprocessArenaControllerFactory(config)).watch(
            config,
            agent_id=agent_id,
            opponent_id=opponent_id,
            round_index=round_index,
            side=side,
            observer=display,
        )
    finally:
        display.close()


def analyze_directory(root: Path) -> ArenaReport:
    """Validate private attempts and return a sanitized report."""
    stored, manifest, results = read_arena(root)
    return build_arena_report(stored.config, manifest, results)


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


__all__ = [
    "analyze_directory",
    "check_external_agent",
    "resume_arena",
    "run_new_arena",
    "watch_match",
]
