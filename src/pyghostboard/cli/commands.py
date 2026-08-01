"""Typer command construction and orchestration adapters."""

from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path
from typing import Annotated
from uuid import uuid4

import structlog
import typer
from rich.console import Console
from rich.prompt import Prompt
from typer import _click
from typer.core import TyperCommand, TyperGroup, TyperOption

from pyghostboard._platform import require_posix
from pyghostboard.adapters.ai import SubprocessAgentController
from pyghostboard.adapters.config import RuntimeSettings
from pyghostboard.adapters.recording import MatchRecorder, read_record
from pyghostboard.application.runner import MatchResult, MatchRunner, MatchSpec, PlayerContext
from pyghostboard.application.service import (
    InMemoryMatchStore,
    MatchAborted,
    MatchService,
    project_player_events,
)
from pyghostboard.cli.config import resolve_agent_command, resolve_rules
from pyghostboard.cli.display import MatchDisplay, player_name, reason_name, supports_live
from pyghostboard.cli.i18n import SUPPORTED_LANGUAGES, activate_language, tr
from pyghostboard.cli.input import prompt_action, prompt_placement
from pyghostboard.domain.match import Match
from pyghostboard.domain.models import (
    Action,
    ActionPlayed,
    MatchStarted,
    Placement,
    Player,
    PlayerView,
    RuleSet,
)


class LocalizedCommand(TyperCommand):
    """Typer command with localized framework-owned help text."""

    def get_help_option(self, ctx: _click.Context) -> TyperOption | None:
        option = super().get_help_option(ctx)
        if option is not None:
            option.help = tr("Show this message and exit.")
        return option

    def get_usage(self, ctx: _click.Context) -> str:
        return super().get_usage(ctx).replace("Usage:", tr("Usage:"), 1)

    def get_help(self, ctx: _click.Context) -> str:
        return super().get_help(ctx).replace("Usage:", tr("Usage:"), 1)


class LocalizedGroup(TyperGroup):
    """Typer group with localized framework-owned help text."""

    def get_help_option(self, ctx: _click.Context) -> TyperOption | None:
        option = super().get_help_option(ctx)
        if option is not None:
            option.help = tr("Show this message and exit.")
        return option

    def get_usage(self, ctx: _click.Context) -> str:
        return super().get_usage(ctx).replace("Usage:", tr("Usage:"), 1)

    def get_help(self, ctx: _click.Context) -> str:
        return super().get_help(ctx).replace("Usage:", tr("Usage:"), 1)


def create_app(language: str, *, console: Console | None = None) -> typer.Typer:
    """Build a localized command tree after language resolution."""
    activate_language(language)
    output = console or Console()
    app = typer.Typer(
        help=tr("Play and inspect pyghostboard matches."),
        no_args_is_help=True,
        add_completion=False,
        cls=LocalizedGroup,
    )
    rules_app = typer.Typer(
        help=tr("Validate game rule files."),
        no_args_is_help=True,
        add_completion=False,
        cls=LocalizedGroup,
    )
    app.add_typer(rules_app, name="rules")

    @app.callback()
    def root(
        language_option: Annotated[
            str,
            typer.Option(
                "--language",
                help=tr("Display language: en or ja."),
                metavar="LANGUAGE",
            ),
        ] = language,
    ) -> None:
        if language_option not in SUPPORTED_LANGUAGES:
            raise typer.BadParameter(tr("language must be 'en' or 'ja'"), param_hint="--language")

    @app.command(help=tr("Play as a human against an isolated AI process."), cls=LocalizedCommand)
    def play(
        config: Annotated[
            Path | None,
            typer.Option(help=tr("TOML rule configuration.")),
        ] = None,
        record: Annotated[
            Path | None,
            typer.Option(help=tr("Save the private match record.")),
        ] = None,
        seed: Annotated[
            int,
            typer.Option(help=tr("Seed for reproducible AI decisions.")),
        ] = 0,
        agent: Annotated[
            str | None,
            typer.Option(help=tr("Built-in AI policy: mcts or random.")),
        ] = None,
        command: Annotated[
            list[str] | None,
            typer.Option(
                "--command",
                help=tr("External AI argument; repeat once for each argument."),
            ),
        ] = None,
        overwrite_record: Annotated[
            bool,
            typer.Option(
                "--overwrite-record",
                help=tr("Replace an existing record destination."),
            ),
        ] = False,
    ) -> None:
        """Play as a human against an isolated AI process."""
        try:
            require_posix("command-line interface")
            settings = RuntimeSettings()
            _configure_logging(settings.log_level)
            rules = resolve_rules(config)
            agent_command = resolve_agent_command(agent, command)
            asyncio.run(
                run_human_match(
                    rules,
                    record,
                    seed,
                    agent_command,
                    settings,
                    output,
                    overwrite_record,
                )
            )
        except MatchAborted as error:
            structlog.get_logger("pyghostboard.cli").warning(
                "match_aborted", reason=error.reason.value, detail=str(error)
            )
            output.print(
                tr("Match aborted ({reason}): {detail}").format(
                    reason=error.reason.value,
                    detail=error,
                )
            )
            raise typer.Exit(code=1) from error
        except (OSError, ValueError) as error:
            output.print(tr("Invalid configuration: {detail}").format(detail=error))
            raise typer.Exit(code=2) from error

    @app.command(
        help=tr("Replay a private match record from one player viewpoint."), cls=LocalizedCommand
    )
    def replay(
        record: Annotated[Path, typer.Argument(exists=True, dir_okay=False)],
        view: Annotated[
            Player,
            typer.Option(help=tr("Player viewpoint used for replay.")),
        ] = Player.ONE,
        step: Annotated[
            bool,
            typer.Option("--step", help=tr("Wait for input after each move.")),
        ] = False,
        delay: Annotated[
            float,
            typer.Option(min=0, help=tr("Seconds between automatically replayed moves.")),
        ] = 0,
    ) -> None:
        """Replay a private match record from one player viewpoint."""
        try:
            require_posix("command-line interface")
            replay_match(record, view, step=step, delay=delay, console=output)
        except (OSError, ValueError) as error:
            raise typer.BadParameter(str(error)) from error

    @rules_app.command("validate", help=tr("Validate a TOML RuleSet."), cls=LocalizedCommand)
    def validate_rules(
        path: Annotated[Path, typer.Argument(exists=True, dir_okay=False)],
    ) -> None:
        """Validate a TOML RuleSet."""
        try:
            require_posix("command-line interface")
            rules = resolve_rules(path)
        except (OSError, ValueError) as error:
            raise typer.BadParameter(str(error)) from error
        output.print(
            tr("Valid rules: {width}x{height}, {count} ghosts per player").format(
                width=rules.width,
                height=rules.height,
                count=rules.good_count + rules.bad_count,
            )
        )

    return app


async def run_human_match(
    rules: RuleSet,
    record: Path | None,
    seed: int,
    command: list[str],
    settings: RuntimeSettings,
    console: Console,
    overwrite_record: bool = False,
) -> None:
    """Run one human-versus-AI match and atomically promote a complete record."""
    match_id = uuid4()
    recorder = MatchRecorder(record, overwrite=overwrite_record)
    service = MatchService(
        InMemoryMatchStore(), logger=structlog.get_logger("pyghostboard.application")
    )
    display = MatchDisplay(console, supports_live(console))
    human = HumanController(console)
    agent = SubprocessAgentController(
        command,
        timeout=settings.agent_timeout,
        max_message_bytes=settings.agent_max_message_bytes,
        max_stderr_bytes=settings.agent_max_stderr_bytes,
    )
    display.start()
    try:
        result = await MatchRunner(service).run(
            MatchSpec(
                match_id=match_id,
                rules=rules,
                player_one_seed=seed,
                player_two_seed=seed,
                max_plies=settings.max_plies,
            ),
            {Player.ONE: human, Player.TWO: agent},
            observer=display,
            private_events=recorder,
        )
        display.close()
        render_result(console, result)
        destination = recorder.finalize()
        if destination is not None:
            console.print(tr("Record saved to {path}").format(path=destination))
    except BaseException:
        recorder.discard()
        raise
    finally:
        display.close()


class HumanController:
    """Interactive controller using only the shared player contract."""

    def __init__(self, console: Console) -> None:
        self._console = console
        self._context: PlayerContext | None = None

    async def initialize(self, context: PlayerContext) -> None:
        self._context = context

    async def choose_placement(self) -> Placement:
        context = self._require_context()
        return prompt_placement(self._console, context.rules, context.player)

    async def choose_action(self, view: PlayerView) -> Action:
        return prompt_action(self._console, view)

    async def finish(self, view: PlayerView) -> None:
        del view

    async def close(self) -> None:
        self._context = None

    def _require_context(self) -> PlayerContext:
        if self._context is None:
            raise RuntimeError("human controller was not initialized")
        return self._context


def replay_match(
    path: Path,
    player: Player,
    *,
    step: bool,
    delay: float,
    console: Console,
) -> None:
    """Validate and present each recorded transition from one viewpoint."""
    match_record = read_record(path)
    events = match_record.events
    if not events or not isinstance(events[0], MatchStarted):
        raise ValueError("record must begin with match_started")
    actions = tuple(event for event in events[1:] if isinstance(event, ActionPlayed))
    match = Match.replay(events[0], ())
    display = MatchDisplay(console, supports_live(console))
    display.start()
    try:
        display.on_turn(match.view_for(player))
        for index, event in enumerate(actions, start=1):
            match = Match.replay(events[0], actions[:index])
            display.on_events(project_player_events(event))
            if match.outcome is None:
                display.on_turn(match.view_for(player))
            else:
                display.on_finished(match.view_for(player))
            if step and index < len(actions):
                Prompt.ask(tr("Press Enter for the next move"), default="", console=console)
            elif delay > 0 and index < len(actions):
                time.sleep(delay)
    finally:
        display.close()
    console.print(tr("Replayed {plies} ply").format(plies=match.revision))


def render_result(console: Console, result: MatchResult) -> None:
    console.print(
        tr("Winner: {player} · Reason: {reason}").format(
            player=player_name(result.outcome.winner.value),
            reason=reason_name(result.outcome.reason.value),
        )
    )


def _configure_logging(level: str) -> None:
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.add_log_level,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level.upper()),
        logger_factory=structlog.WriteLoggerFactory(file=sys.stderr),
    )


__all__ = ["HumanController", "create_app", "replay_match", "run_human_match"]
