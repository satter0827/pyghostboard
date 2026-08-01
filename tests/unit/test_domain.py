"""Domain rules, persistence, and information-boundary tests."""

from uuid import UUID

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from pyghostboard.domain import (
    ActionPlayed,
    Escape,
    GameOutcome,
    GhostKind,
    IllegalAction,
    Match,
    Move,
    OutcomeReason,
    Placement,
    Player,
    PrivateMatchSnapshot,
    RemovalReason,
    RuleSet,
    Square,
    Vector,
    dump_event,
    dump_snapshot,
    load_event,
    load_snapshot,
)
from pyghostboard.domain.models import PrivatePiece

MATCH_ID = UUID("00000000-0000-0000-0000-000000000001")


def standard_placements(*, swap_two: bool = False) -> dict[Player, Placement]:
    rules = RuleSet.standard()
    one = rules.start_squares(Player.ONE)
    two = rules.start_squares(Player.TWO)
    two_good = two[4:] if swap_two else two[:4]
    two_bad = two[:4] if swap_two else two[4:]
    return {
        Player.ONE: Placement(good=one[:4], bad=one[4:]),
        Player.TWO: Placement(good=two_good, bad=two_bad),
    }


def test_standard_rules_and_initial_legal_actions() -> None:
    match = Match.start(MATCH_ID, RuleSet.standard(), standard_placements())

    assert match.revision == 0
    assert match.current_player is Player.ONE
    assert match.outcome is None
    assert len(match.legal_actions()) == 8


def test_observation_is_independent_of_opponent_kinds() -> None:
    first = Match.start(MATCH_ID, RuleSet.standard(), standard_placements())
    second = Match.start(
        MATCH_ID,
        RuleSet.standard(),
        standard_placements(swap_two=True),
    )
    assert (
        first.view_for(Player.ONE).model_dump_json()
        == second.view_for(Player.ONE).model_dump_json()
    )


@given(st.permutations(range(8)))
def test_observation_is_independent_of_every_opponent_kind_assignment(
    order: list[int],
) -> None:
    rules = RuleSet.standard()
    starts = rules.start_squares(Player.TWO)
    good = tuple(starts[index] for index in order[:4])
    placement = standard_placements()
    placement[Player.TWO] = Placement(
        good=good,
        bad=tuple(square for square in starts if square not in good),
    )
    baseline = Match.start(MATCH_ID, rules, standard_placements())
    candidate = Match.start(MATCH_ID, rules, placement)
    assert baseline.view_for(Player.ONE) == candidate.view_for(Player.ONE)


def test_match_is_immutable_and_rejects_wrong_player() -> None:
    match = Match.start(MATCH_ID, RuleSet.standard(), standard_placements())
    action = match.legal_actions()[0]

    with pytest.raises(IllegalAction, match="not active"):
        match.play(Player.TWO, action)

    transition = match.play(Player.ONE, action)
    assert match.revision == 0
    assert transition.match.revision == 1
    assert transition.match.current_player is Player.TWO


def test_escape_finishes_match() -> None:
    rules = small_rules()
    pieces = _pieces_at(
        one_good=Square(x=0, y=5),
        one_bad=Square(x=1, y=1),
        two_good=Square(x=2, y=4),
        two_bad=Square(x=3, y=4),
        rules=rules,
    )
    match = Match.restore(
        PrivateMatchSnapshot(
            match_id=MATCH_ID,
            revision=0,
            rules=rules,
            first_player=Player.ONE,
            current_player=Player.ONE,
            pieces=pieces,
        )
    )

    transition = match.play(Player.ONE, Escape(source=Square(x=0, y=5)))

    assert transition.match.outcome is not None
    assert transition.match.outcome.winner is Player.ONE
    assert transition.match.outcome.reason is OutcomeReason.ESCAPE
    assert transition.match.legal_actions() == ()
    assert transition.match.snapshot().pieces[0].removal is RemovalReason.ESCAPED
    assert transition.match.view_for(Player.ONE).captured == ()


def test_victory_conditions_are_configuration_driven() -> None:
    rules = small_rules().model_copy(
        update={
            "victory_conditions": (
                OutcomeReason.CAPTURE_GOOD,
                OutcomeReason.SACRIFICE_BAD,
            )
        }
    )
    pieces = _pieces_at(
        one_good=Square(x=0, y=5),
        one_bad=Square(x=1, y=1),
        two_good=Square(x=2, y=4),
        two_bad=Square(x=3, y=4),
        rules=rules,
    )
    match = Match.restore(
        PrivateMatchSnapshot(
            match_id=MATCH_ID,
            revision=0,
            rules=rules,
            first_player=Player.ONE,
            current_player=Player.ONE,
            pieces=pieces,
        )
    )
    assert Escape(source=Square(x=0, y=5)) not in match.legal_actions()


def test_capture_all_good_and_sacrifice_all_bad() -> None:
    rules = small_rules()
    for target_kind, winner, reason in (
        (GhostKind.GOOD, Player.ONE, OutcomeReason.CAPTURE_GOOD),
        (GhostKind.BAD, Player.TWO, OutcomeReason.SACRIFICE_BAD),
    ):
        other_kind = GhostKind.BAD if target_kind is GhostKind.GOOD else GhostKind.GOOD
        pieces = (
            PrivatePiece(
                id="one-good-1",
                owner=Player.ONE,
                kind=GhostKind.GOOD,
                square=Square(x=2, y=2),
            ),
            PrivatePiece(
                id="one-bad-1",
                owner=Player.ONE,
                kind=GhostKind.BAD,
                square=Square(x=1, y=1),
            ),
            PrivatePiece(
                id=f"two-{target_kind.value}-1",
                owner=Player.TWO,
                kind=target_kind,
                square=Square(x=2, y=3),
            ),
            PrivatePiece(
                id=f"two-{other_kind.value}-1",
                owner=Player.TWO,
                kind=other_kind,
                square=Square(x=4, y=4),
            ),
        )
        match = Match.restore(
            PrivateMatchSnapshot(
                match_id=MATCH_ID,
                revision=0,
                rules=rules,
                first_player=Player.ONE,
                current_player=Player.ONE,
                pieces=pieces,
            )
        )
        transition = match.play(
            Player.ONE,
            Move(source=Square(x=2, y=2), destination=Square(x=2, y=3)),
        )
        assert transition.match.outcome is not None
        assert transition.match.outcome.winner is winner
        assert transition.match.outcome.reason is reason


def test_snapshot_event_round_trip_and_replay() -> None:
    match = Match.start(MATCH_ID, RuleSet.standard(), standard_placements())
    started = match.started_event()
    transition = match.play(Player.ONE, match.legal_actions()[0])
    event = transition.events[0]

    assert load_snapshot(dump_snapshot(match.snapshot())) == match.snapshot()
    assert load_event(dump_event(started)) == started
    assert load_event(dump_event(event)) == event
    assert Match.replay(started, (event,)).snapshot() == transition.match.snapshot()
    with pytest.raises(ValueError, match="revision zero"):
        transition.match.started_event()


def test_invalid_rules_and_corrupt_snapshot_are_rejected() -> None:
    rules = RuleSet.standard()
    with pytest.raises(ValidationError, match="outside the board"):
        RuleSet.model_validate(
            rules.model_dump() | {"player_one_exits": [{"square": {"x": 9, "y": 9}}]}
        )

    match = Match.start(MATCH_ID, rules, standard_placements())
    terminal_without_state = match.snapshot().model_copy(
        update={"outcome": GameOutcome(winner=Player.ONE, reason=OutcomeReason.CAPTURE_GOOD)}
    )
    with pytest.raises(ValueError, match="not supported"):
        Match.restore(terminal_without_state)

    duplicate = (
        match.snapshot().pieces[0].model_copy(update={"square": match.snapshot().pieces[1].square})
    )
    with pytest.raises(ValueError, match="share a square"):
        Match.restore(
            match.snapshot().model_copy(
                update={"pieces": (duplicate, *match.snapshot().pieces[1:])}
            )
        )


def _pieces_at(
    *,
    one_good: Square,
    one_bad: Square,
    two_good: Square,
    two_bad: Square,
    rules: RuleSet,
) -> tuple[PrivatePiece, ...]:
    del rules
    return (
        PrivatePiece(id="one-good-1", owner=Player.ONE, kind=GhostKind.GOOD, square=one_good),
        PrivatePiece(id="one-bad-1", owner=Player.ONE, kind=GhostKind.BAD, square=one_bad),
        PrivatePiece(id="two-good-1", owner=Player.TWO, kind=GhostKind.GOOD, square=two_good),
        PrivatePiece(id="two-bad-1", owner=Player.TWO, kind=GhostKind.BAD, square=two_bad),
    )


def small_rules() -> RuleSet:
    return RuleSet(
        width=6,
        height=6,
        good_count=1,
        bad_count=1,
        player_one_start=(Square(x=1, y=0), Square(x=2, y=0)),
        player_two_start=(Square(x=1, y=5), Square(x=2, y=5)),
        player_one_exits=RuleSet.standard().player_one_exits,
        player_two_exits=RuleSet.standard().player_two_exits,
        movement=(
            Vector(dx=0, dy=1),
            Vector(dx=1, dy=0),
            Vector(dx=0, dy=-1),
            Vector(dx=-1, dy=0),
        ),
    )


def test_event_adapter_type_is_stable() -> None:
    match = Match.start(MATCH_ID, RuleSet.standard(), standard_placements())
    event = match.play(Player.ONE, match.legal_actions()[0]).events[0]
    assert isinstance(load_event(dump_event(event)), ActionPlayed)
