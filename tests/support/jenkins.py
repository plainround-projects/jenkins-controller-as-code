"""A small typed client for the parts of the Jenkins API the end-to-end tests use: crumb, builds, reports, input."""

from __future__ import annotations

import base64
import http.cookiejar
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from tests.support.waiting import wait_until


class JenkinsError(RuntimeError):
    """The controller answered with an error status."""

    def __init__(self, status: int, url: str, body: str) -> None:
        """Keep the status and the start of the body for the test report."""
        self.status = status
        super().__init__(f"{status} from {url}: {body[:300]}")


@dataclass(frozen=True)
class Build:
    """A finished (or running) build as the API describes it."""

    number: int
    result: str | None
    building: bool
    duration_ms: int


class Jenkins:
    """Talks to one controller as one user; keeps the session cookie the crumb is bound to."""

    def __init__(self, base_url: str, user: str, password: str, opener: Callable[..., Any] | None = None) -> None:
        """Create the client; ``opener`` is replaceable in tests."""
        self.base_url = base_url.rstrip("/")
        self._authorization = "Basic " + base64.b64encode(f"{user}:{password}".encode()).decode()
        self._cookies = http.cookiejar.CookieJar()
        self._opener = opener or urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self._cookies)).open
        self._crumb: tuple[str, str] | None = None

    def request(self, method: str, path: str, data: Mapping[str, str] | None = None, authenticated: bool = True) -> tuple[int, str]:
        """Send a request and return (status, body); error statuses are returned, not raised."""
        headers: dict[str, str] = {}
        if authenticated:
            headers["Authorization"] = self._authorization
        body = None
        if method == "POST":
            if authenticated:
                field, value = self._crumb_header()
                headers[field] = value
            body = urllib.parse.urlencode(dict(data or {})).encode()
        url = f"{self.base_url}{path}"
        request = urllib.request.Request(url, data=body, headers=headers, method=method)  # noqa: S310
        try:
            with self._opener(request, timeout=60) as response:
                return int(response.status), response.read().decode(errors="replace")
        except urllib.error.HTTPError as error:
            return error.code, error.read().decode(errors="replace")

    def _crumb_header(self) -> tuple[str, str]:
        if self._crumb is None:
            status, body = self.request("GET", "/crumbIssuer/api/json")
            if status != 200:
                raise JenkinsError(status, "/crumbIssuer/api/json", body)
            parsed = json.loads(body)
            self._crumb = (parsed["crumbRequestField"], parsed["crumb"])
        return self._crumb

    def get_json(self, path: str) -> Any:
        """GET a JSON document (path includes the ``/api/json`` part); raise JenkinsError on a non-200."""
        status, body = self.request("GET", path)
        if status != 200:
            raise JenkinsError(status, path, body)
        return json.loads(body)

    def get_text(self, path: str) -> str:
        """GET a text document (a console log, for example)."""
        status, body = self.request("GET", path)
        if status != 200:
            raise JenkinsError(status, path, body)
        return body

    def post(self, path: str, data: Mapping[str, str] | None = None) -> tuple[int, str]:
        """POST a form; return (status, body)."""
        return self.request("POST", path, data)

    def next_build_number(self, job: str) -> int:
        """The number the next build of ``job`` will get."""
        return int(self.get_json(f"/job/{job}/api/json?tree=nextBuildNumber")["nextBuildNumber"])

    def trigger(self, job: str, parameters: Mapping[str, str] | None = None) -> int:
        """Start a build and return its number. A job with no parameters yet is started with /build."""
        number = self.next_build_number(job)
        if parameters:
            status, body = self.post(f"/job/{job}/buildWithParameters", parameters)
        else:
            status, body = self.post(f"/job/{job}/build")
        if status not in (200, 201):
            raise JenkinsError(status, f"/job/{job}/build", body)
        wait_until(f"build #{number} of {job} to start", lambda: self._started(job, number), timeout=120, interval=1)
        return number

    def _started(self, job: str, number: int) -> bool:
        status, _ = self.request("GET", f"/job/{job}/{number}/api/json?tree=number")
        return status == 200

    def build(self, job: str, number: int) -> Build:
        """The current state of a build."""
        data = self.get_json(f"/job/{job}/{number}/api/json?tree=number,result,building,duration")
        return Build(data["number"], data["result"], bool(data["building"]), int(data["duration"]))

    def wait_finished(self, job: str, number: int, timeout: float = 900) -> Build:
        """Wait until the build is no longer running and return it."""

        def finished() -> Build | None:
            current = self.build(job, number)
            return None if current.building else current

        return wait_until(f"build #{number} of {job} to finish", finished, timeout=timeout, interval=3)

    def console(self, job: str, number: int) -> str:
        """The build's console log."""
        return self.get_text(f"/job/{job}/{number}/consoleText")

    def pending_inputs(self, job: str, number: int) -> list[dict[str, Any]]:
        """Input steps the build is waiting on."""
        result: list[dict[str, Any]] = self.get_json(f"/job/{job}/{number}/wfapi/pendingInputActions")
        return result

    def approve(self, job: str, number: int) -> None:
        """Proceed the one pending input of the build."""
        inputs = self.pending_inputs(job, number)
        if len(inputs) != 1:
            raise JenkinsError(409, f"/job/{job}/{number}", f"expected one pending input, found {len(inputs)}")
        status, body = self.post(str(inputs[0]["proceedUrl"]))
        if status not in (200, 302):
            raise JenkinsError(status, inputs[0]["proceedUrl"], body)

    def now_ms(self) -> int:
        """Wall-clock milliseconds, for comparing with stage timestamps."""
        return int(time.time() * 1000)
