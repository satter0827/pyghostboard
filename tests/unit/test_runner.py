"""Complete-match runner behavior and failure cleanup."""

from uuid import UUID

import pytest

from pyghostboard.agents import InProcessAgentController, RandomAgent
from pyghostboard.application import (
    AbortReason,
    InMemoryMatchStore,
    MatchAborted,
    MatchRunner,
    MatchService,
    MatchSpec,
)
from pyghostboard.domain import (
    Action,
    Move,
    Placement,
    Player,
    PlayerView,
    PrivateMatchEvent,
    RuleSet,
    Square,
)
from pyghostboard.domain.models import PlayerEvent

MATCH_ID = UUID("00000000-0000-0000-0000-000000000091")


class RecordingObserver:
    def __init__(self) -> None:
        self.views: list[PlayerView] = []
        self.events: list[PlayerEvent] = []
        self.final: PlayerView | None = None

    def on_turn(self, view: PlayerView) -> None:
        self.views.append(view)

    def on_events(self, events: tuple[PlayerEvent, ...]) -> None:
        self.events.extend(events)

    def on_finished(self, view: PlayerView) -> None:
        self.final = view


class RecordingSink:
    def __init__(self) -> None:
        self.events: list[PrivateMatchEvent] = []

    def append(self, *events: PrivateMatchEvent) -> None:
        self.events.extend(events)


@pytest.mark.asyncio
async def test_runner_completes_with_player_safe_observation_and_private_events() -> None:
    observer = RecordingObserver()
    sink = RecordingSink()
    controllers = {
        Player.ONE: InProcessAgentController(RandomAgent),
        Player.TWO: InProcessAgentController(RandomAgent),
    }

    result = await MatchRunner(MatchService(InMemoryMatchStore())).run(
        MatchSpec(
            match_id=MATCH_ID,
            rules=RuleSet.standard(),
            player_one_seed=3,
            player_two_seed=5,
        ),
        controllers,
        observer=observer,
        private_events=sink,
    )

    assert result.match_id == MATCH_ID
    assert result.plies > 0
    assert observer.final is not None
    assert all(view.player is Player.ONE for view in observer.views)
    assert all(
        not hasattr(square, "kind") for view in observer.views for square in view.opponent_squares
    )
    assert sink.events[0].type == "match_started"
    assert len(sink.events) == result.plies + 1


class FailingController(InProcessAgentController):
    def __init__(self) -> None:
        super().__init__(RandomAgent)
        self.closed = False

    async def choose_placement(self) -> Placement:
        raise RuntimeError("placement failed")

    async def close(self) -> None:
        self.closed = True
        await super().close()


@pytest.mark.asyncio
async def test_runner_closes_both_controllers_after_failure() -> None:
    first = FailingController()
    second = FailingController()

    with pytest.raises(MatchAborted) as captured:
        await MatchRunner(MatchService(InMemoryMatchStore())).run(
            MatchSpec(match_id=MATCH_ID, rules=RuleSet.standard()),
            {Player.ONE: first, Player.TWO: second},
        )

    assert captured.value.reason is AbortReason.AGENT_FAILURE
    assert first.closed and second.closed


@pytest.mark.asyncio
async def test_runner_enforces_maximum_plies() -> None:
    with pytest.raises(MatchAborted) as captured:
        await MatchRunner(MatchService(InMemoryMatchStore())).run(
            MatchSpec(match_id=MATCH_ID, rules=RuleSet.standard(), max_plies=1),
            {
                Player.ONE: InProcessAgentController(RandomAgent),
                Player.TWO: InProcessAgentController(RandomAgent),
            },
        )

    assert captured.value.reason is AbortReason.MAXIMUM_PLIES


class IllegalActionController(InProcessAgentController):
    async def choose_action(self, view: PlayerView) -> Action:
        del view
        return Move(source=Square(x=0, y=0), destination=Square(x=0, y=1))


@pytest.mark.asyncio
async def test_runner_rejects_controller_action_outside_the_legal_set() -> None:
    with pytest.raises(MatchAborted) as captured:
        await MatchRunner(MatchService(InMemoryMatchStore())).run(
            MatchSpec(match_id=MATCH_ID, rules=RuleSet.standard()),
            {
                Player.ONE: IllegalActionController(RandomAgent),
                Player.TWO: InProcessAgentController(RandomAgent),
            },
        )

    assert captured.value.reason is AbortReason.ILLEGAL_ACTION


class FinishFailingController(InProcessAgentController):
    def __init__(self) -> None:
        super().__init__(RandomAgent)
        self.closed = False

    async def finish(self, view: PlayerView) -> None:
        del view
        raise RuntimeError("finish failed")

    async def close(self) -> None:
        self.closed = True
        await super().close()


@pytest.mark.asyncio
async def test_runner_closes_both_controllers_when_finish_notification_fails() -> None:
    first = FinishFailingController()
    second = FinishFailingController()

    with pytest.raises(MatchAborted) as captured:
        await MatchRunner(MatchService(InMemoryMatchStore())).run(
            MatchSpec(
                match_id=MATCH_ID,
                rules=RuleSet.standard(),
                player_one_seed=2,
                player_two_seed=3,
            ),
            {Player.ONE: first, Player.TWO: second},
        )

    assert captured.value.reason is AbortReason.AGENT_FAILURE
    assert first.closed and second.closed
