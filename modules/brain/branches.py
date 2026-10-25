"""Ветки развития и нейросвязи одного общего мозга Yakumo.

Ветки считаются по реальному опыту. Связь укрепляется, только когда обе её
стороны выросли между двумя замерами; без использования она медленно слабеет.
Автофокус выбирает самую слабую доступную ветку для следующей тренировки.
"""

from __future__ import annotations

import math
import time


BRANCHES = (
    ("memory", "Память", "Memory"),
    ("logic", "Логика", "Logic"),
    ("documents", "Документы", "Documents"),
    ("code", "Код", "Code"),
    ("work", "Работа", "Work"),
    ("planning", "Планирование", "Planning"),
    ("creativity", "Творчество", "Creativity"),
)

EDGES = (
    ("memory", "logic"), ("memory", "planning"), ("documents", "logic"),
    ("code", "logic"), ("logic", "creativity"), ("work", "planning"),
    ("planning", "creativity"),
)

ACTIONS = {
    "memory": "consolidate",
    "logic": "exam",
    "documents": "study",
    "code": "code_refine",
    "work": "foresee",
    "planning": "foresee",
    "creativity": "ideas",
}


def _level(xp: int) -> tuple[int, int]:
    xp = max(0, int(xp))
    level = min(99, 1 + int(math.log2(xp + 1)))
    start = (2 ** (level - 1)) - 1
    end = (2 ** level) - 1
    progress = 100 if level >= 99 else round((xp - start) * 100 / max(1, end - start))
    return level, max(0, min(100, progress))


class DevelopmentBranches:
    def __init__(self, memory, knowledge=None, code=None, services=None):
        self.memory = memory
        self.knowledge = knowledge
        self.code = code
        self.services = services if services is not None else {}

    def _development(self) -> dict:
        meta = self.memory.data["meta"]
        dev = meta.get("development")
        if not isinstance(dev, dict):
            dev = meta["development"] = {}
        for key, default in (("last_xp", {}), ("last_growth", {}), ("edges", {}), ("history", [])):
            if not isinstance(dev.get(key), type(default)):
                dev[key] = default
        return dev

    def _raw(self) -> dict[str, dict]:
        m = self.memory.data
        thoughts = m.get("thoughts", [])
        done = [t for t in thoughts if t.get("status") == "done"]
        styles = (m.get("style") or {}).get("versions", [])
        code_status = self.code.status() if self.code is not None else {}
        knowledge_status = self.knowledge.status() if self.knowledge is not None else {}
        work_items = sum(f.get("kind") == "work" and not f.get("archived") for f in m.get("facts", []))
        return {
            "memory": {
                "xp": sum(not f.get("archived") for f in m.get("facts", [])) * 3
                      + len(m.get("talks", [])) * 2 + len(m.get("entities", [])) * 2,
                "items": sum(not f.get("archived") for f in m.get("facts", [])) + len(m.get("talks", []))
                         + len(m.get("entities", [])),
                "links": len(m.get("links", [])), "available": True,
            },
            "logic": {
                "xp": len(m.get("lessons", [])) * 8
                      + sum(t.get("kind") in ("exam", "feedback", "think", "consolidate") for t in done) * 3,
                "items": len(m.get("lessons", [])),
                "links": sum(int(x.get("seen", 1)) for x in m.get("lessons", [])), "available": True,
            },
            "documents": {
                "xp": int(knowledge_status.get("chunks", 0)) + int(knowledge_status.get("documents", 0)) * 5,
                "items": int(knowledge_status.get("documents", 0)),
                "links": int(knowledge_status.get("vectors", 0)),
                "available": bool(int(knowledge_status.get("documents", 0))),
            },
            "code": {
                "xp": int(code_status.get("chunks", 0)) + len(m.get("improvements", [])) * 4,
                "items": int(code_status.get("files", 0)),
                "links": sum(bool(x.get("refined")) for x in m.get("improvements", [])),
                "available": bool(int(code_status.get("files", 0))),
            },
            "work": {
                "xp": work_items * 5 + len(m.get("skills", [])) * 4 + (10 if self.services.get("work") else 0),
                "items": work_items + len(m.get("skills", [])),
                "links": sum(bool(s.get("used")) for s in m.get("skills", [])),
                "available": bool(self.services.get("work") or work_items or m.get("skills")),
            },
            "planning": {
                "xp": len(m.get("promises", [])) * 5 + len(m.get("events", [])) * 5
                      + sum(t.get("kind") == "foresee" for t in done) * 4,
                "items": len(m.get("promises", [])) + len(m.get("events", [])),
                "links": sum(not p.get("done") for p in m.get("promises", [])), "available": True,
            },
            "creativity": {
                "xp": len(m.get("user_tools", [])) * 8 + len(m.get("suggestions", [])) * 4
                      + len(styles) * 5 + sum(t.get("kind") in ("idea", "style", "curious") for t in done) * 3,
                "items": len(m.get("user_tools", [])) + len(m.get("suggestions", [])) + len(styles),
                "links": len(m.get("best", [])), "available": True,
            },
        }

    def _focus(self, raw: dict[str, dict]) -> dict:
        dev = self._development()
        candidates = []
        for key, ru, en in BRANCHES:
            item = raw[key]
            if not item["available"]:
                continue
            level, progress = _level(item["xp"])
            last = int(dev["last_growth"].get(key, 0))
            candidates.append((level, progress, last, key, ru, en))
        if not candidates:
            return {}
        level, progress, last, key, ru, en = min(candidates)
        now = int(time.time())
        return {
            "id": key, "name": {"ru": ru, "en": en}, "action": ACTIONS[key],
            "level": level, "progress": progress,
            "reason": "weakest", "stale_days": (now - last) // 86400 if last else None,
        }

    def tick(self) -> dict:
        """Часовой замер: усилить реально совместно выросшие связи и выбрать автофокус."""
        raw = self._raw()
        dev = self._development()
        prev = dev["last_xp"]
        now = int(time.time())
        deltas = {key: max(0, item["xp"] - int(prev.get(key, item["xp"]))) for key, item in raw.items()}
        changed = False

        for key, delta in deltas.items():
            if delta > 0:
                dev["last_growth"][key] = now
                changed = True

        for a, b in EDGES:
            edge_key = f"{a}>{b}"
            edge = dev["edges"].setdefault(edge_key, {"strength": 10, "uses": 0, "last_used": 0})
            da, db = deltas[a], deltas[b]
            if da > 0 and db > 0:
                boost = 2 + min(10, int(math.sqrt(da * db)))
                before = int(edge.get("strength", 10))
                edge["strength"] = min(100, before + boost)
                edge["uses"] = int(edge.get("uses", 0)) + 1
                edge["last_used"] = now
                edge.setdefault("history", []).append({"at": now, "strength": edge["strength"],
                                                        "delta": edge["strength"] - before})
                del edge["history"][:-60]
                changed = True
            elif edge.get("last_used") and now - int(edge["last_used"]) > 14 * 86400 and edge.get("strength", 10) > 5:
                before = int(edge["strength"])
                edge["strength"] = before - 1
                edge.setdefault("history", []).append({"at": now, "strength": edge["strength"], "delta": -1})
                del edge["history"][:-60]
                changed = True

        current = {key: int(item["xp"]) for key, item in raw.items()}
        if current != prev:
            dev["last_xp"] = current
            changed = True
        focus = self._focus(raw)
        if dev.get("focus", {}).get("id") != focus.get("id"):
            dev["focus"] = {**focus, "since": now}
            changed = True
        else:
            dev["focus"] = {**dev.get("focus", {}), **focus}

        if changed:
            dev["history"].append({"at": now, "xp": current, "focus": focus.get("id")})
            del dev["history"][:-180]
            self.memory.save()
        return self.snapshot(raw)

    def note_training(self, branch_id: str, action: str, ok: bool = True) -> None:
        dev = self._development()
        dev["last_training"] = {"branch": branch_id, "action": action, "ok": bool(ok), "at": int(time.time())}
        self.memory.save()

    def snapshot(self, raw: dict[str, dict] | None = None) -> dict:
        raw = raw or self._raw()
        dev = self._development()
        branches = []
        for key, ru, en in BRANCHES:
            item = raw[key]
            level, progress = _level(item["xp"])
            branches.append({
                "id": key, "name": {"ru": ru, "en": en}, "level": level, "progress": progress,
                "last_growth": int(dev["last_growth"].get(key, 0)), **item,
            })
        edges = []
        for a, b in EDGES:
            saved = dev["edges"].get(f"{a}>{b}", {})
            edges.append({
                "from": a, "to": b, "strength": int(saved.get("strength", 10)),
                "uses": int(saved.get("uses", 0)), "last_used": int(saved.get("last_used", 0)),
                "history": list(saved.get("history", []))[-60:],
            })
        return {
            "branches": branches, "edges": edges, "focus": self._focus(raw),
            "last_training": dev.get("last_training"), "updated": int(time.time()),
        }
