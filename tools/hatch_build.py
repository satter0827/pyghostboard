"""Inject build provenance without modifying the source tree."""

from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path
from typing import Any

from hatchling.builders.hooks.plugin.interface import BuildHookInterface

BUILD_COMMIT_ENV = "PYGHOSTBOARD_BUILD_COMMIT"


class CustomBuildHook(BuildHookInterface[Any]):
    """Add a generated build-info module to wheel and source archives."""

    def initialize(self, version: str, build_data: dict[str, Any]) -> None:
        del version
        commit = os.environ.get(BUILD_COMMIT_ENV)
        if commit is None:
            return
        if re.fullmatch(r"[0-9a-f]{40}", commit) is None:
            raise ValueError(f"{BUILD_COMMIT_ENV} must be a complete lowercase Git SHA")

        temporary_directory = tempfile.TemporaryDirectory(prefix="pyghostboard-build-")
        self._temporary_directory = temporary_directory
        generated = Path(temporary_directory.name) / "_build_info.py"
        generated.write_text(
            '"""Build provenance injected while creating the distribution."""\n\n'
            "from typing import Final\n\n"
            f'BUILD_COMMIT: Final[str | None] = "{commit}"\n',
            encoding="utf-8",
        )
        target = (
            "pyghostboard/_build_info.py"
            if self.target_name == "wheel"
            else "src/pyghostboard/_build_info.py"
        )
        force_include = build_data.setdefault("force_include", {})
        if not isinstance(force_include, dict):
            raise TypeError("Hatch force_include build data must be a mapping")
        force_include[str(generated)] = target

    def finalize(
        self,
        version: str,
        build_data: dict[str, Any],
        artifact_path: str,
    ) -> None:
        del version, build_data, artifact_path
        temporary_directory = getattr(self, "_temporary_directory", None)
        if temporary_directory is not None:
            temporary_directory.cleanup()
