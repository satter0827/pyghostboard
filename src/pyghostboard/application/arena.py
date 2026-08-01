"""Deterministic arena planning, public result models, and descriptive analysis."""

from __future__ import annotations

import hashlib
from collections import Counter
from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator

from pyghostboard.domain.models import DomainModel, OutcomeReason, Player, RuleSet

ARENA_FORMAT_VERSION = "0.1.0"


class ArenaAgentSpec(DomainModel):
    """One uniquely identified built-in or external arena participant."""

    id: str = Field(pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,63}$")
    policy: Literal["mcts", "random"] | None = None
    command: tuple[str, ...] | None = None

    @model_validator(mode="after")
    def exactly_one_implementation(self) -> ArenaAgentSpec:
        if (self.policy is None) == (self.command is None):
            raise ValueError("an arena agent requires exactly one of policy or command")
        if self.command is not None and (
            not self.command or any(not item for item in self.command)
        ):
            raise ValueError("an external arena command cannot contain empty arguments")
        return self


class ArenaSearchSettings(DomainModel):
    iterations: int = Field(ge=1)
    exploration_weight: float = Field(ge=0)
    rollout_plies: int = Field(ge=1)
    setup_candidate_limit: int = Field(ge=1)


class ArenaExecutionLimits(DomainModel):
    agent_timeout: float = Field(gt=0)
    agent_max_message_bytes: int = Field(ge=1_024)
    agent_max_stderr_bytes: int = Field(ge=0)
    max_plies: int = Field(ge=1)


class ArenaConfig(DomainModel):
    """Complete reproducible inputs for one arena run."""

    format_version: Literal["0.1.0"] = "0.1.0"
    rounds: int = Field(ge=1)
    root_seed: int
    watch_agent: str
    agents: tuple[ArenaAgentSpec, ...] = Field(min_length=2, max_length=2)
    rules: RuleSet
    search: ArenaSearchSettings
    limits: ArenaExecutionLimits

    @model_validator(mode="after")
    def agents_are_unambiguous(self) -> ArenaConfig:
        identifiers = tuple(agent.id for agent in self.agents)
        if len(set(identifiers)) != 2:
            raise ValueError("arena agent identifiers must be unique")
        if self.watch_agent not in identifiers:
            raise ValueError("watch_agent must identify one configured agent")
        return self


class ArenaMatchPlan(DomainModel):
    """One deterministically scheduled match."""

    match_index: int = Field(ge=1)
    round_index: int = Field(ge=1)
    game_index: int = Field(ge=1, le=2)
    match_id: UUID
    player_one_agent: str
    player_two_agent: str
    player_one_seed: int = Field(ge=0)
    player_two_seed: int = Field(ge=0)


class ArenaManifest(DomainModel):
    """Atomically replaced progress marker for one private result directory."""

    format_version: Literal["0.1.0"] = "0.1.0"
    status: Literal["running", "completed", "interrupted"]
    root_seed: int
    rounds: int = Field(ge=1)
    agent_ids: tuple[str, str]
    planned_matches: int = Field(ge=2)
    completed_matches: int = Field(ge=0)
    failed_matches: int = Field(ge=0)
    results_file: Literal["results.jsonl"] = "results.jsonl"
    matches_directory: Literal["matches"] = "matches"

    @model_validator(mode="after")
    def counters_match_status(self) -> ArenaManifest:
        if len(set(self.agent_ids)) != 2:
            raise ValueError("arena manifest agent identifiers must be unique")
        if self.planned_matches != self.rounds * 2:
            raise ValueError("arena manifest must plan two matches per round")
        attempted = self.completed_matches + self.failed_matches
        if attempted > self.planned_matches:
            raise ValueError("arena counters cannot exceed planned matches")
        if self.status == "completed" and attempted != self.planned_matches:
            raise ValueError("completed arena manifest requires every planned result")
        return self


class ArenaMatchResult(DomainModel):
    """One append-only completed or failed arena attempt."""

    format_version: Literal["0.1.0"] = "0.1.0"
    match_index: int = Field(ge=1)
    round_index: int = Field(ge=1)
    game_index: int = Field(ge=1, le=2)
    match_id: UUID
    player_one_agent: str
    player_two_agent: str
    player_one_seed: int = Field(ge=0)
    player_two_seed: int = Field(ge=0)
    status: Literal["completed", "failed"]
    winner_agent: str | None = None
    winner_player: Player | None = None
    reason: OutcomeReason | None = None
    plies: int | None = Field(default=None, ge=1)
    record: str | None = None
    error_code: str | None = None
    error_detail: str | None = None

    @model_validator(mode="after")
    def completion_fields_match_status(self) -> ArenaMatchResult:
        if self.player_one_agent == self.player_two_agent:
            raise ValueError("arena result agents must be distinct")
        completed = (
            self.winner_agent,
            self.winner_player,
            self.reason,
            self.plies,
            self.record,
        )
        failed = (self.error_code, self.error_detail)
        if self.status == "completed":
            if any(value is None for value in completed) or any(
                value is not None for value in failed
            ):
                raise ValueError("completed arena results require only completion fields")
            expected_winner = (
                self.player_one_agent if self.winner_player is Player.ONE else self.player_two_agent
            )
            if self.winner_agent != expected_winner:
                raise ValueError("winner agent must match the winning player")
        elif any(value is not None for value in completed) or any(
            value is None for value in failed
        ):
            raise ValueError("failed arena results require only failure fields")
        return self


class AgentAnalysis(DomainModel):
    agent_id: str
    games: int = Field(ge=0)
    wins: int = Field(ge=0)
    win_rate: float = Field(ge=0, le=1)
    player_one_games: int = Field(ge=0)
    player_one_wins: int = Field(ge=0)
    player_one_win_rate: float = Field(ge=0, le=1)
    player_two_games: int = Field(ge=0)
    player_two_wins: int = Field(ge=0)
    player_two_win_rate: float = Field(ge=0, le=1)


class ArenaAnalysis(DomainModel):
    """Versioned descriptive statistics without significance claims."""

    format_version: Literal["0.1.0"] = "0.1.0"
    attempted_matches: int = Field(ge=0)
    completed_matches: int = Field(ge=0)
    failed_matches: int = Field(ge=0)
    agents: tuple[AgentAnalysis, ...]
    player_one_wins: int = Field(ge=0)
    player_one_win_rate: float = Field(ge=0, le=1)
    player_two_wins: int = Field(ge=0)
    player_two_win_rate: float = Field(ge=0, le=1)
    victory_reasons: dict[OutcomeReason, int]
    average_plies: float | None = Field(default=None, ge=1)


def derive_agent_seed(root_seed: int, round_index: int, agent_id: str) -> int:
    """Derive a stable unsigned 64-bit seed from the declared inputs."""
    payload = f"{root_seed}\0{round_index}\0{agent_id}".encode()
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big")


def build_match_plans(config: ArenaConfig) -> tuple[ArenaMatchPlan, ...]:
    """Schedule two side-swapped games for every round."""
    first, second = config.agents
    plans: list[ArenaMatchPlan] = []
    for round_index in range(1, config.rounds + 1):
        seeds = {
            agent.id: derive_agent_seed(config.root_seed, round_index, agent.id)
            for agent in config.agents
        }
        for game_index, (one, two) in enumerate(((first, second), (second, first)), start=1):
            match_index = len(plans) + 1
            digest = hashlib.sha256(
                f"match\0{config.root_seed}\0{round_index}\0{game_index}".encode()
            ).digest()
            plans.append(
                ArenaMatchPlan(
                    match_index=match_index,
                    round_index=round_index,
                    game_index=game_index,
                    match_id=UUID(bytes=digest[:16]),
                    player_one_agent=one.id,
                    player_two_agent=two.id,
                    player_one_seed=seeds[one.id],
                    player_two_seed=seeds[two.id],
                )
            )
    return tuple(plans)


def analyze_results(
    agent_ids: tuple[str, str], results: tuple[ArenaMatchResult, ...]
) -> ArenaAnalysis:
    """Compute descriptive counts and rates from append-only results."""
    completed = tuple(result for result in results if result.status == "completed")
    failed = len(results) - len(completed)
    agent_rows: list[AgentAnalysis] = []
    for agent_id in agent_ids:
        games = tuple(
            result
            for result in completed
            if agent_id in (result.player_one_agent, result.player_two_agent)
        )
        as_one = tuple(result for result in games if result.player_one_agent == agent_id)
        as_two = tuple(result for result in games if result.player_two_agent == agent_id)
        wins = sum(result.winner_agent == agent_id for result in games)
        one_wins = sum(result.winner_agent == agent_id for result in as_one)
        two_wins = sum(result.winner_agent == agent_id for result in as_two)
        agent_rows.append(
            AgentAnalysis(
                agent_id=agent_id,
                games=len(games),
                wins=wins,
                win_rate=_rate(wins, len(games)),
                player_one_games=len(as_one),
                player_one_wins=one_wins,
                player_one_win_rate=_rate(one_wins, len(as_one)),
                player_two_games=len(as_two),
                player_two_wins=two_wins,
                player_two_win_rate=_rate(two_wins, len(as_two)),
            )
        )
    one_wins = sum(result.winner_player is Player.ONE for result in completed)
    two_wins = sum(result.winner_player is Player.TWO for result in completed)
    reasons = Counter(result.reason for result in completed)
    plies = [result.plies for result in completed if result.plies is not None]
    return ArenaAnalysis(
        attempted_matches=len(results),
        completed_matches=len(completed),
        failed_matches=failed,
        agents=tuple(agent_rows),
        player_one_wins=one_wins,
        player_one_win_rate=_rate(one_wins, len(completed)),
        player_two_wins=two_wins,
        player_two_win_rate=_rate(two_wins, len(completed)),
        victory_reasons={reason: reasons[reason] for reason in OutcomeReason},
        average_plies=sum(plies) / len(plies) if plies else None,
    )


def _rate(wins: int, games: int) -> float:
    return wins / games if games else 0.0


__all__ = [
    "ARENA_FORMAT_VERSION",
    "AgentAnalysis",
    "ArenaAgentSpec",
    "ArenaAnalysis",
    "ArenaConfig",
    "ArenaExecutionLimits",
    "ArenaManifest",
    "ArenaMatchPlan",
    "ArenaMatchResult",
    "ArenaSearchSettings",
    "analyze_results",
    "build_match_plans",
    "derive_agent_seed",
]
