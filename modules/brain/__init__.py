"""«Мозг»: долговременная память Yakumo.

Yakumo сама выписывает из разговоров факты о пользователе, людей и места
(граф жизни), обещания, даты, настроение и конспекты бесед, а в каждом новом
чате видит это в подсказке. Раз в сутки «спит»: наводит порядок и утром сама
пишет первой. Ищет по смыслу через эмбеддинги Cloud.ru, помнит навыки
(процедуры по шагам), по согласию видит, какая программа открыта. Другим
модулям память доступна через ctx.memory. Хранится в <данные>/brain/.

Фоновый «разум» (mind.py) работает круглые сутки: бодрствует, дремлет и спит,
учится по документам Диска (knowledge.py), сдаёт себе ночные экзамены и
улучшает стиль (grow.py), выполняет длинные задачи в фоне (tasks.py) и пишет
себе инструменты в песочнице (usertools.py). Всё видно на вкладках «Разум» и «Рост».
"""

from __future__ import annotations

import json
import time

from . import learn
from .activity import Activity
from .grow import Growth
from .knowledge import Knowledge
from .learn import Learner
from .mind import Mind
from .semantic import Semantic
from .sleep import Sleep
from .store import ENTITY_TYPES, KINDS, SETTINGS, BrainError, Memory, today
from .tasks import Tasks
from .usertools import NAME as TOOL_NAME, ToolError, calc, check, sandbox

NAME = "Мозг"
VERSION = "3.0"

PROMPT_FACTS = 30     # самые важные факты — в каждую подсказку
PROMPT_RELEVANT = 10  # и ещё столько подходящих к последней реплике (по словам и по смыслу)
PROMPT_TALKS = 3      # последних бесед + столько же подходящих
PROMPT_LESSONS = 10
KNOWLEDGE_SCORE = 0.6  # кусочек документа попадает в подсказку сам, только если очень близок к вопросу

INTRO = {
    "ru": ("Твоя долговременная память — это ты помнишь сама из прошлых разговоров. Используй её к месту и "
           "естественно, не перечисляй без просьбы. Если память расходится со словами пользователя, верь пользователю. "
           "Инструменты памяти: «запомни» — memory_remember; «забудь» — memory_forget с id из списка; вспомнить то, "
           "чего нет ниже, — memory_recall; «откуда ты это знаешь?» — memory_source; обещания — memory_promise и "
           "memory_done; важные даты — memory_date; «запомни, как я делаю…» — memory_skill_save, а чтобы выполнить "
           "навык — memory_skill и дальше по шагам."),
    "en": ("Your long-term memory: things you remember yourself from past conversations. Use it naturally where it "
           "helps; don't list it unless asked. If memory disagrees with the user, trust the user. "
           "Memory tools: \"remember\" — memory_remember; \"forget\" — memory_forget with ids from the list; recall "
           "what is not below — memory_recall; \"how do you know?\" — memory_source; promises — memory_promise and "
           "memory_done; important dates — memory_date; \"remember how I do…\" — memory_skill_save, and to perform a "
           "skill call memory_skill and follow the steps."),
}
RULES = {
    "ru": ("Как думать: перед непростым ответом порассуждай про себя внутри <think>…</think> — пользователь этого не "
           "видит; на простые реплики отвечай сразу. Любые вычисления делай через calc, не в уме. Сведения из документов "
           "пользователя бери через knowledge_search и давай ссылку на файл. Если в чём-то не уверена, честно пометь это "
           "(«не уверена», «стоит проверить»), не выдумывай. Долгую работу (разобрать много файлов, собрать сводку) ставь "
           "в фон через background_task. Если не хватает умения, напиши себе инструмент через tool_propose: его включит "
           "пользователь."),
    "en": ("How to think: before a non-trivial answer reason privately inside <think>…</think> — the user doesn't see "
           "it; answer simple messages right away. Do any calculation with calc, never in your head. Take information "
           "from the user's documents with knowledge_search and link the file. If you're unsure, say so honestly "
           "(\"not sure\", \"worth checking\"), don't make things up. Put long work (many files, a summary) in the "
           "background with background_task. If you lack a skill, write yourself a tool with tool_propose; the user "
           "will enable it."),
}
GROW_HEAD = {
    "ru": {"lessons": "Твои уроки (ты вывела их сама из ошибок):", "style": "Твой стиль ответов (выработан тобой):",
           "notes": "Твои конспекты по темам пользователя:", "docs": "Из документов пользователя (ссылайся на файл):",
           "wishes": "Чему ты хочешь научиться:"},
    "en": {"lessons": "Your lessons (you derived them from mistakes):", "style": "Your answer style (you developed it):",
           "notes": "Your notes on the user's topics:", "docs": "From the user's documents (cite the file):",
           "wishes": "What you want to learn:"},
}
HEAD = {
    "ru": {"now": "Сейчас {now}.", "facts": "Что ты знаешь о пользователе:", "none": "Пока ничего.",
           "self": "Что ты помнишь о себе и ваших отношениях:", "talks": "Прошлые разговоры:",
           "promises": "Открытые обещания (id, кто, срок):", "user": "пользователь", "yakumo": "ты",
           "dates": "Ближайшие даты:", "skills": "Навыки пользователя (шаги — через memory_skill):",
           "memories": "В этот день раньше:", "months": "мес. назад",
           "mood": "В последние дни пользователю, похоже, непросто ({notes}). Будь бережнее; можешь мягко спросить, "
                   "как дела, но без нравоучений.",
           "screen": "Сейчас на экране у пользователя: {app} — «{title}».", "apps": "Сегодня за компьютером: {apps}.",
           "min": "мин", "today": "сегодня", "tomorrow": "завтра", "in": "через {n} дн."},
    "en": {"now": "Now is {now}.", "facts": "What you know about the user:", "none": "Nothing yet.",
           "self": "What you remember about yourself and your relationship:", "talks": "Past conversations:",
           "promises": "Open promises (id, who, due):", "user": "user", "yakumo": "you",
           "dates": "Upcoming dates:", "skills": "The user's skills (get steps with memory_skill):",
           "memories": "On this day before:", "months": "months ago",
           "mood": "The user seems to have a hard time lately ({notes}). Be gentle; you may softly ask how they are, "
                   "no lecturing.",
           "screen": "On the user's screen now: {app} — “{title}”.", "apps": "Time at the computer today: {apps}.",
           "min": "min", "today": "today", "tomorrow": "tomorrow", "in": "in {n} days"},
}


def _day(t: int) -> str:
    return time.strftime("%Y-%m-%d", time.localtime(t))


class MemoryAPI:
    """Память для других модулей: ctx.memory.remember(...), ctx.memory.recall(...)."""

    def __init__(self, memory: Memory, recall, module: str = ""):
        self._memory = memory
        self._recall = recall

    @property
    def enabled(self) -> bool:
        return self._memory.enabled

    def remember(self, text: str, kind: str = "other", about=None, files=None, source: str = "module") -> dict | None:
        """Запомнить факт. about — ["Аня"] или [{"name", "type", "relation"}], files — пути на Диске."""
        if not self._memory.enabled:
            return None
        return self._memory.add(text, kind, 2, source=source, about=about, files=files)

    def recall(self, query: str, limit: int = 10) -> dict:
        """Факты и разговоры по словам и по смыслу: {"facts": [...], "talks": [...], "skills": [...]}."""
        return self._recall(query, limit) if self._memory.enabled else {"facts": [], "talks": [], "skills": []}

    def facts(self) -> list[dict]:
        return self._memory.facts() if self._memory.enabled else []

    def forget(self, ids) -> int:
        return self._memory.delete(ids)

    def moved(self, old: str, new: str) -> int:
        """Сообщить, что файл на Диске переехал: ссылки в памяти обновятся."""
        return self._memory.moved(old, new)

    def say(self, text: str) -> dict:
        """Yakumo сама напишет это в чат при следующем открытии."""
        return self._memory.say(text)


def setup(ctx):
    memory = Memory(ctx.paths.data / "brain" / "memory.json")
    cloud = getattr(ctx, "cloud", None)
    lang = lambda: "en" if ctx.config.language == "en" else "ru"  # noqa: E731
    learner = Learner(memory, cloud, lang)
    mind = Mind(memory, cloud, learner)
    semantic = Semantic(ctx.paths.data / "brain" / "vectors.json", memory, cloud)
    knowledge = Knowledge(ctx.paths.data / "brain" / "knowledge.json", ctx.services, semantic, mind, memory)
    sleep = Sleep(memory, mind, lang, learner)
    growth = Growth(memory, mind, lang)
    activity = Activity(memory)
    tasks = Tasks(memory, mind, ctx.chat_tools, lang)

    def growing(fn):
        """Саморазвитие во сне — только если оно включено."""
        return lambda: fn() if memory.on("grow") else None

    def study():
        if memory.data["meta"].get("last_study") != today():
            memory.data["meta"]["last_study"] = today()
            knowledge.study(lang())

    mind.every("activity", "any", 60, activity.tick)
    mind.every("vectors", "any", 60, semantic.sync)
    mind.every("knowledge", "rest", 5 * 60, knowledge.sync)
    mind.every("sleep", "rest", 60, sleep.tick)
    mind.every("study", "asleep", 30 * 60, growing(study))
    mind.every("exam", "asleep", 30 * 60, growing(growth.exam))
    mind.every("style", "asleep", 30 * 60, growing(growth.evolve))
    learner.ticks = [mind.tick]
    learner.start()
    tasks.resume()
    ctx.on_stop(learner.stop)
    ctx.on_stop(tasks.stop)

    def recall(query: str, limit: int = 10) -> dict:
        """Поиск по словам плюс по смыслу; найденное по смыслу добавляется после совпадений по словам."""
        found = {**memory.search(query, limit), "notes": []}
        hits = semantic.search(query, limit) if memory.enabled else []
        if hits:
            index = {"f": {f["id"]: f for f in memory.data["facts"]}, "t": {t["id"]: t for t in memory.data["talks"]},
                     "s": {s["id"]: s for s in memory.data["skills"]}, "n": {n["id"]: n for n in memory.data["notes"]}}
            names = {"f": "facts", "t": "talks", "s": "skills", "n": "notes"}
            for key, _score in hits:
                kind, item_id = key.split(":", 1)
                item = index.get(kind, {}).get(item_id)
                if item is not None and all(x["id"] != item_id for x in found[names[kind]]):
                    found[names[kind]].append(item)
        return {k: v[:limit] for k, v in found.items()}

    ctx.memory = MemoryAPI(memory, recall)

    # --- Подсказка чата ---

    def context(history: list[dict], chat_id: str) -> str | None:
        if not memory.enabled:
            return None
        ln = lang()
        H = HEAD[ln]
        last = next((m["content"] for m in reversed(history) if m["role"] == "user"), "")
        names = {e["id"]: e for e in memory.data["entities"]}
        facts = [f for f in memory.facts() if not f.get("archived")]  # архив — только через поиск
        chosen = [f for f in facts if f["kind"] != "self"][:PROMPT_FACTS]
        own = [f for f in facts if f["kind"] == "self"][:10]
        found = recall(last, PROMPT_RELEVANT) if last else {"facts": [], "talks": [], "skills": [], "notes": []}
        seen = {f["id"] for f in chosen + own}
        chosen += [f for f in found["facts"] if f["id"] not in seen]

        def line(f):
            about = [names[i] for i in f.get("about", []) if i in names]
            tail = "; ".join(e["name"] + (f" — {e['relation']}" if e.get("relation") else "") for e in about)
            files = " ".join(f"[{p.split('/')[-1]}](disk:{p})" for p in f.get("files", []))
            return f"- [{f['id']}] {f['text']}" + (f" ({tail})" if tail else "") + (f" {files}" if files else "")

        lines = [INTRO[ln], "", RULES[ln], "", H["now"].format(now=time.strftime("%Y-%m-%d %H:%M, %A")), "", H["facts"]]
        lines += [line(f) for f in chosen] or [H["none"]]
        if own:
            lines += ["", H["self"], *(line(f) for f in own)]
        promises = memory.open_promises()[:10]
        if promises:
            lines += ["", H["promises"]]
            lines += [f"- [{p['id']}] {H[p['who']]}: {p['text']}" + (f" ({p['due']})" if p.get("due") else "")
                      for p in promises]
        dates = [x for x in memory.upcoming(7) if x["kind"] == "date"]
        if dates:
            when = lambda n: H["today"] if n == 0 else H["tomorrow"] if n == 1 else H["in"].format(n=n)  # noqa: E731
            lines += ["", H["dates"], *(f"- {x['date']} ({when(x['in_days'])}): {x['text']}" for x in dates)]
        skills = memory.data["skills"][:15]
        if skills:
            lines += ["", H["skills"], *(f"- {s['name']}" + (f": {s['when']}" if s.get("when") else "")
                                         for s in skills)]
        tid = learn.talk_id(history, chat_id)
        picked = [t for t in memory.talks() if t["id"] != tid][:PROMPT_TALKS]
        picked += [t for t in found["talks"] if t["id"] != tid and all(t["id"] != p["id"] for p in picked)]
        if picked:
            lines += ["", H["talks"], *(f"- {_day(t['updated'])} «{t['title']}»: {t['summary']}" for t in picked)]
        memories = memory.on_this_day()
        if memories:
            lines += ["", H["memories"], *(f"- {m['ago_months']} {H['months']}: {m['title']} — {m['summary']}"
                                           for m in memories[:2])]
        mood = memory.mood_trend() if memory.on("mood") else None
        if mood and mood["average"] <= -1:
            lines += ["", H["mood"].format(notes="; ".join(mood["notes"]) or "—")]
        if memory.on("activity"):
            now = activity.now()
            if now:
                lines += ["", H["screen"].format(app=now["app"], title=now["title"])]
            apps = activity.today()
            if apps:
                lines.append(H["apps"].format(apps=", ".join(f"{a} {m} {H['min']}" for a, m in apps)))
        G = GROW_HEAD[ln]
        lessons = sorted(memory.data["lessons"], key=lambda x: -x.get("seen", 1))[:PROMPT_LESSONS]
        if lessons:
            lines += ["", G["lessons"], *(f"- {x['text']}" for x in lessons)]
        style = memory.style()
        if style:
            lines += ["", G["style"], style["text"]]
        if found["notes"]:
            lines += ["", G["notes"], *(f"- {n['topic']}: {n['summary'][:800]}" for n in found["notes"][:2])]
        if last and knowledge.model:
            docs = [c for c in knowledge.search(last, 2) if c["score"] >= KNOWLEDGE_SCORE]
            if docs:
                lines += ["", G["docs"], *(f"- [{c['path'].split('/')[-1]}](disk:{c['path']}): {c['text'][:700]}"
                                           for c in docs)]
        wishes = sorted(memory.data["wishes"], key=lambda x: -x.get("count", 1))[:3]
        if wishes:
            lines += ["", G["wishes"], *(f"- {x['text']}" for x in wishes)]
        return "\n".join(lines)

    ctx.chat_context(context)
    ctx.on_chat(learner.heard)

    # --- Инструменты чата ---

    ru = lambda: lang() == "ru"  # noqa: E731

    def off():
        return {"error": "Память выключена в настройках" if ru() else "Memory is turned off in settings"}

    def last_quote(args):
        return args.get("quote") if isinstance(args.get("quote"), str) else None

    def remember(args):
        if not memory.enabled:
            return off()
        about = args.get("about")
        about = [about] if isinstance(about, str) else about if isinstance(about, list) else None
        file = args.get("file")
        fact = memory.add(str(args.get("text", "")), str(args.get("kind", "other")), 3, source="chat",
                          quote=last_quote(args), about=about, files=[file] if isinstance(file, str) else None)
        return {"ok": True, "id": fact["id"], "text": fact["text"]}

    def forget(args):
        ids = args.get("ids")
        ids = [ids] if isinstance(ids, str) else ids
        return {"forgotten": memory.delete(ids if isinstance(ids, list) else [])}

    def recall_tool(args):
        if not memory.enabled:
            return off()
        found = recall(str(args.get("query", "")), 10)
        names = {e["id"]: e["name"] for e in memory.data["entities"]}
        return {"facts": [{"id": f["id"], "text": f["text"], "about": [names[i] for i in f.get("about", []) if i in names],
                           "files": f.get("files", [])} for f in found["facts"]],
                "conversations": [{"date": _day(t["updated"]), "title": t["title"], "summary": t["summary"]}
                                  for t in found["talks"]],
                "skills": [s["name"] for s in found["skills"]]}

    def source(args):
        try:
            f = memory.fact(str(args.get("id", "")))
        except BrainError as exc:
            return {"error": str(exc)}
        talk = memory.talk(f["talk"]) if f.get("talk") else None
        how = {"auto": "из разговора", "chat": "ты попросила запомнить", "manual": "добавлено на странице «Память»"}
        return {"text": f["text"], "quote": f.get("quote"), "remembered": _day(f["created"]),
                "how": how.get(f.get("source"), f.get("source")) if ru() else f.get("source"),
                "conversation": {"title": talk["title"], "date": _day(talk["started"])} if talk else None}

    def promise(args):
        if not memory.enabled:
            return off()
        p = memory.promise(str(args.get("text", "")), str(args.get("who", "user")), args.get("due"))
        return {"ok": True, "id": p["id"], "due": p.get("due")}

    def done(args):
        ids = args.get("ids")
        return {"done": memory.promise_done(ids if isinstance(ids, (list, str)) else [])}

    def date(args):
        if not memory.enabled:
            return off()
        e = memory.event(str(args.get("text", "")), args.get("date"), args.get("yearly") is True)
        return {"ok": True, "id": e["id"]}

    def skill_save(args):
        if not memory.enabled:
            return off()
        s = memory.skill(str(args.get("name", "")), args.get("steps"), str(args.get("when", "")))
        return {"ok": True, "id": s["id"], "steps": len(s["steps"])}

    def skill(args):
        s = memory.find_skill(str(args.get("name", "")))
        if s is None:
            return {"error": "Такого навыка нет" if ru() else "No such skill",
                    "skills": [x["name"] for x in memory.data["skills"]]}
        return {"name": s["name"], "when": s.get("when"), "steps": s["steps"]}

    def fact_text(args) -> str:
        ids = args.get("ids")
        ids = [ids] if isinstance(ids, str) else ids if isinstance(ids, list) else []
        texts = [f["text"] for f in memory.facts() if f["id"] in ids]
        if len(texts) == 1:
            return f"«{texts[0][:60]}»" if ru() else f"“{texts[0][:60]}”"
        return f"{len(ids)} фактов" if ru() else f"{len(ids)} facts"

    def short(a, key, n=60):
        return str(a.get(key, ""))[:n]

    def calc_tool(args):
        try:
            return {"result": calc(str(args.get("expr", "")))}
        except (ValueError, TypeError, ZeroDivisionError, OverflowError, SyntaxError) as exc:
            return {"error": str(exc) or type(exc).__name__}

    def knowledge_tool(args):
        if not knowledge.disk:
            return {"error": "Диск не подключён" if ru() else "Drive is not connected"}
        if not knowledge.items:  # база ещё не собрана (разум не успел задремать) — собрать сейчас
            knowledge.sync()
        found = knowledge.search(str(args.get("query", "")), 6)
        return {"found": [{"link": f"[{c['path'].split('/')[-1]}](disk:{c['path']})", "text": c["text"],
                           "score": c["score"]} for c in found],
                "note": ("Отвечай по найденному и давай ссылку на файл; если не нашлось — так и скажи."
                         if ru() else "Answer from what was found and link the file; if nothing, say so.")}

    def task_tool(args):
        task = str(args.get("task", "")).strip()
        if not task:
            return {"error": "Нужно описание задачи" if ru() else "Task description required"}
        if not mind.can_think():
            return {"error": "Фоновые задачи сейчас недоступны: нет ключа Cloud.ru или исчерпан дневной бюджет"
                    if ru() else "Background tasks are unavailable: no Cloud.ru key or the daily budget is used up"}
        item = tasks.add(task, str(args.get("title", "")))
        return {"ok": True, "id": item["id"],
                "note": "Задача в очереди; результат придёт сообщением в чат, её видно на вкладке «Разум»."
                        if ru() else "Queued; the result will arrive as a chat message, see the Mind tab."}

    def register_tool(t) -> None:
        from yakumo.core.cloud import ChatTool

        name = "my_" + t["name"]
        example = json.dumps(t.get("example") or {}, ensure_ascii=False)[:200]
        ctx.chat_tools[name] = ChatTool(name, f"{t['description']} args: {example}",
                                        lambda args, code=t["code"]: sandbox(code, args), False,
                                        lambda _a, n=t["name"]: (f"Мой инструмент: {n}" if ru() else f"My tool: {n}"))

    def propose_tool(args):
        name = str(args.get("name", "")).strip().lower()
        description = " ".join(str(args.get("description", "")).split())[:300]
        code, example = args.get("code"), args.get("example") if isinstance(args.get("example"), dict) else {}
        if not TOOL_NAME.fullmatch(name) or not description:
            return {"error": "Нужны name (латиница, a-z0-9_) и description"}
        try:
            check(code)
        except ToolError as exc:
            return {"error": str(exc)}
        test = sandbox(code, example)
        with memory.lock:
            memory.data["user_tools"] = [t for t in memory.data["user_tools"] if t["name"] != name]
            ctx.chat_tools.pop("my_" + name, None)
        memory.add_item("user_tools", {"name": name, "description": description, "code": code, "example": example,
                                       "test": test, "status": "pending"}, 30)
        memory.say((f"Я написала себе инструмент «{name}»: {description}. Проверь код и включи его в «Память» → «Рост»."
                    if ru() else f"I wrote myself a tool “{name}”: {description}. Review the code and enable it in "
                    "Memory → Growth."), "tool")
        return {"ok": True, "test": test,
                "note": "Инструмент ждёт одобрения пользователя на странице «Память» → «Рост»."
                        if ru() else "The tool awaits the user's approval on the Memory → Growth page."}

    for t in memory.data["user_tools"]:
        if t.get("status") == "on":
            register_tool(t)

    tools = [
        ("memory_remember", 'запомнить факт о пользователе надолго (когда просят «запомни»). args: {"text": "кратко '
         'от третьего лица", "kind": "person|likes|work|other|self", "about": ["Аня"], "quote": "слова пользователя", '
         '"file": "путь/на/Диске (если про файл)"}', remember, False,
         lambda a: f"Запоминаю: {short(a, 'text')}" if ru() else f"Remembering: {short(a, 'text')}"),
        ("memory_recall", 'вспомнить по словам и по смыслу: факты, людей, прошлые разговоры, навыки. '
         'args: {"query": "слова"}', recall_tool, False,
         lambda a: f"Вспоминаю: {short(a, 'query')}" if ru() else f"Recalling: {short(a, 'query')}"),
        ("memory_source", 'откуда ты знаешь факт: цитата, дата, разговор. args: {"id": "id факта"}', source, False,
         lambda a: "Вспоминаю, откуда я это знаю" if ru() else "Checking where I learned it"),
        ("memory_promise", 'записать обещание. args: {"text": "что", "who": "user|yakumo", "due": "YYYY-MM-DD или '
         'null"}', promise, False,
         lambda a: f"Записываю обещание: {short(a, 'text')}" if ru() else f"Noting a promise: {short(a, 'text')}"),
        ("memory_done", 'отметить обещания выполненными. args: {"ids": ["id"]}', done, False,
         lambda a: "Отмечаю выполненным" if ru() else "Marking as done"),
        ("memory_date", 'запомнить важную дату. args: {"text": "день рождения Ани", "date": "YYYY-MM-DD", '
         '"yearly": true}', date, False,
         lambda a: f"Запоминаю дату: {short(a, 'text')}" if ru() else f"Remembering a date: {short(a, 'text')}"),
        ("memory_skill_save", 'запомнить процедуру пользователя по шагам («запомни, как я делаю отчёт»). '
         'args: {"name": "недельный отчёт", "when": "когда применять", "steps": ["шаг 1", "шаг 2"]}', skill_save, False,
         lambda a: f"Запоминаю навык: {short(a, 'name')}" if ru() else f"Learning a skill: {short(a, 'name')}"),
        ("memory_skill", 'получить шаги навыка, чтобы выполнить его. args: {"name": "название"}', skill, False,
         lambda a: f"Вспоминаю навык: {short(a, 'name')}" if ru() else f"Recalling skill: {short(a, 'name')}"),
        ("calc", 'точно посчитать выражение (всегда вместо счёта в уме): + - * / // % ** ^, проценты «15%», sqrt, '
         'log, sin, round, pi… args: {"expr": "2000 * 15% + sqrt(16)"}', calc_tool, False,
         lambda a: f"Считаю: {short(a, 'expr')}" if ru() else f"Calculating: {short(a, 'expr')}"),
        ("knowledge_search", 'найти ответ в документах пользователя на Диске (по смыслу, с цитатой и ссылкой). '
         'args: {"query": "вопрос"}', knowledge_tool, False,
         lambda a: f"Ищу в документах: {short(a, 'query')}" if ru() else f"Searching documents: {short(a, 'query')}"),
        ("background_task", 'поставить долгую задачу в фон (разобрать много файлов, собрать сводку); результат придёт '
         'сообщением. args: {"task": "что сделать, подробно", "title": "коротко"}', task_tool, False,
         lambda a: f"Ставлю в фон: {short(a, 'title') or short(a, 'task')}" if ru()
         else f"Queuing: {short(a, 'title') or short(a, 'task')}"),
        ("tool_propose", 'написать себе новый инструмент на Python, когда не хватает умения; включит пользователь. '
         'Код: функция run(args), только модули math, datetime, re, json, statistics, collections и т.п., без файлов и '
         'сети. args: {"name": "mortgage", "description": "что делает", "code": "def run(args): ...", '
         '"example": {"x": 1}}', propose_tool, False,
         lambda a: f"Пишу себе инструмент: {short(a, 'name')}" if ru() else f"Writing a tool: {short(a, 'name')}"),
        ("memory_forget", 'забыть факты (когда просят «забудь»). args: {"ids": ["id из памяти", ...]}', forget, True,
         lambda a: f"Забыть {fact_text(a)}" if ru() else f"Forget {fact_text(a)}"),
    ]
    for name, description, run, change, title in tools:
        ctx.chat_tool(name, description, run, change=change, title=title)

    # --- Страница «Память» ---

    def body(request) -> dict:
        data = request.read_json()
        if not isinstance(data, dict):
            raise BrainError("Ожидается объект")
        return data

    def state(_req=None):
        m = memory.data
        return {**{k: m[k] for k in SETTINGS},
                "cloud": bool(cloud and cloud.api_key()), "busy": learner.busy or bool(learner.pending) or sleep.busy,
                "error": learner.last_error, "kinds": list(KINDS), "entity_types": list(ENTITY_TYPES),
                "activity_available": activity.available(), "semantic": semantic.status(),
                "last_sleep": m["meta"].get("last_sleep"), "last_morning": m["meta"].get("last_morning"),
                "facts": memory.facts(), "talks": memory.talks(), "entities": memory.entities(),
                "promises": sorted(m["promises"], key=lambda p: (p.get("done", False), p.get("due") or "9999")),
                "events": sorted(m["events"], key=lambda e: e["date"][5:] if e.get("yearly") else e["date"]),
                "skills": m["skills"], "upcoming": memory.upcoming(7),
                "mind": mind.status(), "knowledge": knowledge.status(),
                "lessons": sorted(m["lessons"], key=lambda x: -x.get("seen", 1)),
                "wishes": sorted(m["wishes"], key=lambda x: -x.get("count", 1)),
                "suggestions": [x for x in m["suggestions"] if x.get("status") == "new"],
                "user_tools": m["user_tools"], "notes": sorted(m["notes"], key=lambda x: -x["created"]),
                "links": memory.links(), "style": {"versions": m["style"].get("versions", []),
                                                   "active": m["style"].get("active")},
                "mood_days": [{"date": k, "mood": round(sum(v["mood"]) / len(v["mood"]), 2)}
                         for k, v in sorted(m["days"].items())[-30:] if v.get("mood")]}

    def settings(req):
        d = body(req)
        memory.settings(**{k: d.get(k) for k in SETTINGS if k in d})
        return state()

    def save_fact(req):
        d = body(req)
        if d.get("id"):
            memory.edit(str(d["id"]), d.get("text"), d.get("kind"), d.get("pinned"), d.get("about"))
        else:
            memory.add(d.get("text"), str(d.get("kind") or "other"), 3, source="manual",
                       pinned=d.get("pinned") is True, about=d.get("about") if isinstance(d.get("about"), list) else None)
        return state()

    def save_item(req):
        d = body(req)
        kind = d.get("type")
        if kind == "promise":
            if d.get("id"):
                memory.promise_done([str(d["id"])], d.get("done") is True)
            else:
                memory.promise(d.get("text"), str(d.get("who") or "user"), d.get("due"))
        elif kind == "event":
            memory.event(d.get("text"), d.get("date"), d.get("yearly") is True)
        elif kind == "skill":
            memory.skill(d.get("name"), d.get("steps"), str(d.get("when") or ""))
        elif kind == "entity":
            memory.edit_entity(str(d.get("id")), d.get("name"), d.get("entity_type"), d.get("relation"))
        else:
            raise BrainError("Неизвестный тип записи")
        return state()

    def delete_item(req):
        d = body(req)
        kind = d.get("type")
        if kind == "entity":
            memory.delete_entities(d.get("ids"))
        elif kind in ("promises", "events", "skills", "lessons", "wishes", "notes", "links"):
            memory.delete_items(kind, d.get("ids"))
        else:
            raise BrainError("Неизвестный тип записи")
        return state()

    def clear(req):
        if body(req).get("all") is not True:
            raise BrainError("Нужно all: true")
        memory.clear()
        return state()

    def sleep_now(_req):
        return {"morning": sleep.run(), "state": state()}

    def set_mind(req):
        d = body(req)
        if "budget" in d:
            try:
                mind.set_limit(d["budget"])
            except ValueError as exc:
                raise BrainError(str(exc)) from exc
        return mind.status()

    def suggestion(req):
        d = body(req)
        item = memory.item("suggestions", str(d.get("id")))
        if not item:
            raise BrainError("Такого предложения нет")
        if d.get("accept") is True:
            memory.skill(d.get("name") or item["name"], item["steps"], item["name"])
        with memory.lock:
            item["status"] = "accepted" if d.get("accept") is True else "dismissed"
            memory.save()
        return state()

    def user_tool(req):
        d = body(req)
        t = memory.item("user_tools", str(d.get("id")))
        if not t:
            raise BrainError("Такого инструмента нет")
        action = d.get("action")
        if action not in ("on", "off", "delete"):
            raise BrainError("action: on, off или delete")
        with memory.lock:
            ctx.chat_tools.pop("my_" + t["name"], None)
            if action == "delete":
                memory.data["user_tools"].remove(t)
            else:
                t["status"] = action
                if action == "on":
                    register_tool(t)
            memory.save()
        return state()

    def style(req):
        version = body(req).get("id")
        memory.use_style(str(version) if version else None)
        return state()

    def grow_now(req):
        what = body(req).get("what")
        if what not in ("exam", "style", "study"):
            raise BrainError("what: exam, style или study")
        if not mind.can_think():
            raise BrainError("Нет ключа Cloud.ru или исчерпан дневной бюджет")
        if what == "exam":
            growth.exam(force=True)
        elif what == "style":
            growth.evolve(force=True)
        else:
            knowledge.sync()
            knowledge.study(lang())
        return state()

    routes = {
        "/api/brain": state,
        "/api/brain/export": lambda _req: memory.export(),
        "/api/brain/inbox": lambda _req: {"messages": memory.take_inbox() if memory.enabled else []},
        "POST /api/brain/settings": settings,
        "POST /api/brain/fact": save_fact,
        "POST /api/brain/item": save_item,
        "POST /api/brain/item/delete": delete_item,
        "POST /api/brain/forget": lambda r: (memory.delete(body(r).get("ids")), state())[1],
        "POST /api/brain/talks/delete": lambda r: (memory.delete_talks(body(r).get("ids")), state())[1],
        "POST /api/brain/clear": clear,
        "POST /api/brain/sleep": sleep_now,
        "/api/brain/mind": lambda _req: mind.status(),
        "POST /api/brain/mind": set_mind,
        "POST /api/brain/thought/cancel": lambda r: {"ok": mind.cancel(str(body(r).get("id"))), **mind.status()},
        "POST /api/brain/suggestion": suggestion,
        "POST /api/brain/tool": user_tool,
        "POST /api/brain/style": style,
        "POST /api/brain/grow": grow_now,
        "POST /api/brain/fact/restore": lambda r: (memory.touch([str(body(r).get("id"))]), state())[1],
        "POST /api/brain/import": lambda r: {**memory.import_(r.read_json()), "state": state()},
    }
    for path, handler in routes.items():
        ctx.route(path, handler)
    ctx.web("brain.css", "brain.js")
    ctx.status(lambda: {"facts": len(memory.data["facts"]), "talks": len(memory.data["talks"]),
                        "enabled": memory.enabled, "mode": mind.mode()})
    ctx.log.info("Память: %s фактов, %s бесед", len(memory.data["facts"]), len(memory.data["talks"]))
