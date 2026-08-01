"""Subprocess isolation and bundled-agent integration tests."""

import os
import sys
import time
from uuid import UUID

import pytest

from pyghostboard.adapters.ai import AgentFailure, SubprocessAgent
from pyghostboard.domain import Player, RuleSet
from pyghostboard.protocol import InitializeRequest, ReadyResponse, SetupRequest, SetupResponse


def test_agent_configuration_rejects_empty_commands_and_invalid_limits() -> None:
    with pytest.raises(ValueError, match="cannot be empty"):
        SubprocessAgent([])
    with pytest.raises(ValueError, match="limits"):
        SubprocessAgent([sys.executable], timeout=0)


@pytest.mark.asyncio
async def test_bundled_agent_initializes_and_returns_valid_setup() -> None:
    command = [sys.executable, "-m", "pyghostboard.random_agent", "--seed", "7"]
    async with SubprocessAgent(command) as agent:
        ready = await agent.request(
            InitializeRequest(
                request_id=UUID("00000000-0000-0000-0000-000000000010"),
                seed=7,
                player=Player.TWO,
                rules=RuleSet.standard(),
            )
        )
        setup = await agent.request(
            SetupRequest(request_id=UUID("00000000-0000-0000-0000-000000000011"))
        )

    assert isinstance(ready, ReadyResponse)
    assert isinstance(setup, SetupResponse)
    assert len(setup.placement.good) == 4
    assert set(setup.placement.good + setup.placement.bad) == set(
        RuleSet.standard().start_squares(Player.TWO)
    )


@pytest.mark.asyncio
async def test_invalid_agent_response_is_rejected() -> None:
    command = [sys.executable, "-c", "print('not-json', flush=True)"]
    async with SubprocessAgent(command, timeout=1) as agent:
        with pytest.raises(AgentFailure, match="invalid response"):
            await agent.request(
                SetupRequest(request_id=UUID("00000000-0000-0000-0000-000000000012"))
            )


@pytest.mark.asyncio
async def test_agent_timeout_is_rejected_and_process_is_closed() -> None:
    command = [sys.executable, "-c", "import time; time.sleep(1)"]
    async with SubprocessAgent(command, timeout=0.01) as agent:
        with pytest.raises(AgentFailure, match="timed out"):
            await agent.request(
                SetupRequest(request_id=UUID("00000000-0000-0000-0000-000000000013"))
            )


@pytest.mark.asyncio
async def test_agent_message_size_is_limited() -> None:
    command = [sys.executable, "-c", "print('x' * 100, flush=True)"]
    async with SubprocessAgent(command, timeout=1, max_message_bytes=16) as agent:
        with pytest.raises(AgentFailure, match="size limit"):
            await agent.request(
                SetupRequest(request_id=UUID("00000000-0000-0000-0000-000000000014"))
            )


@pytest.mark.asyncio
async def test_agent_abnormal_exit_is_reported() -> None:
    command = [sys.executable, "-c", "raise SystemExit(7)"]
    async with SubprocessAgent(command, timeout=1) as agent:
        with pytest.raises(AgentFailure, match="exited before responding"):
            await agent.request(
                SetupRequest(request_id=UUID("00000000-0000-0000-0000-000000000015"))
            )


@pytest.mark.asyncio
async def test_agent_stderr_is_drained_and_bounded() -> None:
    program = """
import json
import sys
request = json.loads(sys.stdin.readline())
sys.stderr.write("x" * 100_000)
sys.stderr.flush()
print(json.dumps({
    "type": "ready",
    "protocol_version": "0.1.0",
    "request_id": request["request_id"],
}), flush=True)
"""
    request_id = UUID("00000000-0000-0000-0000-000000000016")
    async with SubprocessAgent(
        [sys.executable, "-c", program], timeout=1, max_stderr_bytes=1_024
    ) as agent:
        response = await agent.request(SetupRequest(request_id=request_id))
        assert response.request_id == request_id
    assert len(agent.stderr) == 1_024


@pytest.mark.asyncio
async def test_agent_process_group_is_removed_on_close() -> None:
    program = """
import json
import subprocess
import sys
import time
child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
print(child.pid, file=sys.stderr, flush=True)
request = json.loads(sys.stdin.readline())
print(json.dumps({
    "type": "ready",
    "protocol_version": "0.1.0",
    "request_id": request["request_id"],
}), flush=True)
time.sleep(30)
"""
    agent = SubprocessAgent([sys.executable, "-c", program], timeout=1)
    async with agent:
        await agent.request(SetupRequest(request_id=UUID("00000000-0000-0000-0000-000000000017")))
    child_pid = int(agent.stderr.decode().strip())
    deadline = time.monotonic() + 1
    while time.monotonic() < deadline:
        try:
            os.kill(child_pid, 0)
        except ProcessLookupError:
            break
        time.sleep(0.01)
    else:
        pytest.fail("agent descendant remained after process-group cleanup")


@pytest.mark.asyncio
async def test_agent_rejects_mismatched_response_id_and_invalid_lifecycle() -> None:
    request_id = UUID("00000000-0000-0000-0000-000000000018")
    wrong_id = UUID("00000000-0000-0000-0000-000000000019")
    program = (
        "import json,sys; sys.stdin.readline(); "
        f"print(json.dumps({{'type':'ready','protocol_version':'0.1.0',"
        f"'request_id':'{wrong_id}'}}), flush=True)"
    )
    agent = SubprocessAgent([sys.executable, "-c", program], timeout=1)
    with pytest.raises(AgentFailure, match="not running"):
        await agent.request(SetupRequest(request_id=request_id))
    async with agent:
        with pytest.raises(AgentFailure, match="request_id"):
            await agent.request(SetupRequest(request_id=request_id))
        with pytest.raises(AgentFailure, match="already running"):
            await agent.__aenter__()
    await agent.close()
