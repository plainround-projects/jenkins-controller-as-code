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
