"""Decision-policy contracts and bundled agent behavior."""

from itertools import combinations
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
from pyghostboard.domain import (
    Escape,
    Exit,
    GameOutcome,
    GhostKind,
    Match,
    Move,
    OutcomeReason,
    Placement,
    Player,
    PlayerView,
    PrivateMatchSnapshot,
    RemovalReason,
    RuleSet,
    Square,
)
from pyghostboard.domain.models import PrivatePiece

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
    original_view = view.model_dump()

    assert first.choose_placement() == second.choose_placement()
    assert first.choose_action(view) == second.choose_action(view)
    assert first.choose_action(view) in view.legal_actions
    assert view.model_dump() == original_view


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


def test_mcts_agent_avoids_a_known_immediate_loss() -> None:
    standard = RuleSet.standard()
    rules = RuleSet(
        width=3,
        height=2,
        good_count=1,
        bad_count=1,
        player_one_start=(Square(x=0, y=0), Square(x=1, y=0)),
        player_two_start=(Square(x=1, y=1), Square(x=2, y=1)),
        player_one_exits=(Exit(square=Square(x=2, y=1)),),
        player_two_exits=(Exit(square=Square(x=0, y=0)),),
        movement=standard.movement,
        victory_conditions=(OutcomeReason.SACRIFICE_BAD,),
    )
    match = Match.restore(
        PrivateMatchSnapshot(
            match_id=MATCH_ID,
            revision=1,
            rules=rules,
            first_player=Player.TWO,
            current_player=Player.ONE,
            pieces=(
                PrivatePiece(
                    id="one-good", owner=Player.ONE, kind=GhostKind.GOOD, square=Square(x=1, y=0)
                ),
                PrivatePiece(
                    id="one-bad", owner=Player.ONE, kind=GhostKind.BAD, square=Square(x=0, y=0)
                ),
                PrivatePiece(
                    id="two-bad", owner=Player.TWO, kind=GhostKind.BAD, square=Square(x=1, y=1)
                ),
                PrivatePiece(
                    id="two-good",
                    owner=Player.TWO,
                    kind=GhostKind.GOOD,
                    square=None,
                    removal=RemovalReason.CAPTURED,
                    removed_at=Square(x=2, y=1),
                ),
            ),
        )
    )
    losing_action = Move(source=Square(x=1, y=0), destination=Square(x=1, y=1))
    view = match.view_for(Player.ONE)
    assert losing_action in view.legal_actions
    agent = MctsAgent(
        AgentContext(player=Player.ONE, rules=rules, seed=47),
        SearchConfig(iterations=40, rollout_plies=16),
    )

    assert agent.choose_action(view) != losing_action


def test_mcts_agent_takes_an_immediate_capture_win() -> None:
    standard = RuleSet.standard()
    rules = RuleSet(
        width=3,
        height=2,
        good_count=1,
        bad_count=1,
        player_one_start=(Square(x=0, y=0), Square(x=1, y=0)),
        player_two_start=(Square(x=1, y=1), Square(x=2, y=1)),
        player_one_exits=(Exit(square=Square(x=2, y=1)),),
        player_two_exits=(Exit(square=Square(x=0, y=0)),),
        movement=standard.movement,
        victory_conditions=(OutcomeReason.CAPTURE_GOOD,),
    )
    match = Match.restore(
        PrivateMatchSnapshot(
            match_id=MATCH_ID,
            revision=1,
            rules=rules,
            first_player=Player.TWO,
            current_player=Player.ONE,
            pieces=(
                PrivatePiece(
                    id="one-good", owner=Player.ONE, kind=GhostKind.GOOD, square=Square(x=1, y=0)
                ),
                PrivatePiece(
                    id="one-bad", owner=Player.ONE, kind=GhostKind.BAD, square=Square(x=0, y=0)
                ),
                PrivatePiece(
                    id="two-good", owner=Player.TWO, kind=GhostKind.GOOD, square=Square(x=1, y=1)
                ),
                PrivatePiece(
                    id="two-bad",
                    owner=Player.TWO,
                    kind=GhostKind.BAD,
                    square=None,
                    removal=RemovalReason.CAPTURED,
                    removed_at=Square(x=2, y=1),
                ),
            ),
        )
    )
    winning_action = Move(source=Square(x=1, y=0), destination=Square(x=1, y=1))
    agent = MctsAgent(
        AgentContext(player=Player.ONE, rules=rules, seed=53),
        SearchConfig(iterations=40, rollout_plies=16),
    )

    assert agent.choose_action(match.view_for(Player.ONE)) == winning_action


def test_search_configuration_rejects_invalid_limits() -> None:
    with pytest.raises(ValueError, match="positive"):
        SearchConfig(iterations=0)
    with pytest.raises(ValueError, match="negative"):
        SearchConfig(exploration_weight=-1)


def test_mcts_setup_bounds_candidates_before_enumeration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    player_one_start = tuple(Square(x=x, y=y) for y in (0, 1) for x in range(20))
    player_two_start = tuple(Square(x=x, y=y) for y in (2, 3) for x in range(20))
    standard = RuleSet.standard()
    rules = RuleSet(
        width=20,
        height=4,
        good_count=20,
        bad_count=20,
        player_one_start=player_one_start,
        player_two_start=player_two_start,
        player_one_exits=(Exit(square=Square(x=0, y=3)),),
        player_two_exits=(Exit(square=Square(x=19, y=0)),),
        movement=standard.movement,
    )

    def reject_enumeration(*_: object) -> None:
        raise AssertionError("large placement space was enumerated")

    monkeypatch.setattr("pyghostboard.agents.mcts.combinations", reject_enumeration)
    context = AgentContext(player=Player.ONE, rules=rules, seed=43)
    first = MctsAgent(context, SearchConfig(setup_candidate_limit=16))
    second = MctsAgent(context, SearchConfig(setup_candidate_limit=16))

    assert len(first._placement_candidates(player_one_start, rules.good_count)) == 16
    assert len(second._placement_candidates(player_one_start, rules.good_count)) == 16
    assert first.choose_placement() == second.choose_placement()


def test_mcts_combination_unranking_matches_lexicographic_enumeration() -> None:
    values = tuple(Square(x=x, y=0) for x in range(6))
    expected = list(combinations(values, 3))

    assert [
        MctsAgent._unrank_combination(values, 3, rank) for rank in range(len(expected))
    ] == expected


@pytest.mark.asyncio
async def test_in_process_client_enforces_lifecycle_and_legality() -> None:
    rules, view = _active_view()
    client = InProcessAgentClient(RandomAgent)

    with pytest.raises(AgentProtocolError, match="cannot choose a placement"):
        await client.choose_placement()
    await client.initialize(AgentContext(player=Player.TWO, rules=rules, seed=5))
    with pytest.raises(AgentProtocolError, match="cannot choose an action"):
        await client.choose_action(view)
    await client.choose_placement()
    with pytest.raises(AgentProtocolError, match="cannot choose a placement"):
        await client.choose_placement()
    with pytest.raises(AgentProtocolError, match="another player"):
        await client.choose_action(view.model_copy(update={"player": Player.ONE}))
    assert await client.choose_action(view) in view.legal_actions
    with pytest.raises(AgentProtocolError, match="unfinished"):
        await client.finish(view)
    final_view = view.model_copy(
        update={"outcome": GameOutcome(winner=Player.ONE, reason=OutcomeReason.CAPTURE_GOOD)}
    )
    await client.finish(final_view)
    with pytest.raises(AgentProtocolError, match="while finished"):
        await client.choose_action(view)
    with pytest.raises(AgentProtocolError, match="while finished"):
        await client.finish(final_view)
    await client.close()
    with pytest.raises(AgentProtocolError, match="while closed"):
        await client.initialize(AgentContext(player=Player.TWO, rules=rules, seed=5))


@pytest.mark.asyncio
async def test_in_process_client_rejects_invalid_policy_outputs() -> None:
    rules, view = _active_view()
    starts = rules.start_squares(Player.TWO)

    class InvalidPlacementAgent(RandomAgent):
        def choose_placement(self) -> Placement:
            return Placement(good=starts[:1], bad=starts[1:])

    placement_client = InProcessAgentClient(InvalidPlacementAgent)
    await placement_client.initialize(AgentContext(player=Player.TWO, rules=rules, seed=5))
    with pytest.raises(AgentProtocolError, match="piece counts"):
        await placement_client.choose_placement()

    class InvalidActionAgent(RandomAgent):
        def choose_action(self, view: PlayerView) -> Move:
            del view
            return Move(source=Square(x=0, y=0), destination=Square(x=0, y=1))

    action_client = InProcessAgentClient(InvalidActionAgent)
    await action_client.initialize(AgentContext(player=Player.TWO, rules=rules, seed=5))
    await action_client.choose_placement()
    with pytest.raises(AgentProtocolError, match="illegal action"):
        await action_client.choose_action(view)

    class OutsidePlacementAgent(RandomAgent):
        def choose_placement(self) -> Placement:
            return Placement(good=starts[:4], bad=(*starts[4:7], Square(x=0, y=0)))

    outside_client = InProcessAgentClient(OutsidePlacementAgent)
    await outside_client.initialize(AgentContext(player=Player.TWO, rules=rules, seed=5))
    with pytest.raises(AgentProtocolError, match="outside its starting area"):
        await outside_client.choose_placement()
