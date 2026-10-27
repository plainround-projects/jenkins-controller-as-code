"""The running controller: configured entirely by files, no wizard, no executors of its own, anonymous users refused."""

from __future__ import annotations

from pathlib import Path

from tests.support.jenkins import Jenkins
from tests.support.waiting import wait_until


def installed_plugins(jenkins: Jenkins) -> set[str]:
    data = jenkins.get_json("/pluginManager/api/json?depth=1&tree=plugins[shortName,version]")
    return {f"{plugin['shortName']}:{plugin['version']}" for plugin in data["plugins"]}


def test_the_controller_boots_straight_to_login_with_no_setup_wizard(jenkins: Jenkins) -> None:
    status, body = jenkins.request("GET", "/login", authenticated=False)

    assert status == 200
    assert "setupWizard" not in body
    assert "Unlock Jenkins" not in body


def test_anonymous_users_are_refused(jenkins: Jenkins) -> None:
    status, _ = jenkins.request("GET", "/api/json", authenticated=False)

    assert status == 403


def test_the_plugin_list_of_the_running_controller_matches_the_lock_file_exactly(jenkins: Jenkins, root: Path) -> None:
    lock = {line for line in (root / "controller/plugins.lock.txt").read_text().splitlines() if line.strip() and not line.startswith("#")}
    running = installed_plugins(jenkins)

    # Bundled detached-core plugins can appear in the running list; every locked plugin must be there at the exact version.
    assert lock <= running, sorted(lock - running)
    assert {name for name in running if name.split(":")[0] in {entry.split(":")[0] for entry in lock}} == lock


def test_the_built_in_node_has_no_executors(jenkins: Jenkins) -> None:
    node = jenkins.get_json("/computer/(built-in)/api/json?tree=numExecutors")

    assert node["numExecutors"] == 0


def test_the_container_agent_is_online_with_its_label(jenkins: Jenkins) -> None:
    node = wait_until(
        "the agent to be online",
        lambda: (n := jenkins.get_json("/computer/docker-agent/api/json?tree=offline,numExecutors,assignedLabels[name]"))
        and not n["offline"]
        and n,
        timeout=180,
    )

    assert "docker-agent" in {label["name"] for label in node["assignedLabels"]}
    assert node["numExecutors"] == 2


def test_the_job_and_the_credential_come_from_the_configuration_file(jenkins: Jenkins) -> None:
    job = jenkins.get_json("/job/order-summary/api/json?tree=name,buildable")
    credentials = jenkins.get_json("/credentials/store/system/domain/_/api/json?tree=credentials[id]")

    assert job["name"] == "order-summary"
    assert [entry["id"] for entry in credentials["credentials"]] == ["publish-token"]
