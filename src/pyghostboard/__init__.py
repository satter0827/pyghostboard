"""Public package metadata for pyghostboard."""

from importlib.metadata import version
from typing import Final

from pyghostboard.agents import (
    AgentPolicy,
    AgentProtocolError,
    InProcessAgentController,
    MctsAgent,
    RandomAgent,
    SearchConfig,
)
from pyghostboard.application import (
    InMemoryMatchStore,
    MatchObserver,
    MatchResult,
    MatchRunner,
    MatchService,
    MatchSpec,
    MatchStore,
    PlayerContext,
    PlayerController,
    PrivateEventSink,
)
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
    "AgentPolicy",
    "AgentProtocolError",
    "Escape",
    "Exit",
    "GameOutcome",
    "GhostKind",
    "InMemoryMatchStore",
    "InProcessAgentController",
    "Match",
    "MatchObserver",
    "MatchResult",
    "MatchRunner",
    "MatchService",
    "MatchSpec",
    "MatchStore",
    "MctsAgent",
    "Move",
    "Placement",
    "Player",
    "PlayerContext",
    "PlayerController",
    "PlayerView",
    "PrivateEventSink",
    "RandomAgent",
    "RuleSet",
    "SearchConfig",
    "Square",
    "__version__",
]

__version__: Final[str] = version("pyghostboard")
