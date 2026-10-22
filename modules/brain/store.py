"""Память Yakumo: факты о пользователе и конспекты прошлых разговоров.

Всё лежит одним JSON-файлом в папке данных (на том же носителе, что и Yakumo),
поэтому память переезжает вместе с переносным диском.
"""

from __future__ import annotations

import json
import math
import os
import re
import threading
import time
import uuid
from pathlib import Path

KINDS = ("person", "likes", "work", "other")  # о человеке, предпочтения, дела и планы, прочее
MAX_FACTS = 500
MAX_TALKS = 300
MAX_TEXT = 300      # символов в одном факте
MAX_SUMMARY = 1200  # символов в конспекте разговора
FADE_DAYS = 45      # за столько дней без упоминания факт теряет одно очко
FORGET_DAYS = 180   # мелкие факты, которые не вспоминались так долго, забываются сами

WORD = re.compile(r"\w{3,}", re.U)


class BrainError(ValueError):
    """Понятная пользователю ошибка памяти."""


def words(text: str) -> set[str]:
    """Основы слов для поиска: без окончаний, чтобы «кошку» находила «кошка»."""
    return {w[:5] for w in WORD.findall(text.lower())}


def _clean(text, limit: int) -> str:
    if not isinstance(text, str):
        raise BrainError("Нужен текст")
    text = " ".join(text.split())
    if not text:
        raise BrainError("Пустой текст")
    return text[:limit]


class Memory:
    def __init__(self, path: Path):
        self.path = path
        self.lock = threading.RLock()
        self.data = self._load()

    # --- Файл ---

    def _load(self) -> dict:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError):
            data = {}
        if not isinstance(data, dict):
            data = {}
        data.setdefault("enabled", True)   # использовать память в чате
        data.setdefault("auto", True)      # самой запоминать из разговоров
        data["facts"] = [f for f in data.get("facts", []) if isinstance(f, dict) and isinstance(f.get("text"), str)]
        data["talks"] = [t for t in data.get("talks", []) if isinstance(t, dict) and isinstance(t.get("id"), str)]
        return data

    def save(self) -> None:
        with self.lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self.data, ensure_ascii=False, indent=1), encoding="utf-8")
            os.replace(tmp, self.path)

    # --- Настройки ---

    def settings(self, enabled=None, auto=None) -> dict:
        with self.lock:
            for key, value in (("enabled", enabled), ("auto", auto)):
                if value is not None:
                    if type(value) is not bool:
                        raise BrainError(f"{key}: ожидается true/false")
                    self.data[key] = value
            self.save()
            return {"enabled": self.data["enabled"], "auto": self.data["auto"]}

    @property
    def enabled(self) -> bool:
        return self.data["enabled"]

    @property
    def auto(self) -> bool:
        return self.data["enabled"] and self.data["auto"]

    # --- Факты ---

    def facts(self) -> list[dict]:
        with self.lock:
            return sorted((dict(f, score=round(self.score(f), 2)) for f in self.data["facts"]),
                          key=lambda f: -f["score"])

    def fact(self, fact_id: str) -> dict:
        for f in self.data["facts"]:
            if f["id"] == fact_id:
                return f
        raise BrainError("Такого факта нет")

    @staticmethod
    def score(f: dict, now: float | None = None) -> float:
        """Важность с учётом времени: частые факты крепнут, забытые тускнеют. Закреплённые — всегда наверху."""
        if f.get("pinned"):
            return 10.0
        now = now or time.time()
        days = max(0.0, (now - f.get("last_seen", f.get("created", now))) / 86400)
        return f.get("importance", 2) + min(math.log2(1 + f.get("seen", 1)), 3) - days / FADE_DAYS

    def _similar(self, text: str) -> dict | None:
        """Почти тот же факт (совпадает большинство слов) — чтобы не плодить повторы."""
        new = words(text)
        if not new:
            return None
        for f in self.data["facts"]:
            old = words(f["text"])
            if old and len(new & old) / len(new | old) >= 0.75:
                return f
        return None

    def add(self, text: str, kind: str = "other", importance: int = 2, source: str = "manual",
            pinned: bool = False) -> dict:
        text = _clean(text, MAX_TEXT)
        kind = kind if kind in KINDS else "other"
        importance = importance if isinstance(importance, int) and 1 <= importance <= 3 else 2
        now = int(time.time())
        with self.lock:
            same = self._similar(text)
            if same:
                same.update(text=text, updated=now, last_seen=now, seen=same.get("seen", 1) + 1,
                            importance=max(importance, same.get("importance", 1)))
                if pinned:
                    same["pinned"] = True
                self.save()
                return same
            fact = {"id": uuid.uuid4().hex[:10], "text": text, "kind": kind, "importance": importance,
                    "source": source, "created": now, "updated": now, "last_seen": now, "seen": 1}
            if pinned:
                fact["pinned"] = True
            self.data["facts"].append(fact)
            self._trim()
            self.save()
            return fact

    def edit(self, fact_id: str, text=None, kind=None, pinned=None) -> dict:
        with self.lock:
            f = self.fact(fact_id)
            if text is not None:
                f["text"] = _clean(text, MAX_TEXT)
            if kind is not None:
                if kind not in KINDS:
                    raise BrainError("Неизвестный раздел")
                f["kind"] = kind
            if pinned is not None:
                if type(pinned) is not bool:
                    raise BrainError("pinned: ожидается true/false")
                f["pinned"] = pinned
            f["updated"] = int(time.time())
            self.save()
            return f

    def touch(self, ids) -> None:
        """Факт снова всплыл в разговоре — он крепнет."""
        now = int(time.time())
        with self.lock:
            for f in self.data["facts"]:
                if f["id"] in ids:
                    f["seen"] = f.get("seen", 1) + 1
                    f["last_seen"] = now
            self.save()

    def delete(self, ids) -> int:
        if isinstance(ids, str):
            ids = [ids]
        if not isinstance(ids, list):
            raise BrainError("Нужен список ids")
        with self.lock:
            before = len(self.data["facts"])
            self.data["facts"] = [f for f in self.data["facts"] if f["id"] not in ids]
            removed = before - len(self.data["facts"])
            if removed:
                self.save()
            return removed

    def _trim(self) -> None:
        """Забыть то, что давно не вспоминалось: мелкие факты, выученные самой Yakumo."""
        now = time.time()
        self.data["facts"] = [f for f in self.data["facts"]
                              if f.get("pinned") or f.get("source") != "auto" or f.get("importance", 2) > 1
                              or now - f.get("last_seen", now) < FORGET_DAYS * 86400]
        if len(self.data["facts"]) > MAX_FACTS:
            self.data["facts"].sort(key=lambda f: -self.score(f, now))
            del self.data["facts"][MAX_FACTS:]

    # --- Разговоры ---

    def talks(self) -> list[dict]:
        with self.lock:
            return sorted((dict(t) for t in self.data["talks"]), key=lambda t: -t.get("updated", 0))

    def talk(self, talk_id: str) -> dict | None:
        return next((t for t in self.data["talks"] if t["id"] == talk_id), None)

    def save_talk(self, talk_id: str, title: str, summary: str, messages: int) -> dict:
        now = int(time.time())
        with self.lock:
            t = self.talk(talk_id)
            if t is None:
                t = {"id": talk_id, "started": now}
                self.data["talks"].append(t)
            t.update(title=_clean(title, 80), summary=_clean(summary, MAX_SUMMARY), updated=now,
                     messages=max(messages, t.get("messages", 0)))
            if len(self.data["talks"]) > MAX_TALKS:
                self.data["talks"].sort(key=lambda x: -x.get("updated", 0))
                del self.data["talks"][MAX_TALKS:]
            self.save()
            return t

    def delete_talks(self, ids) -> int:
        if isinstance(ids, str):
            ids = [ids]
        if not isinstance(ids, list):
            raise BrainError("Нужен список ids")
        with self.lock:
            before = len(self.data["talks"])
            self.data["talks"] = [t for t in self.data["talks"] if t["id"] not in ids]
            removed = before - len(self.data["talks"])
            if removed:
                self.save()
            return removed

    def clear(self) -> None:
        with self.lock:
            self.data["facts"], self.data["talks"] = [], []
            self.save()

    # --- Поиск ---

    def search(self, query: str, limit: int = 10) -> dict:
        """Факты и прошлые разговоры, где встречаются слова запроса."""
        q = words(query or "")
        if not q:
            return {"facts": [], "talks": []}

        def rank(text: str) -> int:
            return len(q & words(text))

        with self.lock:
            facts = sorted(((rank(f["text"]), f) for f in self.data["facts"]), key=lambda x: -x[0])
            talks = sorted(((rank(t.get("title", "") + " " + t.get("summary", "")), t) for t in self.data["talks"]),
                           key=lambda x: (-x[0], -x[1].get("updated", 0)))
            return {"facts": [f for r, f in facts if r][:limit], "talks": [t for r, t in talks if r][:limit]}

    # --- Обмен ---

    def export(self) -> dict:
        with self.lock:
            return {"yakumo_memory": 1, "exported": int(time.time()),
                    "facts": list(self.data["facts"]), "talks": list(self.data["talks"])}

    def import_(self, data) -> dict:
        """Добавить память из файла экспорта. Совпадающие факты не дублируются."""
        if not isinstance(data, dict) or data.get("yakumo_memory") != 1:
            raise BrainError("Это не файл памяти Yakumo")
        facts = talks = 0
        with self.lock:
            for f in data.get("facts", [])[:MAX_FACTS]:
                if isinstance(f, dict) and isinstance(f.get("text"), str) and f["text"].strip():
                    before = len(self.data["facts"])
                    added = self.add(f["text"], f.get("kind", "other"), f.get("importance", 2),
                                     f.get("source", "manual"), f.get("pinned") is True)
                    if len(self.data["facts"]) > before:
                        for key in ("created", "last_seen", "seen"):
                            if isinstance(f.get(key), int):
                                added[key] = f[key]
                        facts += 1
            for t in data.get("talks", [])[:MAX_TALKS]:
                if (isinstance(t, dict) and isinstance(t.get("id"), str) and re.fullmatch(r"[\w-]{1,64}", t["id"])
                        and isinstance(t.get("summary"), str) and t["summary"].strip()
                        and self.talk(t["id"]) is None):
                    self.data["talks"].append({
                        "id": t["id"], "title": _clean(t.get("title") or "…", 80),
                        "summary": _clean(t["summary"], MAX_SUMMARY),
                        "started": t.get("started") if isinstance(t.get("started"), int) else int(time.time()),
                        "updated": t.get("updated") if isinstance(t.get("updated"), int) else int(time.time()),
                        "messages": t.get("messages") if isinstance(t.get("messages"), int) else 0})
                    talks += 1
            self.save()
        return {"facts": facts, "talks": talks}
