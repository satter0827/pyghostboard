"""Application service and optimistic-concurrency tests."""

from uuid import UUID

import pytest

from pyghostboard.application import (
    InMemoryMatchStore,
    InvalidCommit,
    MatchNotFound,
    MatchService,
    RevisionConflict,
    project_player_events,
)
from pyghostboard.domain import Match, Placement, Player, RuleSet
from pyghostboard.protocol import ActionRequest, request_adapter

MATCH_ID = UUID("00000000-0000-0000-0000-000000000002")


def placements() -> dict[Player, Placement]:
    rules = RuleSet.standard()
    one = rules.start_squares(Player.ONE)
    two = rules.start_squares(Player.TWO)
    return {
        Player.ONE: Placement(good=one[:4], bad=one[4:]),
        Player.TWO: Placement(good=two[:4], bad=two[4:]),
    }


class CapturingLogger:
    def __init__(self) -> None:
        self.entries: list[tuple[str, dict[str, object]]] = []

    def info(self, event: str, **values: object) -> None:
        self.entries.append((event, values))


@pytest.mark.asyncio
async def test_service_create_view_and_play() -> None:
    store = InMemoryMatchStore()
    service = MatchService(store)
    match = await service.create(MATCH_ID, RuleSet.standard(), placements())

    view = await service.view(MATCH_ID, Player.ONE)
    transition = await service.play(MATCH_ID, Player.ONE, view.legal_actions[0])

    assert match.revision == 0
    assert transition.match.revision == 1
    assert (await service.get(MATCH_ID)).revision == 1
    assert len(store.events(MATCH_ID)) == 2


@pytest.mark.asyncio
async def test_store_rejects_stale_revision_atomically() -> None:
    store = InMemoryMatchStore()
    match = Match.start(MATCH_ID, RuleSet.standard(), placements())
    await store.commit(match.snapshot(), (match.started_event(),), expected_revision=-1)
    transition = match.play(Player.ONE, match.legal_actions()[0])
    await store.commit(transition.match.snapshot(), transition.events, expected_revision=0)

    with pytest.raises(RevisionConflict):
        await store.commit(transition.match.snapshot(), transition.events, expected_revision=0)

    assert len(store.events(MATCH_ID)) == 2


@pytest.mark.asyncio
async def test_store_rejects_mismatched_snapshot_and_events_atomically() -> None:
    store = InMemoryMatchStore()
    match = Match.start(MATCH_ID, RuleSet.standard(), placements())
    await store.commit(match.snapshot(), (match.started_event(),), expected_revision=-1)
    transition = match.play(Player.ONE, match.legal_actions()[0])

    with pytest.raises(InvalidCommit, match="snapshot does not match"):
        await store.commit(match.snapshot(), transition.events, expected_revision=0)

    assert (await store.load(MATCH_ID)) == match.snapshot()
    assert store.events(MATCH_ID) == (match.started_event(),)


@pytest.mark.asyncio
async def test_store_rejects_invalid_event_batches() -> None:
    match = Match.start(MATCH_ID, RuleSet.standard(), placements())
    empty_store = InMemoryMatchStore()
    with pytest.raises(InvalidCommit, match="new match"):
        await empty_store.commit(match.snapshot(), (), expected_revision=-1)

    store = InMemoryMatchStore()
    await store.commit(match.snapshot(), (match.started_event(),), expected_revision=-1)
    with pytest.raises(InvalidCommit, match="only accepts"):
        await store.commit(
            match.snapshot(),
            (match.started_event(),),
            expected_revision=0,
        )


@pytest.mark.asyncio
async def test_missing_match_is_explicit() -> None:
    service = MatchService(InMemoryMatchStore())
    with pytest.raises(MatchNotFound):
        await service.get(MATCH_ID)


@pytest.mark.asyncio
async def test_all_untrusted_outputs_and_logs_are_noninterfering() -> None:
    rules = RuleSet.standard()
    first_placements = placements()
    second_placements = placements()
    starts = rules.start_squares(Player.TWO)
    second_placements[Player.TWO] = Placement(good=starts[4:], bad=starts[:4])
    first_logger = CapturingLogger()
    second_logger = CapturingLogger()
    first_service = MatchService(InMemoryMatchStore(), logger=first_logger)
    second_service = MatchService(InMemoryMatchStore(), logger=second_logger)
    first = await first_service.create(MATCH_ID, rules, first_placements)
    second = await second_service.create(MATCH_ID, rules, second_placements)

    first_view = first.view_for(Player.ONE)
    second_view = second.view_for(Player.ONE)
    assert first_view == second_view
    request_id = UUID("00000000-0000-0000-0000-000000000099")
    assert request_adapter.dump_json(
        ActionRequest(request_id=request_id, view=first_view)
    ) == request_adapter.dump_json(ActionRequest(request_id=request_id, view=second_view))

    action = first_view.legal_actions[0]
    first_transition = await first_service.play(MATCH_ID, Player.ONE, action)
    second_transition = await second_service.play(MATCH_ID, Player.ONE, action)
    assert project_player_events(first_transition.events[0]) == project_player_events(
        second_transition.events[0]
    )
    assert first_logger.entries == second_logger.entries
