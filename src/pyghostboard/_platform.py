"""Runtime platform boundaries shared by infrastructure entry points."""

from __future__ import annotations

import sys

CURRENT_PLATFORM = sys.platform


class UnsupportedPlatformError(OSError):
    """Raised when an infrastructure feature is unavailable on this platform."""


def require_posix(feature: str) -> None:
    """Reject infrastructure features whose lifecycle guarantees require POSIX."""
    if CURRENT_PLATFORM not in {"darwin", "linux"}:
        raise UnsupportedPlatformError(
            f"{feature} requires macOS or Linux; the domain API remains supported on Windows"
        )


__all__ = ["UnsupportedPlatformError", "require_posix"]
