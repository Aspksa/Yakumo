"""Ветки развития Yakumo: измеримые направления роста одного общего мозга.

Это не отдельные модели и не декоративные «мини-мозги». Каждая ветка считает
реальный опыт из памяти, документов, собственного кода и фоновых мыслей.
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
)


def _level(xp: int) -> tuple[int, int]:
    """Уровень растёт логарифмически; возвращает level и прогресс 0..100."""
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

    def snapshot(self) -> dict:
        m = self.memory.data
        thoughts = m.get("thoughts", [])
        done = [t for t in thoughts if t.get("status") == "done"]
        styles = (m.get("style") or {}).get("versions", [])
        code_status = self.code.status() if self.code is not None else {}
        knowledge_status = self.knowledge.status() if self.knowledge is not None else {}

        raw = {
            "memory": {
                "xp": len(m.get("facts", [])) * 3 + len(m.get("talks", [])) * 2 + len(m.get("entities", [])) * 2,
                "items": len(m.get("facts", [])) + len(m.get("talks", [])) + len(m.get("entities", [])),
                "links": len(m.get("links", [])),
            },
            "logic": {
                "xp": len(m.get("lessons", [])) * 8 + sum(t.get("kind") in ("exam", "feedback", "think", "consolidate") for t in done) * 3,
                "items": len(m.get("lessons", [])),
                "links": sum(int(x.get("seen", 1)) for x in m.get("lessons", [])),
            },
            "documents": {
                "xp": int(knowledge_status.get("chunks", 0)) + int(knowledge_status.get("documents", 0)) * 5,
                "items": int(knowledge_status.get("documents", 0)),
                "links": int(knowledge_status.get("vectors", 0)),
            },
            "code": {
                "xp": int(code_status.get("chunks", 0)) + len(m.get("improvements", [])) * 4,
                "items": int(code_status.get("files", 0)),
                "links": sum(bool(x.get("refined")) for x in m.get("improvements", [])),
            },
            "work": {
                "xp": sum(f.get("kind") == "work" for f in m.get("facts", [])) * 5 + len(m.get("skills", [])) * 4
                      + (10 if self.services.get("work") else 0),
                "items": sum(f.get("kind") == "work" for f in m.get("facts", [])) + len(m.get("skills", [])),
                "links": sum(bool(s.get("used")) for s in m.get("skills", [])),
            },
            "planning": {
                "xp": len(m.get("promises", [])) * 5 + len(m.get("events", [])) * 5
                      + sum(t.get("kind") == "foresee" for t in done) * 4,
                "items": len(m.get("promises", [])) + len(m.get("events", [])),
                "links": sum(not p.get("done") for p in m.get("promises", [])),
            },
            "creativity": {
                "xp": len(m.get("user_tools", [])) * 8 + len(m.get("suggestions", [])) * 4
                      + len(styles) * 5 + sum(t.get("kind") in ("idea", "style", "curious") for t in done) * 3,
                "items": len(m.get("user_tools", [])) + len(m.get("suggestions", [])) + len(styles),
                "links": len(m.get("best", [])),
            },
        }

        branches = []
        for key, ru, en in BRANCHES:
            item = raw[key]
            level, progress = _level(item["xp"])
            branches.append({
                "id": key, "name": {"ru": ru, "en": en}, "level": level,
                "progress": progress, **item,
            })
        return {
            "branches": branches,
            "edges": [{"from": a, "to": b} for a, b in EDGES],
            "updated": int(time.time()),
        }
