"""Tests for explicit runtime platform boundaries."""

import pytest
from typer.testing import CliRunner

from pyghostboard import _platform
from pyghostboard.adapters.ai import SubprocessAgentController
from pyghostboard.adapters.recording import MatchRecorder
from pyghostboard.application import PlayerContext
from pyghostboard.cli import create_app
from pyghostboard.domain import Player, RuleSet


def test_posix_infrastructure_is_rejected_on_windows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(_platform, "CURRENT_PLATFORM", "win32")

    with pytest.raises(_platform.UnsupportedPlatformError, match="domain API remains supported"):
        MatchRecorder(None)


@pytest.mark.asyncio
async def test_agent_start_is_rejected_on_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(_platform, "CURRENT_PLATFORM", "win32")
    agent = SubprocessAgentController(["agent"])

    with pytest.raises(_platform.UnsupportedPlatformError, match="AI process isolation"):
        await agent.initialize(PlayerContext(player=Player.ONE, rules=RuleSet.standard(), seed=0))


def test_cui_is_rejected_on_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(_platform, "CURRENT_PLATFORM", "win32")

    result = CliRunner().invoke(create_app("en"), ["play"])

    assert result.exit_code == 2
    assert "domain API remains supported on Windows" in result.stdout
