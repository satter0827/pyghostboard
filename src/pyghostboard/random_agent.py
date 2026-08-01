"""Bundled random agent using only the public JSON Lines protocol."""

from __future__ import annotations

import argparse
import random
import sys
from collections.abc import Iterable
from typing import TextIO

from pyghostboard.domain.models import Placement, Player, RuleSet
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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()
    run(sys.stdin.buffer, sys.stdout, args.seed)


def run(source: Iterable[bytes], destination: TextIO, seed: int) -> None:
    randomizer = random.Random(seed)
    rules: RuleSet | None = None
    player: Player | None = None
    initialized = False
    for line in source:
        request = request_adapter.validate_json(line)
        response: AgentResponse
        if isinstance(request, InitializeRequest):
            if initialized:
                raise RuntimeError("agent was already initialized")
            rules = request.rules
            player = request.player
            initialized = True
            randomizer.seed(request.seed)
            response = ReadyResponse(request_id=request.request_id)
        elif isinstance(request, SetupRequest):
            if rules is None or player is None:
                raise RuntimeError("agent was not initialized")
            starts = list(rules.start_squares(player))
            good = tuple(randomizer.sample(starts, rules.good_count))
            bad = tuple(square for square in starts if square not in good)
            response = SetupResponse(
                request_id=request.request_id,
                placement=Placement(good=good, bad=bad),
            )
        elif isinstance(request, ActionRequest):
            if rules is None or player is None or request.view.player is not player:
                raise RuntimeError("agent received an action request for the wrong player")
            if not request.view.legal_actions:
                raise RuntimeError("no legal action was supplied")
            response = ActionResponse(
                request_id=request.request_id,
                action=randomizer.choice(request.view.legal_actions),
            )
        elif isinstance(request, FinishedRequest):
            if not initialized:
                raise RuntimeError("agent was not initialized")
            response = ReadyResponse(request_id=request.request_id)
        else:  # pragma: no cover - exhaustive union defense
            raise RuntimeError("unsupported request")
        destination.write(response.model_dump_json() + "\n")
        destination.flush()


if __name__ == "__main__":
    main()
