"""«Улучшения»: список того, что стоит доработать в самой Yakumo.

Пункты появляются сами: из её неудач (желания «не смогла», ответы с 👎), из
ошибок программы в журнале и из её собственных идей, которые она придумывает,
пока простаивает. Каждый пункт оформлен как задача для разработчика: что не
так, как воспроизвести, что хочется, в каком модуле. Кнопка «Скопировать для
Claude» собирает готовый текст, который можно вставить в проект с Claude.
"""

from __future__ import annotations

import hashlib
import logging
import os
import threading
import time
import traceback

from .learn import parse
from .store import today

SOURCES = ("wish", "thumbs", "error", "idea", "manual")
STATUSES = ("new", "given", "done", "rejected")
PRIORITIES = ("high", "normal", "low")
MODULES = {"brain": "Мозг", "disk": "Диск", "update": "Обновление", "cloud": "Чат", "web": "Веб-версия",
           "core": "Ядро", "chat": "Чат"}
REFINE_PER_TICK = 3

REFINE = {
    "ru": """Ты — Yakumo, кицунэ-ассистент в программе Yakumo (Windows, Python, веб-интерфейс; модули: Чат, Мозг,
Диск, Обновление, Аватар, Настройки). Оформи пункт из списка «что улучшить в себе» как задачу для разработчика.

Источник: {source}
Сейчас записано:
{item}

Твой код, который может относиться к делу:
{code}

Ответь ТОЛЬКО объектом JSON:
{{"title": "коротко, до 80 символов", "problem": "что не так, 1-3 предложения",
"steps": "как воспроизвести, по шагам, или пусто", "want": "что должно получиться",
"module": "Чат|Мозг|Диск|Обновление|Аватар|Настройки|Ядро", "priority": "high|normal|low",
"fix": "где и что поправить в коде: файл, функция, суть правки — только если это видно из кода, иначе пусто"}}
Не выдумывай подробности, которых нет в записи или в коде.""",
    "en": """You are Yakumo, a kitsune assistant inside the Yakumo app (Windows, Python, web UI; modules: Chat,
Brain, Disk, Update, Avatar, Settings). Turn an item from your "what to improve in me" list into a developer task.

Source: {source}
Current record:
{item}

Your code that may be relevant:
{code}

Reply ONLY with a JSON object:
{{"title": "short, up to 80 chars", "problem": "what is wrong, 1-3 sentences",
"steps": "steps to reproduce, or empty", "want": "the desired result",
"module": "Chat|Brain|Disk|Update|Avatar|Settings|Core", "priority": "high|normal|low",
"fix": "where and what to change in the code: file, function, the gist — only if the code shows it, else empty"}}
Do not invent details that are not in the record or the code.""",
}

IDEAS = {
    "ru": """Ты — Yakumo, кицунэ-ассистент в программе Yakumo (Windows, Python, веб-интерфейс; модули: Чат, Мозг,
Диск, Обновление, Аватар, Настройки). Ты простаиваешь и думаешь, чего тебе самой не хватает, чтобы лучше помогать
своему пользователю.

Чему ты хочешь научиться:
{wishes}
Твои уроки:
{lessons}
Последние изменения в тебе:
{versions}
Уже в списке улучшений (не повторяй):
{existing}

Предложи 0-2 новые функции для программы, которые реально помогут. Ответь ТОЛЬКО объектом JSON:
{{"ideas": [{{"title": "до 80 символов", "problem": "чего не хватает сейчас", "want": "как это должно работать",
"module": "Чат|Мозг|Диск|Обновление|Аватар|Настройки|Ядро", "priority": "high|normal|low"}}]}}""",
    "en": """You are Yakumo, a kitsune assistant inside the Yakumo app (Windows, Python, web UI; modules: Chat,
Brain, Disk, Update, Avatar, Settings). You are idle and thinking about what you lack to help your user better.

What you want to learn:
{wishes}
Your lessons:
{lessons}
Recent changes in you:
{versions}
Already in the improvement list (don't repeat):
{existing}

Suggest 0-2 new features for the app that would really help. Reply ONLY with a JSON object:
{{"ideas": [{{"title": "up to 80 chars", "problem": "what is missing now", "want": "how it should work",
"module": "Chat|Brain|Disk|Update|Avatar|Settings|Core", "priority": "high|normal|low"}}]}}""",
}

COPY = {
    "ru": {"head": "Задачи для Yakumo (репозиторий Aspksa/Yakumo, Windows). Их собрала сама Yakumo.",
           "version": "Установленная версия: {v}.", "module": "Модуль", "source": "Источник", "times": "Повторов",
           "priority": "Важность", "problem": "Что не так", "steps": "Как воспроизвести", "want": "Что хочется",
           "fix": "Где поправить",
           "detail": "Подробности", "sources": {"wish": "Yakumo не смогла", "thumbs": "ответ с 👎",
                                                 "error": "ошибка программы", "idea": "идея Yakumo", "manual": "вы"},
           "priorities": {"high": "важно", "normal": "обычно", "low": "мелочь"}},
    "en": {"head": "Tasks for Yakumo (repository Aspksa/Yakumo, Windows). Collected by Yakumo herself.",
           "version": "Installed version: {v}.", "module": "Module", "source": "Source", "times": "Times",
           "priority": "Priority", "problem": "What is wrong", "steps": "Steps to reproduce", "want": "Desired result",
           "fix": "Where to fix",
           "detail": "Details", "sources": {"wish": "Yakumo couldn't do it", "thumbs": "answer with 👎",
                                            "error": "program error", "idea": "Yakumo's idea", "manual": "you"},
           "priorities": {"high": "important", "normal": "normal", "low": "minor"}},
}


def module_of(logger: str) -> str:
    """yakumo.modules.disk → «Диск»; ядро и чат — по имени файла."""
    parts = logger.split(".")
    name = parts[2] if len(parts) > 2 and parts[1] == "modules" else parts[-1]
    return MODULES.get(name, name.capitalize() if name else "Ядро")


class ErrorCatcher(logging.Handler):
    """Сбои из журнала Yakumo → пункты «починить». Повтор того же места не плодит новый пункт."""

    def __init__(self, improvements, app: str = ""):
        super().__init__(logging.ERROR)
        self.improvements = improvements
        self.app = os.path.normcase(str(app or ""))
        self.local = threading.local()

    def _where(self, tb) -> str:
        frames = traceback.extract_tb(tb) if tb else []
        for frame in reversed(frames):
            path = os.path.normcase(frame.filename)
            if not self.app or path.startswith(self.app):
                rel = os.path.relpath(frame.filename, self.app) if self.app else os.path.basename(frame.filename)
                return f"{rel.replace(os.sep, '/')}:{frame.lineno} ({frame.name})"
        if frames:  # сбой вне папки программы (библиотека) — хотя бы последнее место
            return f"{os.path.basename(frames[-1].filename)}:{frames[-1].lineno} ({frames[-1].name})"
        return ""

    def emit(self, record: logging.LogRecord) -> None:
        if getattr(self.local, "busy", False) or not record.name.startswith("yakumo"):
            return
        self.local.busy = True  # запись в память сама может что-то записать в журнал
        try:
            exc = record.exc_info[1] if record.exc_info else None
            where = self._where(record.exc_info[2]) if record.exc_info else ""
            kind = type(exc).__name__ if exc else ""
            message = record.getMessage()[:300]
            key = "error:" + hashlib.sha1(f"{record.name}|{kind}|{where or message}".encode()).hexdigest()[:16]
            detail = (f"{kind}: {str(exc)[:300]}" if exc else "") + (f"\n{where}" if where else "")
            self.improvements.add({
                "key": key, "source": "error", "module": module_of(record.name),
                "title": f"{message[:80]}" + (f" — {kind}" if kind else ""), "problem": message,
                "detail": detail.strip(), "steps": time.strftime("Случилось %Y-%m-%d %H:%M", time.localtime(record.created))})
        except Exception:  # noqa: BLE001 — журнал не должен падать из-за списка улучшений
            pass
        finally:
            self.local.busy = False


class Improvements:
    def __init__(self, memory, mind, lang, version=lambda: "", code=None):
        self.memory = memory
        self.mind = mind
        self.lang = lang
        self.version = version
        self.code = code

    def add(self, item: dict) -> dict | None:
        return self.memory.improvement(item)

    # --- Источники ---

    def scan(self) -> int:
        """Желания «не смогла» → пункты. Счётчик повторов берётся из желания."""
        added = 0
        dropped = set(self.memory.data["meta"].get("improvements_dropped", []))
        for wish in list(self.memory.data["wishes"]):
            if "wish:" + wish["id"] in dropped:
                continue
            added += bool(self.add({"key": "wish:" + wish["id"], "source": "wish", "title": wish["text"][:80],
                                    "problem": wish["text"], "count": wish.get("count", 1)}))
        return added

    def thumbs(self, question: str, answer: str, note: str) -> None:
        q = " ".join(question.split())
        self.add({"key": "thumbs:" + hashlib.sha1(q.encode()).hexdigest()[:16], "source": "thumbs",
                  "module": "Чат", "title": (note or q)[:80] or "👎",
                  "problem": note or ("Ответ не понравился пользователю" if self.lang() == "ru" else "The user disliked the answer"),
                  "steps": q[:500], "detail": answer[:800]})

    # --- Оформление задачей (в простое, с бюджетом) ---

    def refine(self) -> int:
        done = 0
        for item in [x for x in self.memory.data["improvements"] if not x.get("refined") and x["source"] != "manual"]:
            if done >= REFINE_PER_TICK or not self.mind.can_think():
                break
            lang = self.lang()
            record = "\n".join(f"{k}: {item[k]}" for k in ("title", "problem", "steps", "want", "detail", "module")
                               if item.get(k))
            try:
                data = parse(self.mind.complete([{"role": "user", "content": REFINE[lang].format(
                    source=COPY[lang]["sources"].get(item["source"], item["source"]), item=record,
                    code=self.related_code(item) or "—")}], max_tokens=700))
            finally:
                self.memory.edit_improvement(item["id"], refined=True)
            self.memory.edit_improvement(item["id"], **{k: data[k] for k in ("title", "problem", "steps", "want",
                                                                               "module", "priority", "fix")
                                                         if isinstance(data.get(k), str) and data[k].strip()})
            done += 1
        return done

    def related_code(self, item: dict, limit: int = 6000) -> str:
        """Код к пункту: место сбоя из подробностей ошибки, иначе похожее по смыслу."""
        if self.code is None:
            return ""
        parts = []
        for line in (item.get("detail") or "").splitlines():
            found = self.code.around(line)
            if found:
                parts.append(f"[{found['path']}:{found['start']}-{found['end']}]\n{found['text']}")
                break
        if not parts:
            query = " ".join(x for x in (item.get("title"), item.get("problem"), item.get("module")) if x)
            parts = [f"[{c['path']}:{c['start']}-{c['end']}]\n{c['text']}" for c in self.code.search(query, 2)]
        return "\n\n".join(parts)[:limit]

    # --- Свои идеи ---

    def ideas(self, force: bool = False) -> int:
        meta = self.memory.data["meta"]
        if not force and meta.get("last_ideas") == today():
            return 0
        if not self.mind.can_think():
            return 0
        lang = self.lang()
        meta["last_ideas"] = today()
        thought = self.mind.thought("ideas", "Думаю, чего мне не хватает" if lang == "ru" else "Thinking what I lack")
        lines = lambda items: "\n".join(f"- {x}" for x in items) or "—"  # noqa: E731
        try:
            data = parse(self.mind.complete([{"role": "user", "content": IDEAS[lang].format(
                wishes=lines(w["text"] for w in self.memory.data["wishes"][:15]),
                lessons=lines(x["text"] for x in self.memory.data["lessons"][:15]),
                versions=lines(c for v in self.memory.versions()[:3] for c in v.get("changes", [])[:5]),
                existing=lines(x["title"] for x in self.memory.data["improvements"][-40:]))}], max_tokens=700))
        except Exception:
            self.mind.finish(thought, "failed")
            raise
        added = []
        for idea in (data.get("ideas") or [])[:2] if isinstance(data.get("ideas"), list) else []:
            if not isinstance(idea, dict) or not isinstance(idea.get("title"), str) or not idea["title"].strip():
                continue
            item = self.add({"key": "idea:" + hashlib.sha1(idea["title"].lower().encode()).hexdigest()[:16],
                             "source": "idea", "refined": True,
                             **{k: idea[k] for k in ("title", "problem", "want", "module", "priority")
                                if isinstance(idea.get(k), str)}})
            if item:
                added.append(item["title"])
        self.mind.finish(thought, "done", "\n".join(f"- {t}" for t in added) or "—")
        return len(added)

    # --- Для Claude ---

    def markdown(self, ids=None) -> str:
        T = COPY[self.lang()]
        items = [x for x in self.memory.improvements() if (x["id"] in ids if ids else x["status"] == "new")]
        version = self.version()
        out = [T["head"]] + ([T["version"].format(v=version)] if version else [])
        for n, x in enumerate(items, 1):
            out += ["", f"## {n}. {x['title']}",
                    " · ".join(p for p in (f"{T['module']}: {x['module']}" if x.get("module") else "",
                                           f"{T['source']}: {T['sources'].get(x['source'], x['source'])}",
                                           f"{T['priority']}: {T['priorities'].get(x.get('priority'), '')}"
                                           if x.get("priority") else "",
                                           f"{T['times']}: {x['count']}" if x.get("count", 1) > 1 else "") if p)]
            for key in ("problem", "steps", "want", "fix"):
                if x.get(key):
                    out.append(f"**{T[key]}:** {x[key]}")
            if x.get("detail"):
                out += [f"**{T['detail']}:**", "```", x["detail"], "```"]
        return "\n".join(out)
