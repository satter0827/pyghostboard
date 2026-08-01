"""Live and append-only match presentation."""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from rich.console import Console, Group, RenderableType
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from pyghostboard.cli.i18n import tr
from pyghostboard.domain.models import PlayerEvent, PlayerView, Square


def supports_live(console: Console, environment: dict[str, str] | None = None) -> bool:
    """Return whether an updating colored terminal display is safe."""
    values = environment if environment is not None else os.environ
    return (
        console.is_terminal
        and "NO_COLOR" not in values
        and values.get("TERM", "").lower() != "dumb"
    )


@dataclass
class MatchDisplay:
    """Observe one player-safe stream using live or plain presentation."""

    console: Console
    live_enabled: bool
    _live: Live | None = field(default=None, init=False)
    _view: PlayerView | None = field(default=None, init=False)
    _last_event: PlayerEvent | None = field(default=None, init=False)

    def start(self) -> None:
        if self.live_enabled:
            self._live = Live(
                Text(tr("Preparing match...")),
                console=self.console,
                auto_refresh=False,
                transient=False,
            )
            self._live.start(refresh=True)

    def close(self) -> None:
        if self._live is not None:
            self._live.stop()
            self._live = None

    def on_turn(self, view: PlayerView) -> None:
        self._view = view
        self._present()

    def on_events(self, events: tuple[PlayerEvent, ...]) -> None:
        for event in events:
            self._last_event = event
            if not self.live_enabled:
                self.console.print(render_event(event))
        if self.live_enabled:
            self._present()

    def on_finished(self, view: PlayerView) -> None:
        self._view = view
        self._present()

    def _present(self) -> None:
        if self._view is None:
            return
        renderable = render_screen(self._view, self._last_event)
        if self._live is not None:
            self._live.update(renderable, refresh=True)
        elif not self.live_enabled:
            self.console.print(renderable)


def render_screen(view: PlayerView, last_event: PlayerEvent | None) -> RenderableType:
    """Build a deterministic one-screen match summary."""
    status = tr("Turn: {player} · Ply: {ply}").format(
        player=player_name(view.current_player.value),
        ply=view.revision,
    )
    captured = ", ".join(
        tr("{player} {kind}").format(
            player=player_name(piece.owner.value),
            kind=kind_name(piece.kind.value),
        )
        for piece in view.captured
    ) or tr("none")
    lines: list[RenderableType] = [
        Panel(render_board(view), title=tr("Board")),
        Text(status),
        Text(tr("Last move: {move}").format(move=event_text(last_event))),
        Text(tr("Captured: {pieces}").format(pieces=captured)),
    ]
    if view.outcome is not None:
        lines.append(
            Text(
                tr("Winner: {player} · Reason: {reason}").format(
                    player=player_name(view.outcome.winner.value),
                    reason=reason_name(view.outcome.reason.value),
                )
            )
        )
    return Group(*lines)


def render_board(view: PlayerView) -> Table:
    """Render a board from one player's view without private opponent kinds."""
    own = {piece.square: "G" if piece.kind.value == "good" else "B" for piece in view.own_pieces}
    opponents = set(view.opponent_squares)
    table = Table(show_header=True, box=None, pad_edge=False)
    table.add_column("")
    for x in range(view.width):
        table.add_column(chr(ord("a") + x), justify="center")
    for y in reversed(range(view.height)):
        cells = []
        for x in range(view.width):
            square = Square(x=x, y=y)
            cells.append(own.get(square, "?" if square in opponents else "·"))
        table.add_row(str(y + 1), *cells)
    return table


def render_event(event: PlayerEvent) -> str:
    """Render a public event."""
    return event_text(event)


def event_text(event: PlayerEvent | None) -> str:
    if event is None:
        return tr("none")
    if event.kind == "finished":
        assert event.outcome is not None
        return tr("{player} won by {reason}").format(
            player=player_name(event.outcome.winner.value),
            reason=reason_name(event.outcome.reason.value),
        )
    if event.kind == "escape":
        return tr("{player}: {source} exits").format(
            player=player_name(event.actor.value), source=event.source
        )
    assert event.destination is not None
    text = tr("{player}: {source} to {destination}").format(
        player=player_name(event.actor.value),
        source=event.source,
        destination=event.destination,
    )
    if event.captured is not None:
        text += tr("; captured {kind}").format(kind=kind_name(event.captured.kind.value))
    return text


def player_name(value: str) -> str:
    return tr("Player one") if value == "one" else tr("Player two")


def kind_name(value: str) -> str:
    return tr("good ghost") if value == "good" else tr("bad ghost")


def reason_name(value: str) -> str:
    names = {
        "escape": tr("escape"),
        "capture_good": tr("capturing all good ghosts"),
        "sacrifice_bad": tr("sacrificing all bad ghosts"),
    }
    return names[value]


__all__ = ["MatchDisplay", "render_board", "render_event", "render_screen", "supports_live"]
