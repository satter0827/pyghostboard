"""Inject an exact source commit into release distributions."""

from __future__ import annotations

import re
import sys
from pathlib import Path

OUTPUT = Path(__file__).resolve().parents[1] / "src" / "pyghostboard" / "_build_info.py"


def main(commit: str) -> None:
    if re.fullmatch(r"[0-9a-f]{40}", commit) is None:
        raise ValueError("commit must be a complete lowercase Git SHA")
    OUTPUT.write_text(
        '"""Build provenance injected by the release workflow."""\n\n'
        "from typing import Final\n\n"
        f'BUILD_COMMIT: Final[str | None] = "{commit}"\n',
        encoding="utf-8",
    )


if __name__ == "__main__":
    main(sys.argv[1])
