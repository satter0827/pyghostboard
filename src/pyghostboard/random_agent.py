"""Executable entry point for the bundled random policy."""

from __future__ import annotations

import sys

from pyghostboard.agents.random import RandomAgent
from pyghostboard.agents.runtime import run_agent


def main() -> None:
    run_agent(sys.stdin.buffer, sys.stdout, RandomAgent)


if __name__ == "__main__":
    main()
