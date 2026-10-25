"""Read-only summary of the nine Yakumo Brain areas.

Pure function: no cloud requests, no mutation of memory, no personal content
in diagnostics. Derived from live state, not manually increased counters.
"""
from __future__ import annotations


def summary(data: dict, *, mind: dict | None = None, knowledge: dict | None = None,
            branches: dict | None = None) -> dict:
    mind, knowledge, branches = mind or {}, knowledge or {}, branches or {}
    lists = ("facts", "entities", "talks", "promises", "events", "skills",
             "versions", "thoughts", "improvements")
    totals = {key: len(data.get(key, [])) for key in lists}
    issues = []
    def warn(code, area, message, severity="normal"):
        issues.append({"code": code, "area": area, "severity": severity,
                       "description": message, "verified": True})
    if totals["facts"] and not totals["talks"]:
        warn("talk_history_empty", "Разговоры", "Факты есть, а конспектов разговоров нет.")
    ids = {e.get("id") for e in data.get("entities", [])}
    orphan = sum(1 for f in data.get("facts", []) for e in f.get("about", []) if e not in ids)
    if orphan:
        warn("orphan_entities", "Карта", f"Некорректных ссылок на сущности: {orphan}.", "high")
    open_promises = sum(not p.get("done") for p in data.get("promises", []))
    if open_promises:
        warn("pending_promises", "Обещания и даты",
             f"Незавершённых обещаний: {open_promises}.", "info")
    failed = sum(t.get("status") == "failed" for t in data.get("thoughts", []))
    if failed:
        warn("failed_thoughts", "Разум", f"Неудачных фоновых мыслей: {failed}.")
    stalled = sum(t.get("status") == "running" and t.get("stale") for t in data.get("thoughts", []))
    if stalled:
        warn("stale_thoughts", "Разум", f"Подозрительных активных мыслей: {stalled}.", "high")
    br = branches.get("branches", [])
    weak = [x.get("id") for x in br if x.get("xp", 0) == 0]
    if weak:
        warn("branches_without_experience", "Рост",
             f"Веток без измеренного опыта: {len(weak)}.")
    new_improvements = sum(x.get("status") == "new" for x in data.get("improvements", []))
    return {"version": 1, "read_only": True, "totals": totals,
            "areas": {
                "Факты": {"count": totals["facts"]},
                "Карта": {"count": totals["entities"], "orphan_references": orphan},
                "Разговоры": {"count": totals["talks"]},
                "Обещания и даты": {"count": totals["promises"] + totals["events"],
                                   "open_promises": open_promises},
                "Навыки": {"count": totals["skills"]},
                "Сама Yakumo": {"versions": totals["versions"]},
                "Разум": {"thoughts": totals["thoughts"], "failed": failed,
                          "budget_used": mind.get("used")},
                "Рост": {"branches": len(br), "no_experience": weak,
                         "vectors": knowledge.get("vectors")},
                "Улучшения": {"count": totals["improvements"], "new": new_improvements},
            }, "issues": issues}
