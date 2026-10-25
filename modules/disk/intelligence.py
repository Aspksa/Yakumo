"""Локальный исследовательский слой Диска: связи, события, гипотезы.

Не изменяет исходные файлы и не вызывает облачные API. Все записи производные.
"""
from __future__ import annotations

import datetime as dt
import re
import sqlite3
from collections import defaultdict
from pathlib import Path

DATE = re.compile(r"(?<!\d)(\d{2})[.\-/](\d{2})[.\-/](20\d{2})(?!\d)")
NUMBER = re.compile(r"(?<!\w)(?:[А-ЯA-Z]\s?\d{3}\s?[А-ЯA-Z]{2}\s?\d{2,3}|\d{10,12})(?!\w)", re.I)
WORDS = re.compile(r"[\w]{4,}", re.UNICODE)
STOP = {"документ", "сведения", "данные", "страница", "текст", "информация",
        "приложение", "заявление", "согласно", "который", "которые", "данного"}
MAX_CONTENT = 200_000
MAX_TAGS = 36


def tokens(text: str) -> set[str]:
    return {w.lower() for w in WORDS.findall(text[:MAX_CONTENT]) if w.lower() not in STOP}


def dates(text: str) -> list[str]:
    out = set()
    for d, m, y in DATE.findall(text[:MAX_CONTENT]):
        try:
            out.add(dt.date(int(y), int(m), int(d)).isoformat())
        except ValueError:
            continue
    return sorted(out)[:100]


class Intelligence:
    """Схема хранится отдельно от существующей files, миграции безопасны."""

    def __init__(self, db: sqlite3.Connection, lock):
        self.db, self.lock = db, lock
        with lock:
            db.executescript("""CREATE TABLE IF NOT EXISTS intelligence_docs(
                path TEXT PRIMARY KEY, tags TEXT NOT NULL, dates TEXT NOT NULL,
                modality TEXT NOT NULL DEFAULT 'text');
            CREATE INDEX IF NOT EXISTS intelligence_modality ON intelligence_docs(modality);
            """)
            db.commit()

    def update(self, path: str, text: str, photo: str = "", ocr: str = "") -> None:
        import json
        combined = " ".join((Path(path).stem, text or "", photo or "", ocr or ""))
        tags = sorted(tokens(combined), key=lambda x: (-combined.lower().count(x), x))[:MAX_TAGS]
        ext = Path(path).suffix.lower()
        modality = "image" if ext in {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"} else (
            "scan" if ocr else "document")
        with self.lock:
            self.db.execute("""INSERT INTO intelligence_docs(path,tags,dates,modality)
                VALUES(?,?,?,?) ON CONFLICT(path) DO UPDATE SET
                tags=excluded.tags,dates=excluded.dates,modality=excluded.modality""",
                (path, json.dumps(tags, ensure_ascii=False),
                 json.dumps(dates(combined)), modality))
            self.db.commit()

    def remove_missing(self) -> None:
        with self.lock:
            self.db.execute("DELETE FROM intelligence_docs WHERE path NOT IN (SELECT path FROM files)")
            self.db.commit()

    def rename(self, old: str, new: str) -> None:
        # Явная поддержка перемещения папки: SQLite substr начинается с единицы.
        with self.lock:
            rows = self.db.execute("SELECT path,tags,dates,modality FROM intelligence_docs").fetchall()
            self.db.executemany("DELETE FROM intelligence_docs WHERE path=?", [
                (p,) for p, *_ in rows if p == old or p.startswith(old + "/") or
                p == new or p.startswith(new + "/")])
            for p, tags, dates_json, modality in rows:
                if p == old or p.startswith(old + "/"):
                    self.db.execute("INSERT OR REPLACE INTO intelligence_docs VALUES(?,?,?,?)",
                                    (new + p[len(old):], tags, dates_json, modality))
            self.db.commit()

    def snapshot(self, limit: int = 1000) -> list[dict]:
        import json
        with self.lock:
            rows = self.db.execute("SELECT path,tags,dates,modality FROM intelligence_docs ORDER BY path LIMIT ?",
                                   (min(max(int(limit), 1), 5000),)).fetchall()
        return [{"path": p, "tags": json.loads(t), "dates": json.loads(d), "modality": m}
                for p, t, d, m in rows]

    def timeline(self, limit: int = 100) -> list[dict]:
        events = [{"date": date, "path": r["path"], "source": "document"}
                  for r in self.snapshot(5000) for date in r["dates"]]
        return sorted(events, key=lambda e: (e["date"], e["path"]), reverse=True)[:max(1, min(limit, 500))]

    def links(self, path: str, limit: int = 20) -> list[dict]:
        docs = self.snapshot(5000)
        source = next((r for r in docs if r["path"] == path), None)
        if source is None:
            return []
        a = set(source["tags"])
        scored = []
        for r in docs:
            if r["path"] == path:
                continue
            shared = sorted(a.intersection(r["tags"]))
            common_dates = sorted(set(source["dates"]).intersection(r["dates"]))
            # Связи являются подсказками, а не доказательством причинности.
            score = len(shared) + 3 * len(common_dates)
            if score:
                scored.append({"path": r["path"], "score": score,
                               "shared_terms": shared[:8], "shared_dates": common_dates[:5],
                               "verified": False})
        return sorted(scored, key=lambda r: (-r["score"], r["path"]))[:max(1, min(limit, 100))]

    def discoveries(self, limit: int = 30) -> list[dict]:
        """Ищет общие даты в разных документах; выдаёт проверяемые гипотезы."""
        by_date = defaultdict(set)
        for row in self.snapshot(5000):
            for date in row["dates"]:
                by_date[date].add(row["path"])
        return [{"kind": "shared_date", "date": date, "paths": sorted(paths)[:10],
                 "confidence": "hypothesis", "explanation": "Совпадает дата, связь требует проверки"}
                for date, paths in sorted(by_date.items(), reverse=True) if len(paths) > 1][:max(1, min(limit, 100))]

    def status(self) -> dict:
        with self.lock:
            n = self.db.execute("SELECT count(*) FROM intelligence_docs").fetchone()[0]
        return {"indexed": n, "cloud_requests": 0, "source": "local", "experimental": True}
