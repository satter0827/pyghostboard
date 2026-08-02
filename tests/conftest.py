"""Shared test configuration."""

from pathlib import Path

from hypothesis.configuration import set_hypothesis_home_dir

ROOT = Path(__file__).resolve().parents[1]
set_hypothesis_home_dir(ROOT / ".pyghostboard" / "cache" / "hypothesis")
