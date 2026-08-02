"""Seeded random decision policy."""

from __future__ import annotations

import random

from pyghostboard.application.runner import PlayerContext
from pyghostboard.domain.models import Action, Placement, PlayerView


class RandomAgent:
    """Choose uniformly from every valid placement or legal action."""

    def __init__(self, context: PlayerContext) -> None:
        self._context = context
        self._random = random.Random(context.seed)

    def choose_placement(self) -> Placement:
        rules = self._context.rules
        starts = list(rules.start_squares(self._context.player))
        good = tuple(self._random.sample(starts, rules.good_count))
        good_set = set(good)
        return Placement(
            good=good, bad=tuple(square for square in starts if square not in good_set)
        )

    def choose_action(self, view: PlayerView) -> Action:
        if view.player is not self._context.player:
            raise ValueError("agent received a view for another player")
        if not view.legal_actions:
            raise ValueError("agent received a view without legal actions")
        return self._random.choice(view.legal_actions)

    def on_finished(self, view: PlayerView) -> None:
        if view.player is not self._context.player or view.outcome is None:
            raise ValueError("agent received an invalid final view")
