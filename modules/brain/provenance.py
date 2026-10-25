"""Append-only provenance journal for verified Yakumo graph updates.

Observations record existence/status transitions, not causal relationships.
Explicit links are accepted only when both referenced entities exist and are
validated; never infer that a thought created a lesson from timing alone.
"""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path

KINDS = ("mind", "growth", "skill", "improvement", "evolution", "memory")
MAX_EVENTS = 600
MAX_NODES = 400


def identifiers(data):
    result = {}
    sources = {
        "mind": (data.get("mind") or {}).get("thoughts") or [],
        "growth": data.get("lessons") or [],
        "skill": data.get("skills") or [],
        "improvement": data.get("improvements") or [],
        "evolution": (data.get("evolution") or {}).get("runs") or [],
        "memory": data.get("facts") or [],
    }
    for kind, rows in sources.items():
        for row in rows[:MAX_NODES]:
            if not isinstance(row, dict) or row.get("id") is None:
                continue
            key = kind + ":" + str(row["id"])[:128]
            status = str(row.get("status") or ("archived" if row.get("archived") else "recorded"))[:48]
            result[key] = {"id": key, "kind": kind, "status": status,
                           "created": row.get("created") if isinstance(row.get("created"), (int, float)) else None}
    return result


class ProvenanceJournal:
    def __init__(self, path):
        self.path = Path(path)
        self.lock = threading.RLock()
        self.events = []
        self.links = []
        self.current = {}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                self.events = [x for x in data.get("events", []) if isinstance(x, dict)][-MAX_EVENTS:]
                self.links = [x for x in data.get("links", []) if isinstance(x, dict)][-MAX_EVENTS:]
                self.current = data.get("current", {}) if isinstance(data.get("current"), dict) else {}
        except (ValueError, OSError, TypeError):
            pass

    def _save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_suffix(".tmp")
        temp.write_text(json.dumps({"events": self.events, "links": self.links,
                                    "current": self.current}, ensure_ascii=False), encoding="utf-8")
        temp.replace(self.path)

    def observe(self, data):
        nodes = identifiers(data)
        with self.lock:
            first = not self.current
            previous = self.current
            changes = []
            if not first:
                for key, value in nodes.items():
                    if key not in previous:
                        changes.append(("created", key, value["status"]))
                    elif previous[key].get("status") != value["status"]:
                        changes.append(("status", key, value["status"]))
                for key in previous.keys() - nodes.keys():
                    changes.append(("missing", key, "missing"))
            timestamp = int(time.time())
            for action, key, status in changes[:100]:
                self.events.append({"id": str(time.time_ns()) + ":" + str(len(self.events)),
                                    "time": timestamp, "action": action,
                                    "source_id": key, "status": status})
            self.events = self.events[-MAX_EVENTS:]
            if nodes != previous:
                self.current = nodes
                self._save()
            return self.snapshot()

    def link(self, source, target, relation, data):
        nodes = identifiers(data)
        if source not in nodes or target not in nodes or source == target:
            raise ValueError("Оба уникальных источника связи должны существовать")
        if relation not in ("derived_from", "verified_by", "related_to"):
            raise ValueError("Неизвестный тип подтверждаемой связи")
        with self.lock:
            if any(x["source_id"] == source and x["target_id"] == target and x["relation"] == relation
                   for x in self.links):
                return self.snapshot()
            self.links.append({"id": str(time.time_ns()), "time": int(time.time()),
                               "source_id": source, "target_id": target, "relation": relation,
                               "origin": "explicit"})
            self.links = self.links[-MAX_EVENTS:]
            self._save()
            return self.snapshot()

    def snapshot(self):
        with self.lock:
            return {"version": 1, "events": list(self.events[-80:]),
                    "links": list(self.links[-160:]), "nodes": list(self.current.values())[-MAX_NODES:],
                    "note": "Новые события записываются после начала наблюдения. Причинные связи только явные."}
