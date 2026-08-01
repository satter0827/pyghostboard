"""Configuration, recording, schema, and random-agent adapter tests."""

import json
import stat
from io import StringIO
from pathlib import Path
from uuid import UUID

import pytest

from pyghostboard.adapters.config import RuntimeSettings, load_rules
from pyghostboard.adapters.recording import MatchRecorder, read_record
from pyghostboard.domain import GameOutcome, Match, OutcomeReason, Placement, Player, RuleSet
from pyghostboard.protocol import (
    ActionRequest,
    FinishedRequest,
    InitializeRequest,
    SetupRequest,
    request_adapter,
    response_adapter,
)
from pyghostboard.random_agent import run
from pyghostboard.schemas import SCHEMA_NAMES, schema_path

MATCH_ID = UUID("00000000-0000-0000-0000-000000000020")
COMMIT_SHA = "a" * 40


def _match() -> Match:
    rules = RuleSet.standard()
    one = rules.start_squares(Player.ONE)
    two = rules.start_squares(Player.TWO)
    return Match.start(
        MATCH_ID,
        rules,
        {
            Player.ONE: Placement(good=one[:4], bad=one[4:]),
            Player.TWO: Placement(good=two[:4], bad=two[4:]),
        },
    )


def test_runtime_settings_use_prefixed_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PYGHOSTBOARD_AGENT_TIMEOUT", "2.5")
    monkeypatch.setenv("PYGHOSTBOARD_MAX_PLIES", "42")
    settings = RuntimeSettings()
    assert settings.agent_timeout == 2.5
    assert settings.max_plies == 42


def test_toml_rules_are_validated(tmp_path: Path) -> None:
    path = tmp_path / "rules.toml"
    path.write_text(
        """
[rules]
format_version = "0.1.0"
width = 2
height = 2
good_count = 1
bad_count = 1
player_one_start = [{x = 0, y = 0}, {x = 1, y = 0}]
player_two_start = [{x = 0, y = 1}, {x = 1, y = 1}]
player_one_exits = [{square = {x = 0, y = 1}}]
player_two_exits = [{square = {x = 0, y = 0}}]
movement = [{dx = 0, dy = 1}, {dx = 0, dy = -1}]
""",
        encoding="utf-8",
    )
    rules = load_rules(path)
    assert (rules.width, rules.height) == (2, 2)


def test_private_recorder_promotes_or_discards_atomically(tmp_path: Path) -> None:
    match = _match()
    destination = tmp_path / "nested" / "match.jsonl"
    recorder = MatchRecorder(destination, package_version="0.1.0", main_commit_sha=COMMIT_SHA)
    recorder.append(match.started_event())
    assert recorder.finalize() == destination
    record = read_record(destination)
    assert record.header.package_version == "0.1.0"
    assert record.header.main_commit_sha == COMMIT_SHA
    assert record.events == (match.started_event(),)
    assert stat.S_IMODE(destination.stat().st_mode) == 0o600

    discarded = MatchRecorder(None, package_version="0.1.0", main_commit_sha=COMMIT_SHA)
    discarded.append(match.started_event())
    assert discarded.finalize() is None


def test_private_recorder_refuses_overwrite_by_default(tmp_path: Path) -> None:
    destination = tmp_path / "match.jsonl"
    destination.write_text("existing", encoding="utf-8")
    recorder = MatchRecorder(destination, package_version="0.1.0", main_commit_sha=COMMIT_SHA)

    with pytest.raises(FileExistsError):
        recorder.finalize()

    assert destination.read_text(encoding="utf-8") == "existing"


def test_private_recorder_can_explicitly_overwrite(tmp_path: Path) -> None:
    destination = tmp_path / "match.jsonl"
    destination.write_text("existing", encoding="utf-8")
    match = _match()
    recorder = MatchRecorder(
        destination,
        overwrite=True,
        package_version="0.1.0",
        main_commit_sha=COMMIT_SHA,
    )
    recorder.append(match.started_event())

    assert recorder.finalize() == destination
    assert read_record(destination).events == (match.started_event(),)


def test_recorder_explicit_discard(tmp_path: Path) -> None:
    recorder = MatchRecorder(
        tmp_path / "unused.jsonl",
        package_version="0.1.0",
        main_commit_sha=COMMIT_SHA,
    )
    recorder.discard()
    recorder.discard()
    assert not (tmp_path / "unused.jsonl").exists()


def test_random_agent_handles_complete_protocol_sequence() -> None:
    match = _match()
    ai_match = match.play(Player.ONE, match.legal_actions()[0]).match
    requests = (
        InitializeRequest(
            request_id=UUID("00000000-0000-0000-0000-000000000021"),
            seed=3,
            player=Player.TWO,
            rules=RuleSet.standard(),
        ),
        SetupRequest(request_id=UUID("00000000-0000-0000-0000-000000000022")),
        ActionRequest(
            request_id=UUID("00000000-0000-0000-0000-000000000023"),
            view=ai_match.view_for(Player.TWO),
        ),
        FinishedRequest(
            request_id=UUID("00000000-0000-0000-0000-000000000024"),
            view=ai_match.view_for(Player.TWO).model_copy(
                update={
                    "outcome": GameOutcome(
                        winner=Player.ONE,
                        reason=OutcomeReason.CAPTURE_GOOD,
                    )
                }
            ),
        ),
    )
    source = [request_adapter.dump_json(request) + b"\n" for request in requests]
    destination = StringIO()
    run(source, destination, seed=3)
    responses = [
        response_adapter.validate_json(line) for line in destination.getvalue().splitlines()
    ]
    assert [response.request_id for response in responses] == [
        request.request_id for request in requests
    ]


def test_schema_paths_exist_and_unknown_names_fail() -> None:
    for name in SCHEMA_NAMES:
        assert json.loads(schema_path(name).read_text(encoding="utf-8"))["$id"]
    with pytest.raises(ValueError, match="unknown schema"):
        schema_path("missing")


def test_random_agent_rejects_invalid_protocol_order() -> None:
    setup = SetupRequest(request_id=UUID("00000000-0000-0000-0000-000000000025"))
    with pytest.raises(RuntimeError, match="not initialized"):
        run([request_adapter.dump_json(setup) + b"\n"], StringIO(), seed=0)

    initialize = InitializeRequest(
        request_id=UUID("00000000-0000-0000-0000-000000000026"),
        seed=0,
        player=Player.TWO,
        rules=RuleSet.standard(),
    )
    source = [request_adapter.dump_json(initialize) + b"\n"] * 2
    with pytest.raises(RuntimeError, match="already initialized"):
        run(source, StringIO(), seed=0)
