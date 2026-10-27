"""Fixtures shared by the offline and stack tests."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from tests.support.jenkins import Jenkins

ROOT = Path(__file__).resolve().parent.parent
JOB = "order-summary"


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Tests under tests/stack are marked ``stack`` so `-m "not stack"` runs the offline ones."""
    for item in items:
        if "tests/stack" in str(item.fspath).replace(os.sep, "/"):
            item.add_marker(pytest.mark.stack)


@pytest.fixture(scope="session")
def root() -> Path:
    """The repository root."""
    return ROOT


def read_env_file(root: Path) -> dict[str, str]:
    """The variables in .env (empty when `make up` has not run)."""
    path = root / ".env"
    if not path.is_file():
        return {}
    pairs = (line.split("=", 1) for line in path.read_text().splitlines() if "=" in line and not line.startswith("#"))
    return {key: value for key, value in pairs}


@pytest.fixture(scope="session")
def env(root: Path) -> dict[str, str]:
    """Configuration of the running stack, from .env."""
    values = read_env_file(root)
    if not values.get("ADMIN_PASSWORD"):
        pytest.fail("the stack is not up: run `make up` first", pytrace=False)
    return values


@pytest.fixture(scope="session")
def jenkins(env: dict[str, str]) -> Jenkins:
    """An authenticated client for the controller."""
    return Jenkins(f"http://127.0.0.1:{env.get('CONTROLLER_PORT', '18481')}", "admin", env["ADMIN_PASSWORD"])
