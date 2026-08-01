"""Transport-independent contracts for decision policies and their clients."""

from __future__ import annotations

from collections.abc import Callable
from enum import StrEnum
from typing import Protocol

from pyghostboard.domain.models import Action, DomainModel, Placement, Player, PlayerView, RuleSet


class AgentContext(DomainModel):
    """Public, reproducible information supplied when an agent starts."""

    player: Player
    rules: RuleSet
    seed: int


class AgentPolicy(Protocol):
    """Synchronous decision contract implemented by every AI policy."""

    def choose_placement(self) -> Placement: ...

    def choose_action(self, view: PlayerView) -> Action: ...

    def on_finished(self, view: PlayerView) -> None: ...


PolicyFactory = Callable[[AgentContext], AgentPolicy]


class AgentClient(Protocol):
    """Asynchronous semantic contract used by a trusted game host."""

    async def initialize(self, context: AgentContext) -> None: ...

    async def choose_placement(self) -> Placement: ...

    async def choose_action(self, view: PlayerView) -> Action: ...

    async def finish(self, view: PlayerView) -> None: ...

    async def close(self) -> None: ...


class AgentProtocolError(RuntimeError):
    """Raised when an agent is used outside its lifecycle contract."""


class AgentPhase(StrEnum):
    """Observable phases shared by every agent transport."""

    NEW = "new"
    INITIALIZED = "initialized"
    PLAYING = "playing"
    FINISHED = "finished"
    CLOSED = "closed"


class AgentLifecycle:
    """Validate semantic call order and values independently of transport."""

    def __init__(self) -> None:
        self._phase = AgentPhase.NEW
        self._context: AgentContext | None = None

    @property
    def phase(self) -> AgentPhase:
        return self._phase

    def require_initialization(self) -> None:
        self._require(AgentPhase.NEW, "agent cannot be initialized")

    def initialized(self, context: AgentContext) -> None:
        self.require_initialization()
        self._context = context
        self._phase = AgentPhase.INITIALIZED

    def require_placement(self) -> None:
        self._require(AgentPhase.INITIALIZED, "agent cannot choose a placement")

    def placement_chosen(self, placement: Placement) -> None:
        self.require_placement()
        context = self._require_context()
        rules = context.rules
        if len(placement.good) != rules.good_count or len(placement.bad) != rules.bad_count:
            raise AgentProtocolError("agent returned a placement with invalid piece counts")
        if set(placement.good + placement.bad) != set(rules.start_squares(context.player)):
            raise AgentProtocolError("agent returned a placement outside its starting area")
        self._phase = AgentPhase.PLAYING

    def require_action(self, view: PlayerView) -> None:
        self._require(AgentPhase.PLAYING, "agent cannot choose an action")
        context = self._require_context()
        if view.player is not context.player:
            raise AgentProtocolError("agent received a view for another player")
        if view.current_player is not context.player or view.outcome is not None:
            raise AgentProtocolError("agent received a view outside its active turn")
        if not view.legal_actions:
            raise AgentProtocolError("agent received a view without legal actions")

    def action_chosen(self, view: PlayerView, action: Action) -> None:
        self.require_action(view)
        if action not in view.legal_actions:
            raise AgentProtocolError("agent returned an illegal action")

    def require_finish(self, view: PlayerView) -> None:
        self._require(AgentPhase.PLAYING, "agent cannot finish")
        if view.player is not self._require_context().player:
            raise AgentProtocolError("agent received a final view for another player")
        if view.outcome is None:
            raise AgentProtocolError("agent received an unfinished view")

    def finished(self, view: PlayerView) -> None:
        self.require_finish(view)
        self._phase = AgentPhase.FINISHED

    def require_open(self) -> None:
        if self._phase is AgentPhase.CLOSED:
            raise AgentProtocolError("agent is closed")

    def close(self) -> None:
        self._phase = AgentPhase.CLOSED
        self._context = None

    def _require(self, expected: AgentPhase, message: str) -> None:
        if self._phase is not expected:
            raise AgentProtocolError(f"{message} while {self._phase.value}")

    def _require_context(self) -> AgentContext:
        if self._context is None:  # pragma: no cover - protected by phase checks
            raise AgentProtocolError("agent has no context")
        return self._context


class InProcessAgentClient:
    """Run a policy without transport, primarily for embedding and tests."""

    def __init__(self, factory: PolicyFactory) -> None:
        self._factory = factory
        self._policy: AgentPolicy | None = None
        self._lifecycle = AgentLifecycle()

    async def initialize(self, context: AgentContext) -> None:
        self._lifecycle.require_initialization()
        policy = self._factory(context)
        self._lifecycle.initialized(context)
        self._policy = policy

    async def choose_placement(self) -> Placement:
        self._lifecycle.require_placement()
        placement = self._require_policy().choose_placement()
        self._lifecycle.placement_chosen(placement)
        return placement

    async def choose_action(self, view: PlayerView) -> Action:
        self._lifecycle.require_action(view)
        action = self._require_policy().choose_action(view)
        self._lifecycle.action_chosen(view, action)
        return action

    async def finish(self, view: PlayerView) -> None:
        self._lifecycle.require_finish(view)
        self._require_policy().on_finished(view)
        self._lifecycle.finished(view)

    async def close(self) -> None:
        self._policy = None
        self._lifecycle.close()

    def _require_policy(self) -> AgentPolicy:
        if self._policy is None:
            raise AgentProtocolError("agent was not initialized")
        return self._policy
