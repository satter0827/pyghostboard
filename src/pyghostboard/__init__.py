"""Public package metadata for pyghostboard."""

from importlib.metadata import version
from typing import Final

__all__ = ["__version__"]

__version__: Final[str] = version("pyghostboard")
