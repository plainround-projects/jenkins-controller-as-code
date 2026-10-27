"""The controller is disposable: destroy the container and its volume, start it again, and it is the same controller."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from tests.conftest import JOB, read_env_file
from tests.support.jenkins import Jenkins
from tests.support.shell import run
from tests.support.waiting import wait_until

pytestmark = pytest.mark.rebuild

VOLATILE = re.compile(r"^\s*(?:secret|password|token|apiToken|passwordHash|id):.*$", re.MULTILINE)


def effective_configuration(jenkins: Jenkins) -> str:
    """The controller's effective configuration as configuration as code exports it, without generated secrets."""
    status, body = jenkins.post("/manage/configuration-as-code/export")
    assert status == 200, body[:300]
    return VOLATILE.sub("", body)


def test_destroying_the_container_and_the_volume_gives_the_same_configuration(root: Path) -> None:
    env = read_env_file(root)
    client = Jenkins(f"http://127.0.0.1:{env['CONTROLLER_PORT']}", "admin", env["ADMIN_PASSWORD"])
    before = effective_configuration(client)

    run(["docker", "compose", "down", "--volumes"], cwd=root, timeout=300)
    run(["docker", "compose", "up", "--detach", "--build", "--wait", "--wait-timeout", "600"], cwd=root, timeout=1200)
    run([str(root / "scripts/seed-project.sh")], cwd=root)

    fresh = Jenkins(f"http://127.0.0.1:{env['CONTROLLER_PORT']}", "admin", env["ADMIN_PASSWORD"])
    wait_until("the agent to reconnect", lambda: not fresh.get_json("/computer/docker-agent/api/json?tree=offline")["offline"], timeout=300)
    assert effective_configuration(fresh) == before

    number = fresh.trigger(JOB)
    assert fresh.wait_finished(JOB, number).result == "SUCCESS"
    assert fresh.build(JOB, number).number == 1, "a rebuilt controller starts with no build history"
