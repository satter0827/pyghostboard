"""Subprocess isolation and bundled-agent integration tests."""

import asyncio
import os
import sys
import time
from uuid import UUID

import pytest

from pyghostboard.adapters.ai import AgentFailure, SubprocessAgent
from pyghostboard.agents import (
    AgentContext,
    AgentPolicy,
    AgentProtocolError,
    MctsAgent,
    RandomAgent,
    SearchConfig,
)
from pyghostboard.domain import GameOutcome, Match, OutcomeReason, Placement, Player, RuleSet

CONTEXT = AgentContext(player=Player.TWO, rules=RuleSet.standard(), seed=7)


def test_agent_configuration_rejects_empty_commands_and_invalid_limits() -> None:
    with pytest.raises(ValueError, match="cannot be empty"):
        SubprocessAgent([])
    with pytest.raises(ValueError, match="limits"):
        SubprocessAgent([sys.executable], timeout=0)


@pytest.mark.asyncio
async def test_bundled_agent_initializes_and_returns_valid_setup() -> None:
    command = [sys.executable, "-m", "pyghostboard.random_agent"]
    async with SubprocessAgent(command) as agent:
        await agent.initialize(CONTEXT)
        setup = await agent.choose_placement()

    assert len(setup.good) == 4
    assert set(setup.good + setup.bad) == set(RuleSet.standard().start_squares(Player.TWO))


@pytest.mark.asyncio
async def test_bundled_mcts_agent_uses_the_semantic_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PYGHOSTBOARD_AI_ITERATIONS", "8")
    monkeypatch.setenv("PYGHOSTBOARD_AI_ROLLOUT_PLIES", "8")
    rules = RuleSet.standard()
    one = rules.start_squares(Player.ONE)
    two = rules.start_squares(Player.TWO)
    match = Match.start(
        UUID("00000000-0000-0000-0000-000000000028"),
        rules,
        {
            Player.ONE: Placement(good=one[:4], bad=one[4:]),
            Player.TWO: Placement(good=two[:4], bad=two[4:]),
        },
    )
    match = match.play(Player.ONE, match.legal_actions()[0]).match

    async with SubprocessAgent([sys.executable, "-m", "pyghostboard.mcts_agent"]) as agent:
        await agent.initialize(CONTEXT)
        assert len((await agent.choose_placement()).good) == rules.good_count
        assert await agent.choose_action(match.view_for(Player.TWO)) in match.legal_actions()


@pytest.mark.asyncio
async def test_semantic_agent_client_completes_its_lifecycle() -> None:
    rules = RuleSet.standard()
    one = rules.start_squares(Player.ONE)
    two = rules.start_squares(Player.TWO)
    match = Match.start(
        UUID("00000000-0000-0000-0000-000000000029"),
        rules,
        {
            Player.ONE: Placement(good=one[:4], bad=one[4:]),
            Player.TWO: Placement(good=two[:4], bad=two[4:]),
        },
    )
    match = match.play(Player.ONE, match.legal_actions()[0]).match

    async with SubprocessAgent([sys.executable, "-m", "pyghostboard.random_agent"]) as agent:
        await agent.initialize(AgentContext(player=Player.TWO, rules=rules, seed=29))
        assert len((await agent.choose_placement()).good) == rules.good_count
        assert await agent.choose_action(match.view_for(Player.TWO)) in match.legal_actions()
        final_view = match.view_for(Player.TWO).model_copy(
            update={
                "outcome": GameOutcome(
                    winner=Player.ONE,
                    reason=OutcomeReason.CAPTURE_GOOD,
                )
            }
        )
        await agent.finish(final_view)


@pytest.mark.asyncio
async def test_subprocess_client_rejects_invalid_semantic_order() -> None:
    rules = RuleSet.standard()
    one = rules.start_squares(Player.ONE)
    two = rules.start_squares(Player.TWO)
    match = Match.start(
        UUID("00000000-0000-0000-0000-000000000031"),
        rules,
        {
            Player.ONE: Placement(good=one[:4], bad=one[4:]),
            Player.TWO: Placement(good=two[:4], bad=two[4:]),
        },
    )
    match = match.play(Player.ONE, match.legal_actions()[0]).match
    view = match.view_for(Player.TWO)
    final_view = view.model_copy(
        update={"outcome": GameOutcome(winner=Player.ONE, reason=OutcomeReason.CAPTURE_GOOD)}
    )

    async with SubprocessAgent([sys.executable, "-m", "pyghostboard.random_agent"]) as agent:
        await agent.initialize(CONTEXT)
        with pytest.raises(AgentProtocolError, match="while initialized"):
            await agent.choose_action(view)
        await agent.choose_placement()
        with pytest.raises(AgentProtocolError, match="while playing"):
            await agent.choose_placement()
        await agent.finish(final_view)
        with pytest.raises(AgentProtocolError, match="while finished"):
            await agent.choose_action(view)


@pytest.mark.asyncio
async def test_subprocess_client_serializes_concurrent_lifecycle_calls() -> None:
    async with SubprocessAgent([sys.executable, "-m", "pyghostboard.random_agent"]) as agent:
        await agent.initialize(CONTEXT)
        results = await asyncio.gather(
            agent.choose_placement(), agent.choose_placement(), return_exceptions=True
        )

    assert sum(isinstance(result, Placement) for result in results) == 1
    assert sum(isinstance(result, AgentProtocolError) for result in results) == 1


def _play_policy_match(seed: int, mcts_player: Player) -> Player:
    rules = RuleSet.standard()
    mcts = MctsAgent(
        AgentContext(player=mcts_player, rules=rules, seed=seed),
        SearchConfig(iterations=16, rollout_plies=16),
    )
    random_player = mcts_player.opponent
    random_agent = RandomAgent(AgentContext(player=random_player, rules=rules, seed=seed + 1_000))
    policies: dict[Player, AgentPolicy] = {
        mcts_player: mcts,
        random_player: random_agent,
    }
    match = Match.start(
        UUID(int=seed + 1),
        rules,
        {player: policies[player].choose_placement() for player in Player},
    )

    for _ in range(300):
        if match.outcome is not None:
            break
        view = match.view_for(match.current_player)
        action = policies[match.current_player].choose_action(view)
        match = match.play(match.current_player, action).match

    assert match.outcome is not None
    return match.outcome.winner


def test_mcts_scores_at_least_sixty_percent_against_random() -> None:
    wins = sum(_play_policy_match(seed, side) is side for seed in range(5) for side in Player)

    assert wins >= 6


@pytest.mark.asyncio
async def test_invalid_agent_response_is_rejected() -> None:
    command = [sys.executable, "-c", "print('not-json', flush=True)"]
    async with SubprocessAgent(command, timeout=1) as agent:
        with pytest.raises(AgentFailure, match="invalid response"):
            await agent.initialize(CONTEXT)


@pytest.mark.asyncio
async def test_agent_timeout_is_rejected_and_process_is_closed() -> None:
    command = [sys.executable, "-c", "import time; time.sleep(1)"]
    async with SubprocessAgent(command, timeout=0.01) as agent:
        with pytest.raises(AgentFailure, match="timed out"):
            await agent.initialize(CONTEXT)


@pytest.mark.asyncio
async def test_agent_message_size_is_limited() -> None:
    command = [sys.executable, "-c", "print('x' * 100, flush=True)"]
    async with SubprocessAgent(command, timeout=1, max_message_bytes=16) as agent:
        with pytest.raises(AgentFailure, match="size limit"):
            await agent.initialize(CONTEXT)


@pytest.mark.asyncio
async def test_agent_abnormal_exit_is_reported() -> None:
    command = [sys.executable, "-c", "raise SystemExit(7)"]
    async with SubprocessAgent(command, timeout=1) as agent:
        with pytest.raises(AgentFailure, match="exited before responding"):
            await agent.initialize(CONTEXT)


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
    async with SubprocessAgent(
        [sys.executable, "-c", program], timeout=1, max_stderr_bytes=1_024
    ) as agent:
        await agent.initialize(CONTEXT)
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
        await agent.initialize(CONTEXT)
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
    wrong_id = UUID("00000000-0000-0000-0000-000000000019")
    program = (
        "import json,sys; sys.stdin.readline(); "
        f"print(json.dumps({{'type':'ready','protocol_version':'0.1.0',"
        f"'request_id':'{wrong_id}'}}), flush=True)"
    )
    agent = SubprocessAgent([sys.executable, "-c", program], timeout=1)
    with pytest.raises(AgentFailure, match="not running"):
        await agent.initialize(CONTEXT)
    async with agent:
        with pytest.raises(AgentFailure, match="request_id"):
            await agent.initialize(CONTEXT)
        with pytest.raises(AgentFailure, match="already running"):
            await agent.__aenter__()
    await agent.close()
