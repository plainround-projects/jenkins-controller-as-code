"""Settings read from the environment, validated once at start-up."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path


class ConfigError(ValueError):
    """An environment variable is missing or unusable."""


@dataclass(frozen=True)
class Settings:
    """What the store needs to run."""

    expected_token: str = field(repr=False)
    data_dir: Path
    port: int

    @classmethod
    def from_environment(cls, environ: Mapping[str, str] | None = None) -> Settings:
        """Read settings from ``environ`` (default: the process environment)."""
        source = os.environ if environ is None else environ
        token = source.get("EXPECTED_TOKEN", "")
        if len(token) < 16:
            raise ConfigError("EXPECTED_TOKEN must be set to at least 16 characters")
        try:
            port = int(source.get("PORT", "8080"))
        except ValueError as error:
            raise ConfigError("PORT must be an integer") from error
        return cls(expected_token=token, data_dir=Path(source.get("DATA_DIR", "/data")), port=port)
