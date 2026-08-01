"""Unit tests for the package metadata contract."""

from importlib.metadata import version

import pyghostboard


def test_public_version_matches_distribution_metadata() -> None:
    assert pyghostboard.__version__ == version("pyghostboard")


def test_public_api_is_explicit() -> None:
    assert pyghostboard.__all__ == ["__version__"]
