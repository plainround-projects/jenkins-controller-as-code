"""The Jenkins API client, against a fake that answers like the controller: crumb, builds, reports, input, script console."""

from __future__ import annotations

import io
import json
import urllib.error
import urllib.request
from typing import Any

import pytest

from tests.support.jenkins import Build, Jenkins, JenkinsError


class FakeResponse:
    def __init__(self, status: int, body: str) -> None:
        self.status = status
        self._body = body.encode()

    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, *_exc: object) -> None:
        return None

    def read(self) -> bytes:
        return self._body


class FakeJenkins:
    """Routes (method, path) to canned answers; records every request with its headers and body."""

    def __init__(self, routes: dict[tuple[str, str], Any]) -> None:
        self.routes = routes
        self.requests: list[tuple[str, str, dict[str, str], bytes | None]] = []

    def __call__(self, request: urllib.request.Request, timeout: float = 0) -> FakeResponse:
        path = request.full_url.removeprefix("http://jenkins.test")
        method = request.get_method()
        self.requests.append((method, path, dict(request.header_items()), request.data))  # type: ignore[arg-type]
        answer = self.routes.get((method, path))
        if answer is None:
            raise urllib.error.HTTPError(request.full_url, 404, "not found", {}, io.BytesIO(b"nope"))  # type: ignore[arg-type]
        status, body = answer() if callable(answer) else answer
        if status >= 400:
            raise urllib.error.HTTPError(request.full_url, status, "error", {}, io.BytesIO(body.encode()))  # type: ignore[arg-type]
        return FakeResponse(status, body)


CRUMB = (200, json.dumps({"crumbRequestField": "Jenkins-Crumb", "crumb": "abc"}))


def client(routes: dict[tuple[str, str], Any]) -> tuple[Jenkins, FakeJenkins]:
    fake = FakeJenkins({("GET", "/crumbIssuer/api/json"): CRUMB, **routes})
    return Jenkins("http://jenkins.test/", "admin", "secret", opener=fake), fake


def test_get_json_sends_basic_credentials_and_parses_the_answer() -> None:
    jenkins, fake = client({("GET", "/api/json"): (200, '{"mode": "EXCLUSIVE"}')})

    assert jenkins.get_json("/api/json") == {"mode": "EXCLUSIVE"}
    assert fake.requests[0][2]["Authorization"].startswith("Basic ")


def test_an_error_status_becomes_a_named_error_with_the_start_of_the_body() -> None:
    jenkins, _ = client({("GET", "/boom"): (500, "x" * 500)})

    with pytest.raises(JenkinsError) as raised:
        jenkins.get_json("/boom")

    assert raised.value.status == 500
    assert len(str(raised.value)) < 400


def test_request_returns_the_status_of_a_refusal_instead_of_raising() -> None:
    jenkins, _ = client({("GET", "/job/team-b/api/json"): (404, "not found")})

    assert jenkins.request("GET", "/job/team-b/api/json") == (404, "not found")


def test_an_unauthenticated_request_carries_no_credentials() -> None:
    jenkins, fake = client({("GET", "/login"): (200, "<html>")})

    assert jenkins.request("GET", "/login", authenticated=False) == (200, "<html>")
    assert "Authorization" not in fake.requests[0][2]


def test_a_post_carries_the_crumb_which_is_fetched_once() -> None:
    jenkins, fake = client({("POST", "/a"): (200, ""), ("POST", "/b"): (200, "")})

    jenkins.post("/a", {"k": "v"})
    jenkins.post("/b")

    posts = [request for request in fake.requests if request[0] == "POST"]
    assert all(request[2]["Jenkins-crumb"] == "abc" for request in posts)
    assert sum(1 for request in fake.requests if request[1] == "/crumbIssuer/api/json") == 1
    assert posts[0][3] == b"k=v"


def test_a_missing_crumb_endpoint_is_an_error() -> None:
    fake = FakeJenkins({("GET", "/crumbIssuer/api/json"): (403, "no")})
    jenkins = Jenkins("http://jenkins.test", "admin", "secret", opener=fake)

    with pytest.raises(JenkinsError):
        jenkins.post("/x")


def started_job(number: int = 7) -> dict[tuple[str, str], Any]:
    return {
        ("GET", "/job/j/api/json?tree=nextBuildNumber"): (200, json.dumps({"nextBuildNumber": number})),
        ("POST", "/job/j/build"): (201, ""),
        ("POST", "/job/j/buildWithParameters"): (201, ""),
        ("GET", f"/job/j/{number}/api/json?tree=number"): (200, "{}"),
    }


def test_trigger_without_parameters_starts_a_plain_build_and_returns_its_number() -> None:
    jenkins, fake = client(started_job())

    assert jenkins.trigger("j") == 7
    assert ("POST", "/job/j/build") in [(method, path) for method, path, _, _ in fake.requests]


def test_trigger_with_parameters_uses_build_with_parameters() -> None:
    jenkins, fake = client(started_job())

    assert jenkins.trigger("j", {"ECHO_TOKEN": "true"}) == 7
    assert ("POST", "/job/j/buildWithParameters") in [(method, path) for method, path, _, _ in fake.requests]


def test_a_refused_trigger_is_an_error() -> None:
    jenkins, _ = client({**started_job(), ("POST", "/job/j/build"): (403, "no")})

    with pytest.raises(JenkinsError):
        jenkins.trigger("j")


def test_burst_queues_every_build_and_returns_the_numbers_they_will_get() -> None:
    jenkins, fake = client(started_job(20))

    assert jenkins.burst("j", 3) == [20, 21, 22]
    assert sum(1 for method, path, _, _ in fake.requests if path == "/job/j/buildWithParameters") == 3


def test_a_refused_burst_is_an_error() -> None:
    jenkins, _ = client({**started_job(), ("POST", "/job/j/buildWithParameters"): (500, "x")})

    with pytest.raises(JenkinsError):
        jenkins.burst("j", 2)


def test_build_state_and_waiting_for_it_to_finish() -> None:
    answers = iter(
        [
            (200, '{"number": 7, "result": null, "building": true, "duration": 0}'),
            (200, '{"number": 7, "result": "SUCCESS", "building": false, "duration": 42}'),
        ]
    )
    jenkins, _ = client({("GET", "/job/j/7/api/json?tree=number,result,building,duration"): lambda: next(answers)})

    assert jenkins.wait_finished("j", 7, timeout=60) == Build(7, "SUCCESS", False, 42)


def test_console_timing_and_pending_inputs_are_read_from_their_endpoints() -> None:
    inputs = [{"id": "Approve", "proceedUrl": "/job/j/7/wfapi/inputSubmit?inputId=Approve"}]
    jenkins, _ = client(
        {
            ("GET", "/job/j/7/consoleText"): (200, "Finished: SUCCESS"),
            ("GET", "/job/j/7/wfapi/describe"): (200, '{"queueDurationMillis": 1500, "durationMillis": 30000}'),
            ("GET", "/job/j/7/wfapi/pendingInputActions"): (200, json.dumps(inputs)),
        }
    )

    assert jenkins.console("j", 7) == "Finished: SUCCESS"
    assert jenkins.timing("j", 7) == (1500, 30000)
    assert jenkins.pending_inputs("j", 7) == inputs


def test_approve_posts_to_the_single_pending_inputs_proceed_url() -> None:
    inputs = [{"id": "Approve", "proceedUrl": "/job/j/7/wfapi/inputSubmit?inputId=Approve"}]
    jenkins, fake = client(
        {
            ("GET", "/job/j/7/wfapi/pendingInputActions"): (200, json.dumps(inputs)),
            ("POST", "/job/j/7/wfapi/inputSubmit?inputId=Approve"): (200, ""),
        }
    )

    jenkins.approve("j", 7)

    assert fake.requests[-1][1] == "/job/j/7/wfapi/inputSubmit?inputId=Approve"


def test_approve_refuses_when_nothing_or_several_inputs_are_pending() -> None:
    jenkins, _ = client({("GET", "/job/j/7/wfapi/pendingInputActions"): (200, "[]")})

    with pytest.raises(JenkinsError, match="expected one pending input"):
        jenkins.approve("j", 7)


def test_a_failed_approval_is_an_error() -> None:
    inputs = [{"id": "Approve", "proceedUrl": "/job/j/7/wfapi/inputSubmit?inputId=Approve"}]
    jenkins, _ = client(
        {
            ("GET", "/job/j/7/wfapi/pendingInputActions"): (200, json.dumps(inputs)),
            ("POST", "/job/j/7/wfapi/inputSubmit?inputId=Approve"): (500, "no"),
        }
    )

    with pytest.raises(JenkinsError):
        jenkins.approve("j", 7)


def test_script_console_stop_and_the_clock() -> None:
    jenkins, fake = client({("POST", "/scriptText"): (200, "1"), ("POST", "/job/j/7/stop"): (200, "")})

    assert jenkins.run_groovy("println 1") == "1"
    jenkins.stop("j", 7)
    assert jenkins.now_ms() > 1_700_000_000_000
    assert any(path == "/job/j/7/stop" for _, path, _, _ in fake.requests)


def test_a_refused_script_console_is_an_error() -> None:
    jenkins, _ = client({("POST", "/scriptText"): (403, "no")})

    with pytest.raises(JenkinsError):
        jenkins.run_groovy("println 1")


def test_get_text_returns_the_body_and_raises_on_an_error() -> None:
    jenkins, _ = client({("GET", "/ok"): (200, "text"), ("GET", "/bad"): (500, "x")})

    assert jenkins.get_text("/ok") == "text"
    with pytest.raises(JenkinsError):
        jenkins.get_text("/bad")
