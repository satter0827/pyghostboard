"""Generate bundled JSON Schema documents from public wire models."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from pydantic import TypeAdapter

from pyghostboard.adapters.recording import RECORD_FORMAT_VERSION, RecordLine
from pyghostboard.application.arena import (
    ARENA_FORMAT_VERSION,
    ArenaAnalysis,
    ArenaManifest,
    ArenaMatchResult,
)
from pyghostboard.domain import (
    RULES_FORMAT_VERSION,
    PrivateMatchEvent,
    PrivateMatchSnapshot,
    RuleSet,
)
from pyghostboard.protocol import PROTOCOL_VERSION, AgentRequest, AgentResponse

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "src" / "pyghostboard" / "schemas"
SCHEMA_DIALECT = "https://json-schema.org/draft/2020-12/schema"
SCHEMA_BASE = "https://raw.githubusercontent.com/satter0827/pyghostboard"


def generate_schemas() -> dict[str, str]:
    schemas = {
        f"rules-{RULES_FORMAT_VERSION}.schema.json": (
            RULES_FORMAT_VERSION,
            RuleSet.model_json_schema(),
        ),
        f"snapshot-{RECORD_FORMAT_VERSION}.schema.json": (
            RECORD_FORMAT_VERSION,
            PrivateMatchSnapshot.model_json_schema(),
        ),
        f"event-{RECORD_FORMAT_VERSION}.schema.json": (
            RECORD_FORMAT_VERSION,
            TypeAdapter(PrivateMatchEvent).json_schema(),
        ),
        f"record-{RECORD_FORMAT_VERSION}.schema.json": (
            RECORD_FORMAT_VERSION,
            TypeAdapter(RecordLine).json_schema(),
        ),
        f"agent-request-{PROTOCOL_VERSION}.schema.json": (
            PROTOCOL_VERSION,
            TypeAdapter(AgentRequest).json_schema(),
        ),
        f"agent-response-{PROTOCOL_VERSION}.schema.json": (
            PROTOCOL_VERSION,
            TypeAdapter(AgentResponse).json_schema(),
        ),
        f"arena-manifest-{ARENA_FORMAT_VERSION}.schema.json": (
            ARENA_FORMAT_VERSION,
            ArenaManifest.model_json_schema(),
        ),
        f"arena-result-{ARENA_FORMAT_VERSION}.schema.json": (
            ARENA_FORMAT_VERSION,
            ArenaMatchResult.model_json_schema(),
        ),
        f"arena-analysis-{ARENA_FORMAT_VERSION}.schema.json": (
            ARENA_FORMAT_VERSION,
            ArenaAnalysis.model_json_schema(),
        ),
    }
    documents: dict[str, str] = {}
    for filename, (version, schema) in schemas.items():
        document = {
            "$schema": SCHEMA_DIALECT,
            "$id": f"{SCHEMA_BASE}/v{version}/src/pyghostboard/schemas/{filename}",
            **schema,
        }
        documents[filename] = json.dumps(document, indent=2, sort_keys=True) + "\n"
    return documents


def check_schemas(output: Path = OUTPUT) -> None:
    stale = [
        filename
        for filename, expected in generate_schemas().items()
        if not (output / filename).is_file()
        or (output / filename).read_text(encoding="utf-8") != expected
    ]
    if stale:
        raise ValueError(f"generated schemas are stale: {', '.join(sorted(stale))}")


def write_schemas(output: Path = OUTPUT) -> None:
    output.mkdir(parents=True, exist_ok=True)
    for filename, document in generate_schemas().items():
        (output / filename).write_text(document, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    arguments = parser.parse_args()
    if arguments.check:
        check_schemas()
    else:
        write_schemas()


if __name__ == "__main__":
    main()
