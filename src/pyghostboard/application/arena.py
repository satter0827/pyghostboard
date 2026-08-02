"""Deterministic multi-agent arena planning, execution, and reporting."""

from __future__ import annotations

import hashlib
from collections import Counter
from collections.abc import Mapping
from itertools import combinations
from typing import Annotated, Literal, Protocol
from uuid import UUID

from pydantic import Field, model_validator

from pyghostboard.application.runner import (
    MatchObserver,
    MatchResult,
    MatchRunner,
    MatchSpec,
    PlayerController,
    PrivateEventSink,
)
from pyghostboard.application.service import InMemoryMatchStore, MatchAborted, MatchService
from pyghostboard.domain.models import DomainModel, OutcomeReason, Player, RuleSet

ARENA_FORMAT_VERSION = "0.1.0"


class _ArenaAgentBase(DomainModel):
    id: str = Field(pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,63}$")


class RandomArenaAgent(_ArenaAgentBase):
    """A reproducible bundled random policy."""

    kind: Literal["random"] = "random"


class MctsArenaAgent(_ArenaAgentBase):
    """A bundled MCTS policy with experiment-specific search settings."""

    kind: Literal["mcts"] = "mcts"
    iterations: int = Field(default=256, ge=1)
    exploration_weight: float = Field(default=2**0.5, ge=0)
    rollout_plies: int = Field(default=96, ge=1)
    setup_candidate_limit: int = Field(default=256, ge=1)


class ExternalArenaAgent(_ArenaAgentBase):
    """A shell-free external policy identified by declared provenance."""

    kind: Literal["external"] = "external"
    command: tuple[str, ...] = Field(min_length=1)
    revision: str = Field(min_length=1)

    @model_validator(mode="after")
    def command_has_no_empty_arguments(self) -> ExternalArenaAgent:
        if any(not argument for argument in self.command):
            raise ValueError("an external arena command cannot contain empty arguments")
        return self


ArenaAgent = Annotated[
    RandomArenaAgent | MctsArenaAgent | ExternalArenaAgent,
    Field(discriminator="kind"),
]


class ArenaExecutionLimits(DomainModel):
    agent_timeout: float = Field(default=10.0, gt=0)
    agent_max_message_bytes: int = Field(default=1_048_576, ge=1_024)
    agent_max_stderr_bytes: int = Field(default=65_536, ge=0)
    max_plies: int = Field(default=1_000, ge=1)


class ArenaConfig(DomainModel):
    """Complete reproducible inputs for one multi-agent arena run."""

    format_version: Literal["0.1.0"] = "0.1.0"
    rounds: int = Field(ge=1)
    root_seed: int
    recording: Literal["all", "none"] = "all"
    agents: tuple[ArenaAgent, ...] = Field(min_length=2)
    rules: RuleSet
    limits: ArenaExecutionLimits = ArenaExecutionLimits()

    @model_validator(mode="after")
    def agent_identifiers_are_unique(self) -> ArenaConfig:
        identifiers = tuple(agent.id for agent in self.agents)
        if len(set(identifiers)) != len(identifiers):
            raise ValueError("arena agent identifiers must be unique")
        return self


class ArenaMatchPlan(DomainModel):
    """One internally scheduled side of a paired arena round."""

    match_index: int = Field(ge=1)
    pair_index: int = Field(ge=1)
    round_index: int = Field(ge=1)
    game_index: int = Field(ge=1, le=2)
    match_id: UUID
    player_one_agent: str
    player_two_agent: str
    player_one_seed: int = Field(ge=0)
    player_two_seed: int = Field(ge=0)


class ArenaMatchResult(DomainModel):
    """Private stored result for one completed or failed attempt."""

    format_version: Literal["0.1.0"] = "0.1.0"
    match_index: int = Field(ge=1)
    pair_index: int = Field(ge=1)
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
    record: Literal["match.jsonl"] | None = None
    error_code: str | None = None
    error_detail: str | None = None

    @model_validator(mode="after")
    def fields_match_status(self) -> ArenaMatchResult:
        if self.player_one_agent == self.player_two_agent:
            raise ValueError("arena result agents must be distinct")
        completed = (self.winner_agent, self.winner_player, self.reason, self.plies)
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
        elif (
            any(value is not None for value in completed)
            or self.record is not None
            or any(value is None for value in failed)
        ):
            raise ValueError("failed arena results require only failure fields")
        return self


class ArenaManifest(DomainModel):
    """Private, atomically replaced progress summary."""

    format_version: Literal["0.1.0"] = "0.1.0"
    status: Literal["running", "completed", "interrupted"]
    config_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    package_version: str = Field(min_length=1)
    source_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    planned_matches: int = Field(ge=2)
    completed_matches: int = Field(ge=0)
    failed_matches: int = Field(ge=0)
    attempts_directory: Literal["attempts"] = "attempts"

    @model_validator(mode="after")
    def counters_match_status(self) -> ArenaManifest:
        attempted = self.completed_matches + self.failed_matches
        if attempted > self.planned_matches:
            raise ValueError("arena counters cannot exceed planned matches")
        if self.status == "completed" and attempted != self.planned_matches:
            raise ValueError("completed arena manifest requires every planned result")
        return self


class ArenaStoredConfig(DomainModel):
    """Private normalized configuration and build provenance."""

    format_version: Literal["0.1.0"] = "0.1.0"
    config_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    package_version: str = Field(min_length=1)
    source_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    config: ArenaConfig


class ArenaAgentReport(DomainModel):
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


class ArenaPairReport(DomainModel):
    first_agent: str
    second_agent: str
    completed_games: int = Field(ge=0)
    first_wins: int = Field(ge=0)
    second_wins: int = Field(ge=0)
    first_sweeps: int = Field(ge=0)
    split_rounds: int = Field(ge=0)
    second_sweeps: int = Field(ge=0)
    incomplete_rounds: int = Field(ge=0)


class ArenaReport(DomainModel):
    """Shareable descriptive report without private execution details."""

    format_version: Literal["0.1.0"] = "0.1.0"
    status: Literal["running", "completed", "interrupted"]
    config_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    package_version: str = Field(min_length=1)
    source_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    planned_matches: int = Field(ge=2)
    attempted_matches: int = Field(ge=0)
    completed_matches: int = Field(ge=0)
    failed_matches: int = Field(ge=0)
    agents: tuple[ArenaAgentReport, ...]
    pairs: tuple[ArenaPairReport, ...]
    player_one_wins: int = Field(ge=0)
    player_one_win_rate: float = Field(ge=0, le=1)
    player_two_wins: int = Field(ge=0)
    player_two_win_rate: float = Field(ge=0, le=1)
    victory_reasons: dict[OutcomeReason, int]
    error_codes: dict[str, int]
    average_plies: float | None = Field(default=None, ge=1)
    incomplete_rounds: int = Field(ge=0)


class ArenaAttemptSink(PrivateEventSink, Protocol):
    """Collect private events and atomically commit one attempt."""

    def commit(self, result: ArenaMatchResult) -> None: ...

    def abort(self) -> None: ...


class ArenaRecordWriter(PrivateEventSink, Protocol):
    """Complete or discard one private match record inside an attempt."""

    def finalize(self) -> object: ...

    def discard(self) -> None: ...


class ArenaStore(Protocol):
    """Persistence port for one exclusive arena run."""

    @property
    def manifest(self) -> ArenaManifest: ...

    def results(self) -> tuple[ArenaMatchResult, ...]: ...

    def begin_attempt(self, plan: ArenaMatchPlan) -> ArenaAttemptSink: ...

    def update_status(self, status: Literal["running", "completed", "interrupted"]) -> None: ...


class ArenaControllerFactory(Protocol):
    """Create a fresh controller for one configured arena participant."""

    def create(self, agent: ArenaAgent) -> PlayerController: ...


def _config_digest(config: ArenaConfig) -> str:
    payload = _normalize_config(config).model_dump_json(exclude_none=False).encode()
    return hashlib.sha256(payload).hexdigest()


def _normalize_config(config: ArenaConfig) -> ArenaConfig:
    """Return the canonical persisted form of an arena configuration."""
    return config.model_copy(
        update={"agents": tuple(sorted(config.agents, key=lambda agent: agent.id))}
    )


def _derive_agent_seed(
    root_seed: int,
    pair: tuple[str, str],
    round_index: int,
    agent_id: str,
) -> int:
    payload = f"{root_seed}\0{pair[0]}\0{pair[1]}\0{round_index}\0{agent_id}".encode()
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big")


def _build_match_plans(config: ArenaConfig) -> tuple[ArenaMatchPlan, ...]:
    identifiers = tuple(sorted(agent.id for agent in config.agents))
    plans: list[ArenaMatchPlan] = []
    for pair_index, pair in enumerate(combinations(identifiers, 2), start=1):
        for round_index in range(1, config.rounds + 1):
            seeds = {
                agent_id: _derive_agent_seed(config.root_seed, pair, round_index, agent_id)
                for agent_id in pair
            }
            for game_index, (one, two) in enumerate((pair, pair[::-1]), start=1):
                match_index = len(plans) + 1
                digest = hashlib.sha256(
                    (
                        f"match\0{config.root_seed}\0{pair[0]}\0{pair[1]}"
                        f"\0{round_index}\0{game_index}"
                    ).encode()
                ).digest()
                plans.append(
                    ArenaMatchPlan(
                        match_index=match_index,
                        pair_index=pair_index,
                        round_index=round_index,
                        game_index=game_index,
                        match_id=UUID(bytes=digest[:16]),
                        player_one_agent=one,
                        player_two_agent=two,
                        player_one_seed=seeds[one],
                        player_two_seed=seeds[two],
                    )
                )
    return tuple(plans)


class ArenaRunner:
    """Run deterministic matches through injected controller and storage ports."""

    def __init__(
        self,
        controller_factory: ArenaControllerFactory,
        store: ArenaStore | None = None,
    ) -> None:
        self._controller_factory = controller_factory
        self._store = store

    async def run(self, config: ArenaConfig) -> ArenaReport:
        store = self._require_store()
        if store.manifest.config_digest != _config_digest(config):
            raise ValueError("arena store configuration does not match the requested run")
        agents = {agent.id: agent for agent in config.agents}
        plans = _build_match_plans(config)
        completed_indices = {result.match_index for result in store.results()}
        store.update_status("running")
        try:
            for plan in plans:
                if plan.match_index in completed_indices:
                    continue
                attempt = store.begin_attempt(plan)
                try:
                    result = await self._run_plan(config, plan, agents, private_events=attempt)
                    winner_agent = (
                        plan.player_one_agent
                        if result.outcome.winner is Player.ONE
                        else plan.player_two_agent
                    )
                    attempt.commit(
                        ArenaMatchResult(
                            **plan.model_dump(),
                            status="completed",
                            winner_agent=winner_agent,
                            winner_player=result.outcome.winner,
                            reason=result.outcome.reason,
                            plies=result.plies,
                            record="match.jsonl" if config.recording == "all" else None,
                        )
                    )
                except MatchAborted as error:
                    attempt.commit(
                        ArenaMatchResult(
                            **plan.model_dump(),
                            status="failed",
                            error_code=error.reason.value,
                            error_detail=str(error),
                        )
                    )
                except BaseException:
                    attempt.abort()
                    raise
            store.update_status("completed")
        except BaseException:
            store.update_status("interrupted")
            raise
        return build_arena_report(config, store.manifest, store.results())

    async def watch(
        self,
        config: ArenaConfig,
        *,
        agent_id: str,
        opponent_id: str,
        round_index: int,
        side: Player,
        observer: MatchObserver,
    ) -> MatchResult:
        if agent_id == opponent_id:
            raise ValueError("watch agent and opponent must be distinct")
        configured = {agent.id: agent for agent in config.agents}
        if agent_id not in configured or opponent_id not in configured:
            raise ValueError("watch agent and opponent must be configured")
        if not 1 <= round_index <= config.rounds:
            raise ValueError("watch round is outside the configured range")
        pair = tuple(sorted((agent_id, opponent_id)))
        plan = next(
            candidate
            for candidate in _build_match_plans(config)
            if {candidate.player_one_agent, candidate.player_two_agent} == set(pair)
            and candidate.round_index == round_index
            and (
                candidate.player_one_agent == agent_id
                if side is Player.ONE
                else candidate.player_two_agent == agent_id
            )
        )
        return await self._run_plan(
            config,
            plan,
            configured,
            observer=observer,
            observer_player=side,
        )

    async def _run_plan(
        self,
        config: ArenaConfig,
        plan: ArenaMatchPlan,
        agents: Mapping[str, ArenaAgent],
        *,
        observer: MatchObserver | None = None,
        observer_player: Player = Player.ONE,
        private_events: PrivateEventSink | None = None,
    ) -> MatchResult:
        controllers = {
            Player.ONE: self._controller_factory.create(agents[plan.player_one_agent]),
            Player.TWO: self._controller_factory.create(agents[plan.player_two_agent]),
        }
        return await MatchRunner(MatchService(InMemoryMatchStore())).run(
            MatchSpec(
                match_id=plan.match_id,
                rules=config.rules,
                player_one_seed=plan.player_one_seed,
                player_two_seed=plan.player_two_seed,
                max_plies=config.limits.max_plies,
                observer_player=observer_player,
            ),
            controllers,
            observer=observer,
            private_events=private_events,
        )

    def _require_store(self) -> ArenaStore:
        if self._store is None:
            raise RuntimeError("arena execution requires a store")
        return self._store


def build_arena_report(
    config: ArenaConfig,
    manifest: ArenaManifest,
    results: tuple[ArenaMatchResult, ...],
) -> ArenaReport:
    """Build sanitized descriptive statistics from validated private results."""
    completed = tuple(result for result in results if result.status == "completed")
    agent_rows: list[ArenaAgentReport] = []
    for agent_id in sorted(agent.id for agent in config.agents):
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
            ArenaAgentReport(
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

    pair_rows: list[ArenaPairReport] = []
    total_incomplete = 0
    identifiers = tuple(sorted(agent.id for agent in config.agents))
    for first, second in combinations(identifiers, 2):
        pair_results = tuple(
            result
            for result in results
            if {result.player_one_agent, result.player_two_agent} == {first, second}
        )
        pair_completed = tuple(result for result in pair_results if result.status == "completed")
        first_sweeps = split_rounds = second_sweeps = incomplete = 0
        for round_index in range(1, config.rounds + 1):
            block = tuple(result for result in pair_completed if result.round_index == round_index)
            if len(block) != 2:
                incomplete += 1
                continue
            first_wins = sum(result.winner_agent == first for result in block)
            if first_wins == 2:
                first_sweeps += 1
            elif first_wins == 1:
                split_rounds += 1
            else:
                second_sweeps += 1
        total_incomplete += incomplete
        pair_rows.append(
            ArenaPairReport(
                first_agent=first,
                second_agent=second,
                completed_games=len(pair_completed),
                first_wins=sum(result.winner_agent == first for result in pair_completed),
                second_wins=sum(result.winner_agent == second for result in pair_completed),
                first_sweeps=first_sweeps,
                split_rounds=split_rounds,
                second_sweeps=second_sweeps,
                incomplete_rounds=incomplete,
            )
        )

    one_wins = sum(result.winner_player is Player.ONE for result in completed)
    two_wins = sum(result.winner_player is Player.TWO for result in completed)
    reasons = Counter(result.reason for result in completed)
    errors = Counter(result.error_code for result in results if result.error_code is not None)
    plies = tuple(result.plies for result in completed if result.plies is not None)
    return ArenaReport(
        status=manifest.status,
        config_digest=manifest.config_digest,
        package_version=manifest.package_version,
        source_commit=manifest.source_commit,
        planned_matches=manifest.planned_matches,
        attempted_matches=len(results),
        completed_matches=len(completed),
        failed_matches=len(results) - len(completed),
        agents=tuple(agent_rows),
        pairs=tuple(pair_rows),
        player_one_wins=one_wins,
        player_one_win_rate=_rate(one_wins, len(completed)),
        player_two_wins=two_wins,
        player_two_win_rate=_rate(two_wins, len(completed)),
        victory_reasons={reason: reasons[reason] for reason in OutcomeReason},
        error_codes=dict(sorted(errors.items())),
        average_plies=sum(plies) / len(plies) if plies else None,
        incomplete_rounds=total_incomplete,
    )


def _rate(wins: int, games: int) -> float:
    return wins / games if games else 0.0


__all__ = [
    "ARENA_FORMAT_VERSION",
    "ArenaAgent",
    "ArenaConfig",
    "ArenaControllerFactory",
    "ArenaExecutionLimits",
    "ArenaReport",
    "ArenaRunner",
    "ArenaStore",
    "ExternalArenaAgent",
    "MctsArenaAgent",
    "RandomArenaAgent",
]
