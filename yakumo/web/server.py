"""Минимальный веб-сервер Yakumo на стандартной библиотеке."""

from __future__ import annotations

import json
import logging
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable, Iterator
from urllib.parse import unquote, urlsplit

from yakumo.core.access import AccessControl, AccessResponse

log = logging.getLogger(__name__)

# Обработчик вернул SENT: ответ он отправил сам (файлы с докачкой, архивы).
SENT = object()

TEXT_TYPES = {
    ".html": "text/html", ".htm": "text/html", ".css": "text/css", ".js": "text/javascript",
    ".json": "application/json", ".txt": "text/plain", ".md": "text/markdown",
    ".svg": "image/svg+xml", ".xml": "application/xml", ".csv": "text/csv",
}


class Handler(SimpleHTTPRequestHandler):
    routes: dict[str, Callable[[Any], Any]] = {}
    access: AccessControl
    SENT = SENT
    # Явный charset, чтобы браузер не угадывал кодировку русских текстов.
    extensions_map = {**SimpleHTTPRequestHandler.extensions_map,
                      **{ext: f"{ctype}; charset=utf-8" for ext, ctype in TEXT_TYPES.items()},
                      ".webp": "image/webp"}  # в старых Windows его нет в реестре типов

    @property
    def route_path(self) -> str:
        """Путь без параметров, с раскодированной кириллицей (/api/%D0%BF -> /api/п)."""
        return unquote(urlsplit(self.path).path, encoding="utf-8", errors="replace")

    def do_GET(self) -> None:  # noqa: N802
        if not self._valid_host():
            return
        if self.route_path == "/login":
            self._send(200, "text/html; charset=utf-8", self.access.login_page().encode("utf-8"))
            return
        if self.route_path == "/api/auth":
            self._call(self.access.state)
            return
        if not self._authorized():
            return
        handler = self.routes.get(self.route_path)
        if handler is None:
            super().do_GET()
            return
        self._call(handler)

    def do_HEAD(self) -> None:  # noqa: N802
        if self._valid_host() and self._authorized():
            super().do_HEAD()

    def do_POST(self) -> None:  # noqa: N802
        """POST-маршруты регистрируются с ключом "POST /путь"."""
        if not self._valid_host():
            return
        if not self._same_origin():
            self.close_connection = True  # тело запроса не прочитано
            self._send(403, "application/json; charset=utf-8", b'{"error": "forbidden"}')
            return
        if self.route_path in ("/api/auth/login", "/api/auth/logout"):
            self._call(self.access.login if self.route_path.endswith("/login") else self.access.logout)
            return
        if not self._authorized():
            return
        if self.route_path == "/api/auth/password":
            self._call(self.access.set_password)
            return
        handler = self.routes.get("POST " + self.route_path)
        if handler is None:
            self._send(404, "application/json; charset=utf-8", b'{"error": "not found"}')
            return
        self._call(handler)

    def _valid_host(self) -> bool:
        if self.access.valid_host(self):
            return True
        self.close_connection = True
        self._send(403, "application/json; charset=utf-8", b'{"error": "forbidden host"}')
        return False

    def _authorized(self) -> bool:
        # Публична только ссылка с секретным токеном, не весь API «Диска».
        if (self.command in ("GET", "HEAD") and self.route_path == "/api/disk/s") or self.access.authorized(self):
            return True
        self.close_connection = True
        if self.route_path.startswith("/api/"):
            self._send(401, "application/json; charset=utf-8", b'{"error": "authentication_required"}')
        else:
            self._send(303, "text/plain; charset=utf-8", b"", {"Location": "/login"})
        return False

    def _call(self, handler: Callable[[Any], Any]) -> None:
        """ValueError в обработчике — ошибка запроса (400), FileNotFoundError — 404."""
        try:
            self._respond(handler(self))
        except (ValueError, FileNotFoundError) as exc:
            code = 404 if isinstance(exc, FileNotFoundError) else 400
            text = str(exc) if isinstance(exc, ValueError) else "Не найдено"
            body = json.dumps({"error": text}, ensure_ascii=False).encode("utf-8")
            self.close_connection = True  # тело запроса могло остаться непрочитанным
            self._send(code, "application/json; charset=utf-8", body)
        except Exception:  # noqa: BLE001
            log.exception("Ошибка обработчика %s", self.path)
            self._send(500, "application/json; charset=utf-8", b'{"error": "internal"}')

    def _same_origin(self) -> bool:
        """Защита от чужих сайтов: только JSON и только со своей страницы.

        Страница с другого сайта не может отправить application/json или свой
        заголовок X-Yakumo без предварительного запроса OPTIONS, а на него мы не
        отвечаем разрешением. С X-Yakumo тело может быть любым (загрузка файлов).
        """
        if (not self.headers.get("Content-Type", "").startswith("application/json")
                and self.headers.get("X-Yakumo") != "1"):
            return False
        origin = self.headers.get("Origin")
        return origin is None or urlsplit(origin).netloc == self.headers.get("Host")

    def read_json(self) -> Any:
        length = int(self.headers.get("Content-Length") or 0)
        if length < 0 or length > 1_000_000:
            raise ValueError("Слишком большой запрос")
        try:
            return json.loads(self.rfile.read(length).decode("utf-8") or "null")
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("Неверный JSON") from exc

    def _respond(self, result: Any) -> None:
        if result is SENT:
            return
        if isinstance(result, AccessResponse):
            body = json.dumps(result.data, ensure_ascii=False).encode("utf-8")
            self._send(result.status, "application/json; charset=utf-8", body, result.headers)
        elif isinstance(result, Iterator):
            self._stream(result)
        elif isinstance(result, tuple):
            code, ctype, body = result
            self._send(code, ctype, body.encode("utf-8") if isinstance(body, str) else body)
        elif isinstance(result, bytes):
            self._send(200, "application/octet-stream", result)
        elif isinstance(result, str):
            self._send(200, "text/html; charset=utf-8", result.encode("utf-8"))
        else:
            body = json.dumps(result, ensure_ascii=False, indent=2).encode("utf-8")
            self._send(200, "application/json; charset=utf-8", body)

    def _stream(self, chunks: Iterator[bytes]) -> None:
        """Ответ частями по мере готовности (чат). Длины нет, соединение закрывается в конце."""
        self.send_response(200)
        self.send_header("Content-Type", "application/x-ndjson; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.close_connection = True
        try:
            for chunk in chunks:
                self.wfile.write(chunk)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            log.info("Клиент закрыл соединение до конца ответа")
        finally:
            close = getattr(chunks, "close", None)
            if close:
                close()  # освободить запрос к внешнему сервису

    def _send(self, code: int, ctype: str, body: bytes, headers: dict[str, str] | None = None) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def log_message(self, format: str, *args) -> None:  # noqa: A002
        log.info("%s %s", self.address_string(), format % args)


def create_server(host: str, port: int, static_dir, routes: dict[str, Callable[[Any], Any]],
                  access: AccessControl | None = None) -> ThreadingHTTPServer:
    handler = type("YakumoHandler", (Handler,), {"routes": routes, "access": access or AccessControl()})
    server = ThreadingHTTPServer((host, port), partial(handler, directory=str(static_dir)))
    server.daemon_threads = True
    return server
