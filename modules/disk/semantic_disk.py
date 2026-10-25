"""Explicitly enabled semantic search for Yakumo Disk.

Documents are embedded only by a manual action. Search queries may use Cloud.ru
only after the user opts in. Failure always preserves offline lexical search.
"""
from __future__ import annotations

import hashlib
import json
import math

MAX_DOCS_PER_RUN = 20
MAX_CHARACTERS = 3500


def normalize(vector):
    v = [float(x) for x in vector]
    size = math.sqrt(sum(x*x for x in v))
    if not v or not math.isfinite(size) or size <= 0:
        raise ValueError("Invalid embedding")
    return [x / size for x in v]


class SemanticDisk:
    def __init__(self, db, lock, cloud):
        self.db, self.lock, self.cloud = db, lock, cloud
        with lock:
            db.execute("""CREATE TABLE IF NOT EXISTS disk_vectors(
                path TEXT PRIMARY KEY, model TEXT NOT NULL, digest TEXT NOT NULL,
                vector TEXT NOT NULL)""")
            db.commit()

    def _model(self):
        if not self.cloud or not self.cloud.api_key():
            return None
        return self.cloud.embedding_model()

    def status(self):
        with self.lock:
            n = self.db.execute("SELECT count(*) FROM disk_vectors").fetchone()[0]
        return {"vectors": n, "model": self.cloud.models and next((m for m in self.cloud.models if self.cloud.model_kind(m) == "embedding"), None) if self.cloud else None,
                "manual_indexing": True}

    def refresh(self, *, limit=MAX_DOCS_PER_RUN):
        try:
            model = self._model()
        except Exception as exc:
            return {"processed": 0, "error": str(exc)[:180]}
        if not model:
            return {"processed": 0, "error": "Нет доступной embedding-модели Cloud.ru"}
        limit = max(1, min(MAX_DOCS_PER_RUN, int(limit)))
        with self.lock:
            docs = self.db.execute("""SELECT path,ifnull(text,'') || ' ' || ifnull(ocr,'') ||
                ' ' || ifnull(photo,'') FROM files ORDER BY path""").fetchall()
            current = {p: (m, digest) for p,m,digest in
                       self.db.execute("SELECT path,model,digest FROM disk_vectors")}
            self.db.execute("DELETE FROM disk_vectors WHERE path NOT IN (SELECT path FROM files)")
            self.db.commit()
        todo = []
        for path, text in docs:
            content = (path + "\n" + text).strip()[:MAX_CHARACTERS]
            if not content:
                continue
            digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
            if current.get(path) != (model, digest):
                todo.append((path, content, digest))
            if len(todo) >= limit:
                break
        count = 0
        for path, content, digest in todo:
            try:
                vector = normalize(self.cloud.embed([content], model, timeout=25)[0])
            except Exception as exc:
                return {"processed": count, "error": str(exc)[:180]}
            with self.lock:
                self.db.execute("INSERT OR REPLACE INTO disk_vectors VALUES(?,?,?,?)",
                                (path, model, digest, json.dumps(vector)))
                self.db.commit()
            count += 1
        return {"processed": count, "remaining": max(0, len(docs) - count),
                "model": model, "error": None}

    def search(self, query, *, limit=40):
        try:
            model = self._model()
        except Exception:
            return []
        if not model:
            return []
        with self.lock:
            rows = self.db.execute("SELECT path,vector FROM disk_vectors WHERE model=?", (model,)).fetchall()
        if not rows:
            return []
        try:
            q = normalize(self.cloud.embed([query[:1000]], model, timeout=12)[0])
        except Exception:
            return []
        scored = []
        for path, encoded in rows:
            try:
                v = json.loads(encoded)
                if len(v) != len(q):
                    continue
                score = sum(x*y for x,y in zip(q,v))
            except (ValueError, TypeError):
                continue
            if score > 0:
                scored.append({"path": path, "score": score, "match": "semantic",
                               "snippet": "Найдено по смыслу"})
        return sorted(scored, key=lambda x: (-x["score"], x["path"]))[:limit]

    def rename(self, old, new):
        with self.lock:
            rows = self.db.execute("SELECT path,model,digest,vector FROM disk_vectors").fetchall()
            for path, model, digest, vector in rows:
                if path == old or path.startswith(old + "/"):
                    self.db.execute("DELETE FROM disk_vectors WHERE path=?", (path,))
                    self.db.execute("INSERT OR REPLACE INTO disk_vectors VALUES(?,?,?,?)",
                                    (new + path[len(old):], model, digest, vector))
            self.db.commit()
