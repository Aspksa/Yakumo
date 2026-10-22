"""База знаний: все документы Диска по кусочкам — Yakumo отвечает по ним с цитатой и ссылкой.

Документы берутся из умного поиска Диска (ctx.services["disk"]), режутся на
абзацы, и в фоне (когда вы не пишете) для них считаются векторы смысла.
Без модели эмбеддингов поиск идёт по словам. Хранится в brain/knowledge.json.

Здесь же «учёба»: во сне Yakumo берёт ваши темы (учёба, проекты), читает про
них ваши документы и пишет себе конспекты.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import re
import threading
import time
from array import array
from pathlib import Path

from .semantic import dot, pack
from .store import words

log = logging.getLogger("yakumo.modules.brain")

CHUNK = 900          # символов в кусочке
MAX_CHUNKS = 4000    # всего кусочков в базе
BATCH = 32
PER_SYNC = 96        # сколько векторов считать за один заход (остальное — в следующий)
MIN_SCORE = 0.5
STUDY_TOPICS = 2     # тем за одну «учёбу»
MAX_NOTES = 50


def chunks(text: str) -> list[str]:
    """Текст по абзацам, склеенным до CHUNK символов."""
    parts, cur = [], ""
    for para in re.split(r"\n\s*\n|\n(?=\S)", text):
        para = " ".join(para.split())
        if not para:
            continue
        while len(para) > CHUNK:
            parts.append(para[:CHUNK])
            para = para[CHUNK:]
        if len(cur) + len(para) + 1 > CHUNK and cur:
            parts.append(cur)
            cur = ""
        cur = f"{cur} {para}".strip()
    if cur:
        parts.append(cur)
    return parts


class Knowledge:
    def __init__(self, path: Path, services: dict, semantic, mind, memory):
        self.path = path
        self.services = services
        self.semantic = semantic
        self.mind = mind
        self.memory = memory
        self.lock = threading.Lock()
        self.docs: dict[str, int] = {}     # путь -> mtime, когда разобран
        self.items: list[dict] = []        # {"path", "text", "v": array | None}
        self.model: str | None = None
        self._load()

    def _load(self) -> None:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            self.docs, self.model = data["docs"], data.get("model")
            for c in data["chunks"]:
                v = None
                if c.get("v"):
                    v = array("f")
                    v.frombytes(base64.b64decode(c["v"]))
                self.items.append({"path": c["path"], "text": c["text"], "v": v})
        except (OSError, ValueError, KeyError, TypeError):
            self.docs, self.items = {}, []

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = {"model": self.model, "docs": self.docs,
                "chunks": [{"path": c["path"], "text": c["text"],
                            "v": base64.b64encode(c["v"].tobytes()).decode("ascii") if c["v"] is not None else None}
                           for c in self.items]}
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, self.path)

    @property
    def disk(self):
        return self.services.get("disk")

    # --- Разбор Диска ---

    def sync(self) -> int:
        """Новые и изменённые документы — в кусочки, удалённые — из базы; затем порция векторов."""
        if not self.disk or not self.memory.enabled:
            return 0
        with self.lock:
            changed = False
            docs = {path: (mtime, text) for path, mtime, text in self.disk.documents()}
            gone = [p for p in self.docs if p not in docs or docs[p][0] != self.docs[p]]
            if gone:
                gone_set = set(gone)
                self.items = [c for c in self.items if c["path"] not in gone_set]
                for p in gone:
                    del self.docs[p]
                changed = True
            for path, (mtime, text) in docs.items():
                if path in self.docs or len(self.items) >= MAX_CHUNKS:
                    continue
                self.items += [{"path": path, "text": t, "v": None} for t in chunks(text)][:MAX_CHUNKS - len(self.items)]
                self.docs[path] = mtime
                changed = True
            model = self.semantic.model
            if model != self.model:  # сменилась модель эмбеддингов: векторы надо пересчитать
                self.model = model
                for c in self.items:
                    c["v"] = None
                changed = True
            done = 0
            if model and self.semantic.ready():
                todo = [c for c in self.items if c["v"] is None][:PER_SYNC]
                try:
                    for i in range(0, len(todo), BATCH):
                        part = todo[i:i + BATCH]
                        for c, vec in zip(part, self.semantic.cloud.embed([c["text"] for c in part], model)):
                            c["v"] = pack(vec)
                            done += 1
                except Exception as exc:  # noqa: BLE001 — доделаем в следующий раз
                    log.warning("База знаний: векторы не посчитаны: %s", exc)
                changed = changed or bool(done)
            if changed:
                self._save()
            return done

    def search(self, query: str, limit: int = 5) -> list[dict]:
        """Кусочки документов по смыслу (или по словам): [{"path", "text", "score"}]."""
        vec = self.semantic.query_vector(query) if self.model and any(c["v"] is not None for c in self.items) else None
        if vec is not None:
            scored = [(dot(vec, c["v"]), c) for c in self.items if c["v"] is not None and len(c["v"]) == len(vec)]
            scored = [(s, c) for s, c in scored if s >= MIN_SCORE]
        else:
            q = words(query)
            scored = [(len(q & words(c["text"])) / (len(q) or 1), c) for c in self.items] if q else []
            scored = [(s, c) for s, c in scored if s >= 0.5]
        scored.sort(key=lambda x: -x[0])
        return [{"path": c["path"], "text": c["text"], "score": round(s, 3)} for s, c in scored[:limit]]

    def status(self) -> dict:
        return {"available": bool(self.disk), "documents": len(self.docs), "chunks": len(self.items),
                "vectors": sum(c["v"] is not None for c in self.items), "model": self.model}

    # --- Учёба во сне ---

    def topics(self) -> list[str]:
        """Темы для учёбы: проекты и дела пользователя, о которых давно не было конспекта."""
        m = self.memory.data
        recent = {n["topic"].lower() for n in m["notes"] if time.time() - n.get("created", 0) < 14 * 86400}
        found = [e["name"] for e in m["entities"] if e.get("type") in ("project", "org")]
        found += [f["text"] for f in self.memory.facts() if f["kind"] == "work" and not f.get("archived")]
        return [t for t in dict.fromkeys(found) if t.lower() not in recent][:STUDY_TOPICS]

    def study(self, lang: str = "ru") -> int:
        if not self.items or not self.mind.can_think():
            return 0
        written = 0
        for topic in self.topics():
            found = self.search(topic, 4)
            if not found:
                continue
            item = self.mind.thought("study", f"Изучаю: {topic}" if lang == "ru" else f"Studying: {topic}")
            sources = "\n\n".join(f"[{c['path']}]\n{c['text']}" for c in found)
            prompt = ((f"Ты Yakumo. Пользователь занимается темой «{topic}». Вот отрывки из его документов:\n\n"
                       f"{sources}\n\nНапиши для себя короткий конспект (3-6 пунктов) по этой теме: главное, что "
                       "пригодится, чтобы помогать пользователю. Только по документам, без выдумок.")
                      if lang == "ru" else
                      (f"You are Yakumo. The user works on “{topic}”. Excerpts from their documents:\n\n{sources}\n\n"
                       "Write yourself a short summary (3-6 bullets) of what will help you assist the user. "
                       "Only from the documents, no inventions."))
            summary = self.mind.complete([{"role": "user", "content": prompt}], max_tokens=700).strip()
            if summary:
                self.memory.add_item("notes", {"topic": topic[:120], "summary": summary[:3000],
                                               "sources": list(dict.fromkeys(c["path"] for c in found))},
                                     MAX_NOTES)
                written += 1
            self.mind.finish(item, "done", summary[:300])
        return written
