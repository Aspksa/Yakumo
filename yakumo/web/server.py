"""Минимальный веб-сервер Yakumo на стандартной библиотеке."""

from __future__ import annotations

import json
import logging
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable

log = logging.getLogger(__name__)


class Handler(SimpleHTTPRequestHandler):
    status_provider: Callable[[], dict] = staticmethod(dict)

    def do_GET(self) -> None:  # noqa: N802
        if self.path.split("?")[0] == "/api/status":
            body = json.dumps(self.status_provider(), ensure_ascii=False, indent=2).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        super().do_GET()

    def log_message(self, format: str, *args) -> None:  # noqa: A002
        log.info("%s %s", self.address_string(), format % args)


def create_server(host: str, port: int, static_dir, status_provider: Callable[[], dict]) -> ThreadingHTTPServer:
    handler = type("YakumoHandler", (Handler,), {"status_provider": staticmethod(status_provider)})
    return ThreadingHTTPServer((host, port), partial(handler, directory=str(static_dir)))
