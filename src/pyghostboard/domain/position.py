"""Pure live-position rules shared by trusted matches and AI hypotheses."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from pyghostboard.domain.models import (
    Action,
    CapturedPiece,
    Escape,
    GameOutcome,
    GhostKind,
    Move,
    OutcomeReason,
    Player,
    PlayerView,
    PrivateMatchSnapshot,
    RuleSet,
    Square,
)


class PositionError(ValueError):
    """Raised when a live position or transition is invalid."""


@dataclass(frozen=True, slots=True)
class PositionPiece:
    owner: Player
    kind: GhostKind
    square: Square


@dataclass(frozen=True, slots=True)
class PositionTransition:
    position: Position
    captured: CapturedPiece | None


@dataclass(frozen=True, slots=True)
class Position:
    """Complete live position without persistence history or piece identities."""

    rules: RuleSet
    current_player: Player
    pieces: tuple[PositionPiece, ...]
    outcome: GameOutcome | None = None

    def __post_init__(self) -> None:
        squares = tuple(piece.square for piece in self.pieces)
        if len(set(squares)) != len(squares):
            raise PositionError("living pieces cannot share a square")
        if any(not self._on_board(square) for square in squares):
            raise PositionError("position contains an out-of-board piece")

    @classmethod
    def from_snapshot(cls, snapshot: PrivateMatchSnapshot) -> Position:
        return cls(
            rules=snapshot.rules,
            current_player=snapshot.current_player,
            pieces=tuple(
                PositionPiece(owner=piece.owner, kind=piece.kind, square=piece.square)
                for piece in snapshot.pieces
                if piece.square is not None
            ),
            outcome=snapshot.outcome,
        )

    @classmethod
    def from_view(
        cls,
        view: PlayerView,
        rules: RuleSet,
        opponent_kinds: Mapping[Square, GhostKind],
    ) -> Position:
        if (view.width, view.height) != (rules.width, rules.height):
            raise PositionError("view dimensions do not match the rules")
        if view.current_player is not view.player or view.outcome is not None:
            raise PositionError("view is not an active-player position")
        if set(opponent_kinds) != set(view.opponent_squares):
            raise PositionError("opponent hypotheses do not match the visible squares")
        captured_counts = {
            (player, kind): sum(
                piece.owner is player and piece.kind is kind for piece in view.captured
            )
            for player in Player
            for kind in GhostKind
        }
        for player in Player:
            living = (
                tuple(piece.kind for piece in view.own_pieces)
                if player is view.player
                else tuple(opponent_kinds.values())
            )
            for kind, configured in (
                (GhostKind.GOOD, rules.good_count),
                (GhostKind.BAD, rules.bad_count),
            ):
                if (
                    sum(candidate is kind for candidate in living) + captured_counts[player, kind]
                    != configured
                ):
                    raise PositionError("view has impossible piece-kind counts")
        pieces = tuple(
            PositionPiece(owner=view.player, kind=piece.kind, square=piece.square)
            for piece in view.own_pieces
        ) + tuple(
            PositionPiece(owner=view.player.opponent, kind=opponent_kinds[square], square=square)
            for square in view.opponent_squares
        )
        return cls(rules=rules, current_player=view.current_player, pieces=pieces)

    def legal_actions(self) -> tuple[Action, ...]:
        if self.outcome is not None:
            return ()
        occupied = {piece.square: piece for piece in self.pieces}
        actions: list[Action] = []
        for piece in self.pieces:
            if piece.owner is not self.current_player:
                continue
            for vector in self.rules.movement:
                x = piece.square.x + vector.dx
                y = piece.square.y + vector.dy
                if not (0 <= x < self.rules.width and 0 <= y < self.rules.height):
                    continue
                destination = Square(x=x, y=y)
                target = occupied.get(destination)
                if target is None or target.owner is not piece.owner:
                    actions.append(Move(source=piece.square, destination=destination))
            if (
                OutcomeReason.ESCAPE in self.rules.victory_conditions
                and piece.kind is GhostKind.GOOD
                and piece.square in {exit_.square for exit_ in self.rules.exits(piece.owner)}
            ):
                actions.append(Escape(source=piece.square))
        return tuple(actions)

    def play(self, player: Player, action: Action) -> PositionTransition:
        if self.outcome is not None:
            raise PositionError("the position has already finished")
        if player is not self.current_player:
            raise PositionError("the player is not active")
        if action not in self.legal_actions():
            raise PositionError("the action is not legal")
        moving = next(
            piece
            for piece in self.pieces
            if piece.owner is player and piece.square == action.source
        )
        captured: CapturedPiece | None = None
        outcome: GameOutcome | None
        if isinstance(action, Escape):
            pieces = tuple(piece for piece in self.pieces if piece is not moving)
            outcome = GameOutcome(winner=player, reason=OutcomeReason.ESCAPE)
        else:
            target = next(
                (piece for piece in self.pieces if piece.square == action.destination), None
            )
            captured = (
                None if target is None else CapturedPiece(owner=target.owner, kind=target.kind)
            )
            pieces = tuple(
                PositionPiece(owner=piece.owner, kind=piece.kind, square=action.destination)
                if piece is moving
                else piece
                for piece in self.pieces
                if piece is not target
            )
            outcome = self._capture_outcome(player, pieces)
        return PositionTransition(
            position=Position(
                rules=self.rules,
                current_player=player.opponent,
                pieces=pieces,
                outcome=outcome,
            ),
            captured=captured,
        )

    def _capture_outcome(
        self, player: Player, pieces: tuple[PositionPiece, ...]
    ) -> GameOutcome | None:
        if OutcomeReason.CAPTURE_GOOD in self.rules.victory_conditions and not any(
            piece.owner is player.opponent and piece.kind is GhostKind.GOOD for piece in pieces
        ):
            return GameOutcome(winner=player, reason=OutcomeReason.CAPTURE_GOOD)
        if OutcomeReason.SACRIFICE_BAD in self.rules.victory_conditions and not any(
            piece.owner is player.opponent and piece.kind is GhostKind.BAD for piece in pieces
        ):
            return GameOutcome(winner=player.opponent, reason=OutcomeReason.SACRIFICE_BAD)
        return None

    def _on_board(self, square: Square) -> bool:
        return 0 <= square.x < self.rules.width and 0 <= square.y < self.rules.height
