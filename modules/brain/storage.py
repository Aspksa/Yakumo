"""SQLite-хранилище долговременной памяти Yakumo.

Memory Engine 2.0 хранит верхнеуровневые разделы памяти отдельно в SQLite/WAL,
а таблица events фиксирует, какие разделы изменились при каждом сохранении.
При первом запуске старый memory.json импортируется автоматически и переносится
в резервную копию memory.legacy*.json только после успешной записи в SQLite.
"""

from __future__ import annotations

import contextlib
import json
import os
import sqlite3
import time
from pathlib import Path


SCHEMA = """
CREATE TABLE IF NOT EXISTS state (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS events (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    at INTEGER NOT NULL,
    kind TEXT NOT NULL,
    payload TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS events_at ON events(at);
"""


class BrainDB:
    VERSION = 21

    def __init__(self, path: Path, legacy: Path | None = None):
        self.path = Path(path)
        self.legacy = Path(legacy) if legacy else None
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with contextlib.closing(self.connect()) as con:
            con.execute("PRAGMA journal_mode=WAL")
            con.executescript(SCHEMA)
            con.execute(f"PRAGMA user_version={self.VERSION}")
        self._migrate_legacy_if_needed()

    def connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.path, timeout=20)
        con.execute("PRAGMA busy_timeout=20000")
        con.execute("PRAGMA synchronous=NORMAL")
        con.execute("PRAGMA foreign_keys=ON")
        return con

    def empty(self) -> bool:
        with contextlib.closing(self.connect()) as con:
            return con.execute("SELECT 1 FROM state LIMIT 1").fetchone() is None

    def load(self) -> dict:
        with contextlib.closing(self.connect()) as con:
            rows = con.execute("SELECT key,value FROM state").fetchall()
        data = {}
        for key, raw in rows:
            try:
                data[key] = json.loads(raw)
            except (TypeError, ValueError):
                continue
        return data

    def save(self, data: dict, *, kind: str = "checkpoint") -> list[str]:
        """Атомарно сохранить только изменившиеся разделы и записать событие."""
        now = int(time.time())
        encoded = {str(k): json.dumps(v, ensure_ascii=False, separators=(",", ":")) for k, v in data.items()}
        changed: list[str] = []
        with contextlib.closing(self.connect()) as con:
            con.execute("BEGIN IMMEDIATE")
            old = dict(con.execute("SELECT key,value FROM state"))
            for key, raw in encoded.items():
                if old.get(key) == raw:
                    continue
                con.execute(
                    "INSERT INTO state(key,value,updated) VALUES(?,?,?) "
                    "ON CONFLICT(key) DO UPDATE SET value=excluded.value,updated=excluded.updated",
                    (key, raw, now),
                )
                changed.append(key)
            removed = sorted(set(old) - set(encoded))
            for key in removed:
                con.execute("DELETE FROM state WHERE key=?", (key,))
            changed.extend(removed)
            if changed:
                payload = {
                    "changed": sorted(set(changed)),
                    "facts": len(data.get("facts", [])) if isinstance(data.get("facts"), list) else 0,
                    "talks": len(data.get("talks", [])) if isinstance(data.get("talks"), list) else 0,
                    "entities": len(data.get("entities", [])) if isinstance(data.get("entities"), list) else 0,
                }
                con.execute(
                    "INSERT INTO events(at,kind,payload) VALUES(?,?,?)",
                    (now, kind, json.dumps(payload, ensure_ascii=False, separators=(",", ":"))),
                )
            con.commit()
        return changed

    def history(self, limit: int = 100) -> list[dict]:
        limit = max(1, min(int(limit), 1000))
        with contextlib.closing(self.connect()) as con:
            rows = con.execute(
                "SELECT seq,at,kind,payload FROM events ORDER BY seq DESC LIMIT ?", (limit,)
            ).fetchall()
        out = []
        for seq, at, kind, raw in rows:
            try:
                payload = json.loads(raw)
            except ValueError:
                payload = {}
            out.append({"seq": seq, "at": at, "kind": kind, **payload})
        return out

    def _migrate_legacy_if_needed(self) -> None:
        if not self.empty() or self.legacy is None or not self.legacy.is_file():
            return
        try:
            data = json.loads(self.legacy.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError):
            return
        if not isinstance(data, dict):
            return
        self.save(data, kind="migrate-json")
        self._backup_legacy()

    def _backup_legacy(self) -> None:
        if self.legacy is None or not self.legacy.exists():
            return
        target = self.legacy.with_name("memory.legacy.json")
        if target.exists():
            target = self.legacy.with_name(f"memory.legacy.{int(time.time())}.json")
        try:
            os.replace(self.legacy, target)
        except OSError:
            # SQLite уже содержит данные; не рискуем удалять исходник, если Windows держит файл.
            pass
