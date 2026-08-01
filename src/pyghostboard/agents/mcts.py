"""Information-set Monte Carlo tree search policy for Geister."""

from __future__ import annotations

import math
import random
from collections import defaultdict
from dataclasses import dataclass
from itertools import combinations

from pyghostboard.agents.contracts import AgentContext
from pyghostboard.domain.match import Match
from pyghostboard.domain.models import (
    Action,
    GhostKind,
    Placement,
    PlayerView,
    PrivateMatchSnapshot,
    PrivatePiece,
    RemovalReason,
    Square,
)


@dataclass(frozen=True, slots=True)
class SearchConfig:
    """Deterministic search limits and UCT tuning."""

    iterations: int = 256
    exploration_weight: float = math.sqrt(2.0)
    rollout_plies: int = 96
    setup_candidate_limit: int = 256

    def __post_init__(self) -> None:
        if self.iterations < 1 or self.rollout_plies < 1 or self.setup_candidate_limit < 1:
            raise ValueError("search limits must be positive")
        if self.exploration_weight < 0:
            raise ValueError("exploration weight cannot be negative")


@dataclass(slots=True)
class _Statistics:
    visits: int = 0
    value: float = 0.0


class MctsAgent:
    """Search public information across sampled hidden-piece assignments."""

    def __init__(self, context: AgentContext, config: SearchConfig | None = None) -> None:
        self._context = context
        self._config = config or SearchConfig()
        self._random = random.Random(context.seed)

    def choose_placement(self) -> Placement:
        rules = self._context.rules
        starts = rules.start_squares(self._context.player)
        candidates = list(combinations(starts, rules.good_count))
        if len(candidates) > self._config.setup_candidate_limit:
            candidates = self._random.sample(candidates, self._config.setup_candidate_limit)
        exits = tuple(exit_.square for exit_ in rules.exits(self._context.player))
        scored = [(self._placement_score(good, exits), good) for good in candidates]
        best_score = max(score for score, _ in scored)
        best = [good for score, good in scored if score == best_score]
        good = tuple(self._random.choice(best))
        good_set = set(good)
        return Placement(
            good=good, bad=tuple(square for square in starts if square not in good_set)
        )

    def choose_action(self, view: PlayerView) -> Action:
        if view.player is not self._context.player:
            raise ValueError("agent received a view for another player")
        if not view.legal_actions:
            raise ValueError("agent received a view without legal actions")
        if len(view.legal_actions) == 1:
            return view.legal_actions[0]

        statistics: defaultdict[tuple[Action, ...], _Statistics] = defaultdict(_Statistics)
        for _ in range(self._config.iterations):
            match = self._determinize(view)
            path: tuple[Action, ...] = ()
            visited: list[tuple[Action, ...]] = []
            for _depth in range(self._config.rollout_plies):
                if match.outcome is not None:
                    break
                legal = match.legal_actions()
                if not legal:
                    break
                unexplored = [action for action in legal if statistics[(*path, action)].visits == 0]
                if unexplored:
                    action = self._random.choice(unexplored)
                    path += (action,)
                    visited.append(path)
                    match = match.play(match.current_player, action).match
                    match = self._rollout(match, self._config.rollout_plies - _depth - 1)
                    break
                parent_visits = max(1, statistics[path].visits)
                action = max(
                    legal,
                    key=lambda candidate: self._uct(
                        statistics[(*path, candidate)],
                        parent_visits,
                        maximize=match.current_player is self._context.player,
                    ),
                )
                path += (action,)
                visited.append(path)
                match = match.play(match.current_player, action).match
            reward = self._evaluate(match)
            statistics[()].visits += 1
            statistics[()].value += reward
            for key in visited:
                statistics[key].visits += 1
                statistics[key].value += reward

        return max(
            view.legal_actions,
            key=lambda action: (
                statistics[(action,)].visits,
                statistics[(action,)].value / max(1, statistics[(action,)].visits),
            ),
        )

    def on_finished(self, view: PlayerView) -> None:
        if view.player is not self._context.player or view.outcome is None:
            raise ValueError("agent received an invalid final view")

    def _determinize(self, view: PlayerView) -> Match:
        rules = self._context.rules
        captured = list(view.captured)
        captured_opponent_good = sum(
            piece.owner is view.player.opponent and piece.kind is GhostKind.GOOD
            for piece in captured
        )
        captured_opponent_bad = sum(
            piece.owner is view.player.opponent and piece.kind is GhostKind.BAD
            for piece in captured
        )
        remaining_good = rules.good_count - captured_opponent_good
        remaining_bad = rules.bad_count - captured_opponent_bad
        if remaining_good < 0 or remaining_bad < 0:
            raise ValueError("view has impossible captured-piece counts")
        if remaining_good + remaining_bad != len(view.opponent_squares):
            raise ValueError("view has an impossible number of opposing pieces")
        good_squares = set(self._random.sample(list(view.opponent_squares), remaining_good))

        pieces = [
            PrivatePiece(id=piece.id, owner=view.player, kind=piece.kind, square=piece.square)
            for piece in view.own_pieces
        ]
        for index, square in enumerate(view.opponent_squares, start=1):
            pieces.append(
                PrivatePiece(
                    id=f"hypothesis-{view.player.opponent.value}-{index}",
                    owner=view.player.opponent,
                    kind=GhostKind.GOOD if square in good_squares else GhostKind.BAD,
                    square=square,
                )
            )
        removed_at = Square(x=0, y=0)
        for index, piece in enumerate(captured, start=1):
            pieces.append(
                PrivatePiece(
                    id=f"hypothesis-captured-{piece.owner.value}-{piece.kind.value}-{index}",
                    owner=piece.owner,
                    kind=piece.kind,
                    square=None,
                    removal=RemovalReason.CAPTURED,
                    removed_at=removed_at,
                )
            )
        expected_total = 2 * (rules.good_count + rules.bad_count)
        if len(pieces) != expected_total:
            raise ValueError("view does not account for every configured piece")
        first_player = (
            view.current_player if view.revision % 2 == 0 else view.current_player.opponent
        )
        return Match.restore(
            PrivateMatchSnapshot(
                match_id=view.match_id,
                revision=view.revision,
                rules=rules,
                first_player=first_player,
                current_player=view.current_player,
                pieces=tuple(pieces),
                outcome=view.outcome,
            )
        )

    def _rollout(self, match: Match, remaining: int) -> Match:
        for _ in range(remaining):
            if match.outcome is not None:
                break
            legal = match.legal_actions()
            if not legal:
                break
            match = match.play(match.current_player, self._random.choice(legal)).match
        return match

    def _evaluate(self, match: Match) -> float:
        if match.outcome is not None:
            return 1.0 if match.outcome.winner is self._context.player else -1.0
        snapshot = match.snapshot()
        own = [p for p in snapshot.pieces if p.owner is self._context.player and p.square]
        opposing = [
            p for p in snapshot.pieces if p.owner is self._context.player.opponent and p.square
        ]
        own_good = sum(piece.kind is GhostKind.GOOD for piece in own)
        own_bad = sum(piece.kind is GhostKind.BAD for piece in own)
        opposing_good = sum(piece.kind is GhostKind.GOOD for piece in opposing)
        opposing_bad = sum(piece.kind is GhostKind.BAD for piece in opposing)
        score = (own_good - opposing_good) + (opposing_bad - own_bad) * 0.5
        return math.tanh(score / max(1, self._context.rules.good_count)) * 0.5

    def _uct(self, statistics: _Statistics, parent_visits: int, *, maximize: bool) -> float:
        exploitation = statistics.value / statistics.visits
        exploration = self._config.exploration_weight * math.sqrt(
            math.log(parent_visits) / statistics.visits
        )
        return (exploitation if maximize else -exploitation) + exploration

    @staticmethod
    def _placement_score(good: tuple[Square, ...], exits: tuple[Square, ...]) -> tuple[int, int]:
        distance = sum(
            min(abs(square.x - exit_.x) + abs(square.y - exit_.y) for exit_ in exits)
            for square in good
        )
        spread = len({square.x for square in good}) + len({square.y for square in good})
        return (-distance, spread)
