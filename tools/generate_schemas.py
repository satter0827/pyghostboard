"""Generate bundled JSON Schema documents from public wire models."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import TypeAdapter

from pyghostboard.adapters.recording import RECORD_FORMAT_VERSION, RecordLine
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
SCHEMA_BASE = "https://pyghostboard.dev/schemas"


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
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
    }
    for filename, (version, schema) in schemas.items():
        document = {
            "$schema": SCHEMA_DIALECT,
            "$id": f"{SCHEMA_BASE}/{version}/{filename}",
            **schema,
        }
        (OUTPUT / filename).write_text(
            json.dumps(document, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )


if __name__ == "__main__":
    main()
