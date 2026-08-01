"""Immutable public values for the game domain."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

RULES_FORMAT_VERSION = "0.1.0"


class DomainModel(BaseModel):
    """Strict, immutable base for public domain values."""

    model_config = ConfigDict(frozen=True, extra="forbid")


class Player(StrEnum):
    ONE = "one"
    TWO = "two"

    @property
    def opponent(self) -> Player:
        return Player.TWO if self is Player.ONE else Player.ONE


class GhostKind(StrEnum):
    GOOD = "good"
    BAD = "bad"


class OutcomeReason(StrEnum):
    ESCAPE = "escape"
    CAPTURE_GOOD = "capture_good"
    SACRIFICE_BAD = "sacrifice_bad"


class RemovalReason(StrEnum):
    CAPTURED = "captured"
    ESCAPED = "escaped"


class Square(DomainModel):
    x: int = Field(ge=0, lt=26)
    y: int = Field(ge=0, lt=26)

    @classmethod
    def parse(cls, value: str) -> Square:
        if len(value) < 2 or not value[0].isalpha() or not value[1:].isdigit():
            raise ValueError(f"invalid square notation: {value!r}")
        return cls(x=ord(value[0].lower()) - ord("a"), y=int(value[1:]) - 1)

    def __str__(self) -> str:
        return f"{chr(ord('a') + self.x)}{self.y + 1}"


class Vector(DomainModel):
    dx: int
    dy: int

    @model_validator(mode="after")
    def not_zero(self) -> Vector:
        if self.dx == 0 and self.dy == 0:
            raise ValueError("a movement vector cannot be zero")
        return self


class Exit(DomainModel):
    square: Square


class Placement(DomainModel):
    good: tuple[Square, ...]
    bad: tuple[Square, ...]

    @model_validator(mode="after")
    def squares_are_unique(self) -> Placement:
        if len(set(self.good + self.bad)) != len(self.good) + len(self.bad):
            raise ValueError("placement squares must be unique")
        return self


class RuleSet(DomainModel):
    format_version: Literal["0.1.0"] = "0.1.0"
    width: int = Field(ge=2, le=26)
    height: int = Field(ge=2, le=26)
    good_count: int = Field(ge=1)
    bad_count: int = Field(ge=1)
    player_one_start: tuple[Square, ...]
    player_two_start: tuple[Square, ...]
    player_one_exits: tuple[Exit, ...]
    player_two_exits: tuple[Exit, ...]
    movement: tuple[Vector, ...] = Field(min_length=1, max_length=16)
    victory_conditions: tuple[OutcomeReason, ...] = (
        OutcomeReason.ESCAPE,
        OutcomeReason.CAPTURE_GOOD,
        OutcomeReason.SACRIFICE_BAD,
    )

    @classmethod
    def standard(cls) -> RuleSet:
        one_start = tuple(Square(x=x, y=y) for y in (0, 1) for x in range(1, 5))
        two_start = tuple(Square(x=x, y=y) for y in (4, 5) for x in range(1, 5))
        return cls(
            width=6,
            height=6,
            good_count=4,
            bad_count=4,
            player_one_start=one_start,
            player_two_start=two_start,
            player_one_exits=(Exit(square=Square(x=0, y=5)), Exit(square=Square(x=5, y=5))),
            player_two_exits=(Exit(square=Square(x=0, y=0)), Exit(square=Square(x=5, y=0))),
            movement=(
                Vector(dx=0, dy=1),
                Vector(dx=1, dy=0),
                Vector(dx=0, dy=-1),
                Vector(dx=-1, dy=0),
            ),
            victory_conditions=(
                OutcomeReason.ESCAPE,
                OutcomeReason.CAPTURE_GOOD,
                OutcomeReason.SACRIFICE_BAD,
            ),
        )

    def start_squares(self, player: Player) -> tuple[Square, ...]:
        return self.player_one_start if player is Player.ONE else self.player_two_start

    def exits(self, player: Player) -> tuple[Exit, ...]:
        return self.player_one_exits if player is Player.ONE else self.player_two_exits

    @model_validator(mode="after")
    def valid_board_configuration(self) -> RuleSet:
        required = self.good_count + self.bad_count
        for label, squares in (
            ("player_one_start", self.player_one_start),
            ("player_two_start", self.player_two_start),
        ):
            if len(squares) != required or len(set(squares)) != required:
                raise ValueError(f"{label} must contain exactly {required} unique squares")
        all_squares = self.player_one_start + self.player_two_start
        exit_squares = tuple(
            exit_.square for exit_ in self.player_one_exits + self.player_two_exits
        )
        if any(
            square.x >= self.width or square.y >= self.height
            for square in all_squares + exit_squares
        ):
            raise ValueError("configured square lies outside the board")
        if not self.player_one_exits or not self.player_two_exits:
            raise ValueError("both players require at least one exit")
        if len(set(self.movement)) != len(self.movement):
            raise ValueError("movement vectors must be unique")
        if len(set(self.victory_conditions)) != len(self.victory_conditions):
            raise ValueError("victory conditions must be unique")
        if not self.victory_conditions:
            raise ValueError("at least one victory condition is required")
        if set(self.player_one_start) & set(self.player_two_start):
            raise ValueError("player starting areas cannot overlap")
        for label, exits in (
            ("player_one_exits", self.player_one_exits),
            ("player_two_exits", self.player_two_exits),
        ):
            if len({exit_.square for exit_ in exits}) != len(exits):
                raise ValueError(f"{label} must contain unique squares")
        return self


class Move(DomainModel):
    type: Literal["move"] = "move"
    source: Square
    destination: Square


class Escape(DomainModel):
    type: Literal["escape"] = "escape"
    source: Square


Action = Annotated[Move | Escape, Field(discriminator="type")]


class GameOutcome(DomainModel):
    winner: Player
    reason: OutcomeReason


class PrivatePiece(DomainModel):
    id: str = Field(min_length=1, max_length=128)
    owner: Player
    kind: GhostKind
    square: Square | None
    removal: RemovalReason | None = None
    removed_at: Square | None = None

    @model_validator(mode="after")
    def location_matches_removal(self) -> PrivatePiece:
        on_board = self.square is not None and self.removal is None and self.removed_at is None
        removed = self.square is None and self.removal is not None and self.removed_at is not None
        if not (on_board or removed):
            raise ValueError("a piece must be either on the board or removed")
        if self.removal is RemovalReason.ESCAPED and self.kind is not GhostKind.GOOD:
            raise ValueError("only a good ghost can escape")
        return self


class OwnPiece(DomainModel):
    id: str
    kind: GhostKind
    square: Square


class CapturedPiece(DomainModel):
    owner: Player
    kind: GhostKind


class PlayerView(DomainModel):
    match_id: UUID
    revision: int = Field(ge=0)
    player: Player
    current_player: Player
    width: int
    height: int
    own_pieces: tuple[OwnPiece, ...]
    opponent_squares: tuple[Square, ...]
    captured: tuple[CapturedPiece, ...]
    legal_actions: tuple[Action, ...]
    outcome: GameOutcome | None


class PrivateMatchSnapshot(DomainModel):
    format_version: Literal["0.1.0"] = "0.1.0"
    match_id: UUID
    revision: int = Field(ge=0)
    rules: RuleSet
    first_player: Player
    current_player: Player
    pieces: tuple[PrivatePiece, ...]
    outcome: GameOutcome | None = None


class MatchStarted(DomainModel):
    type: Literal["match_started"] = "match_started"
    sequence: Literal[0] = 0
    snapshot: PrivateMatchSnapshot


class ActionPlayed(DomainModel):
    type: Literal["action_played"] = "action_played"
    sequence: int = Field(ge=1)
    player: Player
    action: Action
    captured: CapturedPiece | None = None
    outcome: GameOutcome | None = None

    @model_validator(mode="after")
    def event_is_coherent(self) -> ActionPlayed:
        if isinstance(self.action, Escape):
            if self.captured is not None:
                raise ValueError("an escape cannot capture a piece")
            expected = GameOutcome(winner=self.player, reason=OutcomeReason.ESCAPE)
            if self.outcome != expected:
                raise ValueError("an escape must finish with an escape outcome")
            return self
        if self.captured is not None and self.captured.owner is self.player:
            raise ValueError("a player cannot capture its own piece")
        if self.outcome is None:
            return self
        if self.outcome.reason is OutcomeReason.ESCAPE:
            raise ValueError("a move cannot produce an escape outcome")
        if self.captured is None:
            raise ValueError("a capture outcome requires a captured piece")
        if self.outcome.reason is OutcomeReason.CAPTURE_GOOD:
            if self.outcome.winner is not self.player or self.captured.kind is not GhostKind.GOOD:
                raise ValueError("capture_good outcome contradicts the capture")
        elif (
            self.outcome.winner is not self.player.opponent
            or self.captured.kind is not GhostKind.BAD
        ):
            raise ValueError("sacrifice_bad outcome contradicts the capture")
        return self


PrivateMatchEvent = Annotated[MatchStarted | ActionPlayed, Field(discriminator="type")]


class PlayerEvent(DomainModel):
    sequence: int = Field(ge=1)
    kind: Literal["move", "capture", "escape", "finished"]
    actor: Player
    source: Square
    destination: Square | None = None
    captured: CapturedPiece | None = None
    outcome: GameOutcome | None = None
