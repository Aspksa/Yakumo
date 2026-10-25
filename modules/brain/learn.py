"""Как Yakumo учится: после разговора модель выписывает факты, людей и места, обещания,
даты, настроение, желания («чему мне стоит научиться») и обновляет конспект беседы.

Ещё Yakumo замечает повторяющиеся цепочки инструментов: если одна и та же
последовательность встретилась CHAIN_REPEATS раза, она предлагает сохранить её как навык.

Работает в фоне и не задерживает ответы: беседа разбирается, когда в ней
наступила пауза (DELAY секунд без новых реплик). Тот же поток раз в минуту
выполняет другие фоновые дела «Памяти» (сон, программы на экране).
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import logging
import re
import threading
import time

from .store import KINDS, Memory

log = logging.getLogger("yakumo.modules.brain")

DELAY = 20            # секунд тишины в беседе, после которых её можно разбирать
TICK = 60             # раз во столько секунд — прочие фоновые дела
LAST_MESSAGES = 12    # сколько последних реплик показывать модели
MESSAGE_CHARS = 1500  # одна реплика
KNOWN_FACTS = 80      # сколько уже известных фактов показывать, чтобы не было повторов
CHAIN_REPEATS = 3     # после стольких повторов цепочки инструментов — предложить навык
MAX_SAMPLES = 30      # примеров «вопрос — ответ» для ночного экзамена и улучшения стиля
WEEKDAYS = {"ru": ("понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"),
            "en": ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")}

PROMPT = {
    "ru": """Ты — память ассистента Yakumo. Прочитай отрывок разговора пользователя с Yakumo и обнови память.
Сегодня {today} ({weekday}).

Уже известные факты (id: текст):
{facts}

Открытые обещания (id: кто: текст):
{promises}

Прежний конспект этой беседы: {summary}

Разговор:
{dialog}

Ответь ТОЛЬКО объектом JSON без пояснений:
{{"new": [{{"text": "факт", "kind": "person|likes|work|other|self", "importance": 1|2|3,
          "quote": "дословные слова пользователя, откуда факт",
          "about": [{{"name": "Аня", "type": "person|pet|place|project|org|thing", "relation": "сестра"}}],
          "files": ["путь/на/Диске, если факт про файл"]}}],
 "seen": ["id известных фактов, которые снова упоминались"],
 "outdated": ["id известных фактов, которые пользователь опроверг или которые устарели"],
 "promises": [{{"text": "что обещано", "who": "user|yakumo", "due": "YYYY-MM-DD или null"}}],
 "done": ["id открытых обещаний, которые выполнены"],
 "dates": [{{"text": "день рождения сестры Ани", "date": "YYYY-MM-DD", "yearly": true}}],
 "mood": -2..2 или null,
 "mood_note": "пара слов, почему (или пусто)",
 "wish": "чему Yakumo стоит научиться, раз сейчас не смогла помочь (или null)",
 "lesson": "правило для Yakumo, если пользователь её поправил или был недоволен ответом (или null)",
 "traces": [{"kind": "cause|decision|project_error|progress", "text": "что произошло/решили",
             "reason": "почему", "result": "результат/что осталось", "status": "open|done",
             "date": "YYYY-MM-DD или null", "files": ["путь из disk:ссылки"],
             "about": [{"name": "сущность", "type": "person|pet|place|project|org|thing", "relation": ""}]}],
 "title": "короткое название беседы, 2-6 слов",
 "summary": "конспект всей беседы в 1-4 предложениях: о чём говорили, что решили, что осталось сделать"}}

Правила для new: только устойчивые сведения о самом пользователе из ЕГО слов (имя, близкие, питомцы, город, работа,
проекты, привычки, вкусы, планы). Не записывай разовые вопросы, общие знания, пароли, ключи, номера карт и документов.
Пиши кратко от третьего лица («Пользователя зовут Аня», «Любит зелёный чай»).
kind: person — о человеке и близких, likes — вкусы и привычки, work — дела, учёба, проекты и планы, other — прочее,
self — о самой Yakumo и ваших отношениях (как пользователь её называет, общие шутки, любимые темы бесед).
importance: 3 — важно помнить всегда (имя, близкие, просьбы «запомни»), 2 — полезно, 1 — мелочь.
about — люди, питомцы, места, проекты, о которых факт (relation — кем приходится пользователю). Пользователя туда не пиши.
files — только пути, которые явно есть в разговоре в ссылках вида (disk:путь).
Не повторяй известные факты: если факт уточняется, верни новый текст в new и старый id в outdated.
promises — явные обещания: «сделаю отчёт к пятнице» (who=user) или «Yakumo, напомни…», «я напомню» (who=yakumo).
Относительные даты («в пятницу», «завтра») переводи в YYYY-MM-DD от сегодняшней.
dates — даты, которые стоит помнить: дни рождения (yearly=true), встречи, экзамены, поездки.
mood — настроение пользователя в этой беседе: -2 очень плохо, 0 обычно, 2 отлично; null, если непонятно.
wish — только если Yakumo явно не смогла что-то сделать или не знала («не умею», «нет доступа»): кратко, что уметь.
lesson — короткое правило на будущее от лица Yakumo («Отвечать короче, без списков»), только если была поправка.
traces — структурная история только из явно сказанного в разговоре:
cause — пользователь явно назвал причину («из-за», «потому что», «причина»);
decision — явно выбрали/решили/отказались от варианта, reason — почему;
project_error — явно описана ошибка/поломка проекта, result — исправление, если оно известно;
progress — что хотели сделать, что сделали и что осталось; status=open, пока прямо не сказано, что завершено.
Не додумывай причинность и не превращай предположение Yakumo в факт. Если не уверен — не добавляй trace.
Если нового нет, верни пустые списки.""",
    "en": """You are the memory of the Yakumo assistant. Read the conversation excerpt and update the memory.
Today is {today} ({weekday}).

Known facts (id: text):
{facts}

Open promises (id: who: text):
{promises}

Previous summary of this conversation: {summary}

Conversation:
{dialog}

Reply ONLY with a JSON object, no comments:
{{"new": [{{"text": "fact", "kind": "person|likes|work|other|self", "importance": 1|2|3,
          "quote": "the user's exact words the fact comes from",
          "about": [{{"name": "Ann", "type": "person|pet|place|project|org|thing", "relation": "sister"}}],
          "files": ["path/on/Drive if the fact is about a file"]}}],
 "seen": ["ids of known facts mentioned again"],
 "outdated": ["ids of known facts the user contradicted or that are out of date"],
 "promises": [{{"text": "what was promised", "who": "user|yakumo", "due": "YYYY-MM-DD or null"}}],
 "done": ["ids of open promises that are done"],
 "dates": [{{"text": "sister Ann's birthday", "date": "YYYY-MM-DD", "yearly": true}}],
 "mood": -2..2 or null,
 "mood_note": "a few words why (or empty)",
 "wish": "what Yakumo should learn because she couldn't help just now (or null)",
 "lesson": "a rule for Yakumo if the user corrected her or disliked the answer (or null)",
 "traces": [{"kind": "cause|decision|project_error|progress", "text": "what happened/was decided",
             "reason": "why", "result": "outcome/what remains", "status": "open|done",
             "date": "YYYY-MM-DD or null", "files": ["path from disk: link"],
             "about": [{"name": "entity", "type": "person|pet|place|project|org|thing", "relation": ""}]}],
 "title": "short conversation title, 2-6 words",
 "summary": "summary of the whole conversation in 1-4 sentences: topics, decisions, what is left to do"}}

Rules for new: only lasting facts about the user from THEIR words (name, family, pets, city, job, projects, habits,
tastes, plans). Never record one-off questions, general knowledge, passwords, keys, card or document numbers.
Write briefly in third person ("The user's name is Ann", "Likes green tea").
kind: person — the person and family, likes — tastes and habits, work — work, study, projects and plans, other,
self — about Yakumo herself and your relationship (what the user calls her, shared jokes, favourite topics).
importance: 3 — always remember (name, family, "remember this" requests), 2 — useful, 1 — minor.
about — people, pets, places, projects the fact is about (relation — who they are to the user). Never the user.
files — only paths explicitly present in the conversation as (disk:path) links.
Do not repeat known facts: if a fact changes, put the new text in new and the old id in outdated.
promises — explicit promises: "I'll finish the report by Friday" (who=user) or "Yakumo, remind me…" (who=yakumo).
Convert relative dates ("on Friday", "tomorrow") to YYYY-MM-DD from today.
dates — dates worth remembering: birthdays (yearly=true), meetings, exams, trips.
mood — the user's mood in this conversation: -2 very bad, 0 normal, 2 great; null if unclear.
wish — only if Yakumo clearly couldn't do or didn't know something ("I can't", "no access"): briefly, what to learn.
lesson — a short rule for the future in Yakumo's voice ("Answer shorter, no lists"), only after a correction.
traces — structured history only when explicitly supported by the conversation:
cause — the user explicitly states why something happened; decision — an explicit choice/rejection and why;
project_error — an explicit project failure/bug and, when known, its fix; progress — wanted/done/remaining work,
status=open until the user explicitly says it is complete. Never invent causality or turn Yakumo's guess into a fact.
If nothing is new, return empty lists.""",
}


def talk_id(history: list[dict], chat_id: str) -> str:
    """Id беседы из браузера, а если его нет — по первой реплике пользователя."""
    if chat_id:
        return chat_id
    first = next((m["content"] for m in history if m["role"] == "user"), "")
    return "h" + hashlib.sha1(first[:500].encode("utf-8")).hexdigest()[:12]


def parse(text: str) -> dict:
    """JSON из ответа модели, даже если она обернула его в ``` или добавила слова."""
    text = re.sub(r"<think>.*?(</think>|$)", "", text, flags=re.S)
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("нет JSON")
    data = json.loads(text[start:end + 1])
    if not isinstance(data, dict):
        raise ValueError("ожидался объект")
    return data


def _list(data: dict, key: str) -> list:
    value = data.get(key)
    return value if isinstance(value, list) else []


class Learner:
    def __init__(self, memory: Memory, cloud, language):
        self.memory = memory
        self.cloud = cloud
        self.language = language                  # () -> "ru" | "en"
        self.pending: dict[str, tuple] = {}       # беседа -> (реплики, когда пришла последняя)
        self.ticks: list = []                     # прочие фоновые дела, раз в TICK секунд
        self.last_chat = time.time()              # когда пользователь последний раз писал (запуск — как реплика)
        self.wake = threading.Event()
        self.stopping = False
        self.busy = False
        self.last_error: str | None = None
        self.thread: threading.Thread | None = None

    # --- Очередь ---

    def heard(self, history: list[dict], answer: str, chat_id: str, tools=()) -> None:
        """Ответ в чате готов: запомнить беседу, разобрать её чуть позже."""
        self.last_chat = time.time()
        if not self.memory.auto or not any(m["role"] == "user" for m in history):
            return
        tid = talk_id(history, chat_id)
        self.pending[tid] = ([*history, {"role": "assistant", "content": answer}], time.time())
        question = next(m["content"] for m in reversed(history) if m["role"] == "user")
        self.memory.add_item("samples", {"question": question[:MESSAGE_CHARS], "answer": answer[:MESSAGE_CHARS]},
                             MAX_SAMPLES)
        self.notice_chain(question, tools)
        self.wake.set()

    def notice_chain(self, question: str, tools) -> None:
        """Одна и та же цепочка инструментов в который раз — предложить сохранить её как навык."""
        steps = [(name, args) for name, args in tools or () if name != "?" and not name.startswith("memory_skill")]
        if len(steps) < 2:
            return
        names = [name for name, _args in steps]
        signature = " → ".join(names)
        if self.memory.chain(signature, names, question) != CHAIN_REPEATS:
            return
        if any(s.get("signature") == signature for s in self.memory.data["suggestions"]):
            return
        ru = self.language() != "en"
        detail = [f"{name} {json.dumps(args, ensure_ascii=False)[:80]}" for name, args in steps]
        self.memory.add_item("suggestions", {"signature": signature, "name": question[:60], "steps": detail,
                                             "status": "new"})
        self.memory.say(
            f"Я заметила, что уже {CHAIN_REPEATS} раза делаю одно и то же: {signature}. Сохранить это как навык? "
            "Загляни в «Память» → «Рост»." if ru else
            f"I've noticed I've done the same thing {CHAIN_REPEATS} times: {signature}. Save it as a skill? "
            "See Memory → Growth.", "suggestion")

    def start(self) -> None:
        self.thread = threading.Thread(target=self._run, name="brain", daemon=True)
        self.thread.start()

    def stop(self) -> None:
        self.stopping = True
        self.wake.set()
        thread = self.thread
        if thread is not None and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout=5)

    def _run(self) -> None:
        next_tick = time.time() + 5
        while not self.stopping:
            ready = [tid for tid, (_h, at) in list(self.pending.items()) if time.time() - at >= DELAY]
            for tid in ready:
                if self.stopping:
                    return
                history, _at = self.pending.pop(tid)
                self.learn(tid, history)
            if time.time() >= next_tick:
                next_tick = time.time() + TICK
                for tick in self.ticks:
                    if self.stopping:
                        return
                    try:
                        tick()
                    except Exception:  # noqa: BLE001 — фоновое дело не должно останавливать память
                        log.exception("Память: ошибка фоновой задачи")
            waits = [DELAY - (time.time() - at) for _h, at in list(self.pending.values())]
            self.wake.wait(max(0.2, min([*waits, next_tick - time.time()])))
            self.wake.clear()

    # --- Разбор беседы ---

    def learn(self, tid: str, history: list[dict]) -> bool:
        if not self.cloud or not self.cloud.api_key():
            return False
        lang = "en" if self.language() == "en" else "ru"
        facts = [f for f in self.memory.facts() if not f.get("archived")][:KNOWN_FACTS]
        promises = self.memory.open_promises()
        talk = self.memory.talk(tid)
        names = {"user": "Пользователь" if lang == "ru" else "User", "assistant": "Yakumo"}
        dialog = "\n\n".join(f"{names[m['role']]}: {m['content'][:MESSAGE_CHARS]}" for m in history[-LAST_MESSAGES:])
        now = dt.date.today()
        prompt = PROMPT[lang].format(
            today=now.isoformat(), weekday=WEEKDAYS[lang][now.weekday()],
            facts="\n".join(f"{f['id']}: {f['text']}" for f in facts) or "—",
            promises="\n".join(f"{p['id']}: {p['who']}: {p['text']}" + (f" (до {p['due']})" if p.get("due") else "")
                               for p in promises) or "—",
            summary=(talk or {}).get("summary") or "—", dialog=dialog)
        self.busy = True
        try:
            reply = self.cloud.complete([{"role": "user", "content": prompt}], max_tokens=2000)
            self.apply(tid, parse(reply), len(history), {f["id"] for f in facts}, {p["id"] for p in promises})
            self.last_error = None
            return True
        except Exception as exc:  # noqa: BLE001 — нет связи или модель ответила не по формату: попробуем в другой раз
            self.last_error = str(exc) or type(exc).__name__
            log.warning("Память: не удалось разобрать беседу: %s", self.last_error)
            return False
        finally:
            self.busy = False

    def apply(self, tid: str, data: dict, messages: int, known: set[str], open_promises: set[str] = frozenset()) -> None:
        def ids(key, allowed):
            return [i for i in _list(data, key) if isinstance(i, str) and i in allowed]

        outdated = set(ids("outdated", known))
        pinned = {f["id"] for f in self.memory.facts() if f.get("pinned")}
        self.memory.supersede([i for i in outdated if i not in pinned], "conversation_update")
        self.memory.touch(set(ids("seen", known)) - outdated)
        for item in _list(data, "new"):
            if isinstance(item, dict) and isinstance(item.get("text"), str) and item["text"].strip():
                kind = item.get("kind") if item.get("kind") in KINDS else "other"
                importance = item.get("importance") if item.get("importance") in (1, 2, 3) else 2
                files = [f for f in _list(item, "files") if isinstance(f, str)]
                self.memory.add(item["text"], kind, importance, source="auto", quote=item.get("quote"),
                                about=_list(item, "about"), files=files, talk=tid)
        for item in _list(data, "promises"):
            if isinstance(item, dict) and isinstance(item.get("text"), str) and item["text"].strip():
                self.memory.promise(item["text"], item.get("who", "user"), item.get("due"))
        self.memory.promise_done(ids("done", open_promises))
        for item in _list(data, "dates"):
            if isinstance(item, dict) and isinstance(item.get("text"), str) and item["text"].strip():
                try:
                    self.memory.event(item["text"], item.get("date"), item.get("yearly") is True)
                except ValueError:
                    pass  # модель не смогла назвать точную дату
        mood = data.get("mood") if type(data.get("mood")) is int and -2 <= data["mood"] <= 2 else None
        if mood is not None and self.memory.on("mood"):
            self.memory.note_mood(mood, data.get("mood_note") or "")
        if isinstance(data.get("wish"), str) and data["wish"].strip():
            self.memory.wish(data["wish"])
        if isinstance(data.get("lesson"), str) and data["lesson"].strip():
            self.memory.lesson(data["lesson"], "chat")
        for item in _list(data, "traces"):
            if not isinstance(item, dict) or item.get("kind") not in ("cause", "decision", "project_error", "progress"):
                continue
            if not isinstance(item.get("text"), str) or not item["text"].strip():
                continue
            files = [x for x in _list(item, "files") if isinstance(x, str)]
            self.memory.trace(item["kind"], item["text"], reason=item.get("reason", ""),
                              result=item.get("result", ""), status=item.get("status", "done"),
                              files=files, about=_list(item, "about"), source="chat", talk=tid,
                              date=item.get("date"))
        title, summary = data.get("title"), data.get("summary")
        if isinstance(summary, str) and summary.strip():
            self.memory.save_talk(tid, title if isinstance(title, str) and title.strip() else summary[:60],
                                  summary, messages, mood if self.memory.on("mood") else None)
