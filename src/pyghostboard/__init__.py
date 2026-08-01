"""Public package metadata for pyghostboard."""

from importlib.metadata import version
from typing import Final

from pyghostboard.application import InMemoryMatchStore, MatchService, MatchStore
from pyghostboard.domain import (
    Escape,
    Exit,
    GameOutcome,
    GhostKind,
    Match,
    Move,
    Placement,
    Player,
    PlayerView,
    RuleSet,
    Square,
)

__all__ = [
    "Escape",
    "Exit",
    "GameOutcome",
    "GhostKind",
    "InMemoryMatchStore",
    "Match",
    "MatchService",
    "MatchStore",
    "Move",
    "Placement",
    "Player",
    "PlayerView",
    "RuleSet",
    "Square",
    "__version__",
]

__version__: Final[str] = version("pyghostboard")
