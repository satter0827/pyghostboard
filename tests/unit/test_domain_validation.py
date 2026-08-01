"""Adversarial validation tests for public domain formats."""

from uuid import UUID

import pytest
from pydantic import ValidationError

from pyghostboard.domain import (
    ActionPlayed,
    CapturedPiece,
    Escape,
    GameOutcome,
    GhostKind,
    Match,
    Move,
    OutcomeReason,
    Placement,
    Player,
    RuleSet,
    Square,
    Vector,
)
from pyghostboard.domain.models import PrivatePiece, RemovalReason

MATCH_ID = UUID("00000000-0000-0000-0000-000000000040")


def _match() -> Match:
    rules = RuleSet.standard()
    one = rules.start_squares(Player.ONE)
    two = rules.start_squares(Player.TWO)
    return Match.start(
        MATCH_ID,
        rules,
        {
            Player.ONE: Placement(good=one[:4], bad=one[4:]),
            Player.TWO: Placement(good=two[:4], bad=two[4:]),
        },
    )


def test_value_notation_and_local_validators() -> None:
    assert Square.parse("A1") == Square(x=0, y=0)
    with pytest.raises(ValueError, match="invalid square"):
        Square.parse("1a")
    with pytest.raises(ValidationError, match="cannot be zero"):
        Vector(dx=0, dy=0)
    with pytest.raises(ValidationError, match="must be unique"):
        Placement(good=(Square(x=0, y=0),), bad=(Square(x=0, y=0),))


@pytest.mark.parametrize(
    ("update", "message"),
    [
        ({"player_one_start": []}, "exactly"),
        ({"player_one_exits": []}, "at least one exit"),
        (
            {"movement": [{"dx": 1, "dy": 0}, {"dx": 1, "dy": 0}]},
            "movement vectors must be unique",
        ),
        ({"victory_conditions": []}, "victory condition"),
        (
            {"victory_conditions": ["escape", "escape"]},
            "victory conditions must be unique",
        ),
    ],
)
def test_rule_configuration_boundaries(update: dict[str, object], message: str) -> None:
    data = RuleSet.standard().model_dump(mode="json") | update
    with pytest.raises(ValidationError, match=message):
        RuleSet.model_validate(data)


def test_rule_areas_and_exits_cannot_overlap_or_repeat() -> None:
    rules = RuleSet.standard()
    data = rules.model_dump(mode="json")
    data["player_two_start"] = data["player_one_start"]
    with pytest.raises(ValidationError, match="cannot overlap"):
        RuleSet.model_validate(data)

    data = rules.model_dump(mode="json")
    data["player_one_exits"] = [data["player_one_exits"][0]] * 2
    with pytest.raises(ValidationError, match="unique squares"):
        RuleSet.model_validate(data)


def test_piece_removal_shape_is_explicit() -> None:
    square = Square(x=0, y=0)
    with pytest.raises(ValidationError, match="either on the board or removed"):
        PrivatePiece(
            id="piece",
            owner=Player.ONE,
            kind=GhostKind.GOOD,
            square=None,
        )
    with pytest.raises(ValidationError, match="only a good ghost"):
        PrivatePiece(
            id="piece",
            owner=Player.ONE,
            kind=GhostKind.BAD,
            square=None,
            removal=RemovalReason.ESCAPED,
            removed_at=square,
        )


def test_private_action_events_reject_contradictions() -> None:
    source = Square(x=0, y=0)
    destination = Square(x=0, y=1)
    captured_good = CapturedPiece(owner=Player.TWO, kind=GhostKind.GOOD)
    with pytest.raises(ValidationError, match="escape must finish"):
        ActionPlayed(sequence=1, player=Player.ONE, action=Escape(source=source))
    with pytest.raises(ValidationError, match="cannot capture"):
        ActionPlayed(
            sequence=1,
            player=Player.ONE,
            action=Escape(source=source),
            captured=captured_good,
            outcome=GameOutcome(winner=Player.ONE, reason=OutcomeReason.ESCAPE),
        )
    with pytest.raises(ValidationError, match="cannot capture its own"):
        ActionPlayed(
            sequence=1,
            player=Player.ONE,
            action=Move(source=source, destination=destination),
            captured=CapturedPiece(owner=Player.ONE, kind=GhostKind.GOOD),
        )
    with pytest.raises(ValidationError, match="requires a captured"):
        ActionPlayed(
            sequence=1,
            player=Player.ONE,
            action=Move(source=source, destination=destination),
            outcome=GameOutcome(winner=Player.ONE, reason=OutcomeReason.CAPTURE_GOOD),
        )
    with pytest.raises(ValidationError, match="contradicts"):
        ActionPlayed(
            sequence=1,
            player=Player.ONE,
            action=Move(source=source, destination=destination),
            captured=captured_good,
            outcome=GameOutcome(winner=Player.TWO, reason=OutcomeReason.CAPTURE_GOOD),
        )


def test_snapshot_rejects_turn_and_escape_forgery() -> None:
    match = _match()
    with pytest.raises(ValueError, match="current player"):
        Match.restore(match.snapshot().model_copy(update={"current_player": Player.TWO}))

    pieces = list(match.snapshot().pieces)
    piece = pieces[0]
    pieces[0] = piece.model_copy(
        update={
            "square": None,
            "removal": RemovalReason.ESCAPED,
            "removed_at": Square(x=1, y=0),
        }
    )
    forged = match.snapshot().model_copy(
        update={
            "revision": 1,
            "current_player": Player.TWO,
            "pieces": tuple(pieces),
            "outcome": GameOutcome(winner=Player.ONE, reason=OutcomeReason.ESCAPE),
        }
    )
    with pytest.raises(ValueError, match="outside a configured exit"):
        Match.restore(forged)


def test_replay_rejects_event_mismatch() -> None:
    match = _match()
    transition = match.play(Player.ONE, match.legal_actions()[0])
    event = transition.events[0].model_copy(update={"sequence": 2})
    with pytest.raises(ValueError, match="event mismatch"):
        Match.replay(match.started_event(), (event,))
