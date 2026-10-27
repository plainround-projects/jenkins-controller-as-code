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
