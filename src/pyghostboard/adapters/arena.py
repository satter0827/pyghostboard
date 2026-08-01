"""Private arena configuration and append-only result storage."""

from __future__ import annotations

import os
import tempfile
import tomllib
from pathlib import Path

from pydantic import TypeAdapter

from pyghostboard.application.arena import ArenaConfig, ArenaManifest, ArenaMatchResult

_result_adapter: TypeAdapter[ArenaMatchResult] = TypeAdapter(ArenaMatchResult)


def load_arena_config(path: Path) -> ArenaConfig:
    """Load one strict, self-contained arena TOML document."""
    return ArenaConfig.model_validate(tomllib.loads(path.read_text(encoding="utf-8")))


class ArenaOutput:
    """Own one new private arena directory and its durable progress files."""

    def __init__(self, root: Path, manifest: ArenaManifest) -> None:
        self.root = root
        self.matches = root / manifest.matches_directory
        self.results = root / manifest.results_file
        self.manifest_path = root / "manifest.json"
        self._manifest = manifest

    @classmethod
    def create(cls, root: Path, config: ArenaConfig) -> ArenaOutput:
        root.mkdir(mode=0o700, parents=True, exist_ok=False)
        os.chmod(root, 0o700)
        matches = root / "matches"
        matches.mkdir(mode=0o700)
        os.chmod(matches, 0o700)
        output = cls(
            root,
            ArenaManifest(
                status="running",
                root_seed=config.root_seed,
                rounds=config.rounds,
                agent_ids=(config.agents[0].id, config.agents[1].id),
                planned_matches=config.rounds * 2,
                completed_matches=0,
                failed_matches=0,
            ),
        )
        output._write_manifest()
        descriptor = os.open(output.results, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        os.close(descriptor)
        return output

    @property
    def manifest(self) -> ArenaManifest:
        return self._manifest

    def record_path(self, match_index: int) -> Path:
        return self.matches / f"{match_index:06d}.jsonl"

    def append(self, result: ArenaMatchResult) -> None:
        if self._manifest.status != "running":
            raise ValueError("arena results can only be appended while running")
        expected_index = self._manifest.completed_matches + self._manifest.failed_matches + 1
        if expected_index > self._manifest.planned_matches:
            raise ValueError("arena already contains every planned result")
        if result.match_index != expected_index:
            raise ValueError(f"expected arena match index {expected_index}")
        if {result.player_one_agent, result.player_two_agent} != set(self._manifest.agent_ids):
            raise ValueError("arena result agents do not match the manifest")
        line = _result_adapter.dump_json(result) + b"\n"
        descriptor = os.open(self.results, os.O_WRONLY | os.O_APPEND)
        try:
            os.write(descriptor, line)
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        completed = self._manifest.completed_matches + (result.status == "completed")
        failed = self._manifest.failed_matches + (result.status == "failed")
        self._manifest = ArenaManifest.model_validate(
            {
                **self._manifest.model_dump(),
                "completed_matches": completed,
                "failed_matches": failed,
            }
        )
        self._write_manifest()

    def finish(self, status: str = "completed") -> None:
        if status not in {"completed", "interrupted"}:
            raise ValueError("arena status must be completed or interrupted")
        self._manifest = ArenaManifest.model_validate(
            {**self._manifest.model_dump(), "status": status}
        )
        self._write_manifest()

    def _write_manifest(self) -> None:
        data = self._manifest.model_dump_json(indent=2).encode() + b"\n"
        handle = tempfile.NamedTemporaryFile(  # noqa: SIM115 - atomic writer owns cleanup
            prefix=".manifest-",
            suffix=".json",
            dir=self.root,
            delete=False,
        )
        temporary = Path(handle.name)
        try:
            os.chmod(temporary, 0o600)
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
            handle.close()
            os.replace(temporary, self.manifest_path)
        finally:
            if not handle.closed:
                handle.close()
            temporary.unlink(missing_ok=True)


def read_arena_results(root: Path) -> tuple[ArenaManifest, tuple[ArenaMatchResult, ...]]:
    """Validate a manifest and every append-only result line."""
    manifest = ArenaManifest.model_validate_json((root / "manifest.json").read_bytes())
    results = tuple(
        _result_adapter.validate_json(line)
        for line in (root / manifest.results_file).read_bytes().splitlines()
        if line
    )
    if len(results) != manifest.completed_matches + manifest.failed_matches:
        raise ValueError("arena manifest counters do not match results.jsonl")
    if tuple(result.match_index for result in results) != tuple(range(1, len(results) + 1)):
        raise ValueError("arena results must use contiguous match indexes")
    configured_agents = set(manifest.agent_ids)
    if any(
        {result.player_one_agent, result.player_two_agent} != configured_agents
        for result in results
    ):
        raise ValueError("arena result agents do not match the manifest")
    return manifest, results


__all__ = ["ArenaOutput", "load_arena_config", "read_arena_results"]
