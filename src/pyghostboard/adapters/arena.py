"""Private arena configuration and atomic filesystem persistence."""

from __future__ import annotations

import fcntl
import os
import shutil
import tempfile
import tomllib
from pathlib import Path
from types import TracebackType
from typing import Literal, Protocol, Self

from pydantic import TypeAdapter

from pyghostboard._provenance import package_version, source_commit
from pyghostboard.application.arena import (
    ArenaConfig,
    ArenaManifest,
    ArenaMatchPlan,
    ArenaMatchResult,
    ArenaRecordWriter,
    ArenaStoredConfig,
    _build_match_plans,
    _config_digest,
    _normalize_config,
)
from pyghostboard.domain.models import PrivateMatchEvent

_result_adapter: TypeAdapter[ArenaMatchResult] = TypeAdapter(ArenaMatchResult)
_TEMPORARY_PREFIX = ".attempt-"


class _ArenaRecordFactory(Protocol):
    def __call__(
        self,
        destination: Path,
        *,
        package_version: str,
        main_commit_sha: str,
    ) -> ArenaRecordWriter: ...


def load_arena_config(path: Path) -> ArenaConfig:
    """Load one strict, self-contained arena TOML document."""
    return ArenaConfig.model_validate(tomllib.loads(path.read_text(encoding="utf-8")))


class ArenaOutput:
    """Own one exclusive private arena directory."""

    def __init__(
        self,
        root: Path,
        stored: ArenaStoredConfig,
        manifest: ArenaManifest,
        lock_descriptor: int,
        record_factory: _ArenaRecordFactory,
    ) -> None:
        self.root = root
        self.attempts = root / manifest.attempts_directory
        self.config_path = root / "config.json"
        self.manifest_path = root / "manifest.json"
        self.lock_path = root / "run.lock"
        self.config = stored.config
        self._stored = stored
        self._manifest = manifest
        self._lock_descriptor = lock_descriptor
        self._record_factory = record_factory

    @classmethod
    def create(
        cls,
        root: Path,
        config: ArenaConfig,
        record_factory: _ArenaRecordFactory,
    ) -> ArenaOutput:
        config = _normalize_config(config)
        root.mkdir(mode=0o700, parents=True, exist_ok=False)
        os.chmod(root, 0o700)
        attempts = root / "attempts"
        attempts.mkdir(mode=0o700)
        os.chmod(attempts, 0o700)
        lock_descriptor = _acquire_lock(root / "run.lock")
        distribution = package_version()
        commit = source_commit()
        digest = _config_digest(config)
        stored = ArenaStoredConfig(
            config_digest=digest,
            package_version=distribution,
            source_commit=commit,
            config=config,
        )
        manifest = ArenaManifest(
            status="running",
            config_digest=digest,
            package_version=distribution,
            source_commit=commit,
            planned_matches=len(_build_match_plans(config)),
            completed_matches=0,
            failed_matches=0,
        )
        output = cls(root, stored, manifest, lock_descriptor, record_factory)
        try:
            _write_json_atomic(output.config_path, stored.model_dump_json(indent=2).encode())
            output._write_manifest()
        except BaseException:
            output.close()
            raise
        return output

    @classmethod
    def resume(cls, root: Path, record_factory: _ArenaRecordFactory) -> ArenaOutput:
        lock_descriptor = _acquire_lock(root / "run.lock")
        try:
            stored, manifest, _ = read_arena(root)
            if manifest.status == "completed":
                raise ValueError("a completed arena cannot be resumed")
            current_provenance = (package_version(), source_commit())
            stored_provenance = (stored.package_version, stored.source_commit)
            if current_provenance != stored_provenance:
                raise ValueError("arena build provenance does not match the current installation")
        except BaseException:
            fcntl.flock(lock_descriptor, fcntl.LOCK_UN)
            os.close(lock_descriptor)
            raise
        output = cls(root, stored, manifest, lock_descriptor, record_factory)
        output._remove_incomplete_attempts()
        output.update_status("running")
        return output

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        del exception_type, exception, traceback
        self.close()

    @property
    def manifest(self) -> ArenaManifest:
        return self._manifest

    def results(self) -> tuple[ArenaMatchResult, ...]:
        return _read_results(self.attempts, self.config)

    def begin_attempt(self, plan: ArenaMatchPlan) -> _FilesystemAttempt:
        destination = self.attempts / f"{plan.match_index:06d}"
        if destination.exists():
            raise ValueError(f"arena attempt {plan.match_index} already exists")
        temporary = Path(tempfile.mkdtemp(prefix=_TEMPORARY_PREFIX, dir=self.attempts))
        os.chmod(temporary, 0o700)
        return _FilesystemAttempt(self, plan, temporary, destination)

    def update_status(self, status: Literal["running", "completed", "interrupted"]) -> None:
        results = self.results()
        completed = sum(result.status == "completed" for result in results)
        failed = len(results) - completed
        self._manifest = ArenaManifest(
            **{
                **self._manifest.model_dump(),
                "status": status,
                "completed_matches": completed,
                "failed_matches": failed,
            }
        )
        self._write_manifest()

    def close(self) -> None:
        descriptor = self._lock_descriptor
        if descriptor < 0:
            return
        self._lock_descriptor = -1
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)

    def _write_manifest(self) -> None:
        _write_json_atomic(
            self.manifest_path,
            self._manifest.model_dump_json(indent=2).encode(),
        )

    def _remove_incomplete_attempts(self) -> None:
        for path in self.attempts.iterdir():
            if path.name.startswith(_TEMPORARY_PREFIX) and path.is_dir():
                shutil.rmtree(path)


class _FilesystemAttempt:
    """Build one private attempt before atomically publishing its directory."""

    def __init__(
        self,
        output: ArenaOutput,
        plan: ArenaMatchPlan,
        temporary: Path,
        destination: Path,
    ) -> None:
        self._output = output
        self._plan = plan
        self._temporary = temporary
        self._destination = destination
        self._recorder: ArenaRecordWriter | None = (
            output._record_factory(
                temporary / "match.jsonl",
                package_version=output._stored.package_version,
                main_commit_sha=output._stored.source_commit,
            )
            if output.config.recording == "all"
            else None
        )
        self._closed = False

    def append(self, *events: PrivateMatchEvent) -> None:
        if self._recorder is not None:
            self._recorder.append(*events)

    def commit(self, result: ArenaMatchResult) -> None:
        if self._closed:
            raise RuntimeError("arena attempt is already closed")
        self._validate_result(result)
        try:
            if result.status == "completed" and result.record is not None:
                assert self._recorder is not None
                self._recorder.finalize()
            elif self._recorder is not None:
                self._recorder.discard()
            _write_private_file(
                self._temporary / "result.json",
                _result_adapter.dump_json(result, indent=2),
            )
            _fsync_directory(self._temporary)
            os.rename(self._temporary, self._destination)
            _fsync_directory(self._destination.parent)
            self._closed = True
            self._output.update_status("running")
        except BaseException:
            self.abort()
            raise

    def abort(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self._recorder is not None:
            self._recorder.discard()
        shutil.rmtree(self._temporary, ignore_errors=True)

    def _validate_result(self, result: ArenaMatchResult) -> None:
        plan_fields = self._plan.model_dump()
        if any(getattr(result, field) != value for field, value in plan_fields.items()):
            raise ValueError("arena result does not match its planned attempt")
        expected_record = (
            "match.jsonl"
            if result.status == "completed" and self._output.config.recording == "all"
            else None
        )
        if result.record != expected_record:
            raise ValueError("arena result record does not match the recording policy")


def read_arena(
    root: Path,
) -> tuple[ArenaStoredConfig, ArenaManifest, tuple[ArenaMatchResult, ...]]:
    """Read and validate one private arena without mutating it."""
    stored = ArenaStoredConfig.model_validate_json((root / "config.json").read_bytes())
    manifest = ArenaManifest.model_validate_json((root / "manifest.json").read_bytes())
    if stored.config_digest != _config_digest(stored.config):
        raise ValueError("arena configuration digest does not match config.json")
    provenance = (
        stored.config_digest,
        stored.package_version,
        stored.source_commit,
    )
    if provenance != (
        manifest.config_digest,
        manifest.package_version,
        manifest.source_commit,
    ):
        raise ValueError("arena manifest does not match config.json")
    plans = _build_match_plans(stored.config)
    if manifest.planned_matches != len(plans):
        raise ValueError("arena manifest planned count does not match config.json")
    attempts = root / manifest.attempts_directory
    results = _read_results(attempts, stored.config)
    if manifest.status == "completed":
        completed = sum(result.status == "completed" for result in results)
        failed = len(results) - completed
        if (manifest.completed_matches, manifest.failed_matches) != (completed, failed):
            raise ValueError("completed arena manifest counters do not match attempts")
    return stored, manifest, results


def _read_results(attempts: Path, config: ArenaConfig) -> tuple[ArenaMatchResult, ...]:
    plans = {plan.match_index: plan for plan in _build_match_plans(config)}
    results: list[ArenaMatchResult] = []
    for path in sorted(attempts.iterdir()):
        if path.name.startswith(_TEMPORARY_PREFIX):
            continue
        if not path.is_dir() or not path.name.isdigit():
            raise ValueError(f"unexpected arena attempt entry: {path.name}")
        index = int(path.name)
        plan = plans.get(index)
        if plan is None or path.name != f"{index:06d}":
            raise ValueError(f"invalid arena attempt index: {path.name}")
        result_path = path / "result.json"
        if not result_path.is_file():
            raise ValueError(f"arena attempt {index} has no result.json")
        result = _result_adapter.validate_json(result_path.read_bytes())
        if result.match_index != index or any(
            getattr(result, field) != value for field, value in plan.model_dump().items()
        ):
            raise ValueError(f"arena attempt {index} does not match its plan")
        record_path = path / "match.jsonl"
        if (result.record is not None) != record_path.is_file():
            raise ValueError(f"arena attempt {index} record does not match result.json")
        results.append(result)
    indexes = tuple(result.match_index for result in results)
    if len(indexes) != len(set(indexes)):
        raise ValueError("arena attempt indexes must be unique")
    return tuple(results)


def _acquire_lock(path: Path) -> int:
    descriptor = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    os.chmod(path, 0o600)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as error:
        os.close(descriptor)
        raise ValueError("arena is already running") from error
    return descriptor


def _write_json_atomic(path: Path, data: bytes) -> None:
    handle = tempfile.NamedTemporaryFile(  # noqa: SIM115 - atomic writer owns cleanup
        prefix=f".{path.name}-",
        suffix=".tmp",
        dir=path.parent,
        delete=False,
    )
    temporary = Path(handle.name)
    try:
        os.chmod(temporary, 0o600)
        handle.write(data + b"\n")
        handle.flush()
        os.fsync(handle.fileno())
        handle.close()
        os.replace(temporary, path)
        _fsync_directory(path.parent)
    finally:
        if not handle.closed:
            handle.close()
        temporary.unlink(missing_ok=True)


def _write_private_file(path: Path, data: bytes) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        os.write(descriptor, data + b"\n")
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


__all__ = ["ArenaOutput", "load_arena_config", "read_arena"]
