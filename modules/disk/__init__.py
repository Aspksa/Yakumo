"""«Диск» — личное хранилище файлов в веб-версии, как Яндекс Диск или Облако Mail.ru.

Файлы лежат рядом с программой (на том же переносном диске), в папке
``YakumoData/disk`` в портативном режиме или ``YakumoDisk`` в остальных случаях.
Пути хранятся относительными, так что смена буквы диска ничего не ломает.
"""

from __future__ import annotations

import html
import os
import re
import zipfile
from pathlib import Path
from urllib.parse import parse_qs, quote, urlsplit

from yakumo.core.network import lan_address

from .store import CHUNK, Disk, DiskError, mime_of

NAME = "Диск"
VERSION = "1.0"

# Такие файлы браузер мог бы выполнить как страницу Yakumo: показываем как текст или в песочнице.
AS_TEXT = {".html", ".htm", ".xhtml", ".mht", ".mhtml", ".shtml"}
SANDBOX = {".svg", ".xml", ".pdf"}


def disk_root(paths) -> Path:
    """Папка «Диска» на том же носителе, что и программа."""
    app, data = Path(paths.app).resolve(), Path(paths.data).resolve()
    if app == data or app in data.parents:  # портативный режим: данные уже рядом
        return data / "disk"
    target = app / "YakumoDisk"
    try:
        target.mkdir(exist_ok=True)
        return target
    except OSError:  # папка программы только для чтения
        return data / "disk"


def query(request) -> dict[str, str]:
    return {k: v[0] for k, v in parse_qs(urlsplit(request.path).query, encoding="utf-8").items()}


def disposition(kind: str, name: str) -> str:
    """Имя файла для браузера; русские буквы — через filename* (RFC 6266)."""
    fallback = re.sub(r'[^A-Za-z0-9._ -]', "_", name) or "file"
    return f"{kind}; filename=\"{fallback}\"; filename*=UTF-8''{quote(name, safe='')}"


def send_file(request, path: Path, download: bool) -> object:
    """Отдать файл с поддержкой докачки и перемотки видео (Range)."""
    size = path.stat().st_size
    start, end, code = 0, size - 1, 200
    match = re.fullmatch(r"bytes=(\d*)-(\d*)", (request.headers.get("Range") or "").strip())
    if match and (match[1] or match[2]):
        if match[1]:
            start = int(match[1])
            end = min(int(match[2]), size - 1) if match[2] else size - 1
        else:  # последние N байт
            start = max(size - int(match[2]), 0)
        if start > end or start >= size:
            request.send_response(416)
            request.send_header("Content-Range", f"bytes */{size}")
            request.send_header("Content-Length", "0")
            request.end_headers()
            return request.SENT
        code = 206
    ext = path.suffix.lower()
    ctype = mime_of(path.name)
    if ctype.startswith("text/") or ext in AS_TEXT:
        ctype = ("text/plain" if ext in AS_TEXT else ctype) + "; charset=utf-8"
    request.send_response(code)
    request.send_header("Content-Type", ctype)
    request.send_header("Content-Length", str(end - start + 1))
    request.send_header("Accept-Ranges", "bytes")
    if code == 206:
        request.send_header("Content-Range", f"bytes {start}-{end}/{size}")
    request.send_header("Content-Disposition", disposition("attachment" if download else "inline", path.name))
    request.send_header("Cache-Control", "no-cache")
    request.send_header("X-Content-Type-Options", "nosniff")
    if ext in SANDBOX and ext != ".pdf":
        request.send_header("Content-Security-Policy", "sandbox")
    request.end_headers()
    try:
        with open(path, "rb") as f:
            f.seek(start)
            left = end - start + 1
            while left:
                chunk = f.read(min(CHUNK, left))
                if not chunk:
                    break
                request.wfile.write(chunk)
                left -= len(chunk)
    except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
        pass  # видео перемотали или скачивание отменили
    return request.SENT


def send_zip(request, folder: Path) -> object:
    """Папка одним архивом; архив собирается на лету, без временных файлов."""
    request.send_response(200)
    request.send_header("Content-Type", "application/zip")
    request.send_header("Content-Disposition", disposition("attachment", folder.name + ".zip"))
    request.end_headers()
    request.close_connection = True  # длина заранее неизвестна
    try:
        with zipfile.ZipFile(request.wfile, "w", zipfile.ZIP_DEFLATED, compresslevel=1) as zf:
            for dirpath, dirnames, filenames in os.walk(folder):
                here = Path(dirpath)
                arc = here.relative_to(folder.parent).as_posix()
                if not dirnames and not filenames:
                    zf.writestr(arc + "/", b"")
                for name in sorted(filenames):
                    try:
                        zf.write(here / name, f"{arc}/{name}")
                    except OSError:
                        continue  # файл занят другой программой
    except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
        pass
    return request.SENT


def share_page(token: str, folder: Path, disk: Disk, sub: str) -> tuple[int, str, str]:
    """Простая страница папки, открытой по ссылке (для телефона и других устройств)."""
    rows = []
    base = f"/api/disk/s?t={quote(token)}"
    for child in sorted(folder.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
        rel = f"{sub}/{child.name}" if sub else child.name
        link = f"{base}&p={quote(rel)}"
        if child.is_dir():
            rows.append(f'<li><a href="{html.escape(link)}">📁 {html.escape(child.name)}</a></li>')
        else:
            size = _human(child.stat().st_size)
            rows.append(f'<li><a href="{html.escape(link)}">{html.escape(child.name)}</a>'
                        f' <small>{size}</small> <a class="dl" href="{html.escape(link)}&download=1">скачать</a></li>')
    up = ""
    if sub:
        parent = "/".join(sub.split("/")[:-1])
        up = f'<p><a href="{html.escape(base + ("&p=" + quote(parent) if parent else ""))}">← назад</a></p>'
    title = html.escape(folder.name)
    zip_link = html.escape(f"{base}{'&p=' + quote(sub) if sub else ''}&zip=1")
    body = f"""<!doctype html><html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>{title} · Yakumo</title>
<style>body{{background:#0d0b09;color:#f4ead7;font:16px "Segoe UI",system-ui,sans-serif;margin:0;padding:24px 16px;
max-width:760px;margin:auto}}a{{color:#dcb04f;text-decoration:none}}h1{{font-size:22px}}ul{{list-style:none;padding:0}}
li{{padding:12px 0;border-bottom:1px solid #2e261c;overflow-wrap:anywhere}}small{{color:#a3927a}}
.dl{{float:right;margin-left:12px}}</style></head><body>
<h1>{title}</h1>{up}<p><a href="{zip_link}">Скачать всё архивом</a></p><ul>{"".join(rows) or "<li>Папка пуста</li>"}</ul>
</body></html>"""
    return 200, "text/html; charset=utf-8", body


def _human(size: int) -> str:
    for unit in ("Б", "КБ", "МБ", "ГБ"):
        if size < 1024:
            return f"{size:.0f} {unit}" if unit == "Б" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} ТБ"


def readable_errors(handler):
    """Ошибки Windows (занят файл, нет доступа, длинный путь) — понятным текстом, а не «internal»."""
    def wrapped(request):
        try:
            return handler(request)
        except (FileNotFoundError, DiskError):
            raise
        except PermissionError as exc:
            raise DiskError("Нет доступа: файл занят другой программой или защищён") from exc
        except OSError as exc:
            raise DiskError(f"Ошибка диска: {exc.strerror or exc}") from exc
    return wrapped


def setup(ctx):
    disk = Disk(disk_root(ctx.paths))
    ctx.log.info("Диск: %s", disk.root)

    def body(request) -> dict:
        data = request.read_json()
        if not isinstance(data, dict):
            raise DiskError("Ожидается объект")
        return data

    def info(_req):
        return {"root": str(disk.root), **disk.usage(),
                "lan": bool(ctx.config.lan), "lan_address": lan_address()}

    def listing(req):
        return disk.list(query(req).get("path"))

    def search(req):
        q = query(req)
        return disk.search(q.get("q", ""), q.get("path"))

    def file(req):
        q = query(req)
        path = disk.path(q.get("path"))
        if path.is_dir():
            return send_zip(req, path)
        return send_file(req, path, bool(q.get("download")))

    def upload(req):
        length = int(req.headers.get("Content-Length") or -1)
        return disk.upload(query(req).get("path", ""), req.rfile, length)

    def shared(req):
        q = query(req)
        token, sub = q.get("t", ""), q.get("p", "")
        path = disk.shared(token, sub)
        if path.is_dir():
            return send_zip(req, path) if q.get("zip") else share_page(token, path, disk, sub)
        return send_file(req, path, bool(q.get("download")))

    routes = {
        "/api/disk/info": info,
        "/api/disk/list": listing,
        "/api/disk/search": search,
        "/api/disk/file": file,
        "/api/disk/trash": lambda _req: disk.trash(),
        "/api/disk/shares": lambda _req: disk.shares(),
        "/api/disk/s": shared,
        "POST /api/disk/upload": upload,
        "POST /api/disk/mkdir": lambda r: (d := body(r)) and disk.mkdir(d.get("path"), d.get("name")),
        "POST /api/disk/rename": lambda r: (d := body(r)) and disk.rename(d.get("path"), d.get("name")),
        "POST /api/disk/move": lambda r: (d := body(r)) and disk.move(d.get("paths"), d.get("to")),
        "POST /api/disk/copy": lambda r: (d := body(r)) and disk.move(d.get("paths"), d.get("to"), copy=True),
        "POST /api/disk/delete": lambda r: {"count": disk.delete(body(r).get("paths"))},
        "POST /api/disk/restore": lambda r: disk.restore(body(r).get("ids")),
        "POST /api/disk/purge": lambda r: {"count": disk.purge((d := body(r)).get("ids"), d.get("all") is True)},
        "POST /api/disk/share": lambda r: disk.share(body(r).get("path")),
        "POST /api/disk/unshare": lambda r: disk.unshare(body(r).get("token")) or {"ok": True},
    }
    for path, handler in routes.items():
        ctx.route(path, readable_errors(handler))
    ctx.web("disk.css", "disk.js")
    ctx.status(lambda: {"root": str(disk.root)})
