"""Минимальный веб-сервер Yakumo на стандартной библиотеке."""

from __future__ import annotations

import json
import logging
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable
from urllib.parse import unquote, urlsplit

log = logging.getLogger(__name__)


TEXT_TYPES = {
    ".html": "text/html", ".htm": "text/html", ".css": "text/css", ".js": "text/javascript",
    ".json": "application/json", ".txt": "text/plain", ".md": "text/markdown",
    ".svg": "image/svg+xml", ".xml": "application/xml", ".csv": "text/csv",
}


class Handler(SimpleHTTPRequestHandler):
    routes: dict[str, Callable[[Any], Any]] = {}
    # Явный charset, чтобы браузер не угадывал кодировку русских текстов.
    extensions_map = {**SimpleHTTPRequestHandler.extensions_map,
                      **{ext: f"{ctype}; charset=utf-8" for ext, ctype in TEXT_TYPES.items()}}

    @property
    def route_path(self) -> str:
        """Путь без параметров, с раскодированной кириллицей (/api/%D0%BF -> /api/п)."""
        return unquote(urlsplit(self.path).path, encoding="utf-8", errors="replace")

    def do_GET(self) -> None:  # noqa: N802
        handler = self.routes.get(self.route_path)
        if handler is None:
            super().do_GET()
            return
        try:
            self._respond(handler(self))
        except Exception:  # noqa: BLE001
            log.exception("Ошибка обработчика %s", self.path)
            self._send(500, "application/json; charset=utf-8", b'{"error": "internal"}')

    def _respond(self, result: Any) -> None:
        if isinstance(result, tuple):
            code, ctype, body = result
            self._send(code, ctype, body.encode("utf-8") if isinstance(body, str) else body)
        elif isinstance(result, bytes):
            self._send(200, "application/octet-stream", result)
        elif isinstance(result, str):
            self._send(200, "text/html; charset=utf-8", result.encode("utf-8"))
        else:
            body = json.dumps(result, ensure_ascii=False, indent=2).encode("utf-8")
            self._send(200, "application/json; charset=utf-8", body)

    def _send(self, code: int, ctype: str, body: bytes) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args) -> None:  # noqa: A002
        log.info("%s %s", self.address_string(), format % args)


def create_server(host: str, port: int, static_dir, routes: dict[str, Callable[[Any], Any]]) -> ThreadingHTTPServer:
    handler = type("YakumoHandler", (Handler,), {"routes": routes})
    server = ThreadingHTTPServer((host, port), partial(handler, directory=str(static_dir)))
    server.daemon_threads = True
    return server
