"""The lesson's pipeline, run on the controller through its API: report, artifact, parallel stages, failure, approval, token."""

from __future__ import annotations

import json
import urllib.request
from pathlib import Path
from typing import Any

import pytest

from tests.conftest import JOB
from tests.support.jenkins import Jenkins


def stages(jenkins: Jenkins, number: int) -> dict[str, dict[str, Any]]:
    description = jenkins.get_json(f"/job/{JOB}/{number}/wfapi/describe")
    return {stage["name"]: stage for stage in description["stages"]}


def sink_artifacts(env: dict[str, str]) -> list[str]:
    url = f"http://127.0.0.1:{env.get('SINK_PORT', '18482')}/artifacts"
    with urllib.request.urlopen(url, timeout=10) as response:  # noqa: S310
        return list(json.loads(response.read())["artifacts"])


@pytest.fixture(scope="module")
def first_build(jenkins: Jenkins) -> int:
    """A run with the default parameters: the job declares them in the configuration file, so it must be started with them."""
    number = jenkins.trigger(JOB, {"REQUIRE_APPROVAL": "false"})
    jenkins.wait_finished(JOB, number)
    return number


def test_a_run_succeeds_publishes_the_report_and_archives_the_jar(jenkins: Jenkins, first_build: int) -> None:
    build = jenkins.build(JOB, first_build)

    assert build.result == "SUCCESS", jenkins.console(JOB, first_build)[-3000:]
    report = jenkins.get_json(f"/job/{JOB}/{first_build}/testReport/api/json?tree=passCount,failCount,skipCount")
    assert report["failCount"] == 0
    assert report["passCount"] + report["skipCount"] >= 30
    artifacts = jenkins.get_json(f"/job/{JOB}/{first_build}/api/json?tree=artifacts[fileName]")["artifacts"]
    assert [artifact["fileName"] for artifact in artifacts] == ["order-summary-1.0.0.jar"]


def test_the_unit_and_integration_branches_ran_in_parallel(jenkins: Jenkins, first_build: int) -> None:
    by_name = stages(jenkins, first_build)
    unit, integration = by_name["Unit"], by_name["Integration"]

    started_last = max(unit["startTimeMillis"], integration["startTimeMillis"])
    finished_first = min(unit["startTimeMillis"] + unit["durationMillis"], integration["startTimeMillis"] + integration["durationMillis"])
    assert started_last < finished_first, "the two branches did not overlap in time"


def test_the_build_ran_on_the_agent_and_never_on_the_controller(jenkins: Jenkins, first_build: int) -> None:
    console = jenkins.console(JOB, first_build)

    assert "Running on docker-agent" in console
    assert "Running on Jenkins in" not in console


def test_the_publish_step_reached_the_artifact_store(env: dict[str, str], first_build: int) -> None:
    assert "order-summary-1.0.0.jar" in sink_artifacts(env)


def test_the_token_never_appears_in_the_log_even_when_the_step_echoes_it(jenkins: Jenkins, env: dict[str, str], first_build: int) -> None:
    number = jenkins.trigger(JOB, {"ECHO_TOKEN": "true"})
    build = jenkins.wait_finished(JOB, number)
    console = jenkins.console(JOB, number)

    assert build.result == "SUCCESS"
    assert env["PUBLISH_TOKEN"] not in console
    assert "token=****" in console
    assert "Masking supported pattern matches of $TOKEN" in console


def test_the_token_is_not_in_the_environment_of_the_other_steps(jenkins: Jenkins, env: dict[str, str], first_build: int) -> None:
    console = jenkins.console(JOB, first_build)

    assert env["PUBLISH_TOKEN"] not in console
    assert env["ADMIN_PASSWORD"] not in console


def test_a_failing_test_fails_the_build_publishes_the_report_and_archives_nothing(jenkins: Jenkins, first_build: int) -> None:
    number = jenkins.trigger(JOB, {"BREAK_A_TEST": "true"})
    build = jenkins.wait_finished(JOB, number)

    assert build.result == "FAILURE"
    report = jenkins.get_json(f"/job/{JOB}/{number}/testReport/api/json?tree=failCount,passCount")
    assert report["failCount"] == 1
    assert report["passCount"] > 1
    assert jenkins.get_json(f"/job/{JOB}/{number}/api/json?tree=artifacts[fileName]")["artifacts"] == []
    assert "Publish" not in {name for name, stage in stages(jenkins, number).items() if stage["status"] == "SUCCESS"}


def test_an_approval_waits_without_holding_an_executor_and_publishing_continues_after_it(jenkins: Jenkins, first_build: int) -> None:
    from tests.support.waiting import wait_until

    number = jenkins.trigger(JOB, {"REQUIRE_APPROVAL": "true"})
    wait_until("the build to wait for approval", lambda: bool(jenkins.pending_inputs(JOB, number)), timeout=600, interval=3)

    agent = jenkins.get_json("/computer/docker-agent/api/json?tree=executors[currentExecutable[number]]")
    busy = [e for e in agent["executors"] if e.get("currentExecutable")]
    assert busy == [], "the waiting build still holds an executor on the agent"
    assert jenkins.build(JOB, number).building is True

    jenkins.approve(JOB, number)
    assert jenkins.wait_finished(JOB, number).result == "SUCCESS"


def test_the_jenkinsfile_passes_the_controllers_own_linter(root: Path, jenkins: Jenkins) -> None:
    status, body = jenkins.post("/pipeline-model-converter/validate", {"jenkinsfile": (root / "Jenkinsfile").read_text()})

    assert status == 200
    assert "successfully validated" in body
