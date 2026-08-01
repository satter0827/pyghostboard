"""JSON Lines runtime shared by bundled and third-party policy entry points."""

from __future__ import annotations

from collections.abc import Iterable
from typing import TextIO

from pyghostboard.agents.contracts import AgentContext, AgentPolicy, PolicyFactory
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
    for line in source:
        request = request_adapter.validate_json(line)
        response: AgentResponse
        if isinstance(request, InitializeRequest):
            if policy is not None:
                raise RuntimeError("agent was already initialized")
            policy = factory(
                AgentContext(player=request.player, rules=request.rules, seed=request.seed)
            )
            response = ReadyResponse(request_id=request.request_id)
        elif isinstance(request, SetupRequest):
            response = SetupResponse(
                request_id=request.request_id,
                placement=_require_policy(policy).choose_placement(),
            )
        elif isinstance(request, ActionRequest):
            action = _require_policy(policy).choose_action(request.view)
            if action not in request.view.legal_actions:
                raise RuntimeError("agent returned an illegal action")
            response = ActionResponse(request_id=request.request_id, action=action)
        elif isinstance(request, FinishedRequest):
            _require_policy(policy).on_finished(request.view)
            response = ReadyResponse(request_id=request.request_id)
        else:  # pragma: no cover - exhaustive union defense
            raise RuntimeError("unsupported request")
        destination.write(response.model_dump_json() + "\n")
        destination.flush()


def _require_policy(policy: AgentPolicy | None) -> AgentPolicy:
    if policy is None:
        raise RuntimeError("agent was not initialized")
    return policy
