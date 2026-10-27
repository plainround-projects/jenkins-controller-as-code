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
