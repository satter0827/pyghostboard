"""Executable entry point for the bundled MCTS policy."""

from __future__ import annotations

import sys

from pyghostboard.adapters.config import RuntimeSettings
from pyghostboard.agents.mcts import MctsAgent, SearchConfig
from pyghostboard.agents.runtime import run_agent


def main() -> None:
    settings = RuntimeSettings()
    config = SearchConfig(
        iterations=settings.ai_iterations,
        exploration_weight=settings.ai_exploration_weight,
        rollout_plies=settings.ai_rollout_plies,
        setup_candidate_limit=settings.ai_setup_candidate_limit,
    )
    run_agent(sys.stdin.buffer, sys.stdout, lambda context: MctsAgent(context, config))


if __name__ == "__main__":
    main()
