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
