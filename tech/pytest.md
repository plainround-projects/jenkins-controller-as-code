# pytest

## 1. What it is

pytest is a Python test runner. It finds files named `test_*.py`, runs every function named `test_*`, and reports which passed. A test passes when it finishes without an error; the `assert` statement raises one when its condition is false.

## 2. Why this repository uses it

Offline tests cover everything that needs no containers (scripts, store, configuration, Jenkinsfile, client); stack tests drive the real controller through its API.

## 3. Where it appears

| File | What it does with this technology |
| --- | --- |
| `tests/unit/` | scripts against a real HTTP artifact store, the store, the configuration and Jenkinsfile structure, the Jenkins client against a fake controller |
| `tests/stack/` | controller, pipeline and rebuild tests |
| `pyproject.toml` | markers `stack` and `rebuild`, coverage over `tests/support` and the store |

## 4. How it works underneath

- A **fixture** is a function marked `@pytest.fixture` that builds something a test needs (a client, a folder). A test asks for it by writing the fixture's name as a parameter. `scope="session"` builds it once for the whole run, `scope="module"` once per file.
- A **marker** (`@pytest.mark.stack`) tags tests; `-m "not stack"` selects or skips tags. `--strict-markers` makes an unregistered tag an error.
- `conftest.py` files hold fixtures shared by the tests in their folder.
- `monkeypatch` and `tmp_path` are built-in fixtures for replacing things and getting a throwaway folder.
- `pytest-cov` measures which lines the tests ran; `fail_under = 90` fails the run below 90 percent.

## 5. Walkthrough of this repository's use

```toml
[tool.pytest.ini_options]
pythonpath = [".", "services/publish-sink"]
markers = [
  "stack: needs the controller, agent and services from `make up` and drives Jenkins through its API",
  "rebuild: destroys and recreates the controller (slow); run by `make rebuild-proof`",
]
[tool.coverage.run]
source = ["tests/support", "services/publish-sink/publish_sink"]
```
Two markers: `stack` (needs the running stack) and `rebuild` (destroys and recreates the controller). `make test-offline` runs `-m "not stack"` with coverage over the helpers and the store (95 percent, gate 90). `make run` runs `-m "stack and not rebuild"`.

What the offline tests prove: the publish script sends the token only in a header read from standard input and refuses without a token (the store runs for real in the test); the summary script totals failures; the store refuses a wrong token and a path-like name; the configuration has no executors on the controller, anonymous users can do nothing, every secret value comes from the environment, the credential id is stable and used by the job, and the agent is a labelled inbound node; the Compose file pins every base image and reads its credentials from the environment; the Jenkinsfile has `agent none`, the three parameters, parallel unit and integration stages and a credential block only around the publish step; the Jenkins client handles crumbs, errors and approvals against a fake.






<!-- full-walkthrough:begin -->
### 5.A Full walkthrough: every test file

**What pytest does.** pytest is a program that finds Python functions named `test_*` in files named `test_*.py`, runs each, and reports which passed. A test passes if it finishes without an error; the `assert` statement raises an error when its condition is false. A **fixture** is a function marked `@pytest.fixture` that prepares something (a folder, a client) and is handed to any test that lists its name as a parameter. A **marker** is a label (`stack`, `rebuild`) that lets you select tests with `-m`. `pyproject.toml` (see `toml.md`) declares the markers and the folders to search. In this repository tests come in two groups: **offline** tests (`tests/unit`) that need nothing running, and **stack** tests (`tests/stack`) that drive the real controller.

#### `tests/conftest.py`: shared fixtures

`conftest.py` is a file pytest loads automatically; fixtures defined in it are available to all tests below it.

```python
"""Fixtures shared by the offline and stack tests."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from tests.support.jenkins import Jenkins

ROOT = Path(__file__).resolve().parent.parent
JOB = "order-summary"

```
`ROOT` is the repository root (two folders up from this file). `JOB` is the name of the Jenkins job every stack test uses.

```python
def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Tests under tests/stack are marked ``stack`` so `-m "not stack"` runs the offline ones."""
    for item in items:
        if "tests/stack" in str(item.fspath).replace(os.sep, "/"):
            item.add_marker(pytest.mark.stack)


@pytest.fixture(scope="session")
def root() -> Path:
    """The repository root."""
    return ROOT
```
`pytest_collection_modifyitems` is a **hook**, a function with a special name that pytest calls after it has collected all tests. This one adds the `stack` marker to every test whose file path contains `tests/stack`, so the Makefile's `-m "not stack"` skips them without each file having to say so. `os.sep` is the path separator of the operating system, replaced by `/` so the check also works on Windows. The `root` fixture has `scope="session"`: it is created once per run.

```python
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
```
`read_env_file` parses `.env` into a dictionary: each line containing `=` and not starting with `#` is split once at the first `=`; it returns `{}` when the file is missing. The `env` fixture fails the whole test with a helpful message (`pytrace=False` hides the traceback) when no admin password is present, i.e. when `make up` has not run. The `jenkins` fixture builds an authenticated client for the controller on the configured port.

#### `tests/unit/test_controller_config.py`: checks of the controller's files

```python
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

```
`PLUGIN_LINE` is a regular expression for a valid `name:version` line. `DIGEST_PIN` matches a Dockerfile line like `ARG X_IMAGE=repo:tag@sha256:<64 hex digits>` (`re.MULTILINE` makes `^` and `$` match at every line). `plugin_lines` returns the meaningful lines of a plugin file. The `casc` fixture parses the configuration YAML once per test file (`scope="module"`) with `yaml.safe_load`, which reads plain data and never runs code.

```python
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

```
Each test pins one rule: no executors on the controller and exclusive mode; anonymous read and sign-up are off; the only values for `password:` and `secret:` keys in the file are the two environment placeholders (a regular expression with `findall` collects them, so a hard-coded secret would change the list and fail the test); the credential id is `publish-token` and the Jenkinsfile asks for that same id; the agent is a node with a matching name and label that connects by WebSocket; the job definition names `order-summary` and the `Jenkinsfile` script path.

```python
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

```
The Dockerfile test demands a digest-pinned `ARG` line, the setup-wizard flag, and no `:latest` tag. The next test is **parametrised**: `@pytest.mark.parametrize("path", [...])` runs the same function once per listed value. The compose test loads the YAML, checks that the two build base images carry a digest, that both password variables use the `:?` must-be-set form, and loops over all services asserting `cap_drop == ["ALL"]`.

```python
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
```
Plugin tests: every line in `plugins.txt` is `name:exact-version` and never `:latest`; the lock file lists exact versions, is sorted, contains every top-level plugin, and is longer (it holds the dependencies too); and a set check `{...} <= installed` (is a subset of) confirms that the plugins the configuration needs are in the lock.

#### `tests/unit/test_jenkinsfile.py`: text checks of the Jenkinsfile

```python
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

```
A module-scoped fixture reads the `Jenkinsfile` as text. The first test checks it starts with a comment, contains `pipeline {` and that `agent none` follows immediately (regular expression `pipeline \{\n    agent none`). The second counts exactly two `agent { label 'docker-agent' }` lines: Verify and Publish.

```python
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
```
`jenkinsfile.index("options {")` finds the position of a text, so slicing `[a:b]` cuts out the part between two landmarks. The tests check those slices for the timeout, timestamps and build discarder; for `failFast`, `parallel {` and both branch names inside the Test stage; and, with the regular expression flag `re.S` (dot also matches newlines), that each of the Unit and Integration stages is followed by its own `post { always { junit ... } }` block.

```python
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
```
Exactly one `archiveArtifacts`, inside a `post { success {...} }` block; the Approve stage has `agent none`, an `input message` and the 10-minute timeout; `withCredentials` appears once, around the `publish.sh` call, and the word `TOKEN` does not occur before the Publish stage (after removing `ECHO_TOKEN`, the parameter name). The last test finds all `sh` lines that echo `TOKEN` and requires that it is the single demonstration line behind `if (params.ECHO_TOKEN)`.

#### `tests/unit/test_publish_script.py`: run the real upload script against a real server

```python
"""pipeline/scripts/publish.sh against a real HTTP server: it uploads with the token, refuses without it, never prints it."""

from __future__ import annotations

import threading
from collections.abc import Iterator
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest
from publish_sink.server import build_handler
from publish_sink.store import ArtifactStore

from tests.support.shell import run

TOKEN = "0123456789abcdef0123456789abcdef"


@pytest.fixture
def sink(tmp_path: Path) -> Iterator[tuple[str, Path]]:
    store = ArtifactStore(tmp_path / "store", TOKEN)
    server = ThreadingHTTPServer(("127.0.0.1", 0), build_handler(store))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}", tmp_path / "store"
    server.shutdown()
    server.server_close()


def publish(root: Path, file: Path, url: str, token: str | None) -> tuple[int, str]:
    environment = {"PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin", "PUBLISH_URL": url}
    if token is not None:
        environment["TOKEN"] = token
    result = run([str(root / "pipeline/scripts/publish.sh"), str(file)], env=environment, check=False)
    return result.returncode, result.output
```
The `sink` fixture starts a real `publish_sink` server on a free port (port `0` means "operating system, choose one") in a background thread, `yield`s its address and storage folder to the test, and then shuts it down (code after `yield` is the clean-up). `tmp_path` is a built-in fixture giving a fresh temporary folder. The helper `publish` runs the real `publish.sh` with a controlled environment (a fixed `PATH` and `PUBLISH_URL`, plus `TOKEN` only if given) using the `run` helper with `check=False`, so a non-zero exit is returned instead of raised.

```python
def test_it_uploads_the_file_with_the_right_token(root: Path, sink: tuple[str, Path], tmp_path: Path) -> None:
    url, store = sink
    artifact = tmp_path / "app.jar"
    artifact.write_bytes(b"jar bytes")

    code, output = publish(root, artifact, url, TOKEN)

    assert code == 0, output
    assert (store / "app.jar").read_bytes() == b"jar bytes"
    assert "publish: stored" in output


def test_it_never_prints_the_token(root: Path, sink: tuple[str, Path], tmp_path: Path) -> None:
    url, _ = sink
    artifact = tmp_path / "app.jar"
    artifact.write_bytes(b"x")

    _, output = publish(root, artifact, url, TOKEN)

    assert TOKEN not in output


def test_a_wrong_token_is_refused_and_nothing_is_stored(root: Path, sink: tuple[str, Path], tmp_path: Path) -> None:
    url, store = sink
    artifact = tmp_path / "app.jar"
    artifact.write_bytes(b"x")

    code, output = publish(root, artifact, url, "f" * 32)

    assert code == 1
    assert "refused the upload" in output
    assert not (store / "app.jar").exists()


def test_a_missing_token_is_an_error_before_any_request(root: Path, sink: tuple[str, Path], tmp_path: Path) -> None:
    url, _ = sink
    artifact = tmp_path / "app.jar"
    artifact.write_bytes(b"x")

    code, output = publish(root, artifact, url, None)

    assert code != 0
    assert "TOKEN must be set" in output


def test_a_missing_file_exits_2(root: Path, sink: tuple[str, Path], tmp_path: Path) -> None:
    url, _ = sink

    code, output = publish(root, tmp_path / "nope.jar", url, TOKEN)

    assert code == 2
    assert "no such file" in output
```
Five tests: a correct token stores the file bytes and prints "publish: stored"; the token never appears in the output; a wrong token gives exit code 1, the message "refused the upload" and no stored file; a missing token fails with "TOKEN must be set"; a missing file exits with code 2 and "no such file".

#### `tests/unit/test_publish_sink.py`: the store and the HTTP service

```python
"""The artifact store the pipeline publishes to."""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from collections.abc import Iterator
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest
from publish_sink.config import ConfigError, Settings
from publish_sink.server import build_handler, main
from publish_sink.store import ArtifactStore, InvalidName, Unauthorized

TOKEN = "0123456789abcdef0123456789abcdef"


def test_settings_require_a_long_enough_token() -> None:
    with pytest.raises(ConfigError, match="EXPECTED_TOKEN"):
        Settings.from_environment({"EXPECTED_TOKEN": "short"})


def test_settings_reject_a_bad_port_and_hide_the_token_in_repr() -> None:
    with pytest.raises(ConfigError, match="PORT"):
        Settings.from_environment({"EXPECTED_TOKEN": TOKEN, "PORT": "x"})
    assert TOKEN not in repr(Settings.from_environment({"EXPECTED_TOKEN": TOKEN}))

```
The imports and token constant, then two settings tests: a short token raises `ConfigError` whose message matches `EXPECTED_TOKEN`; a non-numeric port raises with `PORT` in the message and the printed form (`repr`) of the settings does not contain the token.

```python
def test_store_accepts_only_the_exact_bearer_token(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path, TOKEN)

    store.authorize(f"Bearer {TOKEN}")
    for header in (None, "", "Bearer", "Bearer wrong", f"Basic {TOKEN}", f"bearer {TOKEN}"):
        with pytest.raises(Unauthorized):
            store.authorize(header)


@pytest.mark.parametrize("name", ["../x", "a/b", "", ".hidden", "x" * 200, "a b"])
def test_store_refuses_names_that_could_escape(tmp_path: Path, name: str) -> None:
    with pytest.raises(InvalidName):
        ArtifactStore(tmp_path, TOKEN).put(name, b"x")


def test_store_describes_what_it_kept(tmp_path: Path) -> None:
    stored = ArtifactStore(tmp_path, TOKEN).put("app-1.0.jar", b"hello")

    assert (stored.name, stored.size) == ("app-1.0.jar", 5)
    assert stored.sha256 == "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"

```
The store accepts exactly `Bearer <token>`; a loop over bad headers (none, empty, missing token, wrong token, wrong scheme, wrong capitalisation) must each raise `Unauthorized`. A parametrised test feeds six dangerous names (`../x`, a slash, empty, a leading dot, 200 characters, a space) which must raise `InvalidName`. The last test checks the size and the known SHA-256 of the word "hello".

```python
@pytest.fixture
def base_url(tmp_path: Path) -> Iterator[str]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), build_handler(ArtifactStore(tmp_path, TOKEN)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()
    server.server_close()


def call(url: str, method: str = "GET", token: str | None = None, body: bytes | None = None) -> tuple[int, dict[str, object]]:
    request = urllib.request.Request(url, data=body, method=method)  # noqa: S310
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(request, timeout=5) as response:  # noqa: S310
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read())


def test_upload_then_list(base_url: str) -> None:
    assert call(f"{base_url}/artifacts/a.jar", "PUT", TOKEN, b"abc")[0] == 201
    assert call(f"{base_url}/artifacts") == (200, {"artifacts": ["a.jar"]})


def test_upload_without_the_token_is_401_and_stores_nothing(base_url: str) -> None:
    assert call(f"{base_url}/artifacts/a.jar", "PUT", None, b"abc") == (401, {"error": "unauthorized"})
    assert call(f"{base_url}/artifacts")[1] == {"artifacts": []}


def test_upload_with_a_bad_name_or_empty_body_is_400(base_url: str) -> None:
    assert call(f"{base_url}/artifacts/.x", "PUT", TOKEN, b"abc")[0] == 400
    assert call(f"{base_url}/artifacts/a.jar", "PUT", TOKEN, b"")[0] == 400


def test_health_and_unknown_paths(base_url: str) -> None:
    assert call(f"{base_url}/healthz") == (200, {"status": "ok"})
    assert call(f"{base_url}/nope")[0] == 404
    assert call(f"{base_url}/other/a.jar", "PUT", TOKEN, b"x")[0] == 404


def test_main_exits_2_when_the_token_is_missing(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.delenv("EXPECTED_TOKEN", raising=False)

    assert main() == 2
    assert "EXPECTED_TOKEN" in capsys.readouterr().err
```
The `base_url` fixture starts the real handler on a free port. `call` is a helper that sends a request and returns `(status, parsed JSON)`, including for error statuses. The tests: upload then list; upload without a token is 401 and stores nothing; a bad name or empty body is 400; health, unknown paths and a PUT outside `/artifacts/` behave as designed; and `main()` returns 2 when the token is missing (`monkeypatch.delenv` removes the variable for this test only; `capsys` captures what was printed to standard error).

#### `tests/unit/test_summary_script.py`: totals from XML reports

```python
"""pipeline/scripts/test-summary.sh: totals from JUnit XML, and a failing exit when a test failed."""

from __future__ import annotations

from pathlib import Path

from tests.support.shell import run


def report(directory: Path, name: str, tests: int, failures: int = 0, errors: int = 0, skipped: int = 0) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    header = f'<testsuite name="{name}" tests="{tests}" errors="{errors}" skipped="{skipped}" failures="{failures}">'
    (directory / f"TEST-{name}.xml").write_text(f'<?xml version="1.0"?>\n{header}\n</testsuite>\n')


def summarize(root: Path, *directories: Path) -> tuple[int, str]:
    result = run([str(root / "pipeline/scripts/test-summary.sh"), *map(str, directories)], check=False)
    return result.returncode, result.output


def test_it_adds_up_the_suites_of_each_directory(root: Path, tmp_path: Path) -> None:
    unit, integration = tmp_path / "unit", tmp_path / "it"
    report(unit, "a", 10)
    report(unit, "b", 7, skipped=1)
    report(integration, "c", 5)

    code, output = summarize(root, unit, integration)

    assert code == 0
    assert f"{unit}: 17 tests, 0 failed, 0 errors, 1 skipped" in output
    assert f"{integration}: 5 tests, 0 failed, 0 errors, 0 skipped" in output
    assert "total: 22 tests, 0 failed, 0 errors, 1 skipped" in output


def test_a_failure_or_an_error_makes_it_exit_1(root: Path, tmp_path: Path) -> None:
    unit = tmp_path / "unit"
    report(unit, "a", 10, failures=1)
    report(tmp_path / "other", "b", 3, errors=1)

    assert summarize(root, unit)[0] == 1
    assert summarize(root, tmp_path / "other")[0] == 1


def test_a_directory_without_reports_is_named_and_not_an_error(root: Path, tmp_path: Path) -> None:
    code, output = summarize(root, tmp_path / "empty")

    assert code == 0
    assert "no reports" in output


def test_no_arguments_is_a_usage_error(root: Path) -> None:
    assert summarize(root)[0] == 2
```
`report` writes a tiny JUnit XML file with chosen counts; `summarize` runs the real `test-summary.sh` on folders. The tests check the exact summary lines for two folders and the grand total, exit code 1 for one failure or one error, a folder with no reports printed as "no reports" with exit 0, and exit code 2 for no arguments.

#### `tests/unit/test_shell.py`

```python
from __future__ import annotations

import pytest

from tests.support.shell import CommandError, run


def test_run_returns_output_and_status() -> None:
    result = run(["sh", "-c", "echo out; echo err >&2; exit 0"])

    assert (result.returncode, result.stdout, result.stderr) == (0, "out\n", "err\n")
    assert result.output == "out\nerr\n"
```

- Test 1 runs `sh -c "echo out; echo err >&2; exit 0"`, a tiny shell program that prints one line to each output stream and exits with 0. The assert compares a triple: exit code `0`, standard output `"out\n"`, standard error `"err\n"`. `result.output` must be the two joined.

```python
def test_a_failing_command_raises_with_its_output() -> None:
    with pytest.raises(CommandError) as raised:
        run(["sh", "-c", "echo broken >&2; exit 3"])

    assert raised.value.result.returncode == 3
    assert "broken" in str(raised.value)
```

- Test 2: `with pytest.raises(CommandError) as raised:` says "an error of this kind **must** happen inside this block; the test fails if it does not". The command exits with code 3. Afterwards the test checks the error carries the result (exit code 3) and that its text contains `broken`.

```python
def test_check_false_returns_the_failure_instead_of_raising() -> None:
    assert run(["sh", "-c", "exit 4"], check=False).returncode == 4
```

- Test 3: with `check=False` no error is raised; the exit code `4` comes back.

```python
def test_a_command_that_runs_too_long_is_reported_as_timed_out() -> None:
    with pytest.raises(CommandError, match=r"timed out after 0\.2s"):
        run(["sleep", "5"], timeout=0.2)
```

- Test 4: `sleep 5` with a timeout of `0.2` seconds must raise `CommandError` whose message matches the pattern `timed out after 0\.2s` (the backslash makes the dot a literal dot in the regular expression).

#### `tests/unit/test_waiting.py`

```python
from __future__ import annotations

import pytest

from tests.support.shell import CommandError, CommandResult
from tests.support.waiting import WaitTimeout, wait_until

```

- Imports, including the real `wait_until` and `WaitTimeout`.

```python
class FakeClock:
    """A clock that only moves when the code sleeps."""

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += seconds
```

- `FakeClock` is a clock that moves only when the code sleeps. `__call__` makes an object callable like a function (`clock()` returns `now`); `sleep` adds the seconds to `now`. With it, the test passes `clock=clock, sleep=clock.sleep`, and no real time passes.

```python
def test_returns_the_probe_value_as_soon_as_it_is_truthy() -> None:
    clock = FakeClock()
    answers = iter([None, False, "ready"])

    value = wait_until("the answer", lambda: next(answers), timeout=30, interval=2, clock=clock, sleep=clock.sleep)

    assert value == "ready"
    assert clock.now == 4.0
```

- `iter([None, False, "ready"])` makes an iterator; `next(answers)` returns the next item each call. The probe answers "nothing", "no", then "ready". With an interval of 2 seconds, `wait_until` must return `"ready"` after two sleeps: the fake clock must read `4.0`.

```python
def test_a_failing_command_counts_as_not_yet() -> None:
    clock = FakeClock()
    calls = {"count": 0}

    def probe() -> bool:
        calls["count"] += 1
        if calls["count"] < 3:
            raise CommandError(CommandResult(("kubectl", "get"), 1, "", "NotFound"))
        return True

    assert wait_until("the object", probe, timeout=30, interval=1, clock=clock, sleep=clock.sleep) is True
    assert calls["count"] == 3
```

- A probe that fails with `CommandError` twice, then returns True. The test shows a failing command counts as "not yet": `wait_until` returns `True` and the probe was called exactly three times. `calls = {"count": 0}` is a dictionary used as a counter that the inner function can change.

```python
def test_times_out_and_says_what_it_last_saw() -> None:
    clock = FakeClock()

    with pytest.raises(WaitTimeout, match=r"timed out after 10s waiting for the sync: the probe returned False"):
        wait_until("the sync", lambda: False, timeout=10, interval=3, clock=clock, sleep=clock.sleep)

    assert clock.now >= 10
```

- A probe that is always False with a 10-second timeout: `pytest.raises(WaitTimeout, match=…)` demands the message `timed out after 10s waiting for the sync: the probe returned False`. The clock must have passed 10 seconds.

```python
def test_a_bug_in_the_probe_is_not_swallowed() -> None:
    clock = FakeClock()

    def probe() -> bool:
        raise KeyError("status")

    with pytest.raises(KeyError):
        wait_until("anything", probe, timeout=10, clock=clock, sleep=clock.sleep)
```

- A probe that raises `KeyError` (a bug in the test, not a `CommandError`) must **not** be swallowed: `wait_until` lets it escape and the test expects exactly that.
#### `tests/unit/test_jenkins_client.py` and the stack tests

#### `tests/unit/test_jenkins_client.py`: test the client against a pretend Jenkins

These tests prove the client behaves correctly without starting any container. The trick is the `opener` parameter of `Jenkins`: the tests pass in a **fake**, a stand-in object that answers like a controller would and records every request it received. Terms used below: a *test* is a function whose name starts with `test_`; `assert` stops the test with a failure if its condition is false; a *fixture* is shared setup (none is needed here).

```python
"""The Jenkins API client, against a fake that answers like the controller: crumb, builds, reports, input, script console."""

from __future__ import annotations

import io
import json
import urllib.error
import urllib.request
from typing import Any

import pytest

from tests.support.jenkins import Build, Jenkins, JenkinsError

```
The imports: `io` (in-memory byte streams), `json`, the `urllib` pieces whose error and request types the fake must imitate, `Any`, `pytest` (the test framework), and the classes under test.

```python
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

```
`FakeResponse` imitates what `urlopen` returns. Its `__enter__` and `__exit__` methods make it usable in a `with` statement (they are called when the block starts and ends; here they do nothing). `read()` returns the stored bytes, and `status` holds the number.

```python
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
```
`FakeJenkins` has a table `routes` that maps `(method, path)` to an answer. Defining `__call__` makes an instance callable like a function, which is what the client's `opener` parameter expects. On each call it strips the host from the URL, records `(method, path, headers, body)` in `requests` so tests can inspect them afterwards, and looks up the answer. A missing route raises `HTTPError` 404 like a real server; an answer may also be a function (`callable(answer)`) to give different replies on each call. Status 400 or higher is raised as `HTTPError` exactly as real `urllib` does; anything lower returns a `FakeResponse`. The `# type: ignore[arg-type]` comments silence the type checker where the fake is deliberately simpler than the real classes.

```python
CRUMB = (200, json.dumps({"crumbRequestField": "Jenkins-Crumb", "crumb": "abc"}))


def client(routes: dict[tuple[str, str], Any]) -> tuple[Jenkins, FakeJenkins]:
    fake = FakeJenkins({("GET", "/crumbIssuer/api/json"): CRUMB, **routes})
    return Jenkins("http://jenkins.test/", "admin", "secret", opener=fake), fake
```
`CRUMB` is the canned crumb answer. `client(routes)` returns the pair of a `Jenkins` using the fake and the fake itself; the dictionary merge `{... , **routes}` adds the test's routes to the crumb route.

```python
def test_get_json_sends_basic_credentials_and_parses_the_answer() -> None:
    jenkins, fake = client({("GET", "/api/json"): (200, '{"mode": "EXCLUSIVE"}')})

    assert jenkins.get_json("/api/json") == {"mode": "EXCLUSIVE"}
    assert fake.requests[0][2]["Authorization"].startswith("Basic ")
```
First test: a GET returns parsed JSON, and the recorded request headers contain an `Authorization` value starting with `Basic `.

```python
def test_an_error_status_becomes_a_named_error_with_the_start_of_the_body() -> None:
    jenkins, _ = client({("GET", "/boom"): (500, "x" * 500)})

    with pytest.raises(JenkinsError) as raised:
        jenkins.get_json("/boom")

    assert raised.value.status == 500
    assert len(str(raised.value)) < 400
```
An HTTP 500 with a 500-character body becomes `JenkinsError`. `with pytest.raises(JenkinsError) as raised:` asserts the error happens inside the block and keeps it as `raised`; the test checks the status and that the message is shorter than 400 characters (the body was cut to 300).

```python
def test_request_returns_the_status_of_a_refusal_instead_of_raising() -> None:
    jenkins, _ = client({("GET", "/job/team-b/api/json"): (404, "not found")})

    assert jenkins.request("GET", "/job/team-b/api/json") == (404, "not found")


def test_an_unauthenticated_request_carries_no_credentials() -> None:
    jenkins, fake = client({("GET", "/login"): (200, "<html>")})

    assert jenkins.request("GET", "/login", authenticated=False) == (200, "<html>")
    assert "Authorization" not in fake.requests[0][2]
```
`request()` returns `(404, "not found")` rather than raising, and a request made with `authenticated=False` carries no `Authorization` header (`fake.requests[0][2]` is the recorded header dictionary).

```python
def test_a_post_carries_the_crumb_which_is_fetched_once() -> None:
    jenkins, fake = client({("POST", "/a"): (200, ""), ("POST", "/b"): (200, "")})

    jenkins.post("/a", {"k": "v"})
    jenkins.post("/b")

    posts = [request for request in fake.requests if request[0] == "POST"]
    assert all(request[2]["Jenkins-crumb"] == "abc" for request in posts)
    assert sum(1 for request in fake.requests if request[1] == "/crumbIssuer/api/json") == 1
    assert posts[0][3] == b"k=v"
```
Two POSTs must both carry `Jenkins-crumb` (the library capitalises header names this way) and the crumb must be fetched exactly once; the first POST's body is `b"k=v"` (the `b` prefix means bytes). `sum(1 for ... if ...)` counts matching items.

```python
def test_a_missing_crumb_endpoint_is_an_error() -> None:
    fake = FakeJenkins({("GET", "/crumbIssuer/api/json"): (403, "no")})
    jenkins = Jenkins("http://jenkins.test", "admin", "secret", opener=fake)

    with pytest.raises(JenkinsError):
        jenkins.post("/x")
```
If the crumb endpoint answers 403, a POST raises `JenkinsError`.

```python
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
```
`started_job` builds a table of routes for a job called `j` whose next build number is `number`. The three tests check: `trigger` without parameters uses `/build` and returns 7; with parameters it uses `/buildWithParameters`; a refused trigger (status 403) raises.

```python
def test_burst_queues_every_build_and_returns_the_numbers_they_will_get() -> None:
    jenkins, fake = client(started_job(20))

    assert jenkins.burst("j", 3) == [20, 21, 22]
    assert sum(1 for method, path, _, _ in fake.requests if path == "/job/j/buildWithParameters") == 3


def test_a_refused_burst_is_an_error() -> None:
    jenkins, _ = client({**started_job(), ("POST", "/job/j/buildWithParameters"): (500, "x")})

    with pytest.raises(JenkinsError):
        jenkins.burst("j", 2)
```
`burst("j", 3)` with next number 20 returns `[20, 21, 22]` and sends three POSTs; a 500 from the server is an error.

```python
def test_build_state_and_waiting_for_it_to_finish() -> None:
    answers = iter(
        [
            (200, '{"number": 7, "result": null, "building": true, "duration": 0}'),
            (200, '{"number": 7, "result": "SUCCESS", "building": false, "duration": 42}'),
        ]
    )
    jenkins, _ = client({("GET", "/job/j/7/api/json?tree=number,result,building,duration"): lambda: next(answers)})

    assert jenkins.wait_finished("j", 7, timeout=60) == Build(7, "SUCCESS", False, 42)
```
`iter([...])` makes an iterator; each call to `next(answers)` returns the next canned reply, so the first poll says the build is still running (`"result": null`, `"building": true`) and the second says `SUCCESS`. `wait_finished` must return `Build(7, "SUCCESS", False, 42)`; dataclass instances compare equal when all fields are equal.

```python
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
```
The console text, the timing numbers `(1500, 30000)` and the pending input list are each read from the endpoint written in the route table.

```python
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
```
`approve` posts to the single pending input's `proceedUrl` (checked as the last recorded request), refuses when there are zero or several inputs (`match=` is a regular expression matched against the error message), and raises when the proceed request fails.

```python
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
```
The script console returns its text, `stop` posts to the stop URL, and `now_ms()` is larger than 1.7 trillion (a date in 2023, so any real clock passes). A refused script console and a failing `get_text` raise `JenkinsError`.
#### `tests/stack/test_controller.py`: the running controller

```python
"""The running controller: configured entirely by files, no wizard, no executors of its own, anonymous users refused."""

from __future__ import annotations

from pathlib import Path

from tests.support.jenkins import Jenkins
from tests.support.waiting import wait_until


def installed_plugins(jenkins: Jenkins) -> set[str]:
    data = jenkins.get_json("/pluginManager/api/json?depth=1&tree=plugins[shortName,version]")
    return {f"{plugin['shortName']}:{plugin['version']}" for plugin in data["plugins"]}

```
`installed_plugins` asks the plugin manager API for each plugin's short name and version and returns a set of `name:version` strings (the query string `tree=plugins[shortName,version]` limits the answer to those fields).

```python
def test_the_controller_boots_straight_to_login_with_no_setup_wizard(jenkins: Jenkins) -> None:
    status, body = jenkins.request("GET", "/login", authenticated=False)

    assert status == 200
    assert "setupWizard" not in body
    assert "Unlock Jenkins" not in body


def test_anonymous_users_are_refused(jenkins: Jenkins) -> None:
    status, _ = jenkins.request("GET", "/api/json", authenticated=False)

    assert status == 403

```
The login page must load with no "Unlock Jenkins" text (the setup wizard is off), and an anonymous API call must be answered with 403.

```python
def test_the_plugin_list_of_the_running_controller_matches_the_lock_file_exactly(jenkins: Jenkins, root: Path) -> None:
    lock = {line for line in (root / "controller/plugins.lock.txt").read_text().splitlines() if line.strip() and not line.startswith("#")}
    running = installed_plugins(jenkins)

    # Bundled detached-core plugins can appear in the running list; every locked plugin must be there at the exact version.
    assert lock <= running, sorted(lock - running)
    assert {name for name in running if name.split(":")[0] in {entry.split(":")[0] for entry in lock}} == lock


def test_the_built_in_node_has_no_executors(jenkins: Jenkins) -> None:
    node = jenkins.get_json("/computer/(built-in)/api/json?tree=numExecutors")

    assert node["numExecutors"] == 0

```
The locked plugin set must be a subset of the running set (`<=`), and the running plugins that share a name with a lock entry must equal the lock exactly, so the live version of every locked plugin is the locked version. The built-in node must have 0 executors.

```python
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
```
`wait_until` polls the agent until it is online. The lambda uses the walrus operator `:=` to assign `n` inside an expression; `a and b and n` returns the node data only if the first two parts are truthy, which `wait_until` accepts as success. The test then checks the label and 2 executors, that the job `order-summary` exists, and that the credential store contains exactly the one id `publish-token`.

#### `tests/stack/test_pipeline.py`: the pipeline end to end

```python
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

```
`stages` maps stage names to their JSON from the stage-view API. `sink_artifacts` asks the artifact store which files it holds. The `first_build` fixture (module scope: once for the whole file) starts the job with one default parameter and waits for it to finish. It must send a parameter: the job declares its three parameters in the configuration file, and Jenkins refuses a plain "build" request for a parameterised job with `400 Nothing is submitted`, so the client uses the `buildWithParameters` address.

```python
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

```
The first test requires `SUCCESS`, no failed tests, at least 30 passed or skipped tests (the test-report API exposes `passCount`, `failCount` and `skipCount`, not a total), and exactly one archived artifact, the jar. The parallel test finds the latest start and the earliest end of the two branches and asserts `started_last < finished_first`, which is true only if their time ranges overlap. The agent test looks for "Running on docker-agent" in the console and no "Running on Jenkins in" (which would mean the controller ran it). The publish test lists the store.

```python
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

```
The token test triggers a build with `ECHO_TOKEN=true` and requires success, that the real token text never appears in the log, that `token=****` does, and that Jenkins printed its "Masking supported pattern" notice. The next test also confirms neither the token nor the admin password appear in the first build's log.

```python
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
```
The failing-test run (`BREAK_A_TEST=true`) must end `FAILURE`, report exactly one failed test and more than one passing test, archive nothing, and never show Publish as successful. The approval run waits for a pending input, then reads the agent's executors and asserts none is busy (`currentExecutable` empty), that the build is still `building`, approves, and expects `SUCCESS`. The last test posts the Jenkinsfile to the controller's own linter and expects "successfully validated". The function-level `import` inside the approval test is allowed, only done once there.

#### `tests/stack/test_rebuild.py`: destroy and recreate the controller

```python
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

```
`pytestmark = pytest.mark.rebuild` applies the `rebuild` marker to every test in the file, so it only runs through `make rebuild-proof`. `VOLATILE` is a regular expression matching lines whose key is `secret`, `password`, `token`, `apiToken`, `passwordHash` or `id`; `effective_configuration` asks the controller to export its live configuration (`/manage/configuration-as-code/export`) and deletes those lines, because generated values differ between two boots.

```python
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

    number = fresh.trigger(JOB, {"REQUIRE_APPROVAL": "false"})
    assert fresh.wait_finished(JOB, number).result == "SUCCESS"
    assert fresh.build(JOB, number).number == 1, "a rebuilt controller starts with no build history"
```
The proof: export the configuration `before`; run `docker compose down --volumes` (destroys the container and its volume), `up --build` (builds and starts again) and the seed script; wait for the agent to reconnect; export again and assert the two exports are identical. Then run the job once and assert it succeeds and its build number is 1, meaning the fresh controller has no history. That is "the controller is code": its entire state came back from files.
<!-- full-walkthrough:end -->

## 6. Try it yourself

1. `make test-offline` : 73 pass at 95 percent coverage.
2. `.venv/bin/pytest tests/unit -q -x -v | head -40` : one line per test.
3. `.venv/bin/pytest tests/stack --collect-only -q` : the stack tests, listed.
4. `.venv/bin/pytest tests/unit/test_jenkins_client.py -q` : the client against a fake controller.
5. `make run` (stack up) : triggers the job and asserts the results.

## 7. Mistakes people make

- Tests that depend on the order they run in. Here each test builds what it needs (a temporary folder, a fake controller).
- Real sleeps in tests. The waiting helper takes an injected clock, so its tests take no time.
- Marking a test "skip" to make a run green. A skip hides a real failure.

## 8. Check yourself

1. How does pytest find tests?
   *Answer:* Files named `test_*.py` and functions named `test_*`.
2. What is a fixture?
   *Answer:* A function that builds something a test needs, passed in by parameter name.
3. What does `-m "not stack"` do?
   *Answer:* It runs only tests that do not carry the `stack` marker.
4. What makes a test fail?
   *Answer:* An exception, usually from a false `assert`.
5. What does `fail_under = 90` do?
   *Answer:* It fails the run when less than 90 percent of the measured lines ran.

## 9. Further reading

- pytest documentation: <https://docs.pytest.org/en/stable/> (version 9). pytest-cov: <https://pytest-cov.readthedocs.io/>.
