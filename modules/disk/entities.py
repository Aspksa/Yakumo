"""Evidence-oriented extraction of vehicle, driver and document links.

Rules are deliberately conservative: relationship assertions require an
explicit cue in the same document. Otherwise they are only candidates.
No cloud access, modifications to user files, or hidden background tasks.
"""
from __future__ import annotations

import datetime as dt
import re
from collections import defaultdict

REGISTRATION = re.compile(r"(?<!\w)[АВЕКМНОРСТУХABEKMHOPCTYX]\s?\d{3}\s?[АВЕКМНОРСТУХABEKMHOPCTYX]{2}\s?\d{2,3}(?!\w)", re.I)
PERSON = re.compile(r"(?<!\w)([А-ЯЁ][а-яё]{2,})\s+([А-ЯЁ][а-яё]{2,})\s+([А-ЯЁ][а-яё]{2,})(?!\w)")
DATE = re.compile(r"(?<!\d)(\d{2})[.\-/](\d{2})[.\-/](20\d{2})(?!\d)")
LABELS = {"путевой": "waybill", "чек": "receipt", "квитанц": "receipt",
          "договор": "contract", "акт": "act", "счет": "invoice", "счёт": "invoice"}
DRIVER_CUE = re.compile(r"водител[ьяюи]\s*[:№-]?\s*", re.I)
FUEL_CUE = re.compile(r"\b(?:гсм|топлив\w*|дизел\w*|бензин\w*|дт|аи[-\s]?(?:92|95|98|100))\b", re.I)
LITERS = re.compile(r"(?<!\d)(\d{1,6}(?:[.,]\d{1,3})?)\s*(?:л\.?|литр\w*)\b", re.I)
MONEY = re.compile(r"(?<!\d)(\d{1,9}(?:[ \u00a0]\d{3})*(?:[.,]\d{1,2})?)\s*(?:₽|руб(?:\.|лей|ля)?)", re.I)
MAX_TEXT = 160000


def date_values(text: str) -> list[str]:
    out = set()
    for day, month, year in DATE.findall(text):
        try:
            out.add(dt.date(int(year), int(month), int(day)).isoformat())
        except ValueError:
            continue
    return sorted(out)


def _number(value: str) -> float:
    return float(value.replace(" ", "").replace("\u00a0", "").replace(",", "."))


def _drivers(text: str) -> list[str]:
    """ФИО считается водителем только рядом с явной меткой «водитель»."""
    out = []
    for cue in DRIVER_CUE.finditer(text):
        match = PERSON.match(text, cue.end())
        if match:
            name = " ".join(match.groups())
            if name not in out:
                out.append(name)
    return out[:20]


def extract_entities(path: str, content: str, *, created_at: str | None = None) -> dict:
    text = content[:MAX_TEXT]
    plates = sorted({re.sub(r"\s+", "", x.upper()) for x in REGISTRATION.findall(text)})
    names = sorted({" ".join(p) for p in PERSON.findall(text)})
    kind = next((v for needle, v in LABELS.items() if needle in (path + " " + text[:1000]).lower()), "other")
    dates = date_values(text)
    drivers = _drivers(text)
    fuel = bool(FUEL_CUE.search(text))
    liters = [_number(x) for x in LITERS.findall(text)[:30]]
    amounts = [_number(x) for x in MONEY.findall(text)[:30]]
    # A date found in a document is not necessarily the event date.
    return {"path": path, "kind": kind, "vehicles": plates[:30], "people": names[:30], "drivers": drivers,
            "document_dates": dates[:100], "event_dates": [], "fuel": fuel,
            "liters": liters, "amounts": amounts,
            "indexed_at": created_at, "evidence": "extracted", "uncertain": True}


def candidate_relationships(records: list[dict]) -> list[dict]:
    by_vehicle = defaultdict(list)
    for r in records:
        for vehicle in r["vehicles"]:
            by_vehicle[vehicle].append(r)
    result = []
    seen = set()
    for vehicle, docs in by_vehicle.items():
        for i, a in enumerate(docs):
            for b in docs[i+1:]:
                pair = tuple(sorted([a["path"], b["path"]]))
                key = (vehicle, *pair)
                if key in seen:
                    continue
                seen.add(key)
                result.append({"subject": vehicle, "relation": "mentioned_in_both",
                               "documents": list(pair), "verified": False,
                               "evidence": "Same vehicle registration appears in both files"})
    return sorted(result, key=lambda x: (x["subject"], x["documents"]))[:500]


def timeline(records: list[dict]) -> list[dict]:
    events = []
    for r in records:
        for date in r["document_dates"]:
            events.append({"date": date, "date_type": "document", "path": r["path"],
                           "uncertain": True})
        if r.get("indexed_at"):
            events.append({"date": r["indexed_at"], "date_type": "indexed",
                           "path": r["path"], "uncertain": False})
    return sorted(events, key=lambda x: (x["date"], x["path"]), reverse=True)


def work_candidates(records: list[dict]) -> list[dict]:
    """Кандидаты для «Работы»: только read-only подсказки с явным evidence, никогда не проводки."""
    out = []
    for r in records:
        vehicles = r.get("vehicles", [])
        if not vehicles:
            continue
        relevant = r.get("kind") == "waybill" or r.get("fuel") or r.get("drivers")
        if not relevant:
            continue
        reasons = []
        if r.get("kind") == "waybill":
            reasons.append("document_kind:waybill")
        if r.get("fuel"):
            reasons.append("fuel_terms")
        if r.get("drivers"):
            reasons.append("explicit_driver_label")
        if r.get("liters"):
            reasons.append("liters")
        for vehicle in vehicles[:10]:
            out.append({
                "path": r["path"], "kind": r.get("kind", "other"), "vehicle": vehicle,
                "driver": (r.get("drivers") or [None])[0],
                "date": (r.get("document_dates") or [None])[0],
                "liters": (r.get("liters") or [None])[0],
                "amount": (r.get("amounts") or [None])[0],
                "verified": False, "confidence": "candidate", "evidence": reasons,
                "action": "review_before_import",
            })
    return sorted(out, key=lambda x: (x["path"], x["vehicle"]))[:1000]
