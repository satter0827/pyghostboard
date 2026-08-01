"""Integration tests for source and wheel distributions."""

import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

import pyghostboard
from pyghostboard.schemas import SCHEMA_NAMES

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


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
        source_files = {Path(name).name for name in archive.getnames()}

    assert {"CHANGELOG.md", "LICENSE", "README.md", "pyproject.toml"} <= source_files
