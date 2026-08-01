"""Executable JSON Lines entry point for bundled policies."""

from __future__ import annotations

import argparse
import sys

from pyghostboard.adapters.config import RuntimeSettings
from pyghostboard.agents.mcts import MctsAgent, SearchConfig
from pyghostboard.agents.random import RandomAgent
from pyghostboard.agents.runtime import run_agent
from pyghostboard.application.runner import PlayerContext


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", choices=("mcts", "random"), required=True)
    parser.add_argument("--iterations", type=int)
    parser.add_argument("--exploration-weight", type=float)
    parser.add_argument("--rollout-plies", type=int)
    parser.add_argument("--setup-candidate-limit", type=int)
    arguments = parser.parse_args()
    if arguments.policy == "random":
        run_agent(sys.stdin.buffer, sys.stdout, RandomAgent)
        return
    settings = RuntimeSettings()
    config = SearchConfig(
        iterations=(
            arguments.iterations if arguments.iterations is not None else settings.ai_iterations
        ),
        exploration_weight=(
            arguments.exploration_weight
            if arguments.exploration_weight is not None
            else settings.ai_exploration_weight
        ),
        rollout_plies=(
            arguments.rollout_plies
            if arguments.rollout_plies is not None
            else settings.ai_rollout_plies
        ),
        setup_candidate_limit=(
            arguments.setup_candidate_limit
            if arguments.setup_candidate_limit is not None
            else settings.ai_setup_candidate_limit
        ),
    )
    run_agent(
        sys.stdin.buffer,
        sys.stdout,
        lambda context: _mcts_policy(context, config),
    )


def _mcts_policy(context: PlayerContext, config: SearchConfig) -> MctsAgent:
    return MctsAgent(context, config)


if __name__ == "__main__":
    main()
