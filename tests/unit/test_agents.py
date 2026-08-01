"""Decision-policy contracts and bundled agent behavior."""

from uuid import UUID

import pytest

from pyghostboard.agents import (
    AgentContext,
    InProcessAgentClient,
    MctsAgent,
    RandomAgent,
    SearchConfig,
)
from pyghostboard.agents.contracts import AgentProtocolError
from pyghostboard.domain import Escape, Match, Placement, Player, PlayerView, RuleSet

MATCH_ID = UUID("00000000-0000-0000-0000-000000000090")


def _active_view() -> tuple[RuleSet, PlayerView]:
    rules = RuleSet.standard()
    one = rules.start_squares(Player.ONE)
    two = rules.start_squares(Player.TWO)
    match = Match.start(
        MATCH_ID,
        rules,
        {
            Player.ONE: Placement(good=one[:4], bad=one[4:]),
            Player.TWO: Placement(good=two[:4], bad=two[4:]),
        },
    )
    match = match.play(Player.ONE, match.legal_actions()[0]).match
    return rules, match.view_for(Player.TWO)


def test_random_agent_is_seeded_and_returns_legal_values() -> None:
    rules, view = _active_view()
    context = AgentContext(player=Player.TWO, rules=rules, seed=17)
    first = RandomAgent(context)
    second = RandomAgent(context)

    assert first.choose_placement() == second.choose_placement()
    assert first.choose_action(view) == second.choose_action(view)
    assert first.choose_action(view) in view.legal_actions


def test_mcts_agent_is_seeded_and_returns_a_legal_action() -> None:
    rules, view = _active_view()
    context = AgentContext(player=Player.TWO, rules=rules, seed=23)
    config = SearchConfig(iterations=20, rollout_plies=12)

    first = MctsAgent(context, config)
    second = MctsAgent(context, config)

    assert first.choose_placement() == second.choose_placement()
    assert first.choose_action(view) == second.choose_action(view)
    assert first.choose_action(view) in view.legal_actions


def test_mcts_agent_takes_an_immediate_escape() -> None:
    rules = RuleSet.standard()
    one = rules.start_squares(Player.ONE)
    two = rules.start_squares(Player.TWO)
    match = Match.start(
        MATCH_ID,
        rules,
        {
            Player.ONE: Placement(good=one[:4], bad=one[4:]),
            Player.TWO: Placement(good=two[:4], bad=two[4:]),
        },
    )
    snapshot = match.snapshot()
    exit_square = rules.exits(Player.ONE)[0].square
    pieces = list(snapshot.pieces)
    pieces[0] = pieces[0].model_copy(update={"square": exit_square})
    match = Match.restore(snapshot.model_copy(update={"pieces": tuple(pieces)}))
    agent = MctsAgent(
        AgentContext(player=Player.ONE, rules=rules, seed=41),
        SearchConfig(iterations=40, rollout_plies=16),
    )

    assert agent.choose_action(match.view_for(Player.ONE)) == Escape(source=exit_square)


def test_search_configuration_rejects_invalid_limits() -> None:
    with pytest.raises(ValueError, match="positive"):
        SearchConfig(iterations=0)
    with pytest.raises(ValueError, match="negative"):
        SearchConfig(exploration_weight=-1)


@pytest.mark.asyncio
async def test_in_process_client_enforces_lifecycle_and_legality() -> None:
    rules, view = _active_view()
    client = InProcessAgentClient(RandomAgent)

    with pytest.raises(AgentProtocolError, match="not initialized"):
        await client.choose_placement()
    await client.initialize(AgentContext(player=Player.TWO, rules=rules, seed=5))
    assert await client.choose_action(view) in view.legal_actions
    with pytest.raises(AgentProtocolError, match="unfinished"):
        await client.finish(view)
    await client.close()
