"""Как Yakumo учится: после разговора модель выписывает новые факты и обновляет конспект беседы.

Работает в фоне и не задерживает ответы: беседа разбирается, когда в ней
наступила пауза (DELAY секунд без новых реплик).
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import threading
import time

from .store import KINDS, Memory

log = logging.getLogger("yakumo.modules.brain")

DELAY = 20            # секунд тишины в беседе, после которых её можно разбирать
LAST_MESSAGES = 12    # сколько последних реплик показывать модели
MESSAGE_CHARS = 1500  # одна реплика
KNOWN_FACTS = 80      # сколько уже известных фактов показывать, чтобы не было повторов

PROMPT = {
    "ru": """Ты — память ассистента Yakumo. Прочитай отрывок разговора пользователя с Yakumo и обнови память.

Уже известные факты о пользователе (id: текст):
{facts}

Прежний конспект этой беседы: {summary}

Разговор:
{dialog}

Ответь ТОЛЬКО объектом JSON без пояснений:
{{"new": [{{"text": "факт о пользователе", "kind": "person|likes|work|other", "importance": 1|2|3}}],
 "seen": ["id известных фактов, которые снова упоминались"],
 "outdated": ["id известных фактов, которые пользователь опроверг или которые устарели"],
 "title": "короткое название беседы, 2-6 слов",
 "summary": "конспект всей беседы в 1-4 предложениях: о чём говорили, что решили, что осталось сделать"}}

Правила для new: только устойчивые сведения о самом пользователе из ЕГО слов (имя, близкие, город, работа, проекты,
привычки, вкусы, планы, договорённости с Yakumo). Не записывай разовые вопросы, общие знания, ответы Yakumo,
пароли, ключи, номера карт и документов. Пиши кратко от третьего лица («Пользователя зовут Аня», «Любит зелёный чай»).
kind: person — о человеке и близких, likes — вкусы и предпочтения, work — дела, учёба, проекты и планы, other — прочее.
importance: 3 — важно помнить всегда (имя, близкие, просьбы «запомни»), 2 — полезно, 1 — мелочь.
Не повторяй уже известные факты: если факт уточняется, верни новый текст в new и старый id в outdated.
Если нового нет, верни пустые списки.""",
    "en": """You are the memory of the Yakumo assistant. Read the conversation excerpt and update the memory.

Known facts about the user (id: text):
{facts}

Previous summary of this conversation: {summary}

Conversation:
{dialog}

Reply ONLY with a JSON object, no comments:
{{"new": [{{"text": "fact about the user", "kind": "person|likes|work|other", "importance": 1|2|3}}],
 "seen": ["ids of known facts mentioned again"],
 "outdated": ["ids of known facts the user contradicted or that are out of date"],
 "title": "short conversation title, 2-6 words",
 "summary": "summary of the whole conversation in 1-4 sentences: topics, decisions, what is left to do"}}

Rules for new: only lasting facts about the user from THEIR words (name, family, city, job, projects, habits,
tastes, plans, agreements with Yakumo). Never record one-off questions, general knowledge, Yakumo's answers,
passwords, keys, card or document numbers. Write briefly in third person ("The user's name is Ann", "Likes green tea").
kind: person — the person and family, likes — tastes and preferences, work — work, study, projects and plans, other.
importance: 3 — always remember (name, family, "remember this" requests), 2 — useful, 1 — minor.
Do not repeat known facts: if a fact changes, put the new text in new and the old id in outdated.
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


class Learner:
    def __init__(self, memory: Memory, cloud, language):
        self.memory = memory
        self.cloud = cloud
        self.language = language                  # () -> "ru" | "en"
        self.pending: dict[str, tuple] = {}       # беседа -> (реплики, когда пришла последняя)
        self.wake = threading.Event()
        self.stopping = False
        self.busy = False
        self.last_error: str | None = None
        self.thread: threading.Thread | None = None

    # --- Очередь ---

    def heard(self, history: list[dict], answer: str, chat_id: str) -> None:
        """Ответ в чате готов: запомнить беседу, разобрать её чуть позже."""
        if not self.memory.auto or not any(m["role"] == "user" for m in history):
            return
        tid = talk_id(history, chat_id)
        self.pending[tid] = ([*history, {"role": "assistant", "content": answer}], time.time())
        self.wake.set()

    def start(self) -> None:
        self.thread = threading.Thread(target=self._run, name="brain", daemon=True)
        self.thread.start()

    def stop(self) -> None:
        self.stopping = True
        self.wake.set()

    def _run(self) -> None:
        while not self.stopping:
            ready = [tid for tid, (_h, at) in list(self.pending.items()) if time.time() - at >= DELAY]
            for tid in ready:
                if self.stopping:
                    return
                history, _at = self.pending.pop(tid)
                self.learn(tid, history)
            wait = min((DELAY - (time.time() - at) for _h, at in list(self.pending.values())), default=None)
            self.wake.wait(max(1.0, wait) if wait is not None else None)
            self.wake.clear()

    # --- Разбор беседы ---

    def learn(self, tid: str, history: list[dict]) -> bool:
        if not self.cloud or not self.cloud.api_key():
            return False
        lang = "en" if self.language() == "en" else "ru"
        facts = self.memory.facts()[:KNOWN_FACTS]
        known = "\n".join(f"{f['id']}: {f['text']}" for f in facts) or "—"
        talk = self.memory.talk(tid)
        names = {"user": "Пользователь" if lang == "ru" else "User", "assistant": "Yakumo"}
        dialog = "\n\n".join(f"{names[m['role']]}: {m['content'][:MESSAGE_CHARS]}" for m in history[-LAST_MESSAGES:])
        prompt = PROMPT[lang].format(facts=known, summary=(talk or {}).get("summary") or "—", dialog=dialog)
        self.busy = True
        try:
            reply = self.cloud.complete([{"role": "user", "content": prompt}], max_tokens=1000)
            self.apply(tid, parse(reply), len(history), {f["id"] for f in facts})
            self.last_error = None
            return True
        except Exception as exc:  # noqa: BLE001 — нет связи или модель ответила не по формату: попробуем в другой раз
            self.last_error = str(exc) or type(exc).__name__
            log.warning("Память: не удалось разобрать беседу: %s", self.last_error)
            return False
        finally:
            self.busy = False

    def apply(self, tid: str, data: dict, messages: int, known: set[str]) -> None:
        def ids(key):
            value = data.get(key)
            return [i for i in value if isinstance(i, str) and i in known] if isinstance(value, list) else []

        outdated = set(ids("outdated"))
        pinned = {f["id"] for f in self.memory.facts() if f.get("pinned")}
        self.memory.delete([i for i in outdated if i not in pinned])
        self.memory.touch(set(ids("seen")) - outdated)
        for item in data.get("new") or []:
            if isinstance(item, dict) and isinstance(item.get("text"), str) and item["text"].strip():
                kind = item.get("kind") if item.get("kind") in KINDS else "other"
                importance = item.get("importance") if item.get("importance") in (1, 2, 3) else 2
                self.memory.add(item["text"], kind, importance, source="auto")
        title, summary = data.get("title"), data.get("summary")
        if isinstance(summary, str) and summary.strip():
            self.memory.save_talk(tid, title if isinstance(title, str) and title.strip() else summary[:60],
                                  summary, messages)
