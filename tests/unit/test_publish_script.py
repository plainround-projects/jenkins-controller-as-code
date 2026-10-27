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
