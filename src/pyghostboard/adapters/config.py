"""TOML and environment configuration adapters."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    TomlConfigSettingsSource,
)

from pyghostboard.domain.models import RuleSet


class RuntimeSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PYGHOSTBOARD_", extra="forbid")

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "WARNING"
    agent_timeout: float = Field(default=10.0, gt=0)
    agent_max_message_bytes: int = Field(default=1_048_576, ge=1_024)
    agent_max_stderr_bytes: int = Field(default=65_536, ge=0)
    ai_iterations: int = Field(default=256, ge=1)
    ai_exploration_weight: float = Field(default=2**0.5, ge=0)
    ai_rollout_plies: int = Field(default=96, ge=1)
    ai_setup_candidate_limit: int = Field(default=256, ge=1)
    max_plies: int = Field(default=1_000, ge=1)


def load_rules(path: Path) -> RuleSet:
    class RuleSettings(BaseSettings):
        model_config = SettingsConfigDict(toml_file=path, extra="forbid")

        rules: RuleSet

        @classmethod
        def settings_customise_sources(
            cls,
            settings_cls: type[BaseSettings],
            init_settings: PydanticBaseSettingsSource,
            env_settings: PydanticBaseSettingsSource,
            dotenv_settings: PydanticBaseSettingsSource,
            file_secret_settings: PydanticBaseSettingsSource,
        ) -> tuple[PydanticBaseSettingsSource, ...]:
            del init_settings, env_settings, dotenv_settings, file_secret_settings
            return (TomlConfigSettingsSource(settings_cls),)

    return RuleSettings().rules  # type: ignore[call-arg]
