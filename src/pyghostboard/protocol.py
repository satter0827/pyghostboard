"""Versioned JSON Lines protocol for isolated AI processes."""

from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, TypeAdapter

from pyghostboard.domain.models import Action, DomainModel, Placement, Player, PlayerView, RuleSet

PROTOCOL_VERSION = "0.1.0"


class InitializeRequest(DomainModel):
    type: Literal["initialize"] = "initialize"
    protocol_version: Literal["0.1.0"] = "0.1.0"
    request_id: UUID
    seed: int
    player: Player
    rules: RuleSet


class SetupRequest(DomainModel):
    type: Literal["setup_request"] = "setup_request"
    protocol_version: Literal["0.1.0"] = "0.1.0"
    request_id: UUID


class ActionRequest(DomainModel):
    type: Literal["action_request"] = "action_request"
    protocol_version: Literal["0.1.0"] = "0.1.0"
    request_id: UUID
    view: PlayerView


class FinishedRequest(DomainModel):
    type: Literal["finished"] = "finished"
    protocol_version: Literal["0.1.0"] = "0.1.0"
    request_id: UUID
    view: PlayerView


AgentRequest = Annotated[
    InitializeRequest | SetupRequest | ActionRequest | FinishedRequest,
    Field(discriminator="type"),
]


class ReadyResponse(DomainModel):
    type: Literal["ready"] = "ready"
    protocol_version: Literal["0.1.0"] = "0.1.0"
    request_id: UUID


class SetupResponse(DomainModel):
    type: Literal["setup"] = "setup"
    protocol_version: Literal["0.1.0"] = "0.1.0"
    request_id: UUID
    placement: Placement


class ActionResponse(DomainModel):
    type: Literal["action"] = "action"
    protocol_version: Literal["0.1.0"] = "0.1.0"
    request_id: UUID
    action: Action


AgentResponse = Annotated[
    ReadyResponse | SetupResponse | ActionResponse, Field(discriminator="type")
]

request_adapter: TypeAdapter[AgentRequest] = TypeAdapter(AgentRequest)
response_adapter: TypeAdapter[AgentResponse] = TypeAdapter(AgentResponse)
