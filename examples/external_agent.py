"""Minimal shell-free external AI for pyghostboard."""

import sys

from pyghostboard.agents import RandomAgent, run_agent

if __name__ == "__main__":
    run_agent(sys.stdin.buffer, sys.stdout, RandomAgent)
