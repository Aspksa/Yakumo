"""«Мозг»: долговременная память Yakumo.

Yakumo сама выписывает из разговоров факты о пользователе и конспекты бесед,
а в каждом новом чате видит их в подсказке. В чате можно сказать «запомни…»,
«забудь…» или «помнишь, мы говорили про…». На странице «Память» всё это видно
и редактируется. Хранится в <данные>/brain/memory.json.
"""

from __future__ import annotations

import time

from . import learn
from .learn import Learner
from .store import KINDS, BrainError, Memory

NAME = "Мозг"
VERSION = "1.0"

PROMPT_FACTS = 30     # самые важные факты — в каждую подсказку
PROMPT_RELEVANT = 10  # и ещё столько подходящих к последней реплике
PROMPT_TALKS = 3      # последних бесед + столько же подходящих по словам

INTRO = {
    "ru": ("Твоя долговременная память — это ты помнишь сама из прошлых разговоров. Используй её к месту и "
           "естественно, не перечисляй без просьбы. Если память расходится со словами пользователя, верь пользователю. "
           "Если просят запомнить — вызови memory_remember, забыть — memory_forget с id из списка, а если нужно "
           "вспомнить давний разговор или факт, которого нет ниже, — memory_recall."),
    "en": ("Your long-term memory: things you remember yourself from past conversations. Use it naturally where it "
           "helps; don't list it unless asked. If memory disagrees with the user, trust the user. "
           "When asked to remember something call memory_remember, to forget — memory_forget with ids from the list, "
           "and to recall an old conversation or a fact not listed below — memory_recall."),
}
HEAD = {"ru": ("Что ты знаешь о пользователе:", "Прошлые разговоры:", "Пока ничего."),
        "en": ("What you know about the user:", "Past conversations:", "Nothing yet.")}


def _day(t: int) -> str:
    return time.strftime("%Y-%m-%d", time.localtime(t))


def setup(ctx):
    memory = Memory(ctx.paths.data / "brain" / "memory.json")
    cloud = getattr(ctx, "cloud", None)
    lang = lambda: "en" if ctx.config.language == "en" else "ru"  # noqa: E731
    learner = Learner(memory, cloud, lang)
    learner.start()
    ctx.on_stop(learner.stop)

    # --- Подсказка чата ---

    def context(history: list[dict], chat_id: str) -> str | None:
        if not memory.enabled:
            return None
        ln = lang()
        last = next((m["content"] for m in reversed(history) if m["role"] == "user"), "")
        facts = memory.facts()
        chosen = facts[:PROMPT_FACTS]
        if last:
            seen = {f["id"] for f in chosen}
            found = [f for f in memory.search(last, PROMPT_RELEVANT)["facts"] if f["id"] not in seen]
            chosen += found
        tid = learn.talk_id(history, chat_id)
        talks = [t for t in memory.talks() if t["id"] != tid]
        picked = talks[:PROMPT_TALKS]
        if last:
            picked += [t for t in memory.search(last, PROMPT_TALKS)["talks"]
                       if t["id"] != tid and t not in picked]
        lines = [INTRO[ln], "", HEAD[ln][0]]
        lines += [f"- [{f['id']}] {f['text']}" for f in chosen] or [HEAD[ln][2]]
        if picked:
            lines += ["", HEAD[ln][1]]
            lines += [f"- {_day(t['updated'])} «{t['title']}»: {t['summary']}" for t in picked]
        return "\n".join(lines)

    ctx.chat_context(context)
    ctx.on_chat(learner.heard)

    # --- Инструменты чата ---

    def off():
        return {"error": "Память выключена в настройках" if lang() == "ru" else "Memory is turned off in settings"}

    def remember(args):
        if not memory.enabled:
            return off()
        fact = memory.add(str(args.get("text", "")), str(args.get("kind", "other")), 3, source="chat")
        return {"ok": True, "id": fact["id"], "text": fact["text"]}

    def forget(args):
        ids = args.get("ids")
        ids = [ids] if isinstance(ids, str) else ids
        return {"forgotten": memory.delete(ids if isinstance(ids, list) else [])}

    def recall(args):
        if not memory.enabled:
            return off()
        found = memory.search(str(args.get("query", "")), 10)
        return {"facts": [{"id": f["id"], "text": f["text"]} for f in found["facts"]],
                "conversations": [{"date": _day(t["updated"]), "title": t["title"], "summary": t["summary"]}
                                  for t in found["talks"]]}

    def fact_text(args) -> str:
        ids = args.get("ids")
        ids = [ids] if isinstance(ids, str) else ids if isinstance(ids, list) else []
        texts = [f["text"] for f in memory.facts() if f["id"] in ids]
        if len(texts) == 1:
            return f"«{texts[0][:60]}»" if lang() == "ru" else f"“{texts[0][:60]}”"
        return f"{len(ids)} фактов" if lang() == "ru" else f"{len(ids)} facts"

    ru = lambda: lang() == "ru"  # noqa: E731
    ctx.chat_tool("memory_remember", 'запомнить факт о пользователе надолго (когда просят «запомни»). '
                  'args: {"text": "кратко от третьего лица", "kind": "person|likes|work|other"}', remember,
                  title=lambda a: (f"Запоминаю: {str(a.get('text', ''))[:60]}" if ru()
                                   else f"Remembering: {str(a.get('text', ''))[:60]}"))
    ctx.chat_tool("memory_recall", 'вспомнить по словам: факты и прошлые разговоры. args: {"query": "слова"}',
                  recall, title=lambda a: (f"Вспоминаю: {a.get('query', '')}" if ru()
                                           else f"Recalling: {a.get('query', '')}"))
    ctx.chat_tool("memory_forget", 'забыть факты (когда просят «забудь»). args: {"ids": ["id из памяти", ...]}',
                  forget, change=True,
                  title=lambda a: f"Забыть {fact_text(a)}" if ru() else f"Forget {fact_text(a)}")

    # --- Страница «Память» ---

    def body(request) -> dict:
        data = request.read_json()
        if not isinstance(data, dict):
            raise BrainError("Ожидается объект")
        return data

    def state(_req=None):
        return {"enabled": memory.data["enabled"], "auto": memory.data["auto"],
                "cloud": bool(cloud and cloud.api_key()), "busy": learner.busy or bool(learner.pending),
                "error": learner.last_error, "kinds": list(KINDS),
                "facts": memory.facts(), "talks": memory.talks()}

    def settings(req):
        d = body(req)
        memory.settings(d.get("enabled"), d.get("auto"))
        return state()

    def save_fact(req):
        d = body(req)
        if d.get("id"):
            memory.edit(str(d["id"]), d.get("text"), d.get("kind"), d.get("pinned"))
        else:
            memory.add(d.get("text"), str(d.get("kind") or "other"), 3, source="manual",
                       pinned=d.get("pinned") is True)
        return state()

    def clear(req):
        if body(req).get("all") is not True:
            raise BrainError("Нужно all: true")
        memory.clear()
        return state()

    routes = {
        "/api/brain": state,
        "/api/brain/export": lambda _req: memory.export(),
        "POST /api/brain/settings": settings,
        "POST /api/brain/fact": save_fact,
        "POST /api/brain/forget": lambda r: (memory.delete(body(r).get("ids")), state())[1],
        "POST /api/brain/talks/delete": lambda r: (memory.delete_talks(body(r).get("ids")), state())[1],
        "POST /api/brain/clear": clear,
        "POST /api/brain/import": lambda r: {**memory.import_(r.read_json()), "state": state()},
    }
    for path, handler in routes.items():
        ctx.route(path, handler)
    ctx.web("brain.css", "brain.js")
    ctx.status(lambda: {"facts": len(memory.data["facts"]), "talks": len(memory.data["talks"]),
                        "enabled": memory.enabled})
    ctx.log.info("Память: %s фактов, %s бесед", len(memory.data["facts"]), len(memory.data["talks"]))

