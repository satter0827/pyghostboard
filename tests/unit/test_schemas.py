"""Bundled JSON Schema contract tests."""

import json
from uuid import UUID

import pytest
from jsonschema import Draft202012Validator

from pyghostboard.adapters.recording import RecordHeader
from pyghostboard.domain import Match, Placement, Player, RuleSet
from pyghostboard.protocol import InitializeRequest, ReadyResponse
from pyghostboard.schemas import SCHEMA_FILES, SCHEMA_NAMES, read_schema


def test_all_public_schemas_use_draft_2020_12_and_versioned_ids() -> None:
    assert len(SCHEMA_NAMES) == 6
    for name in SCHEMA_NAMES:
        schema = json.loads(read_schema(name))
        assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
        assert schema["$id"] == (
            "https://raw.githubusercontent.com/satter0827/pyghostboard/"
            f"v0.1.0/src/pyghostboard/schemas/{name}"
        )
        assert "$defs" in schema


def test_unknown_schema_is_rejected() -> None:
    with pytest.raises(ValueError, match="unknown schema"):
        read_schema("unknown.json")


def test_schema_can_be_read_by_public_name() -> None:
    for public_name, file_name in SCHEMA_FILES.items():
        assert read_schema(public_name) == read_schema(file_name)


def test_public_examples_conform_to_bundled_schemas() -> None:
    match_id = UUID("00000000-0000-0000-0000-000000000030")
    request_id = UUID("00000000-0000-0000-0000-000000000031")
    rules = RuleSet.standard()
    one = rules.start_squares(Player.ONE)
    two = rules.start_squares(Player.TWO)
    match = Match.start(
        match_id,
        rules,
        {
            Player.ONE: Placement(good=one[:4], bad=one[4:]),
            Player.TWO: Placement(good=two[:4], bad=two[4:]),
        },
    )
    examples = {
        "rules": rules.model_dump(mode="json"),
        "snapshot": match.snapshot().model_dump(mode="json"),
        "event": match.started_event().model_dump(mode="json"),
        "record": RecordHeader(package_version="0.1.0", main_commit_sha="a" * 40).model_dump(
            mode="json"
        ),
        "agent_request": InitializeRequest(
            request_id=request_id,
            seed=1,
            player=Player.ONE,
            rules=rules,
        ).model_dump(mode="json"),
        "agent_response": ReadyResponse(request_id=request_id).model_dump(mode="json"),
    }
    for name, example in examples.items():
        Draft202012Validator(json.loads(read_schema(name))).validate(example)
