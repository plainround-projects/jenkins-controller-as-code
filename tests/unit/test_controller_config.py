"""Checks of the controller's files: the image, the plugin list and the configuration-as-code file."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
import yaml

PLUGIN_LINE = re.compile(r"^[a-z0-9-]+:[A-Za-z0-9._-]+$")
DIGEST_PIN = re.compile(r"^ARG \w+_IMAGE=\S+@sha256:[0-9a-f]{64}$", re.MULTILINE)


def plugin_lines(path: Path) -> list[str]:
    return [line for line in path.read_text().splitlines() if line.strip() and not line.startswith("#")]


@pytest.fixture(scope="module")
def casc(root: Path) -> dict[str, Any]:
    parsed: dict[str, Any] = yaml.safe_load((root / "controller/casc/jenkins.yaml").read_text())
    return parsed


def test_the_controller_has_no_executors_of_its_own(casc: dict[str, Any]) -> None:
    assert casc["jenkins"]["numExecutors"] == 0
    assert casc["jenkins"]["mode"] == "EXCLUSIVE"


def test_anonymous_users_can_do_nothing(casc: dict[str, Any]) -> None:
    strategy = casc["jenkins"]["authorizationStrategy"]["loggedInUsersCanDoAnything"]

    assert strategy["allowAnonymousRead"] is False
    assert casc["jenkins"]["securityRealm"]["local"]["allowsSignup"] is False


def test_every_secret_value_comes_from_the_environment(root: Path) -> None:
    text = (root / "controller/casc/jenkins.yaml").read_text()
    values = re.findall(r"^\s*(?:password|secret):\s*\"?([^\"\n]+)\"?\s*$", text, flags=re.MULTILINE)

    assert values == ["${ADMIN_PASSWORD}", "${PUBLISH_TOKEN}"]


def test_the_credential_has_a_stable_id_and_the_job_uses_it(root: Path, casc: dict[str, Any]) -> None:
    credential = casc["credentials"]["system"]["domainCredentials"][0]["credentials"][0]["string"]

    assert credential["id"] == "publish-token"
    assert "credentialsId: 'publish-token'" in (root / "Jenkinsfile").read_text()


def test_the_agent_is_declared_as_a_labelled_inbound_node(casc: dict[str, Any]) -> None:
    node = casc["jenkins"]["nodes"][0]["permanent"]

    assert (node["name"], node["labelString"]) == ("docker-agent", "docker-agent")
    assert node["launcher"]["inbound"]["webSocket"] is True


def test_the_job_is_defined_in_the_file_and_reads_the_jenkinsfile_from_git(casc: dict[str, Any]) -> None:
    script = casc["jobs"][0]["script"]

    assert "pipelineJob('order-summary')" in script
    assert "scriptPath('Jenkinsfile')" in script


def test_the_dockerfile_pins_the_image_by_digest_and_skips_the_wizard(root: Path) -> None:
    dockerfile = (root / "controller/Dockerfile").read_text()

    assert DIGEST_PIN.search(dockerfile)
    assert "-Djenkins.install.runSetupWizard=false" in dockerfile
    assert ":latest" not in dockerfile and "lts " not in dockerfile


@pytest.mark.parametrize("path", ["agent/Dockerfile", "services/publish-sink/Dockerfile"])
def test_the_other_images_pin_their_bases(root: Path, path: str) -> None:
    text = (root / path).read_text()

    assert re.search(r"^ARG \w+_IMAGE=\S+:\S+@sha256:[0-9a-f]{64}$", text, re.MULTILINE) or "BASE_IMAGE=python:3.13" in text
    assert ":latest" not in text


def test_compose_pins_every_base_image_and_reads_credentials_from_the_environment(root: Path) -> None:
    compose = yaml.safe_load((root / "docker-compose.yml").read_text())
    text = (root / "docker-compose.yml").read_text()

    assert "@sha256:" in compose["services"]["git-server"]["build"]["args"]["BASE_IMAGE"]
    assert "@sha256:" in compose["services"]["publish-sink"]["build"]["args"]["BASE_IMAGE"]
    assert "${ADMIN_PASSWORD:?" in text and "${PUBLISH_TOKEN:?" in text
    for service in compose["services"].values():
        assert service["cap_drop"] == ["ALL"]


def test_plugins_are_pinned_to_exact_versions(root: Path) -> None:
    lines = plugin_lines(root / "controller/plugins.txt")

    assert lines
    assert all(PLUGIN_LINE.match(line) for line in lines), lines
    assert not any(line.endswith(":latest") for line in lines)


def test_the_lock_file_pins_every_plugin_and_contains_each_top_level_plugin_at_its_version(root: Path) -> None:
    lock = plugin_lines(root / "controller/plugins.lock.txt")
    top_level = plugin_lines(root / "controller/plugins.txt")

    assert all(PLUGIN_LINE.match(line) for line in lock)
    assert lock == sorted(lock)
    assert set(top_level) <= set(lock)
    assert len(lock) > len(top_level)


def test_every_plugin_the_configuration_needs_is_installed(root: Path) -> None:
    installed = {line.split(":")[0] for line in plugin_lines(root / "controller/plugins.lock.txt")}

    assert {
        "configuration-as-code",
        "job-dsl",
        "workflow-aggregator",
        "credentials-binding",
        "junit",
        "git",
    } <= installed
