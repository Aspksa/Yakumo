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
from types import SimpleNamespace
from urllib.parse import parse_qs, quote, urlsplit

from yakumo.core.network import lan_address

from . import assistant, insight
from .extract import extract
from .index import Index, data_url
from .library import Library
from .names import Namer
from .organizer import Organizer
from .store import CHUNK, Disk, DiskError, mime_of

NAME = "Диск"
VERSION = "1.2"

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
    cloud = getattr(ctx, "cloud", None)

    def describe(image: bytes, mime: str, prompt: str) -> str:
        """Описание фото через Cloud.ru (только если пользователь включил это сам)."""
        model = cloud.vision_model()
        if not model:
            raise RuntimeError("no_vision_model")
        return cloud.complete([{"role": "user", "content": [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": data_url(image, mime)}}]}], model=model)

    index = Index(disk, describe if cloud else None, lambda: ctx.config.language)
    disk.on_change.append(index.poke)
    disk.on_move.append(index.moved)
    # Память Yakumo помнит файлы: при переносе ссылки в ней идут следом (модуль «Мозг» мог загрузиться позже).
    disk.on_move.append(lambda old, new: ctx.memory and ctx.memory.moved(old, new))
    index.start()
    ctx.on_stop(index.stop)
    language = lambda: getattr(ctx.config, "language", "ru")  # noqa: E731
    memory = lambda: getattr(ctx, "memory", None)  # noqa: E731 — «Мозг» мог загрузиться позже
    organizer = Organizer(disk, lambda rel: index.text_of(rel)["text"], memory, language)
    namer = Namer(disk, index, cloud, language)
    library = Library(disk)

    def smart_search(q: str, limit: int = 300) -> dict:
        """Имена файлов, текст внутри документов и описания фото — одним списком."""
        names = disk.search(q)
        items = {i["path"]: {**i, "match": "name"} for i in names["items"]}
        for hit in [*index.search(q), *index.bm25(q, limit=80)]:
            if hit["path"] in items:
                items[hit["path"]].setdefault("snippet", hit["snippet"])
                continue
            try:
                entry = disk.entry(disk.path(hit["path"]))
            except (OSError, DiskError):
                continue  # файл уже удалили, индекс ещё не обновился
            items[hit["path"]] = {**entry, "match": hit["match"], "snippet": hit["snippet"]}
        return {"items": list(items.values())[:limit], "more": names["more"] or len(items) > limit}

    def smart(_req):
        vision = None
        if cloud and cloud.api_key():
            try:
                vision = cloud.vision_model()
            except Exception:  # noqa: BLE001 — нет связи: просто не показываем модель
                vision = None
        return {**index.status(), "cloud": bool(cloud and cloud.api_key()), "vision_model": vision}

    def smart_save(req):
        data = req.read_json()
        if not isinstance(data, dict) or not any(type(data.get(k)) is bool for k in ("photos", "ocr")):
            raise DiskError("Ожидается photos или ocr: true/false")
        if type(data.get("photos")) is bool:
            index.set_photos(data["photos"])
        if type(data.get("ocr")) is bool:
            index.set_ocr(data["ocr"])
        return smart(req)

    def body(request) -> dict:
        data = request.read_json()
        if not isinstance(data, dict):
            raise DiskError("Ожидается объект")
        return data

    def info(_req):
        return {"root": str(disk.root), **disk.usage(),
                "lan": bool(ctx.config.lan), "lan_address": lan_address()}

    def starred(res: dict) -> dict:
        stars = library.starred()
        for item in res["items"]:
            item["star"] = item["path"] in stars
        return res

    def listing(req):
        return starred(disk.list(query(req).get("path")))

    def search(req):
        return starred(smart_search(query(req).get("q", "")))

    def file(req):
        q = query(req)
        path = disk.path(q.get("path"))
        if path.is_dir():
            return send_zip(req, path)
        return send_file(req, path, bool(q.get("download")))

    def upload(req):
        length = int(req.headers.get("Content-Length") or -1)
        entry = disk.upload(query(req).get("path", ""), req.rfile, length)
        try:  # новый файл во «Входящих»: правила порядка раскладывают его сразу
            placed = organizer.place(entry["path"])
        except (OSError, DiskError):
            placed = None
        return {**disk.entry(disk.path(placed["path"])), "placed": placed} if placed else entry

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
        "/api/disk/smart": smart,
        "/api/disk/intelligence/status": lambda _req: index.intelligence.status(),
        "/api/disk/intelligence/entities": lambda _req: index.entity_graph(),
        "/api/disk/intelligence/work": lambda _req: {"items": index.work_candidates()},
        "/api/disk/intelligence/timeline": lambda r: {
            "items": index.intelligence.timeline()},
        "/api/disk/intelligence/discoveries": lambda r: {
            "items": index.intelligence.discoveries()},
        "/api/disk/intelligence/links": lambda r: {
            "items": index.intelligence.links(query(r).get("path", ""))},
        "POST /api/disk/smart": smart_save,
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
        # Живой порядок: правила, предложения кицунэ и её уроки.
        "/api/disk/order": lambda _req: organizer.view(),
        "/api/disk/order/plan": lambda _req: {"moves": organizer.plan()},
        "POST /api/disk/order/rule": lambda r: organizer.save_rule(body(r)),
        "POST /api/disk/order/delete": lambda r: {"ok": organizer.delete_rule(str(body(r).get("id", "")))},
        "POST /api/disk/order/answer": lambda r: {"rule": organizer.answer(str((d := body(r)).get("id", "")),
                                                                            d.get("accept") is True)},
        "POST /api/disk/order/apply": lambda r: organizer.apply(body(r).get("moves")),
        # Избранное, недавние, место.
        "/api/disk/favorites": lambda _req: library.favorites(),
        "POST /api/disk/favorite": lambda r: {"paths": library.star((d := body(r)).get("paths"), d.get("on") is not False)},
        "/api/disk/recent": lambda _req: library.recent(),
        "/api/disk/space": lambda _req: library.space(),
        # Понятные имена, похожие файлы, конспект.
        "/api/disk/names": lambda r: namer.suggest(query(r).get("path", ""), query(r).get("all") != "1"),
        "POST /api/disk/names": lambda r: namer.apply(body(r).get("items")),
        "/api/disk/related": lambda r: insight.related(disk, index, memory(), query(r).get("path", "")),
        "POST /api/disk/summary": lambda r: insight.save_summary(disk, index, cloud, str(body(r).get("path", "")),
                                                                 language(), memory()),
    }
    for path, handler in routes.items():
        ctx.route(path, readable_errors(handler))
    ctx.web("disk.css", "disk.js")
    assistant.register(ctx, disk, index, smart_search, organizer, namer)

    def current_text(rel: str):
        """(время изменения, текст) файла прямо сейчас, без индекса; None — файла нет."""
        try:
            path = disk.path(rel)
            return int(path.stat().st_mtime), extract(path)
        except (DiskError, OSError):
            return None

    # Другие модули (например, «Память» для базы знаний) читают документы Диска через ctx.services["disk"].
    services = getattr(ctx, "services", None)
    if isinstance(services, dict):
        services["disk"] = SimpleNamespace(documents=index.documents, search=smart_search,
                                           text=lambda rel: index.text_of(rel)["text"], current=current_text,
                                           status=index.status, intelligence=index.intelligence.status,
                                           entity_graph=index.entity_graph, work_candidates=index.work_candidates)
    ctx.status(lambda: {"root": str(disk.root)})
