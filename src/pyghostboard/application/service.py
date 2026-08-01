"""Application services and persistence ports."""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from typing import Protocol
from uuid import UUID

from pyghostboard.domain.match import Match, Transition
from pyghostboard.domain.models import (
    Action,
    ActionPlayed,
    Escape,
    MatchStarted,
    Placement,
    Player,
    PlayerEvent,
    PlayerView,
    PrivateMatchEvent,
    PrivateMatchSnapshot,
    RuleSet,
)


class RevisionConflict(RuntimeError):
    """Raised when a stored match changed since it was loaded."""


class InvalidCommit(ValueError):
    """Raised when a snapshot and its event batch do not describe one transition."""


class MatchNotFound(LookupError):
    """Raised when the requested match does not exist."""


class AbortReason(StrEnum):
    AGENT_FAILURE = "agent_failure"
    ILLEGAL_ACTION = "illegal_action"
    MAXIMUM_PLIES = "maximum_plies"
    NO_LEGAL_ACTIONS = "no_legal_actions"


class MatchAborted(RuntimeError):
    """Typed application failure for a match that cannot continue."""

    def __init__(self, reason: AbortReason, detail: str) -> None:
        super().__init__(detail)
        self.reason = reason


class MatchStore(Protocol):
    async def load(self, match_id: UUID) -> PrivateMatchSnapshot | None: ...

    async def commit(
        self,
        snapshot: PrivateMatchSnapshot,
        events: tuple[PrivateMatchEvent, ...],
        *,
        expected_revision: int,
    ) -> None: ...


class EventLogger(Protocol):
    def info(self, event: str, **values: object) -> object: ...


class _NullEventLogger:
    def info(self, event: str, **values: object) -> None:
        del event, values


def project_player_events(event: ActionPlayed) -> tuple[PlayerEvent, ...]:
    """Project a private transition event into display-safe public events."""
    action = event.action
    visible = PlayerEvent(
        sequence=event.sequence,
        kind=(
            "escape"
            if isinstance(action, Escape)
            else "capture"
            if event.captured is not None
            else "move"
        ),
        actor=event.player,
        source=action.source,
        destination=None if isinstance(action, Escape) else action.destination,
        captured=event.captured,
    )
    if event.outcome is None:
        return (visible,)
    return (
        visible,
        PlayerEvent(
            sequence=event.sequence,
            kind="finished",
            actor=event.player,
            source=action.source,
            outcome=event.outcome,
        ),
    )


class InMemoryMatchStore:
    """Atomic in-memory store for tests, CUI, and prototypes."""

    def __init__(self) -> None:
        self._snapshots: dict[UUID, PrivateMatchSnapshot] = {}
        self._events: dict[UUID, tuple[PrivateMatchEvent, ...]] = {}

    async def load(self, match_id: UUID) -> PrivateMatchSnapshot | None:
        return self._snapshots.get(match_id)

    async def commit(
        self,
        snapshot: PrivateMatchSnapshot,
        events: tuple[PrivateMatchEvent, ...],
        *,
        expected_revision: int,
    ) -> None:
        current = self._snapshots.get(snapshot.match_id)
        actual_revision = -1 if current is None else current.revision
        if actual_revision != expected_revision:
            raise RevisionConflict(
                f"expected revision {expected_revision}, found {actual_revision}"
            )
        if current is None:
            if (
                snapshot.revision != 0
                or len(events) != 1
                or not isinstance(events[0], MatchStarted)
                or events[0].snapshot != snapshot
            ):
                raise InvalidCommit("a new match requires its exact match_started event")
        else:
            match = Match.restore(current)
            for event in events:
                if not isinstance(event, ActionPlayed):
                    raise InvalidCommit("an existing match only accepts action_played events")
                transition = match.play(event.player, event.action)
                if transition.events != (event,):
                    raise InvalidCommit("event does not match the domain transition")
                match = transition.match
            if not events or match.snapshot() != snapshot:
                raise InvalidCommit("snapshot does not match the committed events")
        self._snapshots[snapshot.match_id] = snapshot
        self._events[snapshot.match_id] = self._events.get(snapshot.match_id, ()) + events

    def events(self, match_id: UUID) -> tuple[PrivateMatchEvent, ...]:
        return self._events.get(match_id, ())


class MatchService:
    def __init__(self, store: MatchStore, *, logger: EventLogger | None = None) -> None:
        self._store = store
        self._logger = logger if logger is not None else _NullEventLogger()

    async def create(
        self,
        match_id: UUID,
        rules: RuleSet,
        placements: Mapping[Player, Placement],
        first_player: Player = Player.ONE,
    ) -> Match:
        match = Match.start(match_id, rules, placements, first_player)
        started = match.started_event()
        await self._store.commit(match.snapshot(), (started,), expected_revision=-1)
        self._logger.info("match_started", match_id=str(match_id), revision=0)
        return match

    async def get(self, match_id: UUID) -> Match:
        snapshot = await self._store.load(match_id)
        if snapshot is None:
            raise MatchNotFound(str(match_id))
        return Match.restore(snapshot)

    async def view(self, match_id: UUID, player: Player) -> PlayerView:
        return (await self.get(match_id)).view_for(player)

    async def play(self, match_id: UUID, player: Player, action: Action) -> Transition:
        match = await self.get(match_id)
        transition = match.play(player, action)
        await self._store.commit(
            transition.match.snapshot(),
            transition.events,
            expected_revision=match.revision,
        )
        for event in transition.events:
            for visible in project_player_events(event):
                self._logger.info(
                    "match_event",
                    match_id=str(match_id),
                    **visible.model_dump(mode="json"),
                )
        return transition
