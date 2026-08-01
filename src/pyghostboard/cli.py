"""Rich command-line interface for pyghostboard."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Annotated
from uuid import uuid4

import structlog
import typer
from rich.console import Console
from rich.prompt import Prompt
from rich.table import Table

from pyghostboard._platform import require_posix
from pyghostboard.adapters.ai import AgentFailure, SubprocessAgent
from pyghostboard.adapters.config import RuntimeSettings, load_rules
from pyghostboard.adapters.recording import MatchRecorder, read_record
from pyghostboard.application.service import (
    AbortReason,
    InMemoryMatchStore,
    MatchAborted,
    MatchService,
    project_player_events,
)
from pyghostboard.domain.match import Match
from pyghostboard.domain.models import (
    Action,
    MatchStarted,
    Placement,
    Player,
    PlayerEvent,
    PlayerView,
    RuleSet,
    Square,
)
from pyghostboard.protocol import (
    ActionRequest,
    ActionResponse,
    FinishedRequest,
    InitializeRequest,
    ReadyResponse,
    SetupRequest,
    SetupResponse,
)

app = typer.Typer(help="Play and inspect pyghostboard matches.", no_args_is_help=True)
rules_app = typer.Typer(help="Validate game rule files.", no_args_is_help=True)
app.add_typer(rules_app, name="rules")
console = Console()


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


@app.command()
def play(
    config: Annotated[Path | None, typer.Option(help="TOML rule configuration.")] = None,
    record: Annotated[Path | None, typer.Option(help="Save the private match record.")] = None,
    seed: Annotated[int, typer.Option(help="Seed for reproducible AI decisions.")] = 0,
    ai_command: Annotated[
        list[str] | None,
        typer.Option("--ai", help="AI executable and arguments; repeat for each argument."),
    ] = None,
    overwrite_record: Annotated[
        bool,
        typer.Option("--overwrite-record", help="Replace an existing record destination."),
    ] = False,
) -> None:
    """Play as player one against an isolated AI process."""
    try:
        require_posix("command-line interface")
        settings = RuntimeSettings()
        _configure_logging(settings.log_level)
        rules = RuleSet.standard() if config is None else load_rules(config)
        command = ai_command or [
            sys.executable,
            "-m",
            "pyghostboard.random_agent",
            "--seed",
            str(seed),
        ]
        asyncio.run(_play(rules, record, seed, command, settings, overwrite_record))
    except MatchAborted as error:
        structlog.get_logger("pyghostboard.cli").warning(
            "match_aborted", reason=error.reason.value, detail=str(error)
        )
        console.print(f"[bold red]Match aborted ({error.reason.value}):[/bold red] {error}")
        raise typer.Exit(code=1) from error
    except (OSError, ValueError) as error:
        console.print(f"[bold red]Invalid configuration:[/bold red] {error}")
        raise typer.Exit(code=2) from error


async def _play(
    rules: RuleSet,
    record: Path | None,
    seed: int,
    command: list[str],
    settings: RuntimeSettings,
    overwrite_record: bool = False,
) -> None:
    match_id = uuid4()
    recorder = MatchRecorder(record, overwrite=overwrite_record)
    store = InMemoryMatchStore()
    service = MatchService(store, logger=structlog.get_logger("pyghostboard.application"))
    try:
        human = _prompt_placement(rules, Player.ONE)
        async with SubprocessAgent(
            command,
            timeout=settings.agent_timeout,
            max_message_bytes=settings.agent_max_message_bytes,
            max_stderr_bytes=settings.agent_max_stderr_bytes,
        ) as agent:
            initialize = InitializeRequest(
                request_id=uuid4(), seed=seed, player=Player.TWO, rules=rules
            )
            if not isinstance(await agent.request(initialize), ReadyResponse):
                raise AgentFailure("agent did not acknowledge initialization")
            setup_response = await agent.request(SetupRequest(request_id=uuid4()))
            if not isinstance(setup_response, SetupResponse):
                raise AgentFailure("agent did not return a placement")
            match = await service.create(
                match_id,
                rules,
                {Player.ONE: human, Player.TWO: setup_response.placement},
                first_player=Player.ONE,
            )
            recorder.append(match.started_event())
            for _ in range(settings.max_plies):
                if match.outcome is not None:
                    break
                view = match.view_for(match.current_player)
                if not view.legal_actions:
                    raise MatchAborted(
                        AbortReason.NO_LEGAL_ACTIONS,
                        f"{match.current_player.value} has no legal action",
                    )
                _render_view(view)
                if match.current_player is Player.ONE:
                    action = _prompt_action(view)
                else:
                    response = await agent.request(ActionRequest(request_id=uuid4(), view=view))
                    if not isinstance(response, ActionResponse):
                        raise AgentFailure("agent did not return an action")
                    action = response.action
                transition = await service.play(match_id, match.current_player, action)
                recorder.append(*transition.events)
                for event in transition.events:
                    for visible in project_player_events(event):
                        _render_player_event(visible)
                match = transition.match
            else:
                raise MatchAborted(AbortReason.MAXIMUM_PLIES, "maximum ply count reached")
            _render_view(match.view_for(Player.ONE))
            assert match.outcome is not None
            winner = match.outcome.winner.value
            reason = match.outcome.reason.value
            console.print(f"[bold green]Winner: {winner} ({reason})[/bold green]")
            if not isinstance(
                await agent.request(
                    FinishedRequest(request_id=uuid4(), view=match.view_for(Player.TWO))
                ),
                ReadyResponse,
            ):
                raise AgentFailure("agent did not acknowledge match completion")
        destination = recorder.finalize()
        if destination is not None:
            console.print(f"Record saved to {destination}")
    except AgentFailure as error:
        recorder.discard()
        raise MatchAborted(AbortReason.AGENT_FAILURE, str(error)) from error
    except ValueError as error:
        recorder.discard()
        raise MatchAborted(AbortReason.ILLEGAL_ACTION, str(error)) from error
    except BaseException:
        recorder.discard()
        raise


@app.command()
def replay(record: Annotated[Path, typer.Argument(exists=True, dir_okay=False)]) -> None:
    """Validate and replay a private JSON Lines record."""
    try:
        require_posix("command-line interface")
        match_record = read_record(record)
    except (OSError, ValueError) as error:
        raise typer.BadParameter(str(error)) from error
    try:
        events = match_record.events
        if not events or not isinstance(events[0], MatchStarted):
            raise ValueError("record must begin with match_started")
        actions = tuple(event for event in events[1:] if event.type == "action_played")
        match = Match.replay(events[0], actions)
    except ValueError as error:
        raise typer.BadParameter(str(error)) from error
    for event in actions:
        for visible in project_player_events(event):
            _render_player_event(visible)
    _render_view(match.view_for(Player.ONE))
    console.print(f"Replayed {match.revision} ply")


@rules_app.command("validate")
def validate_rules(path: Annotated[Path, typer.Argument(exists=True, dir_okay=False)]) -> None:
    """Validate a TOML RuleSet."""
    try:
        require_posix("command-line interface")
        rules = load_rules(path)
    except (OSError, ValueError) as error:
        raise typer.BadParameter(str(error)) from error
    console.print(
        f"[green]Valid rules:[/green] {rules.width}x{rules.height}, "
        f"{rules.good_count + rules.bad_count} ghosts per player"
    )


def _prompt_placement(rules: RuleSet, player: Player) -> Placement:
    starts = rules.start_squares(player)
    default = ",".join(str(square) for square in starts[: rules.good_count])
    while True:
        answer = Prompt.ask(
            f"Choose {rules.good_count} good ghost squares separated by commas",
            default=default,
        )
        try:
            good = tuple(Square.parse(item.strip()) for item in answer.split(","))
            if len(good) != rules.good_count or not set(good) <= set(starts):
                raise ValueError
            bad = tuple(square for square in starts if square not in good)
            return Placement(good=good, bad=bad)
        except ValueError:
            console.print("[red]Choose distinct squares from the configured starting area.[/red]")


def _prompt_action(view: PlayerView) -> Action:
    table = Table(title="Legal actions")
    table.add_column("#", justify="right")
    table.add_column("Action")
    for index, action in enumerate(view.legal_actions, start=1):
        label = (
            f"{action.source} -> {action.destination}"
            if action.type == "move"
            else f"{action.source} exits"
        )
        table.add_row(str(index), label)
    console.print(table)
    choice = Prompt.ask(
        "Select an action",
        choices=[str(index) for index in range(1, len(view.legal_actions) + 1)],
    )
    return view.legal_actions[int(choice) - 1]


def _render_view(view: PlayerView) -> None:
    own = {piece.square: "G" if piece.kind.value == "good" else "B" for piece in view.own_pieces}
    opponents = set(view.opponent_squares)
    table = Table(title=f"Match {view.match_id} · ply {view.revision}", show_header=True)
    table.add_column("")
    for x in range(view.width):
        table.add_column(chr(ord("a") + x), justify="center")
    for y in reversed(range(view.height)):
        cells = []
        for x in range(view.width):
            square = Square(x=x, y=y)
            cells.append(own.get(square, "?" if square in opponents else "·"))
        table.add_row(str(y + 1), *cells)
    console.print(table)


def _render_player_event(event: PlayerEvent) -> None:
    if event.kind == "finished":
        assert event.outcome is not None
        console.print(
            f"[bold]Game finished:[/bold] {event.outcome.winner.value} wins "
            f"({event.outcome.reason.value})"
        )
        return
    if event.kind == "escape":
        console.print(f"{event.sequence}. {event.actor.value}: {event.source} exits")
        return
    assert event.destination is not None
    suffix = f" and captures {event.captured.kind.value}" if event.captured is not None else ""
    console.print(
        f"{event.sequence}. {event.actor.value}: {event.source} -> {event.destination}{suffix}"
    )


if __name__ == "__main__":
    app()
