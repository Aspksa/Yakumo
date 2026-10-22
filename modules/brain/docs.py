"""Мозг и Диск: Yakumo сама читает новые документы и помнит, что в них важного.

Положили на Диск договор или квитанцию — Yakumo в фоне его прочитает: люди,
суммы, номера договоров уходят в память фактами со ссылкой на файл, сроки и
даты — в напоминания, а если есть что-то важное, она сама напишет в чат.
Новые файлы, брошенные в корень Диска (или в «Загрузки»), она предложит
разложить по папкам — сам перенос выполняется только по кнопке в чате.

Здесь же — пересказ целой папки для чата (folder_brief).
Что уже прочитано, хранится в brain/docs.json (по отпечатку текста, поэтому
переименование или перенос файла не заставляют читать его заново).
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
from pathlib import Path

from .learn import parse
from .store import KINDS, today

log = logging.getLogger("yakumo.modules.brain")

PER_SCAN = 3          # документов за один заход (остальные — в следующий)
MIN_TEXT = 80         # короче — читать нечего
DOC_CHARS = 6000      # сколько текста документа показывать модели
MAX_FACTS = 5
INBOX = {"", "загрузки", "downloads", "входящие", "inbox", "разное", "новое"}
BRIEF_DOCS = 40
BRIEF_CHARS = 45000

PROMPT = {
    "ru": """Ты — Yakumo. Пользователь положил на свой Диск документ «{path}». Прочитай его и реши, что запомнить.
Сегодня {today}. Папки на Диске: {folders}.

Текст документа:
{text}

Ответь ТОЛЬКО объектом JSON:
{{"summary": "что это за документ, одно предложение",
 "facts": [{{"text": "факт о пользователе и его делах из документа", "kind": "person|likes|work|other",
            "about": [{{"name": "Иван Петров", "type": "person|place|project|org|thing", "relation": "арендодатель"}}]}}],
 "dates": [{{"text": "что за дата или срок", "date": "YYYY-MM-DD", "yearly": false}}],
 "message": "короткое сообщение пользователю, если в документе есть срок, сумма к оплате или что-то важное (или null)",
 "folder": "в какую папку его положить (лучше из существующих, можно новую), или null"}}

facts — 0-5 полезных сведений: стороны, суммы, номера договоров и счетов, адреса, условия. Пиши кратко от третьего
лица и с названием документа («По договору аренды платит 35 000 ₽ в месяц»). Никогда не записывай пароли, коды,
номера карт, паспортов и полисов. dates — только будущие и важные даты и сроки. message — 1-2 предложения, по делу.""",
    "en": """You are Yakumo. The user put the document “{path}” on their Drive. Read it and decide what to remember.
Today is {today}. Folders on the Drive: {folders}.

Document text:
{text}

Reply ONLY with a JSON object:
{{"summary": "what this document is, one sentence",
 "facts": [{{"text": "a fact about the user and their affairs from the document", "kind": "person|likes|work|other",
            "about": [{{"name": "John Smith", "type": "person|place|project|org|thing", "relation": "landlord"}}]}}],
 "dates": [{{"text": "what the date or deadline is", "date": "YYYY-MM-DD", "yearly": false}}],
 "message": "a short message to the user if the document has a deadline, an amount to pay or something important (or null)",
 "folder": "which folder it belongs in (prefer existing ones, a new one is fine), or null"}}

facts — 0-5 useful items: parties, amounts, contract and invoice numbers, addresses, terms. Briefly, third person, naming
the document. Never record passwords, codes, card, passport or policy numbers. dates — only future, important dates and
deadlines. message — 1-2 sentences, to the point.""",
}

BRIEF = {
    "ru": """Ты — Yakumo. Пользователь спрашивает о папке «{folder}» на своём Диске ({count} документов).
{question}

Документы (путь и начало текста):
{docs}

Перескажи папку: что в ней, главное по каждому важному документу, сроки, суммы и что требует внимания. Если есть
вопрос — ответь на него. Ссылайся на файлы так: [имя](disk:путь). Только по документам, без выдумок.""",
    "en": """You are Yakumo. The user asks about the folder “{folder}” on their Drive ({count} documents).
{question}

Documents (path and the beginning of the text):
{docs}

Summarise the folder: what's in it, the key points of each important document, deadlines, amounts and what needs
attention. If there is a question, answer it. Link files like [name](disk:path). Only from the documents.""",
}


def fingerprint(text: str) -> str:
    return hashlib.sha1(" ".join(text.split())[:200_000].encode("utf-8")).hexdigest()[:16]


class Docs:
    def __init__(self, path: Path, memory, mind, services: dict, cloud, language):
        self.path = path
        self.memory = memory
        self.mind = mind
        self.services = services
        self.cloud = cloud
        self.language = language
        self.lock = threading.Lock()
        self.seen: dict[str, str] = {}   # путь -> отпечаток текста
        self.sort: list[dict] = []       # предложения разложить: {"path", "to", "why"}
        self.baseline = False            # первый заход только запоминает, что уже лежало на Диске
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            self.seen, self.sort, self.baseline = data["seen"], data.get("sort", []), data.get("baseline", True)
        except (OSError, ValueError, KeyError, TypeError):
            pass

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"seen": self.seen, "sort": self.sort, "baseline": self.baseline},
                                  ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, self.path)

    @property
    def disk(self):
        return self.services.get("disk")

    def _lang(self) -> str:
        return "en" if self.language() == "en" else "ru"

    # --- Новые документы ---

    def scan(self, limit: int = PER_SCAN) -> int:
        """Прочитать новые документы (не больше limit за раз). Возвращает, сколько прочитано."""
        if not self.disk or not self.memory.on("docs"):
            return 0
        with self.lock:
            docs = {p: (fingerprint(t), t) for p, _m, t in self.disk.documents()}
            known = set(self.seen.values())
            if not self.baseline:
                self.seen = {p: h for p, (h, _t) in docs.items()}
                self.baseline = True
                self._save()
                return 0
            self.seen = {p: h for p, h in self.seen.items() if p in docs}
            self.sort = [s for s in self.sort if s["path"] in docs]
            fresh = []
            for p, (h, t) in docs.items():
                if self.seen.get(p) == h:
                    continue
                if h in known or len(t.strip()) < MIN_TEXT:  # перенесли/переименовали или читать нечего
                    self.seen[p] = h
                else:
                    fresh.append((p, h, t))
            read = 0
            for p, h, t in fresh[:limit]:
                if not self.mind.can_think():
                    break
                try:
                    self.read(p, t)
                finally:
                    self.seen[p] = h  # не перечитывать по кругу, даже если модель ответила не так
                read += 1
            self._save()
            return read

    def _folders(self) -> list[str]:
        return sorted({p.split("/")[0] for p in self.seen if "/" in p})[:40]

    def read(self, path: str, text: str) -> dict:
        lang, name = self._lang(), path.split("/")[-1]
        item = self.mind.thought("doc", f"Читаю новый документ: {name}" if lang == "ru" else f"Reading a new document: {name}")
        try:
            data = parse(self.mind.complete([{"role": "user", "content": PROMPT[lang].format(
                path=path, today=today(), folders=", ".join(self._folders()) or "—", text=text[:DOC_CHARS])}],
                max_tokens=900))
        except Exception:
            self.mind.finish(item, "failed")
            raise
        facts = 0
        for f in (data.get("facts") or [])[:MAX_FACTS]:
            if isinstance(f, dict) and isinstance(f.get("text"), str) and f["text"].strip():
                about = f.get("about") if isinstance(f.get("about"), list) else None
                self.memory.add(f["text"], f.get("kind") if f.get("kind") in KINDS else "other", 2, source="doc",
                                about=about, files=[path])
                facts += 1
        for d in data.get("dates") or []:
            if isinstance(d, dict) and isinstance(d.get("text"), str) and d["text"].strip():
                try:
                    self.memory.event(f"{d['text']} ({name})", d.get("date"), d.get("yearly") is True)
                except Exception:  # noqa: BLE001 — модель не смогла назвать точную дату
                    pass
        message = data.get("message")
        if isinstance(message, str) and message.strip():
            self.memory.say(f"📄 [{name}](disk:{path}) — {message.strip()}", "doc")
        folder = data.get("folder")
        parent = path.rsplit("/", 1)[0] if "/" in path else ""
        if (isinstance(folder, str) and folder.strip().strip("/") and parent.lower() in INBOX
                and folder.strip().strip("/").lower() != parent.lower()):
            self.sort = [s for s in self.sort if s["path"] != path]
            self.sort.append({"path": path, "to": folder.strip().strip("/")[:120],
                              "why": str(data.get("summary") or "")[:200]})
            self._suggest_sort()
        summary = data.get("summary") if isinstance(data.get("summary"), str) else ""
        self.mind.finish(item, "done", summary + (f"\nФактов: {facts}" if lang == "ru" else f"\nFacts: {facts}"))
        return data

    def _suggest_sort(self) -> None:
        meta = self.memory.data["meta"]
        if meta.get("sort_said") == today():
            return
        meta["sort_said"] = today()
        n = len(self.sort)
        self.memory.say((f"Новые файлы можно разложить по папкам ({n}). Скажи «разложи новые файлы» — я покажу план, "
                         "а переложу по кнопке." if self._lang() == "ru" else
                         f"New files can be sorted into folders ({n}). Say “sort the new files” — I'll show a plan "
                         "and move them when you press the button."), "sort")

    def sort_plan(self) -> dict:
        return {"files": list(self.sort),
                "note": ("Покажи пользователю план и предложи перенос через disk_move (по папкам), "
                         "он выполнится по кнопке." if self._lang() == "ru" else
                         "Show the plan and propose disk_move per folder; it runs when the user presses the button.")}

    # --- Пересказ папки ---

    def brief(self, folder: str, question: str = "") -> dict:
        if not self.disk:
            return {"error": "Диск не подключён"}
        if not self.cloud or not self.cloud.api_key():
            return {"error": "Нет ключа Cloud.ru"}
        folder = folder.replace("\\", "/").strip("/")
        docs = [(p, t) for p, _m, t in self.disk.documents()
                if (not folder or p == folder or p.startswith(folder + "/")) and t.strip()]
        if not docs:
            return {"error": "В этой папке нет документов с текстом", "folder": folder}
        docs.sort(key=lambda d: d[0])
        per = max(400, min(3000, BRIEF_CHARS // min(len(docs), BRIEF_DOCS)))
        listing = "\n\n".join(f"[{p}]\n{t[:per]}" for p, t in docs[:BRIEF_DOCS])
        lang = self._lang()
        q = (f"Вопрос: {question}" if lang == "ru" else f"Question: {question}") if question.strip() else ""
        text = self.cloud.complete([{"role": "user", "content": BRIEF[lang].format(
            folder=folder or "/", count=len(docs), question=q, docs=listing)}], max_tokens=1800)
        return {"folder": folder or "/", "documents": len(docs), "read": min(len(docs), BRIEF_DOCS),
                "brief": text.strip()}
