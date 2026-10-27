"""Structure checks of the Jenkinsfile: the lesson's rules, as text assertions (the controller's linter checks the syntax)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest


@pytest.fixture(scope="module")
def jenkinsfile(root: Path) -> str:
    return (root / "Jenkinsfile").read_text()


def test_it_is_declarative_and_has_no_pipeline_level_agent(jenkinsfile: str) -> None:
    assert jenkinsfile.lstrip().startswith("//") and "\npipeline {" in jenkinsfile
    assert re.search(r"pipeline \{\n    agent none", jenkinsfile)


def test_work_runs_on_the_labelled_container_agent(jenkinsfile: str) -> None:
    assert jenkinsfile.count("agent { label 'docker-agent' }") == 2


def test_the_pipeline_has_a_timeout_timestamps_and_bounded_history(jenkinsfile: str) -> None:
    options = jenkinsfile[jenkinsfile.index("options {") : jenkinsfile.index("environment {")]

    assert "timeout(time: 20, unit: 'MINUTES')" in options
    assert "timestamps()" in options
    assert "buildDiscarder" in options


def test_unit_and_integration_tests_run_in_parallel_and_stop_each_other_on_failure(jenkinsfile: str) -> None:
    test_stage = jenkinsfile[jenkinsfile.index("stage('Test')") : jenkinsfile.index("stage('Coverage')")]

    assert "failFast true" in test_stage
    assert "parallel {" in test_stage
    assert "stage('Unit')" in test_stage and "stage('Integration')" in test_stage


def test_each_test_branch_publishes_its_own_report_from_a_post_block(jenkinsfile: str) -> None:
    assert re.search(r"stage\('Unit'\).*?post \{ always \{ junit 'app/target/surefire-reports/\*\.xml' \} \}", jenkinsfile, re.S)
    assert re.search(
        r"stage\('Integration'\).*?post \{ always \{ junit 'app/target/failsafe-reports/\*\.xml' \} \}",
        jenkinsfile,
        re.S,
    )


def test_the_artifact_is_archived_only_after_a_successful_publish(jenkinsfile: str) -> None:
    assert len(re.findall(r"archiveArtifacts", jenkinsfile)) == 1
    assert re.search(r"post \{\s+success \{ archiveArtifacts artifacts: 'app/target/\*\.jar', fingerprint: true \}", jenkinsfile)


def test_the_approval_holds_no_executor(jenkinsfile: str) -> None:
    approve = jenkinsfile[jenkinsfile.index("stage('Approve')") : jenkinsfile.index("stage('Publish')")]

    assert "agent none" in approve
    assert "input message" in approve
    assert "timeout(time: 10, unit: 'MINUTES')" in approve


def test_the_token_is_bound_around_the_publish_steps_only(jenkinsfile: str) -> None:
    assert jenkinsfile.count("withCredentials") == 1
    publish = jenkinsfile[jenkinsfile.index("stage('Publish')") :]
    bound = publish[publish.index("withCredentials") :]
    assert "publish.sh" in bound
    # Nothing before the Publish stage can read it.
    assert "TOKEN" not in jenkinsfile[: jenkinsfile.index("stage('Publish')")].replace("ECHO_TOKEN", "")


def test_no_step_prints_a_credential_except_the_demonstration_behind_a_parameter(jenkinsfile: str) -> None:
    echoes = [line for line in jenkinsfile.splitlines() if line.strip().startswith("sh ") and "echo" in line and "TOKEN" in line]

    assert echoes == ["                            sh 'echo \"token=$TOKEN\"'"]
    assert "if (params.ECHO_TOKEN)" in jenkinsfile
