"""Distribution and source provenance shared by private artifact adapters."""

from __future__ import annotations

import re
import subprocess
from importlib.metadata import version
from pathlib import Path

from pyghostboard._build_info import BUILD_COMMIT


def package_version() -> str:
    """Return the installed distribution version."""
    return version("pyghostboard")


def source_commit() -> str:
    """Return release-injected provenance or the current checkout commit."""
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
        raise RuntimeError("build provenance is unavailable")
    return commit


__all__ = ["package_version", "source_commit"]
