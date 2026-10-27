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
