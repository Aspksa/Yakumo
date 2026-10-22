"""Поиск по смыслу: факты, разговоры и навыки превращаются в векторы через Cloud.ru.

Так «машина» находит факт про «автомобиль». Векторы лежат рядом с памятью
(brain/vectors.json) и пересчитываются в фоне только для изменённых записей.
Если в каталоге Cloud.ru нет модели эмбеддингов или нет связи, память ищет по словам.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import math
import os
import threading
import time
from array import array
from pathlib import Path

log = logging.getLogger("yakumo.modules.brain")

BATCH = 32         # текстов в одном запросе
MIN_SCORE = 0.45   # насколько близко по смыслу, чтобы считаться находкой
RETRY = 600        # секунд до новой попытки после ошибки
QUERY_TIMEOUT = 6  # секунд на вектор запроса из чата


def _pack(vector: list[float]) -> tuple[str, array]:
    norm = math.sqrt(sum(x * x for x in vector)) or 1.0
    arr = array("f", (x / norm for x in vector))
    return base64.b64encode(arr.tobytes()).decode("ascii"), arr


def dot(a, b) -> float:
    return sum(x * y for x, y in zip(a, b))


def pack(vector: list[float]) -> array:
    """Нормированный вектор (близость тогда — просто скалярное произведение)."""
    return _pack(vector)[1]


def _unpack(text: str) -> array:
    arr = array("f")
    arr.frombytes(base64.b64decode(text))
    return arr


def _hash(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:12]


class Semantic:
    def __init__(self, path: Path, memory, cloud):
        self.path = path
        self.memory = memory
        self.cloud = cloud
        self.lock = threading.Lock()
        self.model: str | None = None
        self.vectors: dict[str, tuple[str, array]] = {}  # ключ -> (хэш текста, вектор)
        self.failed_at = 0.0
        self.error: str | None = None
        self.cache: dict[str, array] = {}
        self._load()

    def _load(self) -> None:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            self.model = data["model"]
            self.vectors = {k: (v["h"], _unpack(v["v"])) for k, v in data["items"].items()}
        except (OSError, ValueError, KeyError, TypeError):
            self.vectors = {}

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        items = {k: {"h": h, "v": base64.b64encode(v.tobytes()).decode("ascii")} for k, (h, v) in self.vectors.items()}
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"model": self.model, "items": items}), encoding="utf-8")
        os.replace(tmp, self.path)

    def texts(self) -> dict[str, str]:
        """Что искать по смыслу: ключ записи -> текст."""
        m = self.memory.data
        out = {}
        with self.memory.lock:
            names = {e["id"]: e["name"] for e in m["entities"]}
            for f in m["facts"]:
                about = ", ".join(names[i] for i in f.get("about", []) if i in names)
                out["f:" + f["id"]] = f["text"] + (f" ({about})" if about else "")
            for t in m["talks"]:
                out["t:" + t["id"]] = f"{t.get('title', '')}. {t.get('summary', '')}"
            for s in m["skills"]:
                out["s:" + s["id"]] = f"{s['name']}. {s.get('when', '')}"
            for n in m["notes"]:
                out["n:" + n["id"]] = f"{n['topic']}. {n['summary'][:500]}"
        return out

    def ready(self) -> bool:
        return bool(self.cloud and self.cloud.api_key()) and time.time() - self.failed_at > RETRY

    def _pick_model(self) -> str | None:
        model = self.cloud.embedding_model()
        if model and model != self.model:
            self.model, self.vectors, self.cache = model, {}, {}  # векторы разных моделей несравнимы
        return model

    def sync(self) -> int:
        """Посчитать векторы для новых и изменённых записей. Возвращает, сколько посчитано."""
        if not self.memory.enabled or not self.ready():
            return 0
        with self.lock:
            try:
                if not self._pick_model():
                    self.failed_at, self.error = time.time(), "no_model"
                    return 0
                texts = self.texts()
                stale = [k for k in self.vectors if k not in texts]
                todo = [(k, t) for k, t in texts.items() if self.vectors.get(k, ("",))[0] != _hash(t)]
                for k in stale:
                    del self.vectors[k]
                for i in range(0, len(todo), BATCH):
                    part = todo[i:i + BATCH]
                    for (k, t), vec in zip(part, self.cloud.embed([t for _k, t in part], self.model)):
                        self.vectors[k] = (_hash(t), _pack(vec)[1])
                if todo or stale:
                    self._save()
                self.error = None
                return len(todo)
            except Exception as exc:  # noqa: BLE001 — нет связи или модели: ищем по словам
                self.failed_at, self.error = time.time(), str(exc) or type(exc).__name__
                log.warning("Память: смысловой поиск недоступен: %s", self.error)
                return 0

    def query_vector(self, query: str) -> array | None:
        """Вектор запроса (с кэшем): им же пользуется база знаний Диска."""
        query = " ".join(query.split())[:1000]
        if not query or not self.model or not self.ready():
            return None
        vec = self.cache.get(query)
        if vec is None:
            try:
                vec = _pack(self.cloud.embed([query], self.model, timeout=QUERY_TIMEOUT)[0])[1]
            except Exception as exc:  # noqa: BLE001
                self.failed_at, self.error = time.time(), str(exc) or type(exc).__name__
                return None
            if len(self.cache) > 64:
                self.cache.clear()
            self.cache[query] = vec
        return vec

    def search(self, query: str, limit: int = 10) -> list[tuple[str, float]]:
        """Ближайшие по смыслу записи: [(ключ, близость)], самые близкие первыми."""
        if not self.vectors:
            return []
        vec = self.query_vector(query)
        if vec is None:
            return []
        scored = []
        for key, (_h, v) in list(self.vectors.items()):
            if len(v) == len(vec):
                score = dot(vec, v)
                if score >= MIN_SCORE:
                    scored.append((key, score))
        return sorted(scored, key=lambda x: -x[1])[:limit]

    def status(self) -> dict:
        return {"model": self.model, "indexed": len(self.vectors), "error": self.error}
