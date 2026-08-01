"""Tests for explicit runtime platform boundaries."""

import pytest
from typer.testing import CliRunner

from pyghostboard import _platform
from pyghostboard.adapters.ai import SubprocessAgent
from pyghostboard.adapters.recording import MatchRecorder
from pyghostboard.cli import app


def test_posix_infrastructure_is_rejected_on_windows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(_platform, "CURRENT_PLATFORM", "win32")

    with pytest.raises(_platform.UnsupportedPlatformError, match="domain API remains supported"):
        MatchRecorder(None)


@pytest.mark.asyncio
async def test_agent_start_is_rejected_on_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(_platform, "CURRENT_PLATFORM", "win32")
    agent = SubprocessAgent(["agent"])

    with pytest.raises(_platform.UnsupportedPlatformError, match="AI process isolation"):
        await agent.__aenter__()


def test_cui_is_rejected_on_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(_platform, "CURRENT_PLATFORM", "win32")

    result = CliRunner().invoke(app, ["play"])

    assert result.exit_code == 2
    assert "domain API remains supported on Windows" in result.stdout
