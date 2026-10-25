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
import math
import os
import re
import sqlite3
import threading
import time
from pathlib import Path
from typing import Callable

from .extract import can_extract, extract, pdf_images
from .intelligence import Intelligence
from .ranking import HybridRanker
from .store import SERVICE, Disk, norm, query_words

log = logging.getLogger("yakumo.modules.disk")

RESCAN = 300                 # секунд между полными проходами
DEBOUNCE = 2.0               # подождать после изменения, чтобы собрать пачку изменений
PHOTO_EXT = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}
PHOTO_RAW_LIMIT = 4 * 1024**2  # без Pillow фото отправляется как есть, если не больше этого

OCR_PROMPT = {
    "ru": ("Перепиши весь текст с этого изображения (скан документа, чек, квитанция) как есть: строки, суммы, даты, "
           "номера. Без пояснений и без Markdown. Если текста нет, ответь одним словом: НЕТ"),
    "en": ("Transcribe all text from this image (a scanned document, receipt, invoice) as is: lines, amounts, dates, "
           "numbers. No comments, no Markdown. If there is no text, reply with one word: NONE"),
}
NO_TEXT = {"нет", "none", "нет.", "none.", "нет текста", "no text"}
# Фото, похожие на документы: по имени, папке или по описанию — их стоит распознать.
SCAN_HINT = re.compile(r"скан|scan|чек|receipt|квитанц|invoice|документ|document|договор|contract|паспорт|справк|"
                       r"счет|счёт|bill|текст|text|страниц|page|бланк|form|таблиц|письм|letter", re.I)
OCR_PAGES = 3

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
            have = {r[1] for r in self.db.execute("PRAGMA table_info(files)")}
            for col in ("ocr", "ocr_norm", "ocr_error"):  # база от прошлой версии: добавить колонки распознавания
                if col not in have:
                    self.db.execute(f"ALTER TABLE files ADD COLUMN {col} TEXT")
            self.db.commit()
        self.intelligence = Intelligence(self.db, self.lock)
        self.wake = threading.Event()
        self.stopping = False
        self.state = {"running": False, "done": 0, "queue": 0, "photo_error": None, "ocr_error": None}
        self.thread: threading.Thread | None = None

    # --- Настройки умного поиска ---

    def settings(self) -> dict:
        try:
            data = json.loads(self.settings_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = {}
        return {"photos": data.get("photos") is True, "ocr": data.get("ocr") is True,
                "semantic": data.get("semantic") is True}

    def _store(self, **changes) -> None:
        tmp = self.settings_path.with_suffix(".tmp")
        tmp.write_text(json.dumps({**self.settings(), **changes}), encoding="utf-8")
        os.replace(tmp, self.settings_path)

    def set_ocr(self, on: bool) -> None:
        self._store(ocr=bool(on))
        if on:
            with self.lock:
                self.db.execute("UPDATE files SET ocr_error = NULL WHERE ocr IS NULL")
                self.db.commit()
            self.state["ocr_error"] = None
        self.poke()

    def set_photos(self, on: bool) -> None:
        self._store(photos=bool(on))
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
            scans = self.db.execute("SELECT count(*) FROM files WHERE ocr IS NOT NULL AND ocr != ''").fetchone()[0]
        return {**self.settings(), **self.state, "texts": texts, "photos_done": photos, "ocr_done": scans,
                "intelligence": self.intelligence.status()}

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
                if self.settings()["ocr"] and self.describe:
                    self.recognize()
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
        self.intelligence.remove_missing()
        # Backfill documents indexed by older Yakumo versions without re-reading files.
        with self.lock:
            legacy = self.db.execute("""SELECT f.path,f.text,ifnull(f.photo,''),ifnull(f.ocr,'')
                FROM files f LEFT JOIN intelligence_docs i ON i.path=f.path
                WHERE i.path IS NULL""").fetchall()
        for p, t, photo, ocr in legacy:
            if self.stopping:
                return
            self.intelligence.update(p, t or "", photo, ocr)
        self.state.update(queue=len(todo), done=0)
        for rel, path, mtime, size in todo:
            if self.stopping:
                return
            text = extract(path) if can_extract(path.name) else ""
            with self.lock:
                # Изменённое фото описываем заново, а описание переименованного сохраняется (см. moved).
                self.db.execute("""INSERT INTO files (path, mtime, size, text, norm) VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(path) DO UPDATE SET mtime=excluded.mtime, size=excluded.size,
                    text=excluded.text, norm=excluded.norm, photo=NULL, photo_norm=NULL, photo_error=NULL,
                    ocr=NULL, ocr_norm=NULL, ocr_error=NULL""",
                                (rel, mtime, size, text, norm(text)))
                self.db.commit()
            self.intelligence.update(rel, text)
            self.state["done"] += 1
        self.state.update(running=False, queue=0)

    def moved(self, old: str, new: str) -> None:
        """Переименование и перенос: описания фото и текст едут вместе с файлом."""
        with self.lock:
            self.db.execute("DELETE FROM files WHERE path = ? OR path LIKE ? ESCAPE '\\'", (new, _like_prefix(new)))
            self.db.execute("UPDATE files SET path = ? || substr(path, ?) WHERE path = ? OR path LIKE ? ESCAPE '\\'",
                            (new, len(old) + 1, old, _like_prefix(old)))
            self.db.commit()
        self.intelligence.rename(old, new)
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
            if text:
                self.intelligence.update(rel, self.text_of(rel)["text"], photo=text)
            self.state["photo_error"] = None

    def recognize(self) -> None:
        """Текст со сканов и чеков: PDF без текстового слоя и фото, похожие на документы."""
        tried: set[str] = set()
        while not self.stopping and self.settings()["ocr"]:
            with self.lock:
                rows = self.db.execute("""SELECT path, text, photo FROM files WHERE ocr IS NULL AND ocr_error IS NULL
                    AND ((lower(path) LIKE '%.pdf' AND text = '') OR """ +
                    " OR ".join("lower(path) LIKE ?" for _ in PHOTO_EXT) + ")", [f"%{e}" for e in PHOTO_EXT]).fetchall()
            todo = [r for r in rows if r[0] not in tried and (r[0].lower().endswith(".pdf") or SCAN_HINT.search(r[0])
                                                                or (r[2] and SCAN_HINT.search(r[2])))]
            if not todo:
                return
            rel = todo[0][0]
            tried.add(rel)
            path = self.disk.root / rel
            prompt = OCR_PROMPT.get(self.language(), OCR_PROMPT["ru"])
            try:
                images = pdf_images(path, OCR_PAGES) if rel.lower().endswith(".pdf") else [photo_bytes(path)]
                if not images:
                    raise PhotoSkip("в PDF нет картинок страниц")
                pages = [self.describe(image, mime, prompt).strip() for image, mime in images]
                text, error = "\n\n".join(p for p in pages if p.lower().strip(" .") not in NO_TEXT), None
            except PhotoSkip as exc:
                text, error = None, str(exc)
            except Exception as exc:  # noqa: BLE001 — связь, ключ, модель: остановиться до следующего раза
                self.state["ocr_error"] = str(exc)
                log.warning("Скан не распознан: %s", exc)
                return
            with self.lock:
                self.db.execute("UPDATE files SET ocr = ?, ocr_norm = ?, ocr_error = ? WHERE path = ?",
                                (text, norm(text) if text else None, error, rel))
                self.db.commit()
            if text:
                data = self.text_of(rel)
                self.intelligence.update(rel, data["text"], photo=data["photo"] or "", ocr=text)
            self.state["ocr_error"] = None

    # --- Поиск ---

    def search(self, query: str, limit: int = 200) -> list[dict]:
        words = query_words(query)
        if not words:
            return []
        cond = " AND ".join("instr(norm || ' ' || ifnull(ocr_norm, '') || ' ' || ifnull(photo_norm, ''), ?) > 0"
                            for _ in words)
        with self.lock:
            rows = self.db.execute(f"""SELECT path, text || CASE WHEN ocr != '' THEN char(10) || ocr ELSE '' END,
                norm || CASE WHEN ocr_norm != '' THEN char(10) || ocr_norm ELSE '' END, photo, photo_norm
                FROM files WHERE {cond} LIMIT 2000""", words).fetchall()
        found = []
        for path, text, text_n, photo, photo_n in rows:
            in_text = all(w in text_n for w in words)
            source, source_n = (text, text_n) if in_text or not photo else (photo, photo_n)
            score = sum(source_n.count(w) for w in words)
            found.append({"path": path, "match": "text" if in_text or not photo else "photo",
                          "snippet": snippet(source, source_n, words), "score": score})
        found.sort(key=lambda f: -f["score"])
        return found[:limit]

    def bm25(self, query: str, limit: int = 30) -> list[dict]:
        """Offline lexical ranking; does not require an embedding API key."""
        with self.lock:
            rows = self.db.execute("""SELECT path, ifnull(text,'') || ' ' ||
                ifnull(photo,'') || ' ' || ifnull(ocr,'') FROM files""").fetchall()
        ranker = HybridRanker()
        ranker.replace({path: text for path, text in rows})
        return [{"path": hit.path, "score": hit.score, "match": "text",
                 "snippet": ""} for hit in ranker.bm25(query, limit)]

    def entity_graph(self, limit: int = 300) -> dict:
        """Read-only extraction with explicit unverified relationship status."""
        from .entities import extract_entities, candidate_relationships, timeline
        with self.lock:
            rows = self.db.execute("""SELECT path,ifnull(text,''),ifnull(ocr,''),ifnull(photo,'')
                FROM files ORDER BY path LIMIT 1500""").fetchall()
        records = [extract_entities(path, " ".join([text, ocr, photo]))
                   for path, text, ocr, photo in rows]
        records = [r for r in records if r["vehicles"] or r["people"] or r["document_dates"]]
        return {"entities": records[:limit], "relations": candidate_relationships(records)[:limit],
                "timeline": timeline(records)[:limit],
                "warning": "Обнаруженные связи требуют проверки по исходным документам"}

    def similar(self, rel: str, limit: int = 8) -> list[dict]:
        """Похожие документы: общие редкие слова текста и имени (без нейросети)."""
        data = self.text_of(rel)
        words = keywords(f"{Path(rel).stem.replace('_', ' ')} {data['text'][:20000]} {data['photo'] or ''}")
        if not words:
            return []
        cond = " OR ".join("instr(norm || ' ' || ifnull(ocr_norm, '') || ' ' || ifnull(photo_norm, ''), ?) > 0"
                           for _ in words)
        with self.lock:
            total = self.db.execute("SELECT count(*) FROM files").fetchone()[0] or 1
            rows = self.db.execute(f"""SELECT path, norm || ' ' || ifnull(ocr_norm, '') || ' ' || ifnull(photo_norm, '')
                FROM files WHERE path != ? AND ({cond}) LIMIT 3000""", [rel, *words]).fetchall()
        df = {w: sum(1 for _p, t in rows if w in t) for w in words}
        found = []
        for path, text in rows:
            shared = [w for w in words if w in text]
            if len(shared) < 2:
                continue
            score = sum(math.log(1 + total / df[w]) for w in shared)
            found.append({"path": path, "score": round(score, 2), "words": shared[:4]})
        found.sort(key=lambda f: -f["score"])
        return found[:limit]

    def documents(self) -> list[tuple[str, int, str]]:
        """Все разобранные документы: (путь, время изменения, текст) — для базы знаний «Памяти»."""
        with self.lock:
            return self.db.execute("""SELECT path, mtime, CASE WHEN text != '' THEN text ELSE ocr END FROM files
                WHERE text != '' OR ocr != ''""").fetchall()

    def text_of(self, rel: str) -> dict:
        """Текст и описание фото для чата (при необходимости разбирает файл сразу)."""
        with self.lock:
            row = self.db.execute("SELECT text, photo, ocr FROM files WHERE path = ?", (rel,)).fetchone()
        if row and (row[0] or row[1] or row[2]):
            return {"text": row[0] or row[2] or "", "photo": row[1]}
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


STOP = set("""это этот эта эти того тому что как для или при без над под про после перед между также только
которые который которая которое если когда чтобы будет было были быть есть может можно нужно очень более менее всех
всего всем она они оно его её ему ней них нам вам вас нас мне меня себя свой своя свои ваш ваша наш наша один одна
года году году дата дней день число номер сумма руб рублей this that with from have will were been they their there
which about into your than then them these those page страница""".split())


def keywords(text: str, limit: int = 12) -> list[str]:
    """Самые частые содержательные слова (основы) документа."""
    counts: dict[str, int] = {}
    for w in query_words(text):
        if len(w) >= 4 and not w.isdigit() and w not in STOP:
            counts[w] = counts.get(w, 0) + 1
    return [w for w, _n in sorted(counts.items(), key=lambda kv: -kv[1])[:limit]]


def _like_prefix(path: str) -> str:
    return re.sub(r"([%_\\])", r"\\\1", path) + "/%"
