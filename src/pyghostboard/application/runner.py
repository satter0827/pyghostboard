"""Complete-match orchestration and player-controller ports."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol
from uuid import UUID

from pydantic import Field

from pyghostboard.application.service import (
    AbortReason,
    MatchAborted,
    MatchService,
    project_player_events,
)
from pyghostboard.domain.models import (
    Action,
    DomainModel,
    GameOutcome,
    Placement,
    Player,
    PlayerEvent,
    PlayerView,
    PrivateMatchEvent,
    RuleSet,
)


class PlayerContext(DomainModel):
    """Public, reproducible information supplied to one controller."""

    player: Player
    rules: RuleSet
    seed: int


class PlayerController(Protocol):
    """Asynchronous input lifecycle shared by people and AI agents."""

    async def initialize(self, context: PlayerContext) -> None: ...

    async def choose_placement(self) -> Placement: ...

    async def choose_action(self, view: PlayerView) -> Action: ...

    async def finish(self, view: PlayerView) -> None: ...

    async def close(self) -> None: ...


class MatchObserver(Protocol):
    """Receive one player-safe presentation stream."""

    def on_turn(self, view: PlayerView) -> None: ...

    def on_events(self, events: tuple[PlayerEvent, ...]) -> None: ...

    def on_finished(self, view: PlayerView) -> None: ...


class PrivateEventSink(Protocol):
    """Receive trusted-host events for an explicitly private destination."""

    def append(self, *events: PrivateMatchEvent) -> None: ...


class MatchSpec(DomainModel):
    """Validated inputs for one deterministic match execution."""

    match_id: UUID
    rules: RuleSet
    first_player: Player = Player.ONE
    player_one_seed: int = 0
    player_two_seed: int = 0
    max_plies: int = Field(default=1_000, ge=1)
    observer_player: Player = Player.ONE


class MatchResult(DomainModel):
    """Completed match summary independent of presentation and transport."""

    match_id: UUID
    outcome: GameOutcome
    plies: int


class MatchRunner:
    """Run a complete match through application and controller ports."""

    def __init__(self, service: MatchService) -> None:
        self._service = service

    async def run(
        self,
        spec: MatchSpec,
        controllers: Mapping[Player, PlayerController],
        *,
        observer: MatchObserver | None = None,
        private_events: PrivateEventSink | None = None,
    ) -> MatchResult:
        if set(controllers) != {Player.ONE, Player.TWO}:
            raise ValueError("controllers must contain exactly player one and player two")
        primary_error: BaseException | None = None
        try:
            return await self._run(spec, controllers, observer, private_events)
        except BaseException as error:
            primary_error = error
            raise
        finally:
            close_errors: list[Exception] = []
            for player in (Player.TWO, Player.ONE):
                try:
                    await controllers[player].close()
                except Exception as error:  # controller cleanup must not hide the primary failure
                    close_errors.append(error)
            if primary_error is None and close_errors:
                raise MatchAborted(AbortReason.AGENT_FAILURE, str(close_errors[0]))

    async def _run(
        self,
        spec: MatchSpec,
        controllers: Mapping[Player, PlayerController],
        observer: MatchObserver | None,
        private_events: PrivateEventSink | None,
    ) -> MatchResult:
        seeds = {Player.ONE: spec.player_one_seed, Player.TWO: spec.player_two_seed}
        try:
            for player in (Player.ONE, Player.TWO):
                await controllers[player].initialize(
                    PlayerContext(player=player, rules=spec.rules, seed=seeds[player])
                )
            placements = {
                player: await controllers[player].choose_placement()
                for player in (Player.ONE, Player.TWO)
            }
        except Exception as error:
            raise MatchAborted(AbortReason.AGENT_FAILURE, str(error)) from error

        match = await self._service.create(
            spec.match_id,
            spec.rules,
            placements,
            first_player=spec.first_player,
        )
        if private_events is not None:
            private_events.append(match.started_event())

        for _ in range(spec.max_plies):
            if match.outcome is not None:
                break
            active_view = match.view_for(match.current_player)
            if not active_view.legal_actions:
                raise MatchAborted(
                    AbortReason.NO_LEGAL_ACTIONS,
                    f"{match.current_player.value} has no legal action",
                )
            if observer is not None:
                observer.on_turn(match.view_for(spec.observer_player))
            try:
                action = await controllers[match.current_player].choose_action(active_view)
            except Exception as error:
                raise MatchAborted(AbortReason.AGENT_FAILURE, str(error)) from error
            try:
                transition = await self._service.play(spec.match_id, match.current_player, action)
            except ValueError as error:
                raise MatchAborted(AbortReason.ILLEGAL_ACTION, str(error)) from error
            if private_events is not None:
                private_events.append(*transition.events)
            if observer is not None:
                observer.on_events(
                    tuple(
                        visible
                        for event in transition.events
                        for visible in project_player_events(event)
                    )
                )
            match = transition.match
        else:
            raise MatchAborted(AbortReason.MAXIMUM_PLIES, "maximum ply count reached")

        assert match.outcome is not None
        if observer is not None:
            observer.on_finished(match.view_for(spec.observer_player))
        try:
            for player in (Player.ONE, Player.TWO):
                await controllers[player].finish(match.view_for(player))
        except Exception as error:
            raise MatchAborted(AbortReason.AGENT_FAILURE, str(error)) from error
        return MatchResult(match_id=spec.match_id, outcome=match.outcome, plies=match.revision)
