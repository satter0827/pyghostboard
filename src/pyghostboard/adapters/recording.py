"""Private, versioned JSON Lines match recording."""

from __future__ import annotations

import os
import re
import subprocess
import tempfile
from importlib.metadata import version
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, TypeAdapter

from pyghostboard._build_info import BUILD_COMMIT
from pyghostboard._platform import require_posix
from pyghostboard.domain.codec import dump_event
from pyghostboard.domain.match import Match
from pyghostboard.domain.models import (
    ActionPlayed,
    DomainModel,
    MatchStarted,
    PrivateMatchEvent,
)

RECORD_FORMAT_VERSION = "0.1.0"


class RecordHeader(DomainModel):
    type: Literal["record_header"] = "record_header"
    format_version: Literal["0.1.0"] = "0.1.0"
    package_version: str = Field(min_length=1)
    main_commit_sha: str = Field(pattern=r"^[0-9a-f]{40}$")


RecordLine = Annotated[RecordHeader | PrivateMatchEvent, Field(discriminator="type")]
_line_adapter: TypeAdapter[RecordLine] = TypeAdapter(RecordLine)


class MatchRecord(DomainModel):
    header: RecordHeader
    events: tuple[PrivateMatchEvent, ...]


class MatchRecorder:
    def __init__(
        self,
        destination: Path | None,
        *,
        overwrite: bool = False,
        package_version: str | None = None,
        main_commit_sha: str | None = None,
    ) -> None:
        require_posix("private match recording")
        self._destination = destination
        self._overwrite = overwrite
        header = RecordHeader(
            package_version=package_version or version("pyghostboard"),
            main_commit_sha=main_commit_sha or _source_commit(),
        )
        directory: Path | None = None
        if destination is not None:
            destination.parent.mkdir(parents=True, exist_ok=True)
            directory = destination.parent
        handle = tempfile.NamedTemporaryFile(  # noqa: SIM115 - recorder owns the lifetime
            prefix=".pyghostboard-",
            suffix=".jsonl",
            dir=directory,
            delete=False,
        )
        self._handle = handle
        self._temporary = Path(handle.name)
        os.chmod(self._temporary, 0o600)
        self._handle.write(_line_adapter.dump_json(header) + b"\n")
        self._handle.flush()

    def append(self, *events: PrivateMatchEvent) -> None:
        for event in events:
            self._handle.write(dump_event(event) + b"\n")
        self._handle.flush()

    def finalize(self) -> Path | None:
        self._handle.flush()
        os.fsync(self._handle.fileno())
        self._handle.close()
        if self._destination is None:
            self._temporary.unlink(missing_ok=True)
            return None
        if self._overwrite:
            os.replace(self._temporary, self._destination)
        else:
            try:
                os.link(self._temporary, self._destination)
            except FileExistsError:
                self._temporary.unlink(missing_ok=True)
                raise
            self._temporary.unlink()
        return self._destination

    def discard(self) -> None:
        if not self._handle.closed:
            self._handle.close()
        self._temporary.unlink(missing_ok=True)


def read_record(path: Path) -> MatchRecord:
    lines = tuple(
        _line_adapter.validate_json(line) for line in path.read_bytes().splitlines() if line
    )
    if not lines or not isinstance(lines[0], RecordHeader):
        raise ValueError("record must begin with record_header")
    if any(isinstance(line, RecordHeader) for line in lines[1:]):
        raise ValueError("record_header can only appear once")
    events = tuple(line for line in lines[1:] if not isinstance(line, RecordHeader))
    if not events or not isinstance(events[0], MatchStarted):
        raise ValueError("record events must begin with match_started")
    actions = tuple(event for event in events[1:] if isinstance(event, ActionPlayed))
    if len(actions) != len(events) - 1:
        raise ValueError("match_started can only appear once")
    Match.replay(events[0], actions)
    return MatchRecord(header=lines[0], events=events)


def _source_commit() -> str:
    if BUILD_COMMIT is not None:
        return BUILD_COMMIT
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=Path(__file__).resolve().parent,
        check=False,
        capture_output=True,
        text=True,
    )
    commit = result.stdout.strip()
    if result.returncode != 0 or re.fullmatch(r"[0-9a-f]{40}", commit) is None:
        raise RuntimeError(
            "build provenance is unavailable; set it when constructing MatchRecorder"
        )
    return commit


__all__ = [
    "RECORD_FORMAT_VERSION",
    "MatchRecord",
    "MatchRecorder",
    "RecordHeader",
    "RecordLine",
    "read_record",
]
