"""CLI-specific configuration resolution."""

from __future__ import annotations

from pathlib import Path

from pyghostboard.adapters.ai import bundled_agent_command
from pyghostboard.adapters.config import load_rules
from pyghostboard.domain.models import RuleSet


def resolve_rules(path: Path | None) -> RuleSet:
    """Load explicit rules or use the standard game."""
    return RuleSet.standard() if path is None else load_rules(path)


def resolve_agent_command(agent: str | None, command: list[str] | None) -> list[str]:
    """Resolve exactly one built-in policy or shell-free external argument vector."""
    if command:
        if agent is not None:
            raise ValueError("--agent and --command cannot be combined")
        return command
    return bundled_agent_command(agent)


__all__ = ["resolve_agent_command", "resolve_rules"]
