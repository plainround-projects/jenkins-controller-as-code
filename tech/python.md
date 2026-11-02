# Python

## 1. What it is

Python is a general-purpose programming language. In this repository it is used for the **tests** and the small helpers behind them, not for the application itself. Version 3.12 or newer is required.

## 2. Why this repository uses it

Python is the language of the tests (including the end-to-end run against Jenkins's API), of the plugin resolver and of the artifact store.

## 3. Where it appears

| File | What it does with this technology |
| --- | --- |
| `tests/support/jenkins.py` | a typed client for the Jenkins HTTP API |
| `tests/support/shell.py, waiting.py` | run commands, wait with an injected clock |
| `tests/unit/` | unit tests of the scripts, the store, the configuration and the Jenkinsfile |
| `tests/stack/` | end-to-end tests against the running stack |
| `scripts/plugins_lock.py` | the plugin resolver |
| `services/publish-sink/` | the artifact store |

## 4. How it works underneath

- `python script.py` starts the interpreter, which compiles the file to bytecode in memory and runs it. A **module** is one `.py` file; a **package** is a folder of modules (with `__init__.py`).
- **Type hints** (`def f(x: int) -> str`) are labels for people and for checkers such as mypy. Python does not enforce them when it runs.
- A **dataclass** (`@dataclass(frozen=True)`) generates `__init__` and comparison methods for a class that is just named fields; `frozen` makes it read-only.
- `from __future__ import annotations` stores hints as text so they can refer to names defined later.
- A **context manager** (`with ...:`) runs set-up and clean-up around a block. A **generic function** such as `def wait_until[T](...)` (Python 3.12 syntax) works for any type `T` and returns the same type it was given.
- `subprocess.run([...])` starts another program and captures its output. A list of arguments (not one string) avoids shell-quoting mistakes.

## 5. Walkthrough of this repository's use

### `tests/support/shell.py` and `waiting.py`
```python
@dataclass(frozen=True)
class CommandResult:
    args: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str
```
A read-only record of one finished command; `CommandError(RuntimeError)` carries the whole result so a failing test shows what the command printed. `run(args, *, cwd=None, env=None, check=True, timeout=300)` calls `subprocess.run(list(args), capture_output=True, text=True, timeout=..., check=False)` and raises `CommandError` on a non-zero exit when `check` is set; a timeout becomes exit code 124 (the code the `timeout` command uses). The `*` makes everything after it keyword-only. `args` is a list, so no shell splitting or quoting is involved.

```python
def wait_until[T](description, probe, *, timeout, interval=2.0, clock=time.monotonic, sleep=time.sleep) -> T:
```
`[T]` is Python 3.12 generic syntax: the type the probe returns is what the function returns. `clock` and `sleep` are parameters with real defaults, so tests inject fakes and finish instantly. The loop calls the probe, returns a truthy value, treats `CommandError` as "not yet" and raises `WaitTimeout(AssertionError)` at the deadline with the last problem in the message.

New here:

### `tests/support/jenkins.py`
```python
class Jenkins:
    def __init__(self, base_url: str, user: str, password: str, opener: Callable[..., Any] = urllib.request.urlopen) -> None: ...
    def request(self, method, path, data=None, authenticated=True) -> tuple[int, str]: ...
    def trigger(self, job: str, parameters: Mapping[str, str] | None = None) -> int: ...
    def wait_finished(self, job: str, number: int, timeout: float) -> Build: ...
```
`Build` is a frozen dataclass (`number`, `result`, `building`, `duration`). `request` builds a `urllib.request.Request`, adds the Basic authorization header, fetches a crumb once and adds it to POSTs, and returns `(status, body)` **instead of raising** on an HTTP error, so a test can assert that a request was refused (for example a 403 or 404). `get_json` and `trigger` raise a named `JenkinsError(status, path, body)` on an unexpected answer. `trigger` reads the job's `nextBuildNumber` first so it knows which build it started, then POSTs `build` or `buildWithParameters`. `wait_finished` uses `wait_until` to poll `.../api/json?tree=number,result,building,duration`. `approve` finds the one pending `input` and POSTs its `proceedUrl`. `opener` is injectable: the offline tests give a fake controller (`tests/unit/test_jenkins_client.py`) so the client is covered without Jenkins.

### The end-to-end tests (`tests/stack/`)
`test_controller.py` (configuration visible through the API), `test_pipeline.py` (a normal run, a broken test, the approval and the masked token) and `test_rebuild.py` (destroy and recreate). They call `jenkins.trigger(...)`, `wait_finished(...)` and assert on the console text, the artifacts and the store's contents. The tests need `make up` first and carry the `stack` marker.

### `scripts/plugins_lock.py`
The resolver (see the plugins note): `re.search` to read the version from the Dockerfile, `urllib.request.urlopen` to fetch JSON, a work-list loop, `sorted(f"{name}:{version}" ...)`, `Path.write_text`, and a `main(argv)` that returns an exit code.





<!-- full-walkthrough:begin -->
### 5.A Full walkthrough: every line of the Python scripts and helpers

Python is a programming language read by a program called the interpreter. A *module* is one `.py` file; `import x` loads another module. A *function* is introduced by `def`, a *class* by `class`, and the code belonging to each is indented. The `publish_sink` package is walked through in `publish-sink.md`, the tests in `pytest.md`. This section covers `scripts/plugins_lock.py` and the test helpers under `tests/support/`.

#### `scripts/plugins_lock.py`: turn the short plugin list into an exact one

Jenkins plugins depend on other plugins. `controller/plugins.txt` lists only the plugins we want (with versions); this script adds every plugin they need, at one exact version each, and writes `controller/plugins.lock.txt`. The image build then installs exactly that list, so two builds on different days produce the same controller.

```python
#!/usr/bin/env python3
"""Resolve controller/plugins.txt into controller/plugins.lock.txt without running Jenkins.

    plugins_lock.py [--check]

The top-level plugins in plugins.txt keep the versions written there. Every plugin they need (required
dependencies, transitively) is added at the newest version the update center offers for the pinned Jenkins line,
which satisfies every minimum version a plugin declares. The result lists each plugin at one exact version, so
`jenkins-plugin-cli` has nothing left to resolve at build time. With --check the file is compared, not written.
"""
```
Line 1 is the shebang. The triple-quoted text is the module's documentation: how to run it (`--check` compares instead of writing) and the rule it follows.

```python
from __future__ import annotations

import json
import re
import sys
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
CORE = re.search(r"jenkins/jenkins:(\d+\.\d+\.\d+)-lts", (ROOT / "controller" / "Dockerfile").read_text())
UPDATE_CENTER = f"https://updates.jenkins.io/dynamic-stable-{CORE.group(1) if CORE else '2.580.1'}/update-center.actual.json"
HEADER = "# Generated by scripts/plugins_lock.py from plugins.txt and the update center of the pinned Jenkins line. Do not edit by hand."
```
- `json` reads the update center's data, `re` finds a version in a text, `sys` gives the command line and `exit`, `urllib.request` downloads over HTTP, `Path` handles files, and `Any` marks "any type".
- `ROOT = Path(__file__).resolve().parent.parent`: `__file__` is this script's path, `.resolve()` makes it absolute, and two `.parent` steps go up from `scripts/` to the repository root.
- `CORE` searches the controller Dockerfile for the Jenkins version (the regular expression `(\d+\.\d+\.\d+)` captures three numbers separated by dots after `jenkins/jenkins:` and before `-lts`).
- `UPDATE_CENTER` builds the URL of the plugin catalogue for exactly that Jenkins line. The expression `CORE.group(1) if CORE else '2.580.1'` uses the match, or a default if the Dockerfile did not match.
- `HEADER` is the first comment line of the lock file.

```python
def fetch_catalog() -> dict[str, Any]:
    """The update center's plugin table for the pinned core version."""
    with urllib.request.urlopen(UPDATE_CENTER, timeout=120) as response:  # noqa: S310 - a fixed https URL
        catalog: dict[str, Any] = json.load(response)["plugins"]
    return catalog
```
`fetch_catalog` downloads the JSON catalogue. `with ... as response:` guarantees the connection is closed afterwards; `timeout=120` aborts a stuck download. The comment `# noqa: S310` tells the linter that the "open this URL" warning is deliberate, since the address is fixed. `json.load(response)["plugins"]` parses the JSON and picks the `plugins` table.

```python
def top_level(path: Path) -> dict[str, str]:
    """Name -> version for every plugin line of plugins.txt."""
    pairs = (line.split(":", 1) for line in path.read_text().splitlines() if line.strip() and not line.startswith("#"))
    return {name: version for name, version in pairs}
```
`top_level` reads `plugins.txt`: every non-blank line that is not a comment is split once at the first colon into name and version; the generator `pairs` is turned into a dictionary by the comprehension `{name: version for ...}`.

```python
def resolve(requested: dict[str, str], catalog: dict[str, Any]) -> dict[str, str]:
    """Every plugin needed, at one version each."""
    lock = dict(requested)
    pending = list(requested)
    while pending:
        name = pending.pop()
        for dependency in catalog[name].get("dependencies", []):
            needed = dependency["name"]
            if dependency.get("optional") or needed == "" or needed in lock or needed not in catalog:
                continue
            lock[needed] = catalog[needed]["version"]
            pending.append(needed)
    return lock
```
`resolve` is the heart. It starts with a copy of the requested plugins (`lock`) and a work list (`pending`). While the list is not empty it takes one plugin (`pop()`), and for each dependency listed in the catalogue it skips optional ones, empty names, plugins already in the lock, and plugins missing from the catalogue (`continue` moves to the next dependency). Anything else is added at the catalogue's newest version and put on the work list, so *its* dependencies get resolved too. The loop ends when no new plugin appears.

```python
def main(argv: list[str]) -> int:
    """Write or check controller/plugins.lock.txt."""
    lock = resolve(top_level(ROOT / "controller" / "plugins.txt"), fetch_catalog())
    text = HEADER + "\n" + "\n".join(sorted(f"{name}:{version}" for name, version in lock.items())) + "\n"
    target = ROOT / "controller" / "plugins.lock.txt"
    if "--check" in argv:
        return 0 if target.read_text() == text else 1
    target.write_text(text)
    print(f"wrote {len(lock)} plugins to {target.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
```
`main` builds the lock, creates the file text (header, then every `name:version` sorted alphabetically so diffs stay small, then a final newline). With `--check` it returns 0 when the file on disk equals the new text and 1 otherwise; without it, it writes the file and prints how many plugins were written. The last two lines are the standard guard `if __name__ == "__main__":` which runs `main` only when the file is executed, not when it is imported, and passes its return value to `sys.exit` as the exit code.

#### The helpers in `tests/support/`

```python
"""Helpers the tests share: running commands, waiting for a condition, reading the controller's state."""
```
A file called `__init__.py` marks a folder as a Python package so `from tests.support.shell import run` works; its only line is a docstring describing what the package holds.

#### `tests/support/shell.py`: run a program and report what it did

When a test needs to run another program (for example one of the repository's scripts), it should get back the exit code and the output, and get a clear error if the program failed. This file does that.

```python
"""Run external commands and report what they did, with typed results and a named error."""

from __future__ import annotations

import subprocess
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

```

- Line 1 is the module's docstring.
- `from __future__ import annotations` tells Python to keep type hints as plain text instead of evaluating them at once. That lets a hint mention a class defined later in the file.
- `import subprocess` loads Python's own module for starting other programs. A **subprocess** is a child process (see the Bash note).
- `from collections.abc import Mapping, Sequence` imports two names used only in type hints: a `Mapping` is anything that behaves like a dictionary, a `Sequence` is anything that behaves like a list.
- `from dataclasses import dataclass` imports a helper described just below.
- `from pathlib import Path` imports the `Path` class: an object that stands for a file or folder path.

```python
@dataclass(frozen=True)
class CommandResult:
    """The outcome of one finished command."""

    args: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str

    @property
    def output(self) -> str:
        """Standard output and standard error together, the way a terminal shows them."""
        return self.stdout + self.stderr

```

- `@dataclass(frozen=True)` is a **decorator**: a line starting with `@` that changes the class right below it. `dataclass` writes the boring parts of a class for you (the `__init__` method and a readable printout) from the list of fields. `frozen=True` makes objects **read-only** after they are created, so a result cannot be changed by mistake.
- `class CommandResult:` and its docstring: a class that holds the outcome of one finished command.
- The four lines `args`, `returncode`, `stdout`, `stderr` declare the **fields**: the command words (`tuple[str, ...]`), its exit code, what it printed on standard output, and what it printed on standard error (see the Bash note for these).
- `@property` turns the next method into something you read without parentheses (`result.output`). `output` returns the two texts joined, "the way a terminal shows them". The docstring inside the method says so.

```python
class CommandError(RuntimeError):
    """A command exited with a non-zero status (or did not finish in time)."""

    def __init__(self, result: CommandResult) -> None:
        """Keep the whole result so the test report shows what the command printed."""
        self.result = result
        command = " ".join(result.args)
        super().__init__(f"{command!r} exited {result.returncode}\n{result.output.strip()}")

```

- `class CommandError(RuntimeError)` creates a new kind of error that is a special case of `RuntimeError`. A named error lets a caller catch exactly this problem.
- `__init__(self, result)` runs when the error is created. It stores the whole result (`self.result = result`) so a test report can show what the command printed.
- `" ".join(result.args)` joins the command words with spaces into one line.
- `super().__init__(…)` calls the parent class's `__init__` with the error message. The message is an f-string: `{command!r}` inserts the command text with quotes around it (`!r` = "show it the way Python would write it in code"), `{result.returncode}` its exit code, `\n` a line break, and `result.output.strip()` the command's output without leading or trailing blank space.

```python
def run(
    args: Sequence[str],
    *,
    cwd: Path | None = None,
    env: Mapping[str, str] | None = None,
    check: bool = True,
    timeout: float = 300,
) -> CommandResult:
    """Run ``args`` and return the result; raise CommandError on a non-zero exit when ``check`` is set."""
```

- The function `run` has a long list of parameters, one per line. `args: Sequence[str]` is the command words. The lone `*` means everything after it **must be given by name** (`run(cmd, check=False)`), which makes calls readable.
- `cwd: Path | None = None` is the folder to run in, or nothing (`= None` is the default). `env: Mapping[str, str] | None = None` replaces the environment variables (see the Bash note), or nothing. `check: bool = True` says "treat a non-zero exit code as an error". `timeout: float = 300` is the longest time to wait, in seconds.
- `-> CommandResult` says what it returns. The docstring explains the behavior.

```python
    try:
        completed = subprocess.run(
            list(args),
            cwd=cwd,
            env=None if env is None else dict(env),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
```

- `try:` starts a block where an error may happen.
- `subprocess.run(…)` starts the program and waits for it to finish. `list(args)` copies the command words into a list. A list (not one long string) means each word is one argument and nothing is split or re-interpreted by a shell.
- `cwd=cwd` runs it in that folder. `env=None if env is None else dict(env)` uses the normal environment unless one was given (a conditional expression: `A if condition else B`).
- `capture_output=True` collects what the program prints instead of showing it. `text=True` gives text instead of raw bytes. `timeout=timeout` stops waiting after that time. `check=False` stops `subprocess` from raising an error by itself; this function does its own error handling.

```python
    except subprocess.TimeoutExpired as expired:
        stdout = expired.stdout.decode() if isinstance(expired.stdout, bytes) else (expired.stdout or "")
        result = CommandResult(tuple(args), 124, stdout, f"timed out after {timeout}s")
        raise CommandError(result) from expired
```

- `except subprocess.TimeoutExpired as expired:` runs if the program took longer than the timeout. The caught error is named `expired`.
- `expired.stdout` holds whatever the program printed before it was stopped. It may be raw bytes, text or nothing; the next line converts it to text: `decode()` turns bytes into text; `isinstance(x, bytes)` asks "is x bytes?"; `(expired.stdout or "")` means "the value, or empty text if there is none".
- A timeout is turned into a normal `CommandResult` with exit code `124` (the number the Unix `timeout` command uses) and the message `timed out after …s`, and then raised as a `CommandError`. `raise … from expired` keeps the original error attached as the cause.

```python
    result = CommandResult(tuple(args), completed.returncode, completed.stdout, completed.stderr)
    if check and result.returncode != 0:
        raise CommandError(result)
    return result
```

- If nothing went wrong, build a `CommandResult` from what `subprocess.run` returned (`completed.returncode`, `.stdout`, `.stderr`).
- `if check and result.returncode != 0:` means "if the caller wants errors and the exit code is not 0", then raise `CommandError`. Otherwise `return result` hands the result back.

#### `tests/support/waiting.py`: wait until something becomes true

A cluster does things in its own time. A test cannot say "do it, then check at once"; it must **wait** until the condition holds, but not forever. This function waits with a limit, and its clock and sleep can be replaced, so a test of the waiting itself needs no real waiting.

```python
"""Poll until a condition holds, with the clock and the sleep injected so the logic is testable."""

from __future__ import annotations

import time
from collections.abc import Callable

from tests.support.shell import CommandError


class WaitTimeout(AssertionError):
    """The condition did not hold within the time allowed."""

```

- The docstring says what the module does. `import time` loads the time functions. `from collections.abc import Callable` imports the hint for "something you can call like a function". `from tests.support.shell import CommandError` imports the error defined above.
- `class WaitTimeout(AssertionError)` is a new error for "waited too long". It inherits from `AssertionError`, the error a failed `assert` raises, so a test runner reports it as a test failure.

```python
def wait_until[T](
    description: str,
    probe: Callable[[], T | None | bool],
    *,
    timeout: float,
    interval: float = 2.0,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> T:
    """Call ``probe`` until it returns something truthy and return that value.

    A probe may raise CommandError (for example ``kubectl get`` on an object that does not exist yet);
    that counts as "not yet". Any other exception is a bug in the test and propagates.
    """
```

- `def wait_until[T](` uses Python 3.12 **generic** syntax. `[T]` declares a placeholder type: whatever type the probe returns is the type this function returns. A generic function works for many types while staying checkable.
- `description: str` names what we wait for. `probe: Callable[[], T | None | bool]` is a function that takes no arguments and returns a value, nothing or a bool. `*` makes the rest keyword-only. `timeout: float` is the limit in seconds; `interval: float = 2.0` the pause between tries.
- `clock: Callable[[], float] = time.monotonic` and `sleep: Callable[[float], None] = time.sleep` are the **replaceable parts**. `time.monotonic` is a clock that only moves forward and cannot jump (unlike the wall clock). `time.sleep` pauses. A test passes fakes here.
- The docstring explains the rule for errors: a `CommandError` inside the probe (for example `kubectl get` for an object that does not exist yet) counts as "not yet"; any other error is a bug in the test and goes up.

```python
    deadline = clock() + timeout
    last_problem = "the probe returned a falsy value"
    while True:
        try:
            value = probe()
            if value:
                return value  # type: ignore[return-value]
            last_problem = f"the probe returned {value!r}"
        except CommandError as error:
            last_problem = str(error).splitlines()[0]
        if clock() >= deadline:
            raise WaitTimeout(f"timed out after {timeout:g}s waiting for {description}: {last_problem}")
        sleep(interval)
```

- `deadline = clock() + timeout` fixes the time at which to give up. `last_problem` remembers why the last try failed, for the final message.
- `while True:` loops forever until `return` or `raise` leaves it.
- Inside `try:`, `value = probe()` calls the probe. `if value:` is true for any "truthy" value (not `None`, `False`, `0`, empty); then `return value` ends the function and returns it. The comment `# type: ignore[return-value]` tells the type checker to skip this one line, because it cannot prove that a truthy `T | None | bool` is a `T`.
- If the value was falsy, remember that (`last_problem = f"the probe returned {value!r}"`).
- `except CommandError as error:` treats a failing command as "not yet" and remembers the first line of its message (`str(error).splitlines()[0]`).
- After each try, `if clock() >= deadline:` raises `WaitTimeout` with a message such as `timed out after 60s waiting for the app: …` (`{timeout:g}` prints the number without extra zeros). Otherwise `sleep(interval)` pauses before the next try.
#### `tests/support/jenkins.py`: a small Jenkins client

Jenkins has a web API: the same address you open in a browser, with `/api/json` added, returns JSON instead of a page. Tests could call it with `curl`, but a small Python class makes tests short and readable. It uses only the standard library. Two Jenkins rules shape the code: every request needs a user name and password (HTTP *Basic authentication*), and every request that changes something (a `POST`) must carry a **crumb**, a one-time-looking token Jenkins issues to defend against forged requests from other web pages. The crumb is tied to the login session, so the client keeps the session cookie.

```python
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

```
The imports: `base64` encodes the login, `http.cookiejar` stores cookies, `json` parses answers, `time` reads the clock, `urllib.error`, `urllib.parse` and `urllib.request` are Python's built-in web client, `Callable` and `Mapping` are type names used in hints, `dataclass` defines a data-holding class, `Any` means "any type". `wait_until` is the waiting helper from `waiting.py`.

```python
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

```
`JenkinsError` is raised when the server answers with an error. Its constructor (`__init__`) stores the status number and calls the parent class's constructor with a message made from the status, the URL and the first 300 characters of the body (`body[:300]` is a *slice*). `Build` is a frozen data class: number, result (`None` while still running), whether it is still `building`, and the duration in milliseconds.

```python
class Jenkins:
    """Talks to one controller as one user; keeps the session cookie the crumb is bound to."""

    def __init__(self, base_url: str, user: str, password: str, opener: Callable[..., Any] | None = None) -> None:
        """Create the client; ``opener`` is replaceable in tests."""
        self.base_url = base_url.rstrip("/")
        self._authorization = "Basic " + base64.b64encode(f"{user}:{password}".encode()).decode()
        self._cookies = http.cookiejar.CookieJar()
        self._opener = opener or urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self._cookies)).open
        self._crumb: tuple[str, str] | None = None
```
`Jenkins.__init__` builds the client. `rstrip("/")` removes a trailing slash from the address. Basic authentication is the text `user:password` encoded as base64 (a way to write bytes as plain characters; it is *not* encryption) and prefixed with `Basic `. The cookie jar keeps session cookies, `build_opener(HTTPCookieProcessor(jar)).open` is a URL opener that sends and stores them, and the `opener` parameter lets unit tests substitute a fake that never touches the network. `_crumb` caches the crumb, `None` until fetched.

```python
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
```
`request` is the one function that sends anything. It builds the headers; a `POST` first fetches the crumb header and encodes the form fields (`urlencode` turns a dictionary into `a=1&b=2`). `noqa: S310` tells the linter the URL scheme is deliberately trusted. `with self._opener(request, timeout=60) as response:` sends the request and returns `(status, body)`. Python raises `HTTPError` for 4xx and 5xx statuses; the `except` converts that into the same `(status, body)` pair, so callers decide what an error means.

```python
    def _crumb_header(self) -> tuple[str, str]:
        if self._crumb is None:
            status, body = self.request("GET", "/crumbIssuer/api/json")
            if status != 200:
                raise JenkinsError(status, "/crumbIssuer/api/json", body)
            parsed = json.loads(body)
            self._crumb = (parsed["crumbRequestField"], parsed["crumb"])
        return self._crumb
```
`_crumb_header` fetches the crumb once from `/crumbIssuer/api/json`, raises `JenkinsError` if that fails, and stores the field name and value from the JSON.

```python
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
```
`get_json` and `get_text` are GET helpers that raise `JenkinsError` unless the status is 200; `get_json` also parses the body. `post` is a thin wrapper that returns the pair.

```python
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
```
`next_build_number` asks for only that field with `?tree=nextBuildNumber`. `trigger` starts a build: it remembers the number the build will get, then POSTs either `/buildWithParameters` (with form values) or `/build` (a job with no parameters). Jenkins answers 201 (created) normally; 200 is also accepted. It then calls `wait_until(...)` with a lambda (a tiny anonymous function) until the build exists, so the caller can safely inspect it. `_started` returns whether the build's page answers 200.

```python
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
```
`build` reads number, result, building flag and duration for one build. `wait_finished` defines an inner function `finished()` that returns the build object when it is no longer running and `None` otherwise; `wait_until` polls it every 3 seconds up to the timeout (default 900 s). `console` downloads the build's log as text.

```python
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
```
`pending_inputs` lists the `input` steps a build is paused on (from the pipeline stage API `wfapi`). `approve` demands exactly one, then POSTs to the "proceed" URL Jenkins provides. A redirect (302) counts as success.

```python
    def burst(self, job: str, count: int, parameters: Mapping[str, str] | None = None) -> list[int]:
        """Queue ``count`` builds at once and return their numbers.

        A build gets its number when it leaves the queue, not when it enters it, so the numbers are the next ``count``
        numbers the job will hand out.
        """
        first = self.next_build_number(job)
        for _ in range(count):
            status, body = self.post(f"/job/{job}/buildWithParameters", parameters or {"_": "1"})
            if status not in (200, 201):
                raise JenkinsError(status, f"/job/{job}/buildWithParameters", body)
        return list(range(first, first + count))

    def timing(self, job: str, number: int) -> tuple[int, int]:
        """(queue time, run time) of a build in milliseconds, from the Pipeline stage view's API."""
        description = self.get_json(f"/job/{job}/{number}/wfapi/describe")
        return int(description["queueDurationMillis"]), int(description["durationMillis"])

    def run_groovy(self, script: str) -> str:
        """Run a Groovy snippet in the controller's script console (administrators only) and return its output."""
        status, body = self.post("/scriptText", {"script": script})
        if status != 200:
            raise JenkinsError(status, "/scriptText", body)
        return body

    def stop(self, job: str, number: int) -> None:
        """Ask a running build to stop."""
        self.post(f"/job/{job}/{number}/stop")

    def now_ms(self) -> int:
        """Wall-clock milliseconds, for comparing with stage timestamps."""
        return int(time.time() * 1000)
```
`burst` queues several builds quickly. The comment explains an important fact: a build gets its number when it leaves the queue, not when it enters, so the returned numbers are the next ones the job hands out. The `{"_": "1"}` placeholder parameter makes Jenkins treat the call as parameterised. `timing` returns queue time and run time in milliseconds from the stage API. `run_groovy` posts a script to `/scriptText`, the administrator-only script console, and returns its text output; the tests use it to inspect the controller. `stop` asks a running build to stop. `now_ms` returns the current time in milliseconds for comparing with timestamps from Jenkins.
<!-- full-walkthrough:end -->

## 6. Try it yourself

1. `.venv/bin/python -c "from tests.support.shell import run; print(run(['echo','hi']).stdout)"` : `hi`.
2. `.venv/bin/python -c "from tests.support.jenkins import Jenkins; print(Jenkins('http://127.0.0.1:18481','admin','x').request('GET','/login',authenticated=False)[0])"` (stack up) : `200`.
3. `.venv/bin/pytest tests/unit -q` : the offline tests.
4. `.venv/bin/mypy` : strict type check passes.
5. `.venv/bin/python scripts/plugins_lock.py --check; echo $?` (network) : `0`.

## 7. Mistakes people make

- Installing packages into the system Python; use a virtual environment (see pip and venv).
- Mutable default arguments (`def f(x=[])`).
- Assuming type hints are checked at run time.
- Building a shell command as one string with user data inside; here the commands are lists.

## 8. Check yourself

1. Does Python check type hints when the program runs?
   *Answer:* No. A separate tool such as mypy checks them.
2. What does `frozen=True` do on a dataclass?
   *Answer:* It makes the instances read-only.
3. Why pass a list to `subprocess.run`?
   *Answer:* Each item is one argument, so no shell splitting or quoting is involved.
4. What is a module and what is a package?
   *Answer:* A module is one `.py` file; a package is a folder of modules.
5. What does `from __future__ import annotations` do?
   *Answer:* It keeps type hints as text, so they can name things defined later.

## 9. Further reading

- Python 3.13 documentation (this repository requires 3.12 or newer): <https://docs.python.org/3.13/>.
