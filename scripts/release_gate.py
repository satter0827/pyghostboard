"""Run deterministic quality and release checks locally and in CI."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import tomllib
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Final

ROOT: Final = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.verify_distribution import verify_distribution  # noqa: E402

PYPROJECT: Final = ROOT / "pyproject.toml"
CHANGELOG: Final = ROOT / "CHANGELOG.md"
LOCAL_STATE_ROOT: Final = ROOT / ".pyghostboard"
CACHE_ROOT: Final = LOCAL_STATE_ROOT / "cache"
COVERAGE_ROOT: Final = LOCAL_STATE_ROOT / "coverage"
BUILD_COMMIT_ENV: Final = "PYGHOSTBOARD_BUILD_COMMIT"
VERSION_ENV: Final = "SETUPTOOLS_SCM_PRETEND_VERSION"
RELEASE_VERSION = re.compile(r"[0-9]+\.[0-9]+\.[0-9]+")
COMPLETE_SHA = re.compile(r"[0-9a-f]{40}")


def run(command: Sequence[str], *, environment: Mapping[str, str] | None = None) -> None:
    printable = " ".join(command)
    print(f"==> {printable}", flush=True)
    merged_environment = os.environ.copy()
    if environment is not None:
        merged_environment.update(environment)
    result = subprocess.run(command, cwd=ROOT, env=merged_environment, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"quality gate command failed ({result.returncode}): {printable}")


def capture(command: Sequence[str]) -> str:
    result = subprocess.run(
        command,
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def load_quality_configuration() -> dict[str, Any]:
    document = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    configuration = document.get("tool", {}).get("quality-gate")
    if not isinstance(configuration, dict):
        raise ValueError("pyproject.toml must define [tool.quality-gate]")
    return configuration


def compatibility_matrix() -> list[dict[str, str]]:
    raw = load_quality_configuration().get("compatibility")
    if not isinstance(raw, list) or not raw:
        raise ValueError("quality-gate compatibility must be a non-empty array")
    matrix: list[dict[str, str]] = []
    for entry in raw:
        if not isinstance(entry, dict) or set(entry) != {"os", "python-version", "scope"}:
            raise ValueError("each compatibility entry must define os, python-version, and scope")
        normalized = {key: str(value) for key, value in entry.items()}
        if normalized["scope"] not in {"full", "domain"}:
            raise ValueError("compatibility scope must be full or domain")
        matrix.append(normalized)
    return matrix


def primary_python() -> str:
    value = load_quality_configuration().get("primary-python")
    if not isinstance(value, str) or re.fullmatch(r"3\.\d+", value) is None:
        raise ValueError("quality-gate primary-python must use 3.X form")
    return value


def current_commit() -> str:
    commit = capture(["git", "rev-parse", "HEAD"])
    validate_commit(commit)
    return commit


def validate_commit(commit: str) -> None:
    if COMPLETE_SHA.fullmatch(commit) is None:
        raise ValueError("commit must be a complete lowercase Git SHA")


def validate_version(version: str) -> None:
    if RELEASE_VERSION.fullmatch(version) is None:
        raise ValueError("release version must use X.Y.Z format")


def check_quality() -> None:
    commands = [
        ["uv", "run", "ruff", "format", "--check", "."],
        ["uv", "run", "ruff", "check", "."],
        ["uv", "run", "mypy"],
        [
            "uv",
            "run",
            "lint-imports",
            "--cache-dir",
            str(CACHE_ROOT / "import-linter"),
        ],
        ["uv", "run", "pytest", "tests/structure"],
        ["uv", "run", "python", "tools/generate_schemas.py", "--check"],
    ]
    for command in commands:
        run(command)


def check_unit() -> None:
    run(["uv", "run", "pytest", "tests/unit"])


def check_integration() -> None:
    COVERAGE_ROOT.mkdir(parents=True, exist_ok=True)
    run(["uv", "run", "coverage", "erase"])
    run(["uv", "run", "coverage", "run", "-m", "pytest", "tests/unit"])
    run(
        [
            "uv",
            "run",
            "coverage",
            "run",
            "--append",
            "-m",
            "pytest",
            "tests/integration",
        ]
    )
    run(["uv", "run", "coverage", "report"])


def build_distributions(output: Path, *, commit: str, version: str | None = None) -> None:
    validate_commit(commit)
    existing = (
        [path for path in output.iterdir() if not path.name.startswith(".")]
        if output.exists()
        else []
    )
    if existing:
        raise ValueError(f"distribution directory is not empty: {output}")
    output.mkdir(parents=True, exist_ok=True)
    environment = {BUILD_COMMIT_ENV: commit}
    if version is not None:
        validate_version(version)
        environment[VERSION_ENV] = version
    before = capture(["git", "status", "--porcelain", "--untracked-files=no"])
    run(["uv", "build", "--out-dir", str(output)], environment=environment)
    after = capture(["git", "status", "--porcelain", "--untracked-files=no"])
    if after != before:
        raise RuntimeError("distribution build modified tracked files")


def distribution_files(output: Path) -> tuple[Path, Path]:
    wheels = list(output.glob("*.whl"))
    sources = list(output.glob("*.tar.gz"))
    if len(wheels) != 1 or len(sources) != 1:
        raise ValueError("package check requires exactly one wheel and one source archive")
    return wheels[0], sources[0]


def installed_python(environment: Path) -> Path:
    if os.name == "nt":
        return environment / "Scripts" / "python.exe"
    return environment / "bin" / "python"


def installed_cli(environment: Path) -> Path:
    if os.name == "nt":
        return environment / "Scripts" / "pyghostboard.exe"
    return environment / "bin" / "pyghostboard"


def smoke_test_wheel(
    wheel: Path,
    environment: Path,
    *,
    scope: str,
    expected_commit: str,
) -> None:
    run(["uv", "venv", "--python", sys.executable, str(environment)])
    python = installed_python(environment)
    run(["uv", "pip", "install", "--python", str(python), str(wheel)])
    run(
        [
            str(python),
            "-c",
            "from pyghostboard.domain import Match, RuleSet; "
            "from pyghostboard.application import MatchService; "
            "print(Match, RuleSet.standard(), MatchService)",
        ]
    )
    run(
        [
            str(python),
            "-c",
            "from pyghostboard._build_info import BUILD_COMMIT; "
            f"assert BUILD_COMMIT == {expected_commit!r}, BUILD_COMMIT",
        ]
    )
    if scope == "domain":
        return
    cli = installed_cli(environment)
    for arguments in (
        ["--help"],
        ["play", "--help"],
        ["replay", "--help"],
        ["rules", "validate", "--help"],
    ):
        run([str(cli), *arguments])
    run([str(python), "-m", "pyghostboard.agent_runner", "--help"])
    run(
        [
            str(python),
            "-c",
            "from pyghostboard.adapters.recording import MatchRecorder; "
            "recorder = MatchRecorder(None); recorder.discard()",
        ]
    )


def check_package(*, scope: str = "full", commit: str | None = None) -> None:
    if scope not in {"full", "domain"}:
        raise ValueError("package scope must be full or domain")
    with tempfile.TemporaryDirectory(prefix="pyghostboard-package-") as temporary:
        root = Path(temporary)
        output = root / "dist"
        expected_commit = commit or current_commit()
        build_distributions(output, commit=expected_commit)
        wheel, source = distribution_files(output)
        run(["uv", "run", "twine", "check", str(wheel), str(source)])
        smoke_test_wheel(
            wheel,
            root / "venv",
            scope=scope,
            expected_commit=expected_commit,
        )


def check_dependencies() -> None:
    run(["uv", "audit", "--locked", "--preview-features", "audit-command"])


def check_compatibility(scope: str) -> None:
    if scope == "domain":
        run(
            [
                "uv",
                "run",
                "pytest",
                "tests/unit/test_domain.py",
                "tests/unit/test_domain_validation.py",
                "tests/unit/test_application.py",
                "tests/unit/test_package.py",
                "tests/structure",
            ]
        )
    elif scope == "full":
        run(["uv", "run", "pytest", "tests/unit", "tests/integration"])
    else:
        raise ValueError("compatibility scope must be full or domain")
    check_package(scope=scope)


def check_all() -> None:
    check_quality()
    check_integration()
    check_package()
    check_dependencies()


def create_release(output: Path, version: str, commit: str) -> None:
    validate_version(version)
    validate_commit(commit)
    changelog = CHANGELOG.read_text(encoding="utf-8")
    if (
        re.search(rf"^## {re.escape(version)} - \d{{4}}-\d{{2}}-\d{{2}}$", changelog, re.MULTILINE)
        is None
    ):
        raise ValueError(f"CHANGELOG.md has no dated {version} release entry")
    build_distributions(output, commit=commit, version=version)
    wheel, source = distribution_files(output)
    verify_distribution(output, version, commit)
    run(["uv", "run", "twine", "check", str(wheel), str(source)])
    with tempfile.TemporaryDirectory(prefix="pyghostboard-release-install-") as temporary:
        smoke_test_wheel(
            wheel,
            Path(temporary) / "venv",
            scope="full",
            expected_commit=commit,
        )


def parse_arguments(arguments: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)

    check = commands.add_parser("check")
    check.add_argument(
        "stage",
        choices=[
            "quality",
            "unit",
            "integration",
            "package",
            "dependencies",
            "compatibility",
            "all",
        ],
    )
    check.add_argument("--scope", choices=["full", "domain"], default="full")
    check.add_argument("--commit")

    commands.add_parser("matrix")
    commands.add_parser("primary-python")

    release = commands.add_parser("release")
    release.add_argument("--version", required=True)
    release.add_argument("--commit", required=True)
    release.add_argument("--dist-dir", type=Path, default=Path("dist"))
    return parser.parse_args(arguments)


def main(arguments: Sequence[str] | None = None) -> None:
    parsed = parse_arguments(arguments)
    if parsed.command == "matrix":
        print(json.dumps({"include": compatibility_matrix()}, separators=(",", ":")))
        return
    if parsed.command == "primary-python":
        print(primary_python())
        return
    if parsed.command == "release":
        output = parsed.dist_dir if parsed.dist_dir.is_absolute() else ROOT / parsed.dist_dir
        create_release(output, parsed.version, parsed.commit)
        return

    stages = {
        "quality": check_quality,
        "unit": check_unit,
        "integration": check_integration,
        "dependencies": check_dependencies,
        "all": check_all,
    }
    if parsed.stage == "package":
        check_package(scope=parsed.scope, commit=parsed.commit)
    elif parsed.stage == "compatibility":
        check_compatibility(parsed.scope)
    else:
        stages[parsed.stage]()


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as error:
        print(f"release gate failed: {error}", file=sys.stderr)
        raise SystemExit(1) from error
