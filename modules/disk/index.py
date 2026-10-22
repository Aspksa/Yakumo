"""Умный поиск: текст из документов и описания фотографий в базе SQLite.

База лежит в ``<Диск>/.yakumo/index.db`` и хранит относительные пути, поэтому
переезжает вместе с переносным диском. Индекс обновляется в фоне: после
изменений на Диске и раз в несколько минут (файлы могли поменять снаружи).
"""

from __future__ import annotations

import base64
import io
import json
import logging
import os
import re
import sqlite3
import threading
import time
from pathlib import Path
from typing import Callable

from .extract import can_extract, extract
from .store import SERVICE, Disk, norm, query_words

log = logging.getLogger("yakumo.modules.disk")

RESCAN = 300                 # секунд между полными проходами
DEBOUNCE = 2.0               # подождать после изменения, чтобы собрать пачку изменений
PHOTO_EXT = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}
PHOTO_RAW_LIMIT = 4 * 1024**2  # без Pillow фото отправляется как есть, если не больше этого

PHOTO_PROMPT = {
    "ru": ("Опиши это изображение для поиска по личному архиву: что и кто изображено, где это, какое событие, "
           "какие предметы и цвета. Если на изображении есть текст (документ, чек, вывеска), перепиши главное. "
           "3–5 предложений по-русски, без вступлений."),
    "en": ("Describe this image for searching a personal archive: what and who is shown, where, what event, "
           "objects and colours. If there is text (a document, receipt, sign), copy the key parts. "
           "3–5 sentences, no preamble."),
}


class Index:
    def __init__(self, disk: Disk, describe: Callable[[bytes, str, str], str] | None = None,
                 language: Callable[[], str] = lambda: "ru"):
        self.disk = disk
        self.describe = describe  # (фото, тип, подсказка) -> описание (через Cloud.ru); None — без фото
        self.language = language
        self.settings_path = disk.meta / "smart.json"
        self.db = sqlite3.connect(disk.meta / "index.db", check_same_thread=False)
        self.lock = threading.Lock()
        with self.lock:
            self.db.execute("""CREATE TABLE IF NOT EXISTS files (
                path TEXT PRIMARY KEY, mtime INTEGER, size INTEGER, text TEXT, norm TEXT,
                photo TEXT, photo_norm TEXT, photo_error TEXT)""")
            self.db.commit()
        self.wake = threading.Event()
        self.stopping = False
        self.state = {"running": False, "done": 0, "queue": 0, "photo_error": None}
        self.thread: threading.Thread | None = None

    # --- Настройки умного поиска ---

    def settings(self) -> dict:
        try:
            data = json.loads(self.settings_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = {}
        return {"photos": data.get("photos") is True}

    def set_photos(self, on: bool) -> None:
        tmp = self.settings_path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"photos": bool(on)}), encoding="utf-8")
        os.replace(tmp, self.settings_path)
        if on:
            with self.lock:  # дать фото с прошлыми ошибками ещё одну попытку
                self.db.execute("UPDATE files SET photo_error = NULL WHERE photo IS NULL")
                self.db.commit()
            self.state["photo_error"] = None
        self.poke()

    def status(self) -> dict:
        with self.lock:
            texts = self.db.execute("SELECT count(*) FROM files WHERE text != ''").fetchone()[0]
            photos = self.db.execute("SELECT count(*) FROM files WHERE photo IS NOT NULL").fetchone()[0]
        return {**self.settings(), **self.state, "texts": texts, "photos_done": photos}

    # --- Фоновое обновление ---

    def start(self) -> None:
        self.thread = threading.Thread(target=self._loop, name="disk-index", daemon=True)
        self.thread.start()

    def stop(self) -> None:
        self.stopping = True
        self.wake.set()

    def poke(self) -> None:
        """Что-то изменилось: обновить индекс (с небольшой задержкой, чтобы собрать пачку изменений)."""
        self.wake.set()

    def _loop(self) -> None:
        while not self.stopping:
            try:
                self.scan()
                if self.settings()["photos"] and self.describe:
                    self.describe_photos()
            except Exception:  # noqa: BLE001
                log.exception("Индекс Диска не обновился")
            self.wake.wait(RESCAN)
            self.wake.clear()
            time.sleep(DEBOUNCE)
        with self.lock:
            self.db.close()

    def _files(self):
        for dirpath, dirnames, filenames in os.walk(self.disk.root):
            here = Path(dirpath)
            if here == self.disk.root:
                dirnames[:] = [d for d in dirnames if d.lower() != SERVICE]
            for name in filenames:
                yield here / name

    def scan(self) -> None:
        """Пройти Диск: новые и изменённые документы — разобрать, пропавшие — убрать."""
        self.state.update(running=True)
        with self.lock:
            known = {p: (m, s) for p, m, s in self.db.execute("SELECT path, mtime, size FROM files")}
        seen = set()
        todo = []
        for path in self._files():
            if not (can_extract(path.name) or path.suffix.lower() in PHOTO_EXT):
                continue
            try:
                st = path.stat()
            except OSError:
                continue
            rel = self.disk.rel(path)
            seen.add(rel)
            if known.get(rel) != (int(st.st_mtime), st.st_size):
                todo.append((rel, path, int(st.st_mtime), st.st_size))
        gone = [p for p in known if p not in seen]
        if gone:
            with self.lock:
                self.db.executemany("DELETE FROM files WHERE path = ?", [(p,) for p in gone])
                self.db.commit()
        self.state.update(queue=len(todo), done=0)
        for rel, path, mtime, size in todo:
            if self.stopping:
                return
            text = extract(path) if can_extract(path.name) else ""
            with self.lock:
                # Изменённое фото описываем заново, а описание переименованного сохраняется (см. moved).
                self.db.execute("""INSERT INTO files (path, mtime, size, text, norm) VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(path) DO UPDATE SET mtime=excluded.mtime, size=excluded.size,
                    text=excluded.text, norm=excluded.norm, photo=NULL, photo_norm=NULL, photo_error=NULL""",
                                (rel, mtime, size, text, norm(text)))
                self.db.commit()
            self.state["done"] += 1
        self.state.update(running=False, queue=0)

    def moved(self, old: str, new: str) -> None:
        """Переименование и перенос: описания фото и текст едут вместе с файлом."""
        with self.lock:
            self.db.execute("DELETE FROM files WHERE path = ? OR path LIKE ? ESCAPE '\\'", (new, _like_prefix(new)))
            self.db.execute("UPDATE files SET path = ? || substr(path, ?) WHERE path = ? OR path LIKE ? ESCAPE '\\'",
                            (new, len(old) + 1, old, _like_prefix(old)))
            self.db.commit()
        self.poke()

    def describe_photos(self) -> None:
        while not self.stopping and self.settings()["photos"]:
            with self.lock:
                row = self.db.execute("""SELECT path FROM files WHERE photo IS NULL AND photo_error IS NULL
                    AND (""" + " OR ".join("lower(path) LIKE ?" for _ in PHOTO_EXT) + ") LIMIT 1",
                    [f"%{e}" for e in PHOTO_EXT]).fetchone()
            if not row:
                return
            rel = row[0]
            try:
                image, mime = photo_bytes(self.disk.root / rel)
                text = self.describe(image, mime, PHOTO_PROMPT.get(self.language(), PHOTO_PROMPT["ru"]))
                error = None
            except PhotoSkip as exc:
                text, error = None, str(exc)
            except Exception as exc:  # noqa: BLE001 — связь, ключ, модель: остановиться до следующего раза
                self.state["photo_error"] = str(exc)
                log.warning("Фото не описано: %s", exc)
                return
            with self.lock:
                self.db.execute("UPDATE files SET photo = ?, photo_norm = ?, photo_error = ? WHERE path = ?",
                                (text, norm(text) if text else None, error, rel))
                self.db.commit()
            self.state["photo_error"] = None

    # --- Поиск ---

    def search(self, query: str, limit: int = 200) -> list[dict]:
        words = query_words(query)
        if not words:
            return []
        cond = " AND ".join("instr(norm || ' ' || ifnull(photo_norm, ''), ?) > 0" for _ in words)
        with self.lock:
            rows = self.db.execute(f"SELECT path, text, norm, photo, photo_norm FROM files WHERE {cond} LIMIT 2000",
                                   words).fetchall()
        found = []
        for path, text, text_n, photo, photo_n in rows:
            in_text = all(w in text_n for w in words)
            source, source_n = (text, text_n) if in_text or not photo else (photo, photo_n)
            score = sum(source_n.count(w) for w in words)
            found.append({"path": path, "match": "text" if in_text or not photo else "photo",
                          "snippet": snippet(source, source_n, words), "score": score})
        found.sort(key=lambda f: -f["score"])
        return found[:limit]

    def documents(self) -> list[tuple[str, int, str]]:
        """Все разобранные документы: (путь, время изменения, текст) — для базы знаний «Памяти»."""
        with self.lock:
            return self.db.execute("SELECT path, mtime, text FROM files WHERE text IS NOT NULL AND text != ''"
                                   ).fetchall()

    def text_of(self, rel: str) -> dict:
        """Текст и описание фото для чата (при необходимости разбирает файл сразу)."""
        with self.lock:
            row = self.db.execute("SELECT text, photo FROM files WHERE path = ?", (rel,)).fetchone()
        if row and (row[0] or row[1]):
            return {"text": row[0] or "", "photo": row[1]}
        path = self.disk.path(rel)
        return {"text": extract(path) if can_extract(path.name) else "", "photo": None}


class PhotoSkip(Exception):
    """Это фото описать нельзя (формат, размер) — пропустить и не пытаться снова."""


def photo_bytes(path: Path) -> tuple[bytes, str]:
    """Уменьшенная копия фото в JPEG (если есть Pillow) или сам файл, если он небольшой."""
    try:
        from PIL import Image
    except ImportError:
        Image = None
    if Image is not None:
        try:
            with Image.open(path) as im:
                im.thumbnail((1280, 1280))
                buf = io.BytesIO()
                im.convert("RGB").save(buf, "JPEG", quality=85)
                return buf.getvalue(), "image/jpeg"
        except Exception as exc:  # noqa: BLE001
            raise PhotoSkip(f"не открылось: {exc}") from exc
    if path.stat().st_size > PHOTO_RAW_LIMIT:
        raise PhotoSkip("большой файл, нужна библиотека Pillow")
    mime = {"jpg": "image/jpeg", "jpeg": "image/jpeg"}.get(path.suffix.lower()[1:], f"image/{path.suffix.lower()[1:]}")
    return path.read_bytes(), mime


def data_url(image: bytes, mime: str) -> str:
    return f"data:{mime};base64,{base64.b64encode(image).decode()}"


def snippet(text: str, text_n: str, words: list[str], width: int = 90) -> str:
    pos = min((text_n.find(w) for w in words if w in text_n), default=0)
    start = max(0, pos - width // 3)
    end = min(len(text), start + width * 2)
    cut = " ".join(text[start:end].split())
    return ("…" if start else "") + cut + ("…" if end < len(text) else "")


def _like_prefix(path: str) -> str:
    return re.sub(r"([%_\\])", r"\\\1", path) + "/%"
