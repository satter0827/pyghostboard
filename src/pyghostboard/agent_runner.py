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
    arguments = parser.parse_args()
    if arguments.policy == "random":
        run_agent(sys.stdin.buffer, sys.stdout, RandomAgent)
        return
    settings = RuntimeSettings()
    config = SearchConfig(
        iterations=settings.ai_iterations,
        exploration_weight=settings.ai_exploration_weight,
        rollout_plies=settings.ai_rollout_plies,
        setup_candidate_limit=settings.ai_setup_candidate_limit,
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
