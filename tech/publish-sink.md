# Python standard library (the publish-sink service)

## 1. What it is

`publish-sink` is a tiny artifact store written with only Python's standard library. It accepts `PUT /artifacts/<name>` with a valid bearer token, lists artifacts, and answers a health check. It stands in for a real artifact repository.

## 2. Why this repository uses it

The pipeline's last stage needs somewhere to publish and a token to present. The store shows the token handling end to end: the stage uses a credential bound to one step, and the store refuses an upload with the wrong token.

## 3. Where it appears

| File | What it does with this technology |
| --- | --- |
| `services/publish-sink/publish_sink/config.py` | `Settings` from environment variables |
| `services/publish-sink/publish_sink/store.py` | `ArtifactStore`: token check and file writes |
| `services/publish-sink/publish_sink/server.py` | the HTTP interface and clean shutdown |
| `services/publish-sink/Dockerfile` | the image |
| `tests/unit/` | tests over real HTTP |

## 4. How it works underneath

- A **bearer token** is a secret string sent in an HTTP header `Authorization: Bearer <token>`.
- `hmac.compare_digest(a, b)` compares two byte strings in **constant time**, so an attacker cannot learn how many leading characters were right from response timing.
- The store accepts only plain file names (`^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$`), so a name like `../etc/passwd` cannot escape the data folder (**path traversal**).
- HTTP status codes used: 201 created, 400 bad request, 401 unauthorized, 404 not found.

## 5. Walkthrough of this repository's use

### `config.py`
`Settings` is a frozen dataclass with `expected_token: str = field(repr=False)` (`repr=False` keeps the token out of any printed representation), `data_dir` and `port`. `from_environment` requires `EXPECTED_TOKEN` of at least 16 characters (a short secret is refused at start-up), reads `PORT` as an integer and `DATA_DIR` (default `/data`). Errors raise `ConfigError`; `main` prints `configuration error: ...` and exits 2.

### `store.py`
```python
_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")

def authorize(self, authorization_header: str | None) -> None:
    scheme, _, presented = (authorization_header or "").partition(" ")
    if scheme != "Bearer" or not hmac.compare_digest(presented.encode(), self._expected):
        raise Unauthorized("missing or wrong token")

def put(self, name: str, content: bytes) -> Stored:
    if not _NAME.match(name):
        raise InvalidName(f"not a plain artifact name: {name!r}")
    (self._directory / name).write_bytes(content)
    return Stored(name=name, size=len(content), sha256=hashlib.sha256(content).hexdigest())
```
`str.partition(" ")` splits at the first space into three parts; `_` ignores the separator. A missing header becomes the empty string, so it fails the scheme test. The name must start with a letter or digit and contain only letters, digits, dot, underscore, hyphen, up to 128 characters. A successful `put` returns a frozen `Stored` record with the name, size and SHA-256.

### `server.py`
`build_handler(store)` returns a handler **class** closed over the store. `do_PUT` handles `PUT /artifacts/<name>`: it checks the prefix, calls `store.authorize(self.headers.get("Authorization"))`, reads `Content-Length`, refuses a body outside 1 byte to 50 MB, reads exactly that many bytes from `self.rfile`, stores them and answers `201` with the JSON `{name, size, sha256}`. `try / except Unauthorized / except InvalidName / else:` sends 401 or 400 for the failures and 201 in the `else` branch (code that runs only when no exception occurred). `GET /artifacts` lists names; `GET /healthz` answers `ok`.

`main()` builds the server on `0.0.0.0:<port>` and installs `lambda *_: stop.set()` for SIGTERM and SIGINT, runs `serve_forever` in a daemon thread and waits on an Event, then shuts down cleanly. The data directory in Compose is a memory-backed `tmpfs`, so uploads disappear with the container.





<!-- full-walkthrough:begin -->
### 5.A Full walkthrough: every line of the `publish-sink` package

`publish-sink` is a small web service written in Python that plays the part of an artifact repository (a place that stores build outputs such as jars). It accepts `PUT /artifacts/<name>` with a secret token, lists stored files with `GET /artifacts`, and answers `GET /healthz`. It uses only Python's standard library, so there is nothing to install. See `python.md` for Python basics.

#### `publish_sink/__init__.py` and `publish_sink/__main__.py`

```python
"""publish-sink: a tiny artifact store that accepts an upload only with the right bearer token."""
```
A folder with a file called `__init__.py` is a Python *package*. The file holds only a one-line description (a string at the top of a file is called a *docstring*).

```python
"""``python -m publish_sink`` starts the store."""

import sys

from publish_sink.server import main

sys.exit(main())
```
`python -m publish_sink` runs a package by running its `__main__.py`. The file imports `main` from `server.py` and calls `sys.exit(main())`: whatever number `main` returns becomes the process's exit code (0 means success).

#### `publish_sink/config.py`: read and check the settings

```python
"""Settings read from the environment, validated once at start-up."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path


class ConfigError(ValueError):
    """An environment variable is missing or unusable."""

```
- `from __future__ import annotations` lets type hints refer to classes defined later in the file.
- The imports bring in `os` (environment variables), `Mapping` (a read-only dictionary type used only for hints), `dataclass` and `field` (tools to define a plain data-holding class), and `Path` (file paths as objects).
- `class ConfigError(ValueError)` defines a new kind of error, a special case of `ValueError`; the docstring says when it is raised. Its own body is just the docstring, since it needs no behaviour.

```python
@dataclass(frozen=True)
class Settings:
    """What the store needs to run."""

    expected_token: str = field(repr=False)
    data_dir: Path
    port: int

    @classmethod
    def from_environment(cls, environ: Mapping[str, str] | None = None) -> Settings:
        """Read settings from ``environ`` (default: the process environment)."""
        source = os.environ if environ is None else environ
        token = source.get("EXPECTED_TOKEN", "")
        if len(token) < 16:
            raise ConfigError("EXPECTED_TOKEN must be set to at least 16 characters")
        try:
            port = int(source.get("PORT", "8080"))
        except ValueError as error:
            raise ConfigError("PORT must be an integer") from error
        return cls(expected_token=token, data_dir=Path(source.get("DATA_DIR", "/data")), port=port)
```
- `@dataclass(frozen=True)` generates the constructor for a class from its field list, and `frozen=True` makes instances read-only after creation.
- `expected_token: str = field(repr=False)`: the `field(repr=False)` part keeps the secret out of the text Python prints for the object, so it cannot leak into a log or traceback.
- `data_dir: Path` and `port: int` are the other two fields.
- `@classmethod` marks `from_environment` as belonging to the class (it builds an instance), and `cls` is the class itself. The `environ` argument defaults to `None`; line 26 picks the real environment if none is given, which lets tests pass a plain dictionary.
- Line 27 reads `EXPECTED_TOKEN` with an empty-string fallback; line 28 rejects tokens under 16 characters, raising `ConfigError`, so a weak or missing token stops the service at start-up.
- Lines 30-33: `int(...)` converts the port text to a number; if it is not numeric a `ValueError` happens, which is caught by `except ... as error` and re-raised as a clearer `ConfigError` (`raise ... from error` keeps the original as the cause).
- Line 34 builds the result; `/data` is the default folder.

#### `publish_sink/store.py`: save files and check the token

```python
"""Where uploaded artifacts are kept, and who may add to them."""

from __future__ import annotations

import hashlib
import hmac
import re
from dataclasses import dataclass
from pathlib import Path

_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


class Unauthorized(PermissionError):
    """The bearer token is missing or wrong."""


class InvalidName(ValueError):
    """The artifact name could escape the store or is not a plain file name."""


@dataclass(frozen=True)
class Stored:
    """An artifact that was accepted."""

    name: str
    size: int
    sha256: str

```
- `hashlib` computes checksums, `hmac` has a safe comparison function, `re` is regular expressions.
- Line 11 `_NAME` is a compiled pattern: the name must start with a letter or digit and then contain only letters, digits, dot, underscore or dash, up to 128 characters in total. That forbids `/`, `..` and anything else that could walk out of the storage folder (the leading underscore says "internal to this file").
- `Unauthorized` and `InvalidName` are two named error types, so the HTTP layer can answer each with the right status code.
- `Stored` is a frozen data class: the name, size and SHA-256 checksum of an accepted upload.

```python
class ArtifactStore:
    """Writes artifacts under one directory after checking a token in constant time."""

    def __init__(self, directory: Path, expected_token: str) -> None:
        """Create the store; ``directory`` is created when missing."""
        self._directory = directory
        self._expected = expected_token.encode()
        directory.mkdir(parents=True, exist_ok=True)

    def authorize(self, authorization_header: str | None) -> None:
        """Raise Unauthorized unless the header is ``Bearer <expected token>``."""
        scheme, _, presented = (authorization_header or "").partition(" ")
        if scheme != "Bearer" or not hmac.compare_digest(presented.encode(), self._expected):
            raise Unauthorized("missing or wrong token")

    def put(self, name: str, content: bytes) -> Stored:
        """Store ``content`` as ``name`` (a plain file name) and describe it."""
        if not _NAME.match(name):
            raise InvalidName(f"not a plain artifact name: {name!r}")
        (self._directory / name).write_bytes(content)
        return Stored(name=name, size=len(content), sha256=hashlib.sha256(content).hexdigest())

    def names(self) -> list[str]:
        """The names of every stored artifact, sorted."""
        return sorted(path.name for path in self._directory.iterdir() if path.is_file())
```
- `__init__` is the constructor. It keeps the folder, stores the expected token as bytes (`.encode()`), and creates the folder if missing (`parents=True` also creates parents, `exist_ok=True` accepts that it exists).
- `authorize`: `(header or "").partition(" ")` splits `"Bearer abc"` into the scheme `Bearer`, the separator and the presented token; a missing header becomes an empty string. The check `scheme != "Bearer" or not hmac.compare_digest(...)` rejects wrong schemes and wrong tokens. `hmac.compare_digest` compares in *constant time*: an ordinary `==` stops at the first differing byte, which could let an attacker guess a token one character at a time by timing responses.
- `put`: validates the name with the pattern, writes the bytes to `directory / name` (the `/` operator joins paths), and returns a `Stored` with the length and the hex SHA-256.
- `names`: lists the regular files in the folder, sorted.

#### `publish_sink/server.py`: the HTTP layer

```python
"""HTTP interface: PUT /artifacts/<name>, GET /artifacts, GET /healthz."""

from __future__ import annotations

import json
import logging
import signal
import sys
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from publish_sink.config import ConfigError, Settings
from publish_sink.store import ArtifactStore, InvalidName, Unauthorized

LOGGER = logging.getLogger("publish_sink")
MAX_BYTES = 50 * 1024 * 1024

```
The imports bring `json`, `logging` (structured log messages), `signal` and `threading` (clean shutdown), `HTTPStatus` (named status codes), and the standard library's `BaseHTTPRequestHandler` and `ThreadingHTTPServer`. `LOGGER` is this program's logger. `MAX_BYTES` is 50 mebibytes, written as `50 * 1024 * 1024`.

```python
def build_handler(store: ArtifactStore) -> type[BaseHTTPRequestHandler]:
    """Return a handler class bound to ``store``."""

    class Handler(BaseHTTPRequestHandler):
        server_version = "publish-sink"

        def do_GET(self) -> None:
            if self.path == "/healthz":
                self._send(HTTPStatus.OK, {"status": "ok"})
            elif self.path == "/artifacts":
                self._send(HTTPStatus.OK, {"artifacts": store.names()})
            else:
                self._send(HTTPStatus.NOT_FOUND, {"error": "not found"})
```
`build_handler(store)` returns a *class* made on the fly that remembers `store` (this is called a closure; the standard server wants a class, not an object). `server_version` is the name sent in the `Server` header. `do_GET` handles GET requests: `/healthz` gives `{"status": "ok"}`, `/artifacts` the list of names, everything else 404 (not found).

```python
        def do_PUT(self) -> None:
            prefix = "/artifacts/"
            if not self.path.startswith(prefix):
                self._send(HTTPStatus.NOT_FOUND, {"error": "not found"})
                return
            try:
                store.authorize(self.headers.get("Authorization"))
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= MAX_BYTES:
                    self._send(HTTPStatus.BAD_REQUEST, {"error": "a body of 1 byte to 50 MB is required"})
                    return
                stored = store.put(self.path[len(prefix) :], self.rfile.read(length))
            except Unauthorized:
                LOGGER.warning("rejected an upload: missing or wrong token")
                self._send(HTTPStatus.UNAUTHORIZED, {"error": "unauthorized"})
            except InvalidName as error:
                self._send(HTTPStatus.BAD_REQUEST, {"error": str(error)})
            else:
                LOGGER.info("stored %s (%d bytes)", stored.name, stored.size)
                self._send(HTTPStatus.CREATED, {"name": stored.name, "size": stored.size, "sha256": stored.sha256})
```
`do_PUT` handles uploads. Anything outside `/artifacts/` is a 404. Inside the `try`: `authorize` reads the `Authorization` header; `Content-Length` says how many body bytes follow; the size check `0 < length <= MAX_BYTES` is a chained comparison and answers 400 (bad request) outside the range; `self.path[len(prefix):]` is the name after the prefix and `self.rfile.read(length)` reads exactly that many bytes. The handlers below the `try`: `Unauthorized` is logged and answered with 401, `InvalidName` with 400, and the `else` branch (run only when no exception happened) logs the success and answers 201 (created) with name, size and checksum. The token is never logged.

```python
        def _send(self, status: HTTPStatus, body: dict[str, Any]) -> None:
            payload = json.dumps(body).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, format: str, *args: object) -> None:
            LOGGER.debug("%s %s", self.address_string(), format % args)

    return Handler
```
`_send` turns a dictionary into JSON bytes, sends the status line, the two headers `Content-Type` and `Content-Length`, ends the header section (`end_headers`) and writes the body. `log_message` replaces the library's default access log (which would print to standard error for every request) with a debug-level message, so normal runs stay quiet. `return Handler` hands back the finished class.

```python
def main() -> int:
    """Entry point: read settings, serve until SIGTERM or SIGINT, then close cleanly."""
    try:
        settings = Settings.from_environment()
    except ConfigError as error:
        print(f"configuration error: {error}", file=sys.stderr)
        return 2
    logging.basicConfig(level=logging.INFO, format="ts=%(asctime)s level=%(levelname)s msg=%(message)s", stream=sys.stderr)
    server = ThreadingHTTPServer(("0.0.0.0", settings.port), build_handler(ArtifactStore(settings.data_dir, settings.expected_token)))
    stop = threading.Event()
    for signum in (signal.SIGTERM, signal.SIGINT):
        signal.signal(signum, lambda *_: stop.set())
    threading.Thread(target=server.serve_forever, daemon=True).start()
    LOGGER.info("listening on :%d", settings.port)
    stop.wait()
    server.shutdown()
    server.server_close()
    return 0
```
`main` reads the settings (printing a configuration error and returning exit code 2 if invalid), sets the log format to `key=value` pairs, creates a threaded server bound to all interfaces on the chosen port (`0.0.0.0` inside a container is normal; the host port is restricted to the loopback in `docker-compose.yml`), and defines an event `stop`. Each of `SIGTERM` (what `docker stop` sends) and `SIGINT` (Ctrl+C) is wired to set that event. The server runs in a background daemon thread, the main thread waits on `stop`, and then `shutdown()` stops accepting requests and `server_close()` frees the port, giving a clean exit with code 0.
<!-- full-walkthrough:end -->

## 6. Try it yourself

1. `PYTHONPATH=services/publish-sink EXPECTED_TOKEN=0123456789abcdef0123 DATA_DIR=/tmp/store PORT=18499 .venv/bin/python -m publish_sink &` then `curl -s localhost:18499/healthz` : `{"status": "ok"}`.
2. `curl -s -X PUT --data-binary hello -H 'Authorization: Bearer wrong' localhost:18499/artifacts/a.txt` : 401 `unauthorized`.
3. `curl -s -X PUT --data-binary hello -H 'Authorization: Bearer 0123456789abcdef0123' localhost:18499/artifacts/a.txt` : 201 with the SHA-256.
4. `curl -s -X PUT --data-binary x -H 'Authorization: Bearer 0123456789abcdef0123' 'localhost:18499/artifacts/..%2Fx'` : 400 `not a plain artifact name`.
5. `.venv/bin/pytest tests/unit/test_publish_sink.py -q` : the store and server tested over real HTTP.

## 7. Mistakes people make

- Comparing tokens with `==`: timing differences leak information. Use `hmac.compare_digest`.
- Building a path from the request name without validating it.
- Logging the token. The settings object hides it from `repr`.
- Accepting unbounded bodies.

## 8. Check yourself

1. Why `hmac.compare_digest`?
   *Answer:* It compares in constant time, so timing reveals nothing about the secret.
2. What stops `../x` as a name?
   *Answer:* The name regular expression allows only plain file names.
3. What does `field(repr=False)` do?
   *Answer:* Keeps the value out of the dataclass's printed form.
4. Which status means a wrong token?
   *Answer:* 401.
5. Why is the data folder a tmpfs in Compose?
   *Answer:* The store is disposable; uploads vanish with the container.

## 9. Further reading

- `http.server`: <https://docs.python.org/3.13/library/http.server.html>. `hmac.compare_digest`: <https://docs.python.org/3.13/library/hmac.html#hmac.compare_digest>.
