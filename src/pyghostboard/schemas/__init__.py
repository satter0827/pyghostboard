"""Access bundled public JSON Schema documents."""

from importlib.resources import files
from pathlib import Path

SCHEMA_NAMES = (
    "agent-request-0.1.0.schema.json",
    "agent-response-0.1.0.schema.json",
    "event-0.1.0.schema.json",
    "record-0.1.0.schema.json",
    "rules-0.1.0.schema.json",
    "snapshot-0.1.0.schema.json",
)
SCHEMA_FILES = {
    "agent_request": "agent-request-0.1.0.schema.json",
    "agent_response": "agent-response-0.1.0.schema.json",
    "event": "event-0.1.0.schema.json",
    "record": "record-0.1.0.schema.json",
    "rules": "rules-0.1.0.schema.json",
    "snapshot": "snapshot-0.1.0.schema.json",
}


def _file_name(name: str) -> str:
    if name in SCHEMA_FILES:
        return SCHEMA_FILES[name]
    if name in SCHEMA_NAMES:
        return name
    raise ValueError(f"unknown schema: {name}")


def schema_path(name: str) -> Path:
    resource = files(__package__).joinpath(_file_name(name))
    return Path(str(resource))


def read_schema(name: str) -> str:
    return files(__package__).joinpath(_file_name(name)).read_text(encoding="utf-8")


__all__ = ["SCHEMA_FILES", "SCHEMA_NAMES", "read_schema", "schema_path"]
