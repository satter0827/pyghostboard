"""JSON Lines runtime shared by bundled and third-party policy entry points."""

from __future__ import annotations

from collections.abc import Iterable
from typing import TextIO

from pyghostboard.agents.contracts import (
    AgentContext,
    AgentLifecycle,
    AgentPolicy,
    PolicyFactory,
)
from pyghostboard.protocol import (
    ActionRequest,
    ActionResponse,
    AgentResponse,
    FinishedRequest,
    InitializeRequest,
    ReadyResponse,
    SetupRequest,
    SetupResponse,
    request_adapter,
)


def run_agent(source: Iterable[bytes], destination: TextIO, factory: PolicyFactory) -> None:
    """Serve one policy instance over the versioned wire protocol."""
    policy: AgentPolicy | None = None
    lifecycle = AgentLifecycle()
    for line in source:
        request = request_adapter.validate_json(line)
        response: AgentResponse
        if isinstance(request, InitializeRequest):
            lifecycle.require_initialization()
            context = AgentContext(player=request.player, rules=request.rules, seed=request.seed)
            policy = factory(context)
            lifecycle.initialized(context)
            response = ReadyResponse(request_id=request.request_id)
        elif isinstance(request, SetupRequest):
            lifecycle.require_placement()
            placement = _require_policy(policy).choose_placement()
            lifecycle.placement_chosen(placement)
            response = SetupResponse(
                request_id=request.request_id,
                placement=placement,
            )
        elif isinstance(request, ActionRequest):
            lifecycle.require_action(request.view)
            action = _require_policy(policy).choose_action(request.view)
            lifecycle.action_chosen(request.view, action)
            response = ActionResponse(request_id=request.request_id, action=action)
        elif isinstance(request, FinishedRequest):
            lifecycle.require_finish(request.view)
            _require_policy(policy).on_finished(request.view)
            lifecycle.finished(request.view)
            response = ReadyResponse(request_id=request.request_id)
        else:  # pragma: no cover - exhaustive union defense
            raise RuntimeError("unsupported request")
        destination.write(response.model_dump_json() + "\n")
        destination.flush()


def _require_policy(policy: AgentPolicy | None) -> AgentPolicy:
    if policy is None:
        raise RuntimeError("agent was not initialized")
    return policy
