"""Живой порядок на Диске: правила раскладки, которые кицунэ выводит сама.

Кицунэ смотрит, как вы раскладываете файлы. Если вы три раза положили чеки в
«Финансы/2026», она предложит правило «чеки → Финансы/{год}». Правило можно
создать и самому (на вкладке «Порядок» или в чате). Включённые правила
срабатывают, когда файл попадает в корень Диска или во «Входящие»/«Загрузки»:
файл сам переезжает в нужную папку.

Если вы переложили файл, который положила кицунэ, это урок: после двух
одинаковых поправок правило меняет папку, а урок уходит в «Мозг».

Всё хранится в ``<Диск>/.yakumo/organizer.json`` с относительными путями.
"""

from __future__ import annotations

import json
import os
import re
import threading
import time
import uuid
from collections import Counter

from .store import Disk, DiskError, check_name, kind_of, norm, query_words, split_rel

INBOX = {"", "загрузки", "downloads", "входящие", "inbox", "разное", "новое", "сканы", "scans"}
NOTICE = 3            # столько одинаковых переносов — и кицунэ предлагает правило
SHARE = 0.6           # доля переносов в папку, у которых есть общий признак
WINDOW = 120 * 86400  # переносы за последние 120 дней
FIX = 2               # столько одинаковых поправок — и правило меняет папку
PLACED_FOR = 30 * 86400
TEXT_HEAD = 3000      # начало текста, в котором ищутся слова правила
MAX_MOVES, MAX_LESSONS, MAX_RULES = 400, 40, 100
YEAR = re.compile(r"^(19|20)\d{2}$")

# Типы документов, которые кицунэ узнаёт по имени и началу текста.
DOC_TYPES = {
    "чек": ["чек", "кассов", "receipt"], "квитанция": ["квитанц"], "договор": ["договор", "contract"],
    "счёт": ["счет на оплату", "счет №", "счет-фактур", "invoice"], "акт": ["акт выполнен", "акт приема", "акт сверки"],
    "справка": ["справк"], "выписка": ["выписк", "statement"], "полис": ["полис", "страхов"],
    "билет": ["билет", "boarding", "посадочн", "ticket"], "резюме": ["резюме", "curriculum", "resume"],
    "накладная": ["накладн"], "отчёт": ["отчет", "report"], "заявление": ["заявлени"],
    "доверенность": ["доверенност"], "рецепт": ["рецепт", "назначени врач"], "анализы": ["анализ кров", "результат анализ"],
}
GENERIC = {"img", "dsc", "dscn", "pxl", "vid", "photo", "image", "scan", "скан", "file", "файл", "doc", "document",
           "документ", "новый", "new", "копия", "copy", "untitled", "screenshot", "снимок", "экрана", "whatsapp",
           "telegram", "фото", "видео", "video", "final", "итог", "версия", "version", "без", "имени"}
KIND_NAMES = {"ru": {"image": "фото", "video": "видео", "audio": "музыка", "pdf": "PDF", "text": "тексты",
                     "doc": "документы Word", "sheet": "таблицы", "slides": "презентации", "archive": "архивы",
                     "book": "книги", "app": "программы"},
              "en": {"image": "photos", "video": "videos", "audio": "music", "pdf": "PDFs", "text": "text files",
                     "doc": "Word documents", "sheet": "spreadsheets", "slides": "presentations",
                     "archive": "archives", "book": "books", "app": "programs"}}


def parent_of(rel: str) -> str:
    return rel.rsplit("/", 1)[0] if "/" in rel else ""


def in_inbox(rel: str) -> bool:
    return norm(parent_of(rel)) in INBOX


def doc_types(text: str) -> list[str]:
    low = norm(text)
    return [t for t, marks in DOC_TYPES.items() if any(m in low for m in marks)]


def name_words(name: str) -> list[str]:
    stem = name.rsplit(".", 1)[0] if "." in name else name
    return [w for w in query_words(re.sub(r"[\d_]+", " ", stem)) if len(w) >= 3 and w not in GENERIC]


def features(name: str, text: str) -> list[str]:
    """Признаки файла: тип документа (по имени и тексту) и слова имени."""
    types = doc_types(f"{name}\n{text[:TEXT_HEAD]}")
    return [*(f"type:{t}" for t in types), *(f"word:{w}" for w in name_words(name) if w not in types)]


def template(folder: str, when: float | None = None) -> str:
    """«Финансы/2026» -> «Финансы/{год}», если год совпадает с годом переноса."""
    year = time.strftime("%Y", time.localtime(when or time.time()))
    return "/".join("{год}" if p == year else p for p in split_rel(folder))


def expand(to: str, when: float | None = None) -> str:
    t = time.localtime(when or time.time())
    return (to.replace("{год}", time.strftime("%Y", t)).replace("{year}", time.strftime("%Y", t))
            .replace("{месяц}", time.strftime("%m", t)).replace("{month}", time.strftime("%m", t)))


def _clean_list(value, limit: int = 10) -> list[str]:
    if isinstance(value, str):
        value = re.split(r"[,;]", value)
    if not isinstance(value, list):
        return []
    out = []
    for v in value:
        if isinstance(v, str) and v.strip() and v.strip().lower() not in out:
            out.append(v.strip().lower()[:40])
    return out[:limit]


class Organizer:
    def __init__(self, disk: Disk, text_of, memory=lambda: None, language=lambda: "ru"):
        self.disk = disk
        self.text_of = text_of      # путь -> текст документа (из умного поиска)
        self.memory = memory        # -> ctx.memory или None (модуль «Мозг» может быть выключен)
        self.language = language
        self.path = disk.meta / "organizer.json"
        self.lock = disk.lock  # общий замок с Диском: правила переносят файлы, а хуки Диска зовут нас
        self.local = threading.local()  # local.own: переносы, которые делает сама кицунэ
        self.data = {"rules": [], "proposals": [], "declined": [], "moves": [], "placed": {}, "lessons": []}
        try:
            saved = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(saved, dict):
                self.data.update({k: v for k, v in saved.items() if k in self.data and isinstance(v, type(self.data[k]))})
        except (OSError, ValueError):
            pass
        disk.on_move.append(self.moved)

    def _save(self) -> None:
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, self.path)

    def _ru(self) -> bool:
        return self.language() != "en"

    def _text(self, rel: str) -> str:
        try:
            return self.text_of(rel) or ""
        except (OSError, DiskError):
            return ""

    # --- Правила ---

    def label(self, rule: dict) -> str:
        parts = [w for w in rule.get("words", [])]
        kinds = KIND_NAMES["ru" if self._ru() else "en"]
        parts += [kinds.get(k, k) for k in rule.get("kinds", [])]
        return ", ".join(parts) or ("все файлы" if self._ru() else "all files")

    def view(self) -> dict:
        with self.lock:
            now = time.time()
            return {"rules": [{**r, "label": r.get("name") or self.label(r), "target": expand(r["to"])}
                              for r in self.data["rules"]],
                    "proposals": [{**p, "label": self.label(p), "target": expand(p["to"])}
                                  for p in self.data["proposals"]],
                    "lessons": list(reversed(self.data["lessons"][-15:])),
                    "placed": sum(1 for p in self.data["placed"].values() if now - p["at"] < PLACED_FOR)}

    def save_rule(self, data: dict, source: str = "user") -> dict:
        if not isinstance(data, dict):
            raise DiskError("Ожидается правило")
        words, kinds = _clean_list(data.get("words")), [k for k in _clean_list(data.get("kinds")) if k in KIND_NAMES["ru"]]
        if not words and not kinds:
            raise DiskError("Нужны слова или тип файлов")
        to = "/".join(check_name(p) if "{" not in p else p.strip() for p in split_rel(str(data.get("to", ""))))
        if not to:
            raise DiskError("Нужна папка, куда класть")
        check_name(expand(to).split("/")[-1])
        rule = {"words": words, "kinds": kinds, "to": to, "tell": str(data.get("tell") or "")[:200].strip(),
                "name": str(data.get("name") or "")[:60].strip(), "on": data.get("on", True) is not False}
        with self.lock:
            old = next((r for r in self.data["rules"] if r["id"] == data.get("id")), None)
            if old:
                old.update(rule)
                rule = old
            else:
                if len(self.data["rules"]) >= MAX_RULES:
                    raise DiskError("Слишком много правил")
                rule = {"id": uuid.uuid4().hex[:10], **rule, "source": source, "made": int(time.time()),
                        "hits": 0, "fixes": []}
                self.data["rules"].append(rule)
            self._save()
            return rule

    def delete_rule(self, rule_id: str) -> bool:
        with self.lock:
            before = len(self.data["rules"])
            self.data["rules"] = [r for r in self.data["rules"] if r["id"] != rule_id]
            self._save()
            return len(self.data["rules"]) != before

    def answer(self, proposal_id: str, accept: bool) -> dict | None:
        """Ответ на предложение кицунэ: включить правило или больше не предлагать."""
        with self.lock:
            p = next((x for x in self.data["proposals"] if x["id"] == proposal_id), None)
            if not p:
                raise DiskError("Предложение уже неактуально")
            self.data["proposals"].remove(p)
            if not accept:
                self.data["declined"] = [*self.data["declined"][-99:], p["sig"]]
                self._save()
                return None
            rule = self.save_rule({"words": p["words"], "kinds": p["kinds"], "to": p["to"]}, source="learned")
            self._lesson(f"Правило «{self.label(rule)} → {rule['to']}» я вывела сама из ваших переносов."
                         if self._ru() else f"I worked out the rule “{self.label(rule)} → {rule['to']}” from your moves.")
            return rule

    def match(self, rule: dict, rel: str, text: str | None = None) -> bool:
        """Подходит ли файл: нужный тип (если задан) и хотя бы одно из слов в имени или начале текста."""
        name = rel.split("/")[-1]
        if rule.get("kinds") and kind_of(name) not in rule["kinds"]:
            return False
        phrases = [query_words(w) or [norm(w)] for w in rule.get("words") or []]
        if not phrases:
            return True

        def found(hay: str) -> bool:
            return any(all(re.search(r"(?<!\w)" + re.escape(s), hay) for s in stems) for stems in phrases)

        if found(norm(name.replace("_", " "))):
            return True
        text = self._text(rel) if text is None else text
        return found(norm(text[:TEXT_HEAD]))

    def rule_for(self, rel: str) -> dict | None:
        text = None
        for rule in self.data["rules"]:
            if not rule.get("on"):
                continue
            if rule.get("words") and text is None:
                text = self._text(rel)
            if self.match(rule, rel, text):
                return rule
        return None

    def place(self, rel: str) -> dict | None:
        """Новый файл во «Входящих»: если есть правило, переложить. Возвращает, куда положен."""
        if not in_inbox(rel) or not self.data["rules"]:
            return None
        with self.lock:
            rule = self.rule_for(rel)
            if not rule:
                return None
            return self._put(rel, expand(rule["to"]), rule)

    def _put(self, rel: str, folder: str, rule: dict | None) -> dict | None:
        if parent_of(rel) == folder:
            return None
        self.local.own = True
        try:
            self.disk.makedirs(folder)
            entry = self.disk.move([rel], folder)[0]
        finally:
            self.local.own = False
        if rule:
            rule["hits"] = rule.get("hits", 0) + 1
            rule["last"] = int(time.time())
            self.data["placed"][entry["path"]] = {"rule": rule["id"], "to": folder, "from": parent_of(rel),
                                                 "at": int(time.time())}
            if rule.get("tell"):
                memory = self.memory()
                if memory:
                    memory.say(f"🦊 [{entry['name']}](disk:{entry['path']}) → «{folder}». {rule['tell']}")
        self._prune()
        self._save()
        return {"path": entry["path"], "name": entry["name"], "to": folder,
                "rule": rule["id"] if rule else None, "label": self.label(rule) if rule else None}

    def plan(self) -> list[dict]:
        """Что разложить прямо сейчас: файлы во «Входящих», к которым подходит правило."""
        out = []
        roots = [""] + [e["path"] for e in self.disk.list("")["items"] if e["dir"] and norm(e["name"]) in INBOX]
        for folder in roots:
            for e in self.disk.list(folder)["items"]:
                if e["dir"]:
                    continue
                rule = self.rule_for(e["path"])
                if rule and expand(rule["to"]) != folder:
                    out.append({"path": e["path"], "name": e["name"], "kind": e["kind"], "to": expand(rule["to"]),
                                "rule": rule["id"], "label": rule.get("name") or self.label(rule)})
        return out[:300]

    def apply(self, moves: list) -> list[dict]:
        if not isinstance(moves, list):
            raise DiskError("Ожидается список")
        done = []
        with self.lock:
            rules = {r["id"]: r for r in self.data["rules"]}
            for m in moves[:300]:
                if not isinstance(m, dict) or not isinstance(m.get("path"), str) or not isinstance(m.get("to"), str):
                    continue
                try:
                    placed = self._put(m["path"], "/".join(split_rel(m["to"])), rules.get(m.get("rule")))
                except (OSError, DiskError):
                    continue
                if placed:
                    done.append(placed)
        return done

    # --- Наблюдение и уроки ---

    def moved(self, old: str, new: str) -> None:
        """Хук Диска: перенос или переименование. Свои переносы кицунэ не считает уроками."""
        if getattr(self.local, "own", False):
            return
        with self.lock:
            placed = self.data["placed"]
            for key in [k for k in placed if k.startswith(old + "/")]:  # переименовали папку
                placed[new + key[len(old):]] = placed.pop(key)
            p = placed.pop(old, None)
            if parent_of(old) == parent_of(new):  # переименование, не перенос
                if p:
                    placed[new] = p
                self._save()
                return
            try:
                if self.disk.path(new).is_dir():
                    self._save()
                    return
            except (OSError, DiskError):
                return
            if p:
                self._fix(p, new)
            self._observe(old, new)
            self._save()

    def _observe(self, old: str, new: str) -> None:
        name, to = new.split("/")[-1], parent_of(new)
        self.data["moves"].append({"name": name, "kind": kind_of(name), "from": parent_of(old), "to": to,
                                   "feats": features(name, self._text(new)), "at": int(time.time())})
        del self.data["moves"][:-MAX_MOVES]
        self._notice(to)

    def _notice(self, to: str) -> None:
        """Повторяющиеся переносы в одну папку -> предложение правила."""
        now = time.time()
        moves = [m for m in self.data["moves"] if m["to"] == to and now - m["at"] < WINDOW]
        if len(moves) < NOTICE or not to:
            return
        words, kinds = [], []
        counts = Counter(f for m in moves for f in set(m["feats"]))
        best = max(counts.items(), key=lambda kv: (kv[1], kv[0].startswith("type:")), default=None)
        if best and best[1] >= NOTICE and best[1] / len(moves) >= SHARE:
            words = [best[0].split(":", 1)[1]]
            examples = [m["name"] for m in moves if best[0] in m["feats"]]
        else:
            kind, n = Counter(m["kind"] for m in moves).most_common(1)[0]
            if n < NOTICE or n / len(moves) < SHARE or kind == "file":
                return
            kinds = [kind]
            examples = [m["name"] for m in moves if m["kind"] == kind]
        target = template(to)
        sig = f"{','.join(words)}|{','.join(kinds)}|{target.lower()}"
        known = {p["sig"] for p in self.data["proposals"]} | set(self.data["declined"])
        if sig in known:
            return
        for r in self.data["rules"]:
            if r["words"] == words and r["kinds"] == kinds:
                return  # такое правило уже есть (возможно, с другой папкой — её правят поправки)
        p = {"id": uuid.uuid4().hex[:10], "sig": sig, "words": words, "kinds": kinds, "to": target,
             "count": len(examples), "examples": examples[-3:], "made": int(now)}
        self.data["proposals"] = [*self.data["proposals"][-9:], p]
        memory = self.memory()
        if memory:
            memory.say(f"🦊 Я заметила: {self.label(p)} вы кладёте в «{to}». Включить правило? Диск → «Порядок»."
                       if self._ru() else f"🦊 I noticed you put {self.label(p)} into “{to}”. Turn it into a rule? "
                       "Drive → Order.")

    def _fix(self, placed: dict, new: str) -> None:
        """Пользователь переложил файл, который положила кицунэ: учимся."""
        rule = next((r for r in self.data["rules"] if r["id"] == placed["rule"]), None)
        to = parent_of(new)
        if not rule or to == placed["to"]:
            return
        name = new.split("/")[-1]
        rule["fixes"] = [*rule.get("fixes", [])[-4:], {"to": template(to), "at": int(time.time())}]
        last = [f["to"] for f in rule["fixes"][-FIX:]]
        if len(last) == FIX and len(set(last)) == 1 and last[0] != rule["to"]:
            old_to, rule["to"], rule["fixes"] = rule["to"], last[0], []
            self._lesson(f"Поняла: {self.label(rule)} кладу не в «{old_to}», а в «{rule['to']}»."
                         if self._ru() else f"Got it: {self.label(rule)} go to “{rule['to']}”, not “{old_to}”.",
                         chat=True)
        else:
            self._lesson(f"Вы переложили «{name}» из «{placed['to']}» в «{to or '/'}». Если повторится, поменяю правило."
                         if self._ru() else f"You moved “{name}” from “{placed['to']}” to “{to or '/'}”. "
                         "If it happens again, I'll change the rule.")

    def _lesson(self, text: str, chat: bool = False) -> None:
        self.data["lessons"] = [*self.data["lessons"][-(MAX_LESSONS - 1):], {"text": text, "at": int(time.time())}]
        memory = self.memory()
        if memory and chat:
            if hasattr(memory, "lesson"):
                memory.lesson(text)
            memory.say("🦊 " + text)

    def _prune(self) -> None:
        now = time.time()
        self.data["placed"] = {k: v for k, v in self.data["placed"].items() if now - v["at"] < PLACED_FOR}
