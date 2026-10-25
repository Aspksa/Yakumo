"""Память Yakumo: факты, люди и места, разговоры, обещания, даты, навыки и дни.

Memory Engine 2.0 хранит память в SQLite/WAL. Старый memory.json импортируется
автоматически при первом запуске, поэтому обновление не теряет накопленные данные.
"""

from __future__ import annotations

import datetime as dt
import json
import math
import re
import threading
import time
import uuid
from pathlib import Path

from .storage import BrainDB

# о человеке, вкусы, дела и планы, прочее, о самой Yakumo и ваших отношениях
KINDS = ("person", "likes", "work", "other", "self")
ENTITY_TYPES = ("person", "pet", "place", "project", "org", "thing")
TRACE_KINDS = ("cause", "decision", "project_error", "progress")
SETTINGS = {"enabled": True,    # использовать память в чате
            "auto": True,       # самой запоминать из разговоров
            "sleep": True,      # «сон»: ночная уборка памяти и утреннее сообщение
            "grow": True,       # саморазвитие во сне: учёба по Диску, экзамен, стиль
            "docs": True,       # читать новые документы на Диске: факты, сроки, сообщение в чат
            "mood": False,      # замечать настроение
            "activity": False}  # видеть, какая программа открыта (только Windows)
MAX_FACTS = 50_000
MAX_TALKS = 20_000
MAX_ITEMS = 10_000  # обещаний, дат, навыков, людей и мест
MAX_TEXT = 300      # символов в одном факте
MAX_SUMMARY = 1200  # символов в конспекте разговора
MAX_DAYS = 3650     # до десяти лет дневной истории
MAX_VERSIONS = 5000 # записей «истории меня»: установленные версии Yakumo
MAX_IMPROVEMENTS = 5000  # пунктов «что улучшить в Yakumo»
FADE_DAYS = 45      # за столько дней без упоминания факт теряет одно очко
FORGET_DAYS = 180   # мелкие факты, которые не вспоминались так долго, забываются сами

MAX_LESSONS = 1000  # правил до ночной консолидации; старые не теряются из-за маленького лимита
ARCHIVE_SCORE = 0  # факты слабее этого во сне уходят в архив: не в подсказке, но находятся поиском
MEMORY_TIERS = ("operational", "episodic", "longterm", "archive")
OPERATIONAL_DAYS = 7
LONGTERM_SEEN = 5
# Списки «роста»: уроки, желания, предложенные навыки, свои инструменты, конспекты, ассоциации,
# примеры разговоров (для улучшения подсказки), мысли фонового разума, ответы с 👍 (образцы) и
# ответы с 👎, которые ещё не разобраны, файлы, которые Yakumo написала (ждут ваших правок).
GROWTH = ("lessons", "wishes", "suggestions", "user_tools", "notes", "links", "samples", "thoughts", "best",
          "feedback", "drafts")

WORD = re.compile(r"\w{3,}", re.U)
DATE = re.compile(r"\d{4}-\d{2}-\d{2}")


class BrainError(ValueError):
    """Понятная пользователю ошибка памяти."""


def words(text: str) -> set[str]:
    """Основы слов для поиска: без окончаний, чтобы «кошку» находила «кошка»."""
    return {w[:5] for w in WORD.findall(text.lower())}


def alike(a: str, b: str) -> bool:
    """Почти одно и то же: совпадает большинство слов."""
    x, y = words(a), words(b)
    return bool(x and y) and len(x & y) / len(x | y) >= 0.75


def today() -> str:
    return dt.date.today().isoformat()


def _clean(text, limit: int) -> str:
    if not isinstance(text, str):
        raise BrainError("Нужен текст")
    text = " ".join(text.split())
    if not text:
        raise BrainError("Пустой текст")
    return text[:limit]


def _block(text, limit: int) -> str:
    """Как _clean, но абзацы и списки сохраняются (сообщения в чат, стиль)."""
    if not isinstance(text, str) or not text.strip():
        raise BrainError("Пустой текст")
    return re.sub(r"\n{3,}", "\n\n", "\n".join(" ".join(line.split()) for line in text.strip().splitlines()))[:limit]


def _date(value) -> str | None:
    """Дата YYYY-MM-DD или None."""
    if not isinstance(value, str) or not DATE.fullmatch(value.strip()):
        return None
    try:
        return dt.date.fromisoformat(value.strip()).isoformat()
    except ValueError:
        return None


def _anniversary(date: dt.date, year: int) -> dt.date:
    try:
        return date.replace(year=year)
    except ValueError:  # 29 февраля в невисокосный год
        return dt.date(year, 3, 1)


def _id() -> str:
    return uuid.uuid4().hex[:10]


def _entity_key(value: str) -> str:
    """Консервативный ключ: нормализуем только явные разделители, не стираем смысловые символы C++/C#."""
    value = value.casefold().replace("ё", "е")
    value = re.sub(r"[\s._\-‐‑‒–—―]+", " ", value, flags=re.U)
    return " ".join(value.split())


def _ids(value) -> list[str]:
    if isinstance(value, str):
        return [value]
    if not isinstance(value, list):
        raise BrainError("Нужен список ids")
    return [v for v in value if isinstance(v, str)]


class Memory:
    def __init__(self, path: Path):
        self.legacy_path = Path(path)
        self.path = self.legacy_path.with_name("memory.sqlite3")
        self.db = BrainDB(self.path, self.legacy_path)
        self.lock = threading.RLock()
        self.on_change: list = []  # (вид, id) — для смыслового поиска
        self.data = self._load()

    # --- Файл ---

    def _load(self) -> dict:
        try:
            data = self.db.load()
        except (OSError, ValueError):
            data = {}
        if not isinstance(data, dict):
            data = {}
        for key, default in SETTINGS.items():
            if type(data.get(key)) is not bool:
                data[key] = default
        data["facts"] = [f for f in data.get("facts", []) if isinstance(f, dict) and isinstance(f.get("text"), str)]
        for name in ("talks", "entities", "promises", "events", "skills", "inbox", "versions", "improvements", "traces", *GROWTH):
            data[name] = [x for x in data.get(name, []) if isinstance(x, dict) and isinstance(x.get("id"), str)]
        for key in ("days", "meta", "chains", "style"):
            if not isinstance(data.get(key), dict):
                data[key] = {}
        return data

    def save(self) -> None:
        with self.lock:
            self.data["meta"]["changed"] = int(time.time())
            self.db.save(self.data)

    def storage_status(self) -> dict:
        """Диагностика движка памяти без содержимого личных воспоминаний."""
        return {"engine": "sqlite-wal", "version": self.db.VERSION, "memory_engine": "2.1",
                "events": self.db.history(20)}

    def memory_tier(self, fact: dict, now: float | None = None) -> str:
        """Слой памяти: оперативная → эпизодическая → долговременная → архив."""
        if fact.get("archived") or fact.get("superseded"):
            return "archive"
        now = now or time.time()
        if fact.get("pinned") or fact.get("seen", 1) >= LONGTERM_SEEN:
            return "longterm"
        age = max(0.0, (now - fact.get("last_seen", fact.get("created", now))) / 86400)
        if age <= OPERATIONAL_DAYS:
            return "operational"
        if fact.get("importance", 2) >= 3:
            return "longterm"
        return "episodic"

    def rebalance_tiers(self) -> dict[str, int]:
        """Автоматически перераспределить факты по слоям, ничего не удаляя."""
        now = time.time()
        counts = {tier: 0 for tier in MEMORY_TIERS}
        changed = False
        with self.lock:
            for fact in self.data["facts"]:
                tier = self.memory_tier(fact, now)
                if fact.get("tier") != tier:
                    fact["tier"] = tier
                    changed = True
                counts[tier] += 1
            if changed:
                self.save()
        return counts

    def tier_counts(self) -> dict[str, int]:
        counts = {tier: 0 for tier in MEMORY_TIERS}
        for fact in self.data["facts"]:
            counts[self.memory_tier(fact)] += 1
        return counts

    def supersede(self, ids, reason: str = "new_information") -> int:
        """Старая версия факта не уничтожается: уходит в архив как заменённая."""
        ids = set(_ids(ids))
        count = 0
        now = int(time.time())
        with self.lock:
            for fact in self.data["facts"]:
                if fact["id"] in ids and not fact.get("pinned"):
                    fact.update(archived=True, superseded=True, tier="archive",
                                superseded_at=now, superseded_reason=str(reason)[:80])
                    count += 1
            if count:
                self.save()
        return count

    def _changed(self, kind: str, item_id: str) -> None:
        for hook in self.on_change:
            hook(kind, item_id)

    # --- Настройки ---

    def settings(self, **changes) -> dict:
        with self.lock:
            for key, value in changes.items():
                if value is None:
                    continue
                if key not in SETTINGS or type(value) is not bool:
                    raise BrainError(f"{key}: ожидается true/false")
                self.data[key] = value
            self.save()
            return {k: self.data[k] for k in SETTINGS}

    def on(self, key: str) -> bool:
        """Включена ли возможность (всё, кроме самой памяти, работает только при включённой памяти)."""
        return self.data["enabled"] and (key == "enabled" or self.data[key])

    @property
    def enabled(self) -> bool:
        return self.on("enabled")

    @property
    def auto(self) -> bool:
        return self.on("auto")

    # --- Люди, места, проекты (граф) ---

    def entity(self, name: str, etype: str = "thing", relation: str = "") -> dict:
        """Найти или создать сущность, безопасно объединяя только нормализованные варианты имени."""
        name = _clean(name, 60)
        etype = etype if etype in ENTITY_TYPES else "thing"
        relation = " ".join(relation.split())[:40] if isinstance(relation, str) else ""
        with self.lock:
            key = _entity_key(name)
            for e in self.data["entities"]:
                aliases = [e.get("name", ""), *e.get("aliases", [])]
                if key and any(_entity_key(str(a)) == key for a in aliases):
                    if name != e.get("name") and name not in e.get("aliases", []):
                        e.setdefault("aliases", []).append(name)
                        e["aliases"] = e["aliases"][-20:]
                    if relation and not e.get("relation"):
                        e["relation"] = relation
                    if etype != "thing" and e.get("type") == "thing":
                        e["type"] = etype
                    return e
            e = {"id": _id(), "name": name, "type": etype, "relation": relation, "created": int(time.time())}
            self.data["entities"].append(e)
            return e

    def observe_entity(self, name: str, etype: str = "thing", files=None, source: str = "disk",
                       relation: str = "") -> dict:
        """Добавить наблюдаемую сущность без превращения гипотезы Диска в факт."""
        with self.lock:
            e = self.entity(name, etype, relation)
            e["keep"] = True
            e["observed"] = True
            e["last_seen"] = int(time.time())
            sources = e.setdefault("sources", [])
            if source and source not in sources:
                sources.append(str(source)[:40])
            clean_files = [str(p).replace("\\", "/").strip("/") for p in files or [] if isinstance(p, str) and p.strip()]
            e["files"] = list(dict.fromkeys([*e.get("files", []), *clean_files]))[-50:]
            self.save()
            return e

    def _about(self, about) -> list[str]:
        """Список связей из ответа модели или формы: [{"name", "type", "relation"}] или ["имя"]."""
        ids = []
        for item in about or []:
            try:
                if isinstance(item, str):
                    e = self.entity(item)
                elif isinstance(item, dict) and isinstance(item.get("name"), str):
                    e = self.entity(item["name"], item.get("type", "thing"), item.get("relation", ""))
                else:
                    continue
            except BrainError:
                continue
            if e["id"] not in ids:
                ids.append(e["id"])
        return ids[:8]

    def entities(self) -> list[dict]:
        """Сущности с фактами, документами и ближайшими связями для карточки/карты."""
        with self.lock:
            counts: dict[str, int] = {}
            files: dict[str, list[str]] = {}
            related: dict[str, dict[str, int]] = {}
            latest: dict[str, int] = {}
            for f in self.data["facts"]:
                ids = [i for i in f.get("about", []) if isinstance(i, str)]
                for i in ids:
                    counts[i] = counts.get(i, 0) + 1
                    latest[i] = max(latest.get(i, 0), int(f.get("updated", f.get("created", 0)) or 0))
                    files[i] = list(dict.fromkeys([*files.get(i, []), *f.get("files", [])]))[-50:]
                    for j in ids:
                        if j != i:
                            related.setdefault(i, {})[j] = related.setdefault(i, {}).get(j, 0) + 1
            result = []
            for e in self.data["entities"]:
                eid = e["id"]
                rel = sorted(related.get(eid, {}).items(), key=lambda x: (-x[1], x[0]))[:8]
                result.append(dict(e, facts=counts.get(eid, 0),
                                   files=list(dict.fromkeys([*e.get("files", []), *files.get(eid, [])]))[-50:],
                                   related=[{"id": rid, "weight": weight} for rid, weight in rel],
                                   latest=latest.get(eid, int(e.get("last_seen", e.get("created", 0)) or 0))))
            return result

    def edit_entity(self, entity_id: str, name=None, etype=None, relation=None) -> dict:
        with self.lock:
            e = next((x for x in self.data["entities"] if x["id"] == entity_id), None)
            if e is None:
                raise BrainError("Нет такого узла")
            if name is not None:
                e["name"] = _clean(name, 60)
            if etype is not None:
                if etype not in ENTITY_TYPES:
                    raise BrainError("Неизвестный тип")
                e["type"] = etype
            if relation is not None:
                e["relation"] = " ".join(str(relation).split())[:40]
            self.save()
            return e

    def delete_entities(self, ids) -> int:
        ids = set(_ids(ids))
        with self.lock:
            before = len(self.data["entities"])
            self.data["entities"] = [e for e in self.data["entities"] if e["id"] not in ids]
            for f in self.data["facts"]:
                f["about"] = [i for i in f.get("about", []) if i not in ids]
            self.save()
            return before - len(self.data["entities"])

    def _prune_entities(self) -> None:
        used = {i for f in self.data["facts"] for i in f.get("about", [])}
        used |= {i for x in self.data["events"] + self.data["promises"] for i in x.get("about", [])}
        used |= {i for x in self.data["traces"] for i in x.get("about", [])}
        self.data["entities"] = [e for e in self.data["entities"] if e["id"] in used or e.get("keep")]

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
        return next((f for f in self.data["facts"] if not f.get("superseded") and alike(f["text"], text)), None)

    def add(self, text: str, kind: str = "other", importance: int = 2, source: str = "manual",
            pinned: bool = False, quote: str | None = None, about=None, files=None, talk: str | None = None) -> dict:
        """Запомнить факт. quote — слова пользователя, из которых он взят (ответ на «откуда ты знаешь?»)."""
        text = _clean(text, MAX_TEXT)
        kind = kind if kind in KINDS else "other"
        importance = importance if isinstance(importance, int) and 1 <= importance <= 3 else 2
        files = [p.replace("\\", "/").strip("/") for p in files or [] if isinstance(p, str) and p.strip()][:5]
        quote = " ".join(quote.split())[:400] if isinstance(quote, str) and quote.strip() else None
        now = int(time.time())
        with self.lock:
            about_ids = self._about(about)
            same = self._similar(text)
            if same:
                same.update(text=text, updated=now, last_seen=now, seen=same.get("seen", 1) + 1,
                            importance=max(importance, same.get("importance", 1)))
                same["about"] = list(dict.fromkeys(same.get("about", []) + about_ids))
                same["files"] = list(dict.fromkeys(same.get("files", []) + files))
                if quote and not same.get("quote"):
                    same["quote"] = quote
                if pinned:
                    same["pinned"] = True
                self.save()
                self._changed("f", same["id"])
                return same
            fact = {"id": _id(), "text": text, "kind": kind, "importance": importance, "source": source,
                    "created": now, "updated": now, "last_seen": now, "seen": 1}
            for key, value in (("pinned", pinned), ("quote", quote), ("about", about_ids), ("files", files),
                               ("talk", talk)):
                if value:
                    fact[key] = value
            self.data["facts"].append(fact)
            self._trim()
            self.save()
            self._changed("f", fact["id"])
            return fact

    def edit(self, fact_id: str, text=None, kind=None, pinned=None, about=None) -> dict:
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
            if about is not None:
                f["about"] = self._about(about)
                self._prune_entities()
            f["updated"] = int(time.time())
            self.save()
            self._changed("f", f["id"])
            return f

    def touch(self, ids) -> None:
        """Факт снова всплыл в разговоре — он крепнет."""
        now = int(time.time())
        with self.lock:
            for f in self.data["facts"]:
                if f["id"] in ids:
                    f["seen"] = f.get("seen", 1) + 1
                    f["last_seen"] = now
                    if not f.get("superseded"):
                        f.pop("archived", None)  # вспомнилось — возвращается из архива
                    f["tier"] = self.memory_tier(f, now)
            self.save()

    def delete(self, ids) -> int:
        ids = set(_ids(ids))
        with self.lock:
            before = len(self.data["facts"])
            self.data["facts"] = [f for f in self.data["facts"] if f["id"] not in ids]
            removed = before - len(self.data["facts"])
            if removed:
                self._prune_entities()
                self.save()
            return removed

    def merge(self, ids: list[str], text: str) -> dict | None:
        """Склеить несколько фактов в один (во «сне»): связи, файлы и сила складываются."""
        with self.lock:
            group = [f for f in self.data["facts"] if f["id"] in ids]
            if len(group) < 2:
                return None
            keep = group[0]
            keep.update(text=_clean(text, MAX_TEXT), updated=int(time.time()),
                        seen=sum(f.get("seen", 1) for f in group),
                        importance=max(f.get("importance", 2) for f in group),
                        last_seen=max(f.get("last_seen", 0) for f in group))
            for key in ("about", "files"):
                merged = list(dict.fromkeys(x for f in group for x in f.get(key, [])))
                if merged:
                    keep[key] = merged
            if any(f.get("pinned") for f in group):
                keep["pinned"] = True
            gone = {f["id"] for f in group[1:]}
            self.data["facts"] = [f for f in self.data["facts"] if f["id"] not in gone]
            self.save()
            self._changed("f", keep["id"])
            return keep

    def archive_faded(self) -> int:
        """Во сне: слабое уходит в архив, но больше не уничтожается."""
        count = 0
        with self.lock:
            for f in self.data["facts"]:
                if not f.get("pinned") and not f.get("archived") and self.score(f) < ARCHIVE_SCORE:
                    f.update(archived=True, tier="archive", archived_at=int(time.time()))
                    count += 1
            if count:
                self.save()
        self.rebalance_tiers()
        return count

    def _trim(self) -> None:
        """Engine 2.1: вместо удаления старое переводится в архивный слой."""
        now = time.time()
        for fact in self.data["facts"]:
            forgotten = (not fact.get("pinned") and fact.get("source") == "auto"
                         and fact.get("importance", 2) <= 1
                         and now - fact.get("last_seen", now) >= FORGET_DAYS * 86400)
            if forgotten and not fact.get("archived"):
                fact.update(archived=True, tier="archive", archived_at=int(now))
        active = [f for f in self.data["facts"] if not f.get("archived")]
        if len(active) > MAX_FACTS:
            active.sort(key=lambda f: self.score(f, now))
            for fact in active[:len(active) - MAX_FACTS]:
                fact.update(archived=True, tier="archive", archived_at=int(now))
        for fact in self.data["facts"]:
            fact["tier"] = self.memory_tier(fact, now)
        self._prune_entities()

    # --- Файлы Диска в памяти ---

    def moved(self, old: str, new: str) -> int:
        """Файл или папку на Диске перенесли: ссылки в фактах идут следом."""
        old, new = old.replace("\\", "/").strip("/"), new.replace("\\", "/").strip("/")
        count = 0
        with self.lock:
            for f in self.data["facts"]:
                files = f.get("files", [])
                fixed = [new + p[len(old):] if p == old or p.startswith(old + "/") else p for p in files]
                if fixed != files:
                    f["files"] = fixed
                    count += 1
            for d in self.data["drafts"]:
                if d["path"] == old or d["path"].startswith(old + "/"):
                    d["path"] = new + d["path"][len(old):]
                    count += 1
            if count:
                self.save()
        return count

    # --- Разговоры ---

    def talks(self) -> list[dict]:
        with self.lock:
            return sorted((dict(t) for t in self.data["talks"]), key=lambda t: -t.get("updated", 0))

    def talk(self, talk_id: str) -> dict | None:
        return next((t for t in self.data["talks"] if t["id"] == talk_id), None)

    def save_talk(self, talk_id: str, title: str, summary: str, messages: int, mood: int | None = None) -> dict:
        now = int(time.time())
        with self.lock:
            t = self.talk(talk_id)
            if t is None:
                t = {"id": talk_id, "started": now}
                self.data["talks"].append(t)
            t.update(title=_clean(title, 80), summary=_clean(summary, MAX_SUMMARY), updated=now,
                     messages=max(messages, t.get("messages", 0)))
            if mood is not None:
                t["mood"] = mood
            if len(self.data["talks"]) > MAX_TALKS:
                self.data["talks"].sort(key=lambda x: -x.get("updated", 0))
                del self.data["talks"][MAX_TALKS:]
            self.save()
            self._changed("t", t["id"])
            return t

    def delete_talks(self, ids) -> int:
        ids = set(_ids(ids))
        with self.lock:
            before = len(self.data["talks"])
            self.data["talks"] = [t for t in self.data["talks"] if t["id"] not in ids]
            removed = before - len(self.data["talks"])
            if removed:
                self.save()
            return removed

    # --- Обещания и даты ---

    def promise(self, text: str, who: str = "user", due=None, quote: str | None = None) -> dict:
        """Обещание: who="user" — обещали вы, "yakumo" — обещала она."""
        text = _clean(text, MAX_TEXT)
        with self.lock:
            same = next((p for p in self.data["promises"] if not p.get("done") and alike(p["text"], text)), None)
            if same:
                same["due"] = _date(due) or same.get("due")
                self.save()
                return same
            p = {"id": _id(), "text": text, "who": "yakumo" if who == "yakumo" else "user", "due": _date(due),
                 "done": False, "created": int(time.time())}
            if isinstance(quote, str) and quote.strip():
                p["quote"] = " ".join(quote.split())[:400]
            self.data["promises"].append(p)
            self._limit("promises")
            self.save()
            return p

    def promise_done(self, ids, done: bool = True) -> int:
        ids = set(_ids(ids))
        count = 0
        with self.lock:
            for p in self.data["promises"]:
                if p["id"] in ids and p.get("done") != done:
                    p["done"] = done
                    p["done_at"] = int(time.time()) if done else None
                    count += 1
            self.save()
        return count

    def open_promises(self) -> list[dict]:
        with self.lock:
            return sorted((dict(p) for p in self.data["promises"] if not p.get("done")),
                          key=lambda p: (p.get("due") or "9999", p["created"]))

    def event(self, text: str, date, yearly: bool = False) -> dict:
        """Дата, которую стоит помнить: день рождения (yearly), встреча, срок."""
        text = _clean(text, MAX_TEXT)
        date = _date(date)
        if not date:
            raise BrainError("Нужна дата YYYY-MM-DD")
        with self.lock:
            for e in self.data["events"]:
                same_day = e["date"][5:] == date[5:] if yearly else e["date"] == date
                if same_day and words(e["text"]) & words(text):
                    e.update(text=text, date=date, yearly=bool(yearly) or e.get("yearly", False))
                    self.save()
                    return e
            e = {"id": _id(), "text": text, "date": date, "yearly": bool(yearly), "created": int(time.time())}
            self.data["events"].append(e)
            self._limit("events")
            self.save()
            return e

    def upcoming(self, days: int = 1, on: dt.date | None = None) -> list[dict]:
        """Даты и сроки обещаний на ближайшие days дней (0 — только сегодня)."""
        on = on or dt.date.today()
        found = []
        with self.lock:
            for e in self.data["events"]:
                when = dt.date.fromisoformat(e["date"])
                if e.get("yearly"):
                    when = _anniversary(when, on.year)
                    if when < on:
                        when = _anniversary(when, on.year + 1)
                delta = (when - on).days
                if 0 <= delta <= days:
                    found.append({"text": e["text"], "date": when.isoformat(), "in_days": delta, "kind": "date"})
            for p in self.data["promises"]:
                if p.get("done") or not p.get("due"):
                    continue
                delta = (dt.date.fromisoformat(p["due"]) - on).days
                if delta <= days:  # просроченные тоже
                    found.append({"text": p["text"], "date": p["due"], "in_days": delta,
                                  "kind": "promise", "who": p["who"]})
        return sorted(found, key=lambda x: x["in_days"])

    def on_this_day(self, on: dt.date | None = None) -> list[dict]:
        """Разговоры ровно месяц, полгода или год (и больше лет) назад — для «а помнишь…»."""
        on = on or dt.date.today()
        found = []
        with self.lock:
            for t in self.data["talks"]:
                day = dt.date.fromtimestamp(t.get("started", t.get("updated", 0)))
                months = (on.year - day.year) * 12 + on.month - day.month
                if day.day == on.day and (months in (1, 6) or (months >= 12 and months % 12 == 0)):
                    found.append({"ago_months": months, "title": t["title"], "summary": t["summary"]})
        return found

    def delete_items(self, name: str, ids) -> int:
        if name not in ("promises", "events", "skills", "inbox", "improvements", *GROWTH):
            raise BrainError("Неизвестный список")
        ids = set(_ids(ids))
        with self.lock:
            if name == "improvements":  # удалённое не возвращается само при следующем просмотре источников
                dropped = self.data["meta"].setdefault("improvements_dropped", [])
                dropped += [x["key"] for x in self.data[name] if x["id"] in ids and x.get("key")]
                del dropped[:-300]
            before = len(self.data[name])
            self.data[name] = [x for x in self.data[name] if x["id"] not in ids]
            self.save()
            return before - len(self.data[name])

    def _limit(self, name: str) -> None:
        items = self.data[name]
        if len(items) > MAX_ITEMS:
            items.sort(key=lambda x: (not x.get("done"), x.get("created", 0)), reverse=True)
            del items[MAX_ITEMS:]

    # --- Навыки ---

    def skill(self, name: str, steps, when: str = "") -> dict:
        """Процедура пользователя по шагам («как я делаю отчёт»): Yakumo повторит её по просьбе."""
        name = _clean(name, 80)
        if isinstance(steps, str):
            steps = [s for s in steps.splitlines() if s.strip()]
        if not isinstance(steps, list) or not steps:
            raise BrainError("Нужен список шагов")
        steps = [_clean(str(s), 400) for s in steps[:30]]
        when = " ".join(when.split())[:200] if isinstance(when, str) else ""
        with self.lock:
            s = next((x for x in self.data["skills"] if x["name"].lower() == name.lower()), None)
            if s is None:
                s = {"id": _id(), "name": name, "created": int(time.time()), "used": 0}
                self.data["skills"].append(s)
            s.update(steps=steps, when=when, updated=int(time.time()))
            self._limit("skills")
            self.save()
            self._changed("s", s["id"])
            return s

    def find_skill(self, name: str) -> dict | None:
        q = words(name or "")
        with self.lock:
            best = max(self.data["skills"], default=None,
                       key=lambda s: len(q & words(s["name"] + " " + s.get("when", ""))))
            if best is None or not q & words(best["name"] + " " + best.get("when", "")):
                return None
            best["used"] = best.get("used", 0) + 1
            best["last_used"] = int(time.time())
            self.save()
            return best

    # --- Дни: настроение и программы ---

    def day(self, date: str | None = None) -> dict:
        date = date or today()
        with self.lock:
            d = self.data["days"].setdefault(date, {})
            if len(self.data["days"]) > MAX_DAYS:
                for old in sorted(self.data["days"])[:-MAX_DAYS]:
                    del self.data["days"][old]
            return d

    def note_mood(self, mood: int, note: str = "") -> None:
        if not isinstance(mood, int) or not -2 <= mood <= 2:
            return
        with self.lock:
            d = self.day()
            d.setdefault("mood", []).append(mood)
            if isinstance(note, str) and note.strip():
                d.setdefault("notes", []).append(" ".join(note.split())[:120])
                d["notes"] = d["notes"][-5:]
            self.save()

    def mood_trend(self, days: int = 3) -> dict | None:
        """Среднее настроение за последние дни, если есть данные хотя бы за два дня."""
        with self.lock:
            recent = [(k, v) for k, v in sorted(self.data["days"].items())[-days:] if v.get("mood")]
            if len(recent) < 2:
                return None
            values = [m for _k, v in recent for m in v["mood"]]
            notes = [n for _k, v in recent for n in v.get("notes", [])][-3:]
            return {"average": round(sum(values) / len(values), 2), "days": len(recent), "notes": notes}

    # --- Сообщения от Yakumo ---

    def say(self, text: str, kind: str = "note") -> dict:
        """Сообщение, которое Yakumo сама напишет в чат при следующем открытии страницы."""
        item = {"id": _id(), "text": _block(text, 3000), "kind": kind, "at": int(time.time())}
        with self.lock:
            self.data["inbox"].append(item)
            self.data["inbox"] = self.data["inbox"][-10:]
            self.save()
        return item

    def take_inbox(self) -> list[dict]:
        with self.lock:
            items, self.data["inbox"] = self.data["inbox"], []
            if items:
                self.save()
            return items

    # --- Рост: уроки, желания, цепочки действий ---

    def item(self, name: str, item_id: str) -> dict | None:
        return next((x for x in self.data[name] if x["id"] == item_id), None)

    def add_item(self, name: str, item: dict, limit: int = MAX_ITEMS) -> dict:
        with self.lock:
            item = {"id": _id(), "created": int(time.time()), **item}
            self.data[name].append(item)
            del self.data[name][:-limit]
            self.save()
            return item

    def lesson(self, text: str, source: str = "exam") -> dict:
        """Правило, которое Yakumo вывела сама (из ошибки, ночной тренировки). Повтор не дублируется."""
        text = _clean(text, 300)
        with self.lock:
            same = next((x for x in self.data["lessons"] if alike(x["text"], text)), None)
            if same:
                same["seen"] = same.get("seen", 1) + 1
                self.save()
                return same
            return self.add_item("lessons", {"text": text, "source": source, "seen": 1}, MAX_LESSONS)

    def replace_lessons(self, items: list[tuple[str, int]]) -> None:
        """После консолидации во сне: новый, сжатый список уроков (текст, сколько раз подтверждался)."""
        with self.lock:
            now = int(time.time())
            self.data["lessons"] = [{"id": _id(), "created": now, "text": _clean(t, 300), "source": "sleep",
                                     "seen": max(1, seen)} for t, seen in items if isinstance(t, str) and t.strip()]
            del self.data["lessons"][:-MAX_LESSONS]
            self.save()

    def wish(self, text: str) -> dict:
        """Чему Yakumo хочет научиться: её просили, а она не умеет."""
        text = _clean(text, 200)
        with self.lock:
            same = next((x for x in self.data["wishes"] if alike(x["text"], text)), None)
            if same:
                same["count"] = same.get("count", 1) + 1
                same["last"] = int(time.time())
                self.save()
                return same
            return self.add_item("wishes", {"text": text, "count": 1, "last": int(time.time())}, 50)

    def chain(self, signature: str, steps: list, question: str) -> int:
        """Запомнить цепочку инструментов; вернуть, сколько раз она уже встречалась."""
        with self.lock:
            c = self.data["chains"].setdefault(signature, {"count": 0})
            c.update(count=c["count"] + 1, steps=steps, question=question[:200], last=int(time.time()))
            if len(self.data["chains"]) > 200:
                for old in sorted(self.data["chains"], key=lambda k: self.data["chains"][k].get("last", 0))[:50]:
                    del self.data["chains"][old]
            self.save()
            return c["count"]

    def link(self, a: str, b: str, why: str) -> dict | None:
        """Ассоциация между двумя фактами (находит «сон»). Повтор той же пары не дублируется."""
        ids = {f["id"] for f in self.data["facts"]}
        why = _clean(why, 200)
        if a == b or a not in ids or b not in ids or not why:
            return None
        with self.lock:
            pair = {a, b}
            same = next((x for x in self.data["links"] if {x["a"], x["b"]} == pair), None)
            if same:
                same["why"] = why
                self.save()
                return same
            return self.add_item("links", {"a": a, "b": b, "why": why}, 100)

    def links(self) -> list[dict]:
        ids = {f["id"] for f in self.data["facts"]}
        return [x for x in self.data["links"] if x["a"] in ids and x["b"] in ids]

    # --- Стиль: подсказка, которую Yakumo улучшает сама ---

    def style(self) -> dict | None:
        """Действующая версия стиля или None."""
        st = self.data["style"]
        return next((v for v in st.get("versions", []) if v["id"] == st.get("active")), None)

    def add_style(self, text: str, why: str) -> dict:
        with self.lock:
            st = self.data["style"]
            version = {"id": _id(), "text": _block(text, 800), "why": " ".join(str(why or "").split())[:300],
                       "created": int(time.time())}
            st["versions"] = [*st.get("versions", []), version][-10:]
            st["active"] = version["id"]
            self.save()
            return version

    def use_style(self, version_id: str | None) -> None:
        """Откатить стиль к прежней версии (или выключить, если None)."""
        with self.lock:
            st = self.data["style"]
            if version_id is not None and all(v["id"] != version_id for v in st.get("versions", [])):
                raise BrainError("Такой версии нет")
            st["active"] = version_id
            self.save()

    # --- Структурная память: причины, решения, ошибки и незавершённая работа ---

    def trace(self, kind: str, text: str, *, reason: str = "", result: str = "", status: str = "done",
              files=None, about=None, source: str = "chat", talk: str | None = None, date: str | None = None) -> dict | None:
        if kind not in TRACE_KINDS:
            return None
        text = _clean(text, 400)
        reason = " ".join(str(reason or "").split())[:500]
        result = " ".join(str(result or "").split())[:500]
        status = status if status in ("open", "done", "failed") else ("open" if kind == "progress" else "done")
        clean_files = [p.replace("\\", "/").strip("/") for p in files or [] if isinstance(p, str) and p.strip()][:20]
        about_ids = self._about(about)
        scope = frozenset(about_ids)
        with self.lock:
            # Одинаковый текст у разных проектов/людей — разные следы. Дедупликация только в том же scope.
            same = next((x for x in reversed(self.data["traces"][-500:])
                         if x.get("kind") == kind
                         and frozenset(x.get("about", [])) == scope
                         and alike(x.get("text", ""), text)), None)
            if same:
                same.update(text=text, reason=reason or same.get("reason", ""),
                            result=result or same.get("result", ""), status=status,
                            updated=int(time.time()))
                same["files"] = list(dict.fromkeys([*same.get("files", []), *clean_files]))[-20:]
                same["about"] = list(dict.fromkeys([*same.get("about", []), *about_ids]))[:12]
                self.save()
                return same
            item = {"id": _id(), "kind": kind, "text": text, "reason": reason, "result": result,
                    "status": status, "source": str(source)[:40], "created": int(time.time())}
            if date and _date(date):
                item["date"] = _date(date)
            if clean_files:
                item["files"] = clean_files
            if about_ids:
                item["about"] = about_ids
            if talk:
                item["talk"] = str(talk)[:80]
            self.data["traces"].append(item)
            del self.data["traces"][:-MAX_ITEMS]
            self.save()
            return item

    def conflicts(self, limit: int = 30) -> list[dict]:
        """Кандидаты на противоречие только внутри одной сущности и вида факта."""
        active = [f for f in self.data["facts"] if not f.get("archived") and not f.get("superseded")]
        groups: dict[tuple[str, str], list[dict]] = {}
        word_cache: dict[str, set[str]] = {}
        for fact in active:
            about = set(fact.get("about", []))
            if not about:
                continue
            word_cache[fact["id"]] = words(fact.get("text", ""))
            for entity_id in about:
                groups.setdefault((entity_id, fact.get("kind", "other")), []).append(fact)

        out, seen_pairs = [], set()
        cap = max(1, min(int(limit), 200))
        for facts in groups.values():
            for i, a in enumerate(facts):
                wa = word_cache[a["id"]]
                for b in facts[i + 1:]:
                    pair = tuple(sorted((a["id"], b["id"])))
                    if pair in seen_pairs:
                        continue
                    seen_pairs.add(pair)
                    if alike(a.get("text", ""), b.get("text", "")):
                        continue
                    common = wa & word_cache[b["id"]]
                    if len(common) < 2:
                        continue
                    out.append({"a": a["id"], "b": b["id"], "status": "needs_clarification",
                                "shared": sorted(common)[:8], "verified": False})
                    if len(out) >= cap:
                        return out
        return out

    def timeline(self, limit: int = 100) -> list[dict]:
        """Единая временная память без выдумывания причинности."""
        rows = []
        for x in self.data["traces"]:
            rows.append({"kind": x.get("kind"), "text": x.get("text"), "at": int(x.get("updated", x.get("created", 0)) or 0),
                         "date": x.get("date"), "status": x.get("status"), "reason": x.get("reason", ""),
                         "result": x.get("result", ""), "files": x.get("files", []), "id": x.get("id")})
        for e in self.data["events"]:
            rows.append({"kind": "event", "text": e.get("text"), "at": int(e.get("created", 0) or 0),
                         "date": e.get("date"), "id": e.get("id")})
        for p in self.data["promises"]:
            rows.append({"kind": "promise", "text": p.get("text"), "at": int(p.get("done_at", p.get("created", 0)) or 0),
                         "date": p.get("due"), "status": "done" if p.get("done") else "open", "id": p.get("id")})
        def effective_at(item: dict) -> float:
            value = item.get("date")
            if isinstance(value, str):
                try:
                    day = dt.date.fromisoformat(value)
                    return dt.datetime.combine(day, dt.time.min).timestamp()
                except ValueError:
                    pass
            return float(item.get("at", 0) or 0)

        return sorted(rows, key=effective_at, reverse=True)[:max(1, min(int(limit), 1000))]

    def activity_feed(self, limit: int = 50) -> list[dict]:
        rows = []
        for t in self.data["thoughts"]:
            at = int(t.get("finished", t.get("started", t.get("created", 0))) or 0)
            rows.append({"kind": "thought", "title": t.get("title", ""), "status": t.get("status"), "at": at,
                         "detail": t.get("kind", "")})
        for v in self.versions():
            rows.append({"kind": "version", "title": v.get("title") or v.get("revision", "")[:7],
                         "status": v.get("kind"), "at": int(v.get("at", 0) or 0), "detail": v.get("revision", "")[:7]})
        for x in self.data["traces"]:
            rows.append({"kind": x.get("kind"), "title": x.get("text", ""), "status": x.get("status"),
                         "at": int(x.get("updated", x.get("created", 0)) or 0), "detail": x.get("reason", "")})
        return sorted(rows, key=lambda x: -x.get("at", 0))[:max(1, min(int(limit), 200))]

    def diagnostics(self, conflicts: list[dict] | None = None) -> dict:
        ids = {e["id"] for e in self.data["entities"]}
        orphan_refs = sum(1 for f in self.data["facts"] for i in f.get("about", []) if i not in ids)
        tiers = self.tier_counts()
        conflict_items = self.conflicts(100) if conflicts is None else conflicts
        return {"ok": not orphan_refs, "facts": len(self.data["facts"]), "entities": len(self.data["entities"]),
                "tiers": tiers, "conflicts": len(conflict_items), "orphan_entity_refs": orphan_refs,
                "open_progress": sum(x.get("kind") == "progress" and x.get("status") == "open" for x in self.data["traces"])}

    # --- История меня: свои версии ---

    def version(self, record: dict) -> dict | None:
        """Запомнить версию; seen и install одного SHA схлопываются в одну карточку."""
        key = record.get("key") if isinstance(record, dict) else None
        revision = record.get("revision") if isinstance(record, dict) else None
        if not isinstance(key, str) or not key or not isinstance(revision, str) or not re.fullmatch(r"[a-f0-9]{40}", revision):
            return None
        kind = record.get("kind") if record.get("kind") in ("install", "rollback", "seen") else "seen"
        at = record.get("at")
        previous = record.get("from_revision")

        def text(value, limit):
            try:
                return _clean(value, limit)
            except BrainError:
                return ""

        changes = [c for c in (text(x, 200) for x in record.get("changes") or [] if isinstance(x, str)) if c][:15]
        payload = {
            "key": key[:100], "kind": kind, "revision": revision,
            "from_revision": previous if isinstance(previous, str) and re.fullmatch(r"[a-f0-9]{40}", previous) else None,
            "title": text(record.get("title"), 200), "date": text(record.get("date"), 40),
            "at": int(at) if isinstance(at, (int, float)) and at > 0 else int(time.time()),
            "changes": changes, "total": record.get("total") if type(record.get("total")) is int else len(changes)}
        with self.lock:
            if any(v.get("key") == key for v in self.data["versions"]):
                return None
            same = [v for v in self.data["versions"] if v.get("revision") == revision]
            if same:
                rank = {"seen": 0, "install": 1, "rollback": 2}
                keep = max(same, key=lambda v: (rank.get(v.get("kind"), 0), v.get("at", 0)))
                old_changes = list(dict.fromkeys(c for v in same for c in v.get("changes", []) if isinstance(c, str)))
                old_total = max([int(v.get("total", 0) or 0) for v in same] + [len(old_changes)])
                if rank.get(kind, 0) >= rank.get(keep.get("kind"), 0):
                    keep.update({k: v for k, v in payload.items() if v not in (None, "", [])})
                keep["changes"] = list(dict.fromkeys([*old_changes, *changes]))[:15]
                keep["total"] = max(old_total, int(payload.get("total", 0) or 0), len(keep["changes"]))
                self.data["versions"] = [v for v in self.data["versions"] if v is keep or v.get("revision") != revision]
                self.save()
                return keep
            return self.add_item("versions", payload, MAX_VERSIONS)

    def versions(self) -> list[dict]:
        """Свои версии, новые сверху; старые дубли одного SHA скрываются без потери деталей."""
        rank = {"seen": 0, "install": 1, "rollback": 2}
        grouped: dict[str, dict] = {}
        for v in self.data["versions"]:
            rev = v.get("revision") or v.get("id")
            current = grouped.get(rev)
            if current is None or (rank.get(v.get("kind"), 0), v.get("at", 0)) > (
                    rank.get(current.get("kind"), 0), current.get("at", 0)):
                base, other = dict(v), current
            else:
                base, other = dict(current), v
            if other:
                base["changes"] = list(dict.fromkeys([*base.get("changes", []), *other.get("changes", [])]))[:15]
                base["total"] = max(int(base.get("total", 0) or 0), int(other.get("total", 0) or 0), len(base["changes"]))
            grouped[rev] = base
        return sorted(grouped.values(), key=lambda v: -v.get("at", 0))

    # --- Улучшения: что доработать в самой Yakumo ---

    IMPROVEMENT_TEXT = {"title": 200, "problem": 1500, "steps": 1500, "want": 1500, "fix": 1500, "module": 40}

    def _improvement_fields(self, fields: dict) -> dict:
        out = {}
        for key, limit in self.IMPROVEMENT_TEXT.items():
            if isinstance(fields.get(key), str):
                out[key] = " ".join(fields[key].split())[:limit]
        if isinstance(fields.get("detail"), str):
            out["detail"] = fields["detail"].strip()[:3000]
        if fields.get("priority") in ("high", "normal", "low"):
            out["priority"] = fields["priority"]
        if fields.get("status") in ("new", "given", "done", "rejected"):
            out["status"] = fields["status"]
        if isinstance(fields.get("refined"), bool):
            out["refined"] = fields["refined"]
        return out

    def improvement(self, item: dict) -> dict | None:
        """Добавить пункт или отметить повтор (тот же key). Сделанный пункт при повторе снова становится новым."""
        key = item.get("key") if isinstance(item, dict) else None
        if not isinstance(key, str) or not key:
            return None
        fields = self._improvement_fields(item)
        if not fields.get("title"):
            return None
        with self.lock:
            same = next((x for x in self.data["improvements"] if x.get("key") == key), None)
            if same:
                count = item.get("count") if type(item.get("count")) is int else same.get("count", 1) + 1
                if count > same.get("count", 1):
                    same.update(count=count, last=int(time.time()))
                    if same.get("status") == "done":
                        same.update(status="new", reopened=True)
                    self.save()
                return None
            source = item.get("source") if item.get("source") in ("wish", "thumbs", "error", "idea", "manual") else "manual"
            return self.add_item("improvements", {
                "key": key[:100], "source": source, "status": "new", "refined": False,
                "count": item["count"] if type(item.get("count")) is int and item["count"] > 0 else 1,
                "last": int(time.time()), **fields}, MAX_IMPROVEMENTS)

    def edit_improvement(self, item_id: str, **fields) -> dict:
        with self.lock:
            item = self.item("improvements", item_id)
            if item is None:
                raise BrainError("Нет такого пункта")
            item.update(self._improvement_fields(fields))
            self.save()
            return item

    def improvements(self) -> list[dict]:
        """Новые и важные выше, потом по повторам и свежести."""
        rank = {"new": 0, "given": 1, "done": 2, "rejected": 3}
        prio = {"high": 0, "normal": 1, "low": 2}
        return sorted(self.data["improvements"], key=lambda x: (rank.get(x.get("status"), 0), prio.get(x.get("priority"), 1),
                                                                -x.get("count", 1), -x.get("last", 0)))

    # --- Всё сразу ---

    def clear(self) -> None:
        with self.lock:
            for name in ("facts", "talks", "entities", "promises", "events", "skills", "inbox", "traces", *GROWTH):
                self.data[name] = []
            self.data["days"], self.data["chains"], self.data["style"] = {}, {}, {}
            self.save()

    # --- Поиск по словам ---

    def search(self, query: str, limit: int = 10) -> dict:
        """Факты, разговоры и навыки, где встречаются слова запроса или упомянут человек/место из запроса."""
        q = words(query or "")
        if not q:
            return {"facts": [], "talks": [], "skills": []}

        def rank(text: str) -> int:
            return len(q & words(text))

        with self.lock:
            names = {e["id"]: e["name"] + " " + e.get("relation", "") for e in self.data["entities"]}
            facts = sorted(((rank(f["text"] + " " + " ".join(names.get(i, "") for i in f.get("about", []))), f)
                            for f in self.data["facts"]), key=lambda x: -x[0])
            talks = sorted(((rank(t.get("title", "") + " " + t.get("summary", "")), t) for t in self.data["talks"]),
                           key=lambda x: (-x[0], -x[1].get("updated", 0)))
            skills = sorted(((rank(s["name"] + " " + s.get("when", "")), s) for s in self.data["skills"]),
                            key=lambda x: -x[0])
            return {"facts": [f for r, f in facts if r][:limit], "talks": [t for r, t in talks if r][:limit],
                    "skills": [s for r, s in skills if r][:limit]}

    # --- Обмен ---

    def export(self) -> dict:
        with self.lock:
            out = {"yakumo_memory": 1, "exported": int(time.time())}
            for name in ("facts", "talks", "entities", "promises", "events", "skills", "traces"):
                out[name] = list(self.data[name])
            return out

    def import_(self, data) -> dict:
        """Добавить память из файла экспорта. Совпадающие записи не дублируются."""
        if not isinstance(data, dict) or data.get("yakumo_memory") != 1:
            raise BrainError("Это не файл памяти Yakumo")
        facts = talks = 0
        with self.lock:
            entity_names = {e.get("id"): e for e in data.get("entities", []) if isinstance(e, dict)}
            for f in data.get("facts", [])[:MAX_FACTS]:
                if isinstance(f, dict) and isinstance(f.get("text"), str) and f["text"].strip():
                    before = len(self.data["facts"])
                    about = [{"name": entity_names[i]["name"], "type": entity_names[i].get("type", "thing"),
                              "relation": entity_names[i].get("relation", "")}
                             for i in f.get("about", []) if i in entity_names and isinstance(entity_names[i].get("name"), str)]
                    added = self.add(f["text"], f.get("kind", "other"), f.get("importance", 2),
                                     f.get("source", "manual"), f.get("pinned") is True, f.get("quote"), about,
                                     f.get("files") if isinstance(f.get("files"), list) else None)
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
            for p in data.get("promises", [])[:MAX_ITEMS]:
                if isinstance(p, dict) and isinstance(p.get("text"), str) and p["text"].strip():
                    added = self.promise(p["text"], p.get("who", "user"), p.get("due"), p.get("quote"))
                    if p.get("done") is True:
                        added["done"] = True
            for e in data.get("events", [])[:MAX_ITEMS]:
                if isinstance(e, dict) and isinstance(e.get("text"), str) and _date(e.get("date")):
                    self.event(e["text"], e["date"], e.get("yearly") is True)
            for s in data.get("skills", [])[:MAX_ITEMS]:
                if isinstance(s, dict) and isinstance(s.get("name"), str) and isinstance(s.get("steps"), list):
                    try:
                        self.skill(s["name"], s["steps"], s.get("when", ""))
                    except BrainError:
                        pass
            raw_traces = data.get("traces", [])
            for x in (raw_traces if isinstance(raw_traces, list) else [])[:MAX_ITEMS]:
                if isinstance(x, dict) and x.get("kind") in TRACE_KINDS and isinstance(x.get("text"), str):
                    about = [{"name": entity_names[i]["name"], "type": entity_names[i].get("type", "thing"),
                              "relation": entity_names[i].get("relation", "")}
                             for i in x.get("about", []) if i in entity_names and isinstance(entity_names[i].get("name"), str)]
                    try:
                        before = len(self.data["traces"])
                        restored = self.trace(x["kind"], x["text"], reason=x.get("reason", ""), result=x.get("result", ""),
                                              status=x.get("status", "done"), files=x.get("files"), about=about,
                                              source=x.get("source", "import"), date=x.get("date"))
                        if restored is not None and len(self.data["traces"]) > before:
                            if isinstance(x.get("created"), int):
                                restored["created"] = x["created"]
                            if isinstance(x.get("updated"), int):
                                restored["updated"] = x["updated"]
                    except BrainError:
                        pass
            self.save()
        return {"facts": facts, "talks": talks}
