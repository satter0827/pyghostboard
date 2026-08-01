"""Transport-independent contracts for decision policies and their clients."""

from __future__ import annotations

from collections.abc import Callable
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


class InProcessAgentClient:
    """Run a policy without transport, primarily for embedding and tests."""

    def __init__(self, factory: PolicyFactory) -> None:
        self._factory = factory
        self._policy: AgentPolicy | None = None

    async def initialize(self, context: AgentContext) -> None:
        if self._policy is not None:
            raise AgentProtocolError("agent was already initialized")
        self._policy = self._factory(context)

    async def choose_placement(self) -> Placement:
        return self._require_policy().choose_placement()

    async def choose_action(self, view: PlayerView) -> Action:
        policy = self._require_policy()
        action = policy.choose_action(view)
        if action not in view.legal_actions:
            raise AgentProtocolError("agent returned an illegal action")
        return action

    async def finish(self, view: PlayerView) -> None:
        if view.outcome is None:
            raise AgentProtocolError("agent received an unfinished view")
        self._require_policy().on_finished(view)

    async def close(self) -> None:
        self._policy = None

    def _require_policy(self) -> AgentPolicy:
        if self._policy is None:
            raise AgentProtocolError("agent was not initialized")
        return self._policy
