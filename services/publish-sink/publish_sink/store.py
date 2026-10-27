"""Where uploaded artifacts are kept, and who may add to them."""

from __future__ import annotations

import hashlib
import hmac
import re
from dataclasses import dataclass
from pathlib import Path

_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


class Unauthorized(PermissionError):
    """The bearer token is missing or wrong."""


class InvalidName(ValueError):
    """The artifact name could escape the store or is not a plain file name."""


@dataclass(frozen=True)
class Stored:
    """An artifact that was accepted."""

    name: str
    size: int
    sha256: str


class ArtifactStore:
    """Writes artifacts under one directory after checking a token in constant time."""

    def __init__(self, directory: Path, expected_token: str) -> None:
        """Create the store; ``directory`` is created when missing."""
        self._directory = directory
        self._expected = expected_token.encode()
        directory.mkdir(parents=True, exist_ok=True)

    def authorize(self, authorization_header: str | None) -> None:
        """Raise Unauthorized unless the header is ``Bearer <expected token>``."""
        scheme, _, presented = (authorization_header or "").partition(" ")
        if scheme != "Bearer" or not hmac.compare_digest(presented.encode(), self._expected):
            raise Unauthorized("missing or wrong token")

    def put(self, name: str, content: bytes) -> Stored:
        """Store ``content`` as ``name`` (a plain file name) and describe it."""
        if not _NAME.match(name):
            raise InvalidName(f"not a plain artifact name: {name!r}")
        (self._directory / name).write_bytes(content)
        return Stored(name=name, size=len(content), sha256=hashlib.sha256(content).hexdigest())

    def names(self) -> list[str]:
        """The names of every stored artifact, sorted."""
        return sorted(path.name for path in self._directory.iterdir() if path.is_file())
