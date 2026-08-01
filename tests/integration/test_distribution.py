"""Integration tests for source and wheel distributions."""

import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

import pyghostboard
from pyghostboard.schemas import SCHEMA_NAMES

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DESIGN_DOCUMENTS = {
    path.relative_to(REPOSITORY_ROOT).as_posix()
    for path in (REPOSITORY_ROOT / "docs" / "design").glob("*.md")
}


def test_distribution_contains_required_public_files(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "build",
            "--no-isolation",
            "--outdir",
            str(tmp_path),
            str(REPOSITORY_ROOT),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr

    wheel = next(tmp_path.glob("pyghostboard-*.whl"))
    source_distribution = next(tmp_path.glob("pyghostboard-*.tar.gz"))

    assert pyghostboard.__version__ in wheel.name

    with zipfile.ZipFile(wheel) as archive:
        wheel_files = set(archive.namelist())

    assert "pyghostboard/__init__.py" in wheel_files
    assert "pyghostboard/py.typed" in wheel_files
    assert {f"pyghostboard/schemas/{name}" for name in SCHEMA_NAMES} <= wheel_files
    assert any(name.endswith(".dist-info/entry_points.txt") for name in wheel_files)

    with tarfile.open(source_distribution, mode="r:gz") as archive:
        source_files: set[str] = set()
        for name in archive.getnames():
            path = Path(name)
            if len(path.parts) > 1:
                source_files.add(Path(*path.parts[1:]).as_posix())

    assert {
        "CHANGELOG.md",
        "CONTRIBUTING.md",
        "LICENSE",
        "README.ja.md",
        "README.md",
        "SECURITY.md",
        "docs/README.md",
        "pyproject.toml",
        "examples/rules.toml",
    } <= source_files
    assert source_files >= DESIGN_DOCUMENTS
    assert not any(name.startswith("docs/notes/") for name in source_files)
