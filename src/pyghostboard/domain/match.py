"""Pure match state transitions."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from uuid import UUID

from pyghostboard.domain.models import (
    Action,
    ActionPlayed,
    CapturedPiece,
    Escape,
    GameOutcome,
    GhostKind,
    MatchStarted,
    Move,
    OutcomeReason,
    OwnPiece,
    Placement,
    Player,
    PlayerView,
    PrivateMatchSnapshot,
    PrivatePiece,
    RemovalReason,
    RuleSet,
    Square,
)


class DomainError(ValueError):
    """Base error raised for invalid domain operations."""


class IllegalAction(DomainError):
    """Raised when an action is not legal in the current state."""


@dataclass(frozen=True, slots=True)
class Transition:
    match: Match
    events: tuple[ActionPlayed, ...]


class Match:
    """Trusted host facade over an immutable complete match snapshot."""

    __slots__ = ("_snapshot",)

    def __init__(self, snapshot: PrivateMatchSnapshot) -> None:
        validated = PrivateMatchSnapshot.model_validate(snapshot.model_dump())
        self._validate_snapshot(validated)
        self._snapshot = validated

    @classmethod
    def start(
        cls,
        match_id: UUID,
        rules: RuleSet,
        placements: Mapping[Player, Placement],
        first_player: Player = Player.ONE,
    ) -> Match:
        if set(placements) != {Player.ONE, Player.TWO}:
            raise DomainError("placements are required for both players")
        pieces: list[PrivatePiece] = []
        for player in Player:
            placement = placements[player]
            if len(placement.good) != rules.good_count or len(placement.bad) != rules.bad_count:
                raise DomainError("placement piece counts do not match the rules")
            if set(placement.good + placement.bad) != set(rules.start_squares(player)):
                raise DomainError("placement must occupy every configured start square")
            for kind, squares in ((GhostKind.GOOD, placement.good), (GhostKind.BAD, placement.bad)):
                for index, square in enumerate(squares, start=1):
                    pieces.append(
                        PrivatePiece(
                            id=f"{player.value}-{kind.value}-{index}",
                            owner=player,
                            kind=kind,
                            square=square,
                        )
                    )
        return cls(
            PrivateMatchSnapshot(
                match_id=match_id,
                revision=0,
                rules=rules,
                first_player=first_player,
                current_player=first_player,
                pieces=tuple(pieces),
            )
        )

    @classmethod
    def restore(cls, snapshot: PrivateMatchSnapshot) -> Match:
        return cls(snapshot)

    @classmethod
    def replay(cls, started: MatchStarted, events: Sequence[ActionPlayed]) -> Match:
        if started.snapshot.revision != 0:
            raise DomainError("a match_started snapshot must have revision zero")
        match = cls.restore(started.snapshot)
        for expected in events:
            transition = match.play(expected.player, expected.action)
            actual = transition.events[0]
            if actual != expected:
                raise DomainError(f"event mismatch at sequence {expected.sequence}")
            match = transition.match
        return match

    @property
    def revision(self) -> int:
        return self._snapshot.revision

    @property
    def outcome(self) -> GameOutcome | None:
        return self._snapshot.outcome

    @property
    def current_player(self) -> Player:
        return self._snapshot.current_player

    def snapshot(self) -> PrivateMatchSnapshot:
        return self._snapshot

    def started_event(self) -> MatchStarted:
        if self.revision != 0:
            raise DomainError("a match_started event is only available at revision zero")
        return MatchStarted(snapshot=self._snapshot)

    def legal_actions(self) -> tuple[Action, ...]:
        if self.outcome is not None:
            return ()
        occupied = {
            piece.square: piece for piece in self._snapshot.pieces if piece.square is not None
        }
        actions: list[Action] = []
        for piece in self._living(self.current_player):
            assert piece.square is not None
            for vector in self._snapshot.rules.movement:
                destination = (
                    Square(
                        x=piece.square.x + vector.dx,
                        y=piece.square.y + vector.dy,
                    )
                    if self._on_board(piece.square.x + vector.dx, piece.square.y + vector.dy)
                    else None
                )
                if destination is None:
                    continue
                target = occupied.get(destination)
                if target is None or target.owner is not piece.owner:
                    actions.append(Move(source=piece.square, destination=destination))
            if (
                OutcomeReason.ESCAPE in self._snapshot.rules.victory_conditions
                and piece.kind is GhostKind.GOOD
                and piece.square
                in {exit_.square for exit_ in self._snapshot.rules.exits(piece.owner)}
            ):
                actions.append(Escape(source=piece.square))
        return tuple(actions)

    def view_for(self, player: Player) -> PlayerView:
        own = tuple(
            OwnPiece(id=piece.id, kind=piece.kind, square=piece.square)
            for piece in self._living(player)
            if piece.square is not None
        )
        opponent = tuple(
            sorted(
                (
                    piece.square
                    for piece in self._living(player.opponent)
                    if piece.square is not None
                ),
                key=lambda square: (square.y, square.x),
            )
        )
        captured = tuple(
            CapturedPiece(owner=piece.owner, kind=piece.kind)
            for piece in self._snapshot.pieces
            if piece.removal is RemovalReason.CAPTURED
        )
        return PlayerView(
            match_id=self._snapshot.match_id,
            revision=self.revision,
            player=player,
            current_player=self.current_player,
            width=self._snapshot.rules.width,
            height=self._snapshot.rules.height,
            own_pieces=own,
            opponent_squares=opponent,
            captured=captured,
            legal_actions=self.legal_actions() if player is self.current_player else (),
            outcome=self.outcome,
        )

    def play(self, player: Player, action: Action) -> Transition:
        if self.outcome is not None:
            raise IllegalAction("the match has already finished")
        if player is not self.current_player:
            raise IllegalAction("the player is not active")
        if action not in self.legal_actions():
            raise IllegalAction("the action is not legal")
        pieces = list(self._snapshot.pieces)
        moving_index = self._piece_index(player, action.source)
        moving = pieces[moving_index]
        captured: CapturedPiece | None = None
        outcome: GameOutcome | None = None
        if isinstance(action, Move):
            target_index = self._optional_piece_index(action.destination)
            if target_index is not None:
                target = pieces[target_index]
                captured = CapturedPiece(owner=target.owner, kind=target.kind)
                pieces[target_index] = target.model_copy(
                    update={
                        "square": None,
                        "removal": RemovalReason.CAPTURED,
                        "removed_at": target.square,
                    }
                )
            pieces[moving_index] = moving.model_copy(update={"square": action.destination})
            outcome = self._capture_outcome(player, pieces)
        else:
            pieces[moving_index] = moving.model_copy(
                update={
                    "square": None,
                    "removal": RemovalReason.ESCAPED,
                    "removed_at": moving.square,
                }
            )
            outcome = GameOutcome(winner=player, reason=OutcomeReason.ESCAPE)
        revision = self.revision + 1
        snapshot = self._snapshot.model_copy(
            update={
                "revision": revision,
                "current_player": player.opponent,
                "pieces": tuple(pieces),
                "outcome": outcome,
            }
        )
        event = ActionPlayed(
            sequence=revision,
            player=player,
            action=action,
            captured=captured,
            outcome=outcome,
        )
        return Transition(match=Match(snapshot), events=(event,))

    def _capture_outcome(
        self, player: Player, pieces: Iterable[PrivatePiece]
    ) -> GameOutcome | None:
        living = tuple(piece for piece in pieces if piece.square is not None)
        if OutcomeReason.CAPTURE_GOOD in self._snapshot.rules.victory_conditions and not any(
            piece.owner is player.opponent and piece.kind is GhostKind.GOOD for piece in living
        ):
            return GameOutcome(winner=player, reason=OutcomeReason.CAPTURE_GOOD)
        if OutcomeReason.SACRIFICE_BAD in self._snapshot.rules.victory_conditions and not any(
            piece.owner is player.opponent and piece.kind is GhostKind.BAD for piece in living
        ):
            return GameOutcome(winner=player.opponent, reason=OutcomeReason.SACRIFICE_BAD)
        return None

    def _living(self, player: Player) -> tuple[PrivatePiece, ...]:
        return tuple(
            piece
            for piece in self._snapshot.pieces
            if piece.owner is player and piece.square is not None
        )

    def _piece_index(self, player: Player, square: Square) -> int:
        for index, piece in enumerate(self._snapshot.pieces):
            if piece.owner is player and piece.square == square:
                return index
        raise IllegalAction("no owned piece exists on the source square")

    def _optional_piece_index(self, square: Square) -> int | None:
        for index, piece in enumerate(self._snapshot.pieces):
            if piece.square == square:
                return index
        return None

    def _on_board(self, x: int, y: int) -> bool:
        return 0 <= x < self._snapshot.rules.width and 0 <= y < self._snapshot.rules.height

    @staticmethod
    def _validate_snapshot(snapshot: PrivateMatchSnapshot) -> None:
        if len({piece.id for piece in snapshot.pieces}) != len(snapshot.pieces):
            raise DomainError("piece identifiers must be unique")
        living_squares = [piece.square for piece in snapshot.pieces if piece.square is not None]
        if len(set(living_squares)) != len(living_squares):
            raise DomainError("living pieces cannot share a square")
        for player in Player:
            pieces = [piece for piece in snapshot.pieces if piece.owner is player]
            if sum(piece.kind is GhostKind.GOOD for piece in pieces) != snapshot.rules.good_count:
                raise DomainError("snapshot has an invalid good-piece count")
            if sum(piece.kind is GhostKind.BAD for piece in pieces) != snapshot.rules.bad_count:
                raise DomainError("snapshot has an invalid bad-piece count")
        expected_player = (
            snapshot.first_player if snapshot.revision % 2 == 0 else snapshot.first_player.opponent
        )
        if snapshot.current_player is not expected_player:
            raise DomainError("snapshot current player does not match its revision")
        removed_count = sum(piece.removal is not None for piece in snapshot.pieces)
        if removed_count > snapshot.revision:
            raise DomainError("snapshot removes more pieces than its revision permits")
        if any(
            square is not None
            and (square.x >= snapshot.rules.width or square.y >= snapshot.rules.height)
            for square in living_squares
        ):
            raise DomainError("snapshot contains an out-of-board piece")
        if any(
            piece.removed_at is not None
            and not (
                0 <= piece.removed_at.x < snapshot.rules.width
                and 0 <= piece.removed_at.y < snapshot.rules.height
            )
            for piece in snapshot.pieces
        ):
            raise DomainError("snapshot contains an invalid removal square")
        if any(
            piece.removal is RemovalReason.ESCAPED
            and piece.removed_at
            not in {exit_.square for exit_ in snapshot.rules.exits(piece.owner)}
            for piece in snapshot.pieces
        ):
            raise DomainError("snapshot contains an escape outside a configured exit")
        candidates: set[GameOutcome] = set()
        conditions = snapshot.rules.victory_conditions
        escaped = tuple(
            piece for piece in snapshot.pieces if piece.removal is RemovalReason.ESCAPED
        )
        if escaped and (OutcomeReason.ESCAPE not in conditions or len(escaped) != 1):
            raise DomainError("snapshot contains an impossible escape history")
        if OutcomeReason.ESCAPE in conditions:
            candidates.update(
                GameOutcome(winner=piece.owner, reason=OutcomeReason.ESCAPE) for piece in escaped
            )
        for player in Player:
            owned_pieces = tuple(piece for piece in snapshot.pieces if piece.owner is player)
            good = tuple(piece for piece in owned_pieces if piece.kind is GhostKind.GOOD)
            bad = tuple(piece for piece in owned_pieces if piece.kind is GhostKind.BAD)
            if OutcomeReason.CAPTURE_GOOD in conditions and all(
                piece.removal is RemovalReason.CAPTURED for piece in good
            ):
                candidates.add(
                    GameOutcome(winner=player.opponent, reason=OutcomeReason.CAPTURE_GOOD)
                )
            if OutcomeReason.SACRIFICE_BAD in conditions and all(
                piece.removal is RemovalReason.CAPTURED for piece in bad
            ):
                candidates.add(GameOutcome(winner=player, reason=OutcomeReason.SACRIFICE_BAD))
        if not candidates and snapshot.outcome is not None:
            raise DomainError("snapshot outcome is not supported by its piece state")
        if candidates and snapshot.outcome not in candidates:
            raise DomainError("snapshot omits or contradicts a terminal outcome")
        if len(candidates) > 1:
            raise DomainError("snapshot contains multiple terminal outcomes")
