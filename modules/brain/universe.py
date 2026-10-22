"""Вселенная Yakumo: галактики жизни и документы у звёзд.

Каждая звезда карты (человек, питомец, место, проект) попадает в «галактику» —
область жизни: семья, друзья, работа, дом, места, здоровье, увлечения. Сначала
по простым признакам (тип и «кем приходится»), потом, когда вы не работаете,
Yakumo уточняет сама по фактам о звезде. Если вы перенесли звезду в другую
галактику руками, она её больше не трогает.

Документы Диска сами прилипают к звёздам: если имя звезды встречается в
документе, документ показывается рядом с ней.
"""

from __future__ import annotations

import re
import time

from .learn import parse

AREAS = ("family", "friends", "work", "home", "places", "health", "hobby", "other")
FAMILY = ("мам", "пап", "мать", "отец", "сестр", "брат", "жена", "муж", "сын", "доч", "бабуш", "дедуш", "дед",
          "тёт", "тет", "дяд", "племян", "внук", "внуч", "свекр", "свекров", "тёщ", "тещ", "тест", "кузен", "кузин",
          "родител", "семь", "mom", "mother", "dad", "father", "sister", "brother", "wife", "husband", "son",
          "daughter", "grand", "aunt", "uncle", "cousin", "niece", "nephew", "parent", "family")
WORK = ("коллег", "начальн", "руковод", "директор", "клиент", "партнёр", "партнер", "сотрудн", "подчин", "заказчик",
        "colleague", "boss", "manager", "client", "partner", "coworker", "employer")
HEALTH = ("врач", "доктор", "терапевт", "стоматолог", "клиник", "больниц", "тренер", "психолог", "doctor", "dentist",
          "clinic", "hospital", "therapist", "coach")
FRIENDS = ("друг", "подруг", "приятел", "сосед", "friend", "neighbo")
MAX_DOCS = 6
REFINE_BATCH = 25

REFINE = {
    "ru": """Разложи звёзды карты пользователя по областям его жизни.
Области: family (семья и родные), friends (друзья, знакомые, соседи), work (работа, проекты, коллеги, клиенты,
организации), home (дом, питомцы, быт), places (города, страны, места), health (здоровье, врачи, спорт),
hobby (увлечения, учёба, творчество), other (не подходит никуда).

Звёзды:
{items}

Ответь ТОЛЬКО объектом JSON: {{"areas": {{"id звезды": "область", ...}}}}""",
    "en": """Sort the stars of the user's map into areas of their life.
Areas: family, friends (friends, acquaintances, neighbours), work (work, projects, colleagues, clients,
organisations), home (home, pets, household), places (cities, countries, places), health (health, doctors,
sport), hobby (hobbies, study, creativity), other.

Stars:
{items}

Reply ONLY with a JSON object: {{"areas": {{"star id": "area", ...}}}}""",
}


def guess_area(entity: dict) -> str:
    """Область по типу и «кем приходится» — без модели."""
    rel = (entity.get("relation") or "").lower()
    etype = entity.get("type")
    if any(w in rel for w in FAMILY):
        return "family"
    if any(w in rel for w in HEALTH):
        return "health"
    if any(w in rel for w in WORK) or etype in ("project", "org"):
        return "work"
    if etype == "pet":
        return "home"
    if etype == "place":
        return "places"
    if etype == "person" or any(w in rel for w in FRIENDS):
        return "friends"
    return "other"


class Universe:
    def __init__(self, memory, mind, knowledge, lang):
        self.memory = memory
        self.mind = mind
        self.knowledge = knowledge
        self.lang = lang

    # --- Галактики ---

    def classify(self) -> int:
        """Звёзды без галактики — по простым признакам."""
        done = 0
        with self.memory.lock:
            for e in self.memory.data["entities"]:
                if e.get("area") not in AREAS:
                    e["area"], e["area_by"] = guess_area(e), "auto"
                    done += 1
            if done:
                self.memory.save()
        return done

    def refine(self) -> int:
        """Когда вы не работаете: Yakumo уточняет галактики по фактам о звёздах (по разу на звезду)."""
        self.classify()
        todo = [e for e in self.memory.data["entities"] if e.get("area_by") == "auto"][:REFINE_BATCH]
        if not todo or not self.mind.can_think():
            return 0
        facts: dict[str, list[str]] = {}
        for f in self.memory.facts():
            for i in f.get("about", []):
                facts.setdefault(i, []).append(f["text"])
        lines = [f"- {e['id']}: {e['name']} ({e.get('type', 'thing')}"
                 + (f", {e['relation']}" if e.get("relation") else "") + ")"
                 + (": " + "; ".join(facts.get(e["id"], [])[:3]) if facts.get(e["id"]) else "") for e in todo]
        lang = self.lang()
        try:
            data = parse(self.mind.complete([{"role": "user", "content": REFINE[lang].format(items="\n".join(lines))}],
                                            max_tokens=600))
        finally:
            with self.memory.lock:
                for e in todo:
                    if e.get("area_by") == "auto":
                        e["area_by"] = "tried"  # больше не спрашивать, даже если ответ не пришёл
                self.memory.save()
        areas = data.get("areas") if isinstance(data.get("areas"), dict) else {}
        changed = 0
        with self.memory.lock:
            for e in todo:
                area = areas.get(e["id"])
                if area in AREAS and e.get("area_by") != "user":
                    changed += area != e.get("area")
                    e["area"], e["area_by"] = area, "yakumo"
            self.memory.save()
        return changed

    def set_area(self, entity_id: str, area: str) -> dict:
        if area not in AREAS:
            raise ValueError("Неизвестная область")
        with self.memory.lock:
            e = next((x for x in self.memory.data["entities"] if x["id"] == entity_id), None)
            if e is None:
                raise ValueError("Нет такой звезды")
            e["area"], e["area_by"] = area, "user"
            self.memory.save()
            return e

    # --- Документы у звёзд ---

    def docs(self) -> dict[str, list[str]]:
        """Документы Диска, где встречается имя звезды: {id звезды: [пути]}. Пересчитывается в фоне."""
        items = getattr(self.knowledge, "items", [])
        result: dict[str, list[str]] = {}
        for e in self.memory.data["entities"]:
            names = [n for n in [e.get("name", ""), *e.get("aliases", [])] if isinstance(n, str) and len(n) >= 3]
            if not names:
                continue
            pattern = re.compile(r"(?<!\w)(" + "|".join(re.escape(n) for n in names) + r")", re.I)
            hits: dict[str, int] = {}
            for c in items:
                found = len(pattern.findall(c["text"]))
                if found:
                    hits[c["path"]] = hits.get(c["path"], 0) + found
            if hits:
                result[e["id"]] = [p for p, _ in sorted(hits.items(), key=lambda x: -x[1])[:MAX_DOCS]]
        with self.memory.lock:
            self.memory.data["meta"]["entity_docs"] = result
            self.memory.data["meta"]["entity_docs_at"] = int(time.time())
        return result
