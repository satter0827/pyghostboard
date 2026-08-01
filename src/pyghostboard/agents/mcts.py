"""Information-set Monte Carlo tree search policy for Geister."""

from __future__ import annotations

import math
import random
from collections import defaultdict
from dataclasses import dataclass
from itertools import combinations

from pyghostboard.application.runner import PlayerContext
from pyghostboard.domain.models import (
    Action,
    GhostKind,
    Placement,
    PlayerView,
    Square,
)
from pyghostboard.domain.position import Position


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

    def __init__(self, context: PlayerContext, config: SearchConfig | None = None) -> None:
        self._context = context
        self._config = config or SearchConfig()
        self._random = random.Random(context.seed)

    def choose_placement(self) -> Placement:
        rules = self._context.rules
        starts = rules.start_squares(self._context.player)
        candidates = self._placement_candidates(starts, rules.good_count)
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
            position = self._determinize(view)
            path: tuple[Action, ...] = ()
            visited: list[tuple[Action, ...]] = []
            for _depth in range(self._config.rollout_plies):
                if position.outcome is not None:
                    break
                legal = position.legal_actions()
                if not legal:
                    break
                unexplored = [action for action in legal if statistics[(*path, action)].visits == 0]
                if unexplored:
                    action = self._random.choice(unexplored)
                    path += (action,)
                    visited.append(path)
                    position = position.play(position.current_player, action).position
                    position = self._rollout(position, self._config.rollout_plies - _depth - 1)
                    break
                parent_visits = max(1, statistics[path].visits)
                action = max(
                    legal,
                    key=lambda candidate: self._uct(
                        statistics[(*path, candidate)],
                        parent_visits,
                        maximize=position.current_player is self._context.player,
                    ),
                )
                path += (action,)
                visited.append(path)
                position = position.play(position.current_player, action).position
            reward = self._evaluate(position)
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

    def _determinize(self, view: PlayerView) -> Position:
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

        return Position.from_view(
            view,
            rules,
            {
                square: GhostKind.GOOD if square in good_squares else GhostKind.BAD
                for square in view.opponent_squares
            },
        )

    def _rollout(self, position: Position, remaining: int) -> Position:
        for _ in range(remaining):
            if position.outcome is not None:
                break
            legal = position.legal_actions()
            if not legal:
                break
            position = position.play(position.current_player, self._random.choice(legal)).position
        return position

    def _evaluate(self, position: Position) -> float:
        if position.outcome is not None:
            return 1.0 if position.outcome.winner is self._context.player else -1.0
        own = [p for p in position.pieces if p.owner is self._context.player]
        opposing = [p for p in position.pieces if p.owner is self._context.player.opponent]
        own_good = sum(piece.kind is GhostKind.GOOD for piece in own)
        own_bad = sum(piece.kind is GhostKind.BAD for piece in own)
        opposing_good = sum(piece.kind is GhostKind.GOOD for piece in opposing)
        opposing_bad = sum(piece.kind is GhostKind.BAD for piece in opposing)
        score = (own_good - opposing_good) + (opposing_bad - own_bad) * 0.5
        return math.tanh(score / max(1, self._context.rules.good_count)) * 0.5

    def _placement_candidates(
        self, starts: tuple[Square, ...], good_count: int
    ) -> list[tuple[Square, ...]]:
        total = math.comb(len(starts), good_count)
        limit = min(total, self._config.setup_candidate_limit)
        if total <= limit:
            return list(combinations(starts, good_count))
        ranks: set[int] = set()
        for upper in range(total - limit, total):
            candidate = self._random.randrange(upper + 1)
            ranks.add(upper if candidate in ranks else candidate)
        return [self._unrank_combination(starts, good_count, rank) for rank in sorted(ranks)]

    @staticmethod
    def _unrank_combination(values: tuple[Square, ...], size: int, rank: int) -> tuple[Square, ...]:
        selected: list[Square] = []
        start = 0
        for remaining in range(size, 0, -1):
            for index in range(start, len(values)):
                suffixes = math.comb(len(values) - index - 1, remaining - 1)
                if rank < suffixes:
                    selected.append(values[index])
                    start = index + 1
                    break
                rank -= suffixes
        return tuple(selected)

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
