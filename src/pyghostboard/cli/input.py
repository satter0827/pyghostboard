"""Human placement and action input."""

from __future__ import annotations

from rich.console import Console
from rich.prompt import Prompt

from pyghostboard.cli.i18n import tr
from pyghostboard.domain.models import (
    Action,
    Escape,
    Move,
    Placement,
    Player,
    PlayerView,
    RuleSet,
    Square,
)


def prompt_placement(console: Console, rules: RuleSet, player: Player) -> Placement:
    """Prompt until the selected good pieces form a legal placement."""
    starts = rules.start_squares(player)
    default = ",".join(str(square) for square in starts[: rules.good_count])
    while True:
        answer = Prompt.ask(
            tr("Choose {count} good ghost squares separated by commas").format(
                count=rules.good_count
            ),
            default=default,
            console=console,
        )
        try:
            good = tuple(Square.parse(item.strip()) for item in answer.split(","))
            if len(good) != rules.good_count or len(set(good)) != len(good):
                raise ValueError
            if not set(good) <= set(starts):
                raise ValueError
            bad = tuple(square for square in starts if square not in good)
            return Placement(good=good, bad=bad)
        except ValueError:
            console.print(tr("Choose distinct squares from the configured starting area."))


def prompt_action(console: Console, view: PlayerView) -> Action:
    """Prompt until a number or coordinate expression matches a legal action."""
    console.print(tr("Legal actions:"))
    for index, action in enumerate(view.legal_actions, start=1):
        console.print(f"  {index}. {format_action(action)}")
    while True:
        answer = Prompt.ask(
            tr("Choose a number, 'b2 c2', or 'b2 exit'"),
            console=console,
        )
        selected = parse_action(answer, view.legal_actions)
        if selected is not None:
            return selected
        console.print(tr("Choose one of the listed legal actions."))


def parse_action(answer: str, legal_actions: tuple[Action, ...]) -> Action | None:
    """Return the legal action selected by a supported input form."""
    normalized = answer.strip().lower()
    if normalized.isdigit():
        index = int(normalized) - 1
        return legal_actions[index] if 0 <= index < len(legal_actions) else None
    parts = normalized.split()
    if len(parts) != 2:
        return None
    try:
        source = Square.parse(parts[0])
        candidate: Action = (
            Escape(source=source)
            if parts[1] == "exit"
            else Move(source=source, destination=Square.parse(parts[1]))
        )
    except ValueError:
        return None
    return candidate if candidate in legal_actions else None


def format_action(action: Action) -> str:
    """Format an action without changing wire values."""
    if isinstance(action, Escape):
        return tr("{source} exits").format(source=action.source)
    return tr("{source} to {destination}").format(
        source=action.source,
        destination=action.destination,
    )


__all__ = ["format_action", "parse_action", "prompt_action", "prompt_placement"]
