"""«Сон кицунэ»: раз в сутки Yakumo наводит порядок в памяти и пишет утреннее сообщение.

Во сне модель склеивает повторы, а утром Yakumo с юмором рассказывает, что ей
«приснилось» из вашей недели, и сама напоминает о важном: даты, обещания,
цели, «а помнишь, год назад…», бережный вопрос, если в последние дни было тяжело.
Сообщение появляется в чате при следующем открытии Yakumo.
"""

from __future__ import annotations

import datetime as dt
import logging
import time

from .learn import parse
from .store import today

log = logging.getLogger("yakumo.modules.brain")

IDLE = 20 * 60     # спит, только когда в чате тихо столько секунд
WAKE_HOUR = 4      # новые сутки для сна начинаются в 4 утра
MAX_FACTS = 200

PROMPT = {
    "ru": """Ты — Yakumo, кицунэ с девятью золотыми хвостами, помощница пользователя. Ночь: ты «спишь» и наводишь
порядок в своей памяти, а утром первой пишешь пользователю. Сегодня {today}.

Факты, которые ты помнишь (id: текст):
{facts}

Разговоры за последнюю неделю:
{talks}

Что важно сегодня и завтра (даты, сроки обещаний, просроченное):
{upcoming}

Открытые обещания:
{promises}

Цели и планы пользователя:
{goals}

Воспоминания «в этот день»:
{memories}

Настроение в последние дни: {mood}
Компьютер ночью: {late}

Ответь ТОЛЬКО объектом JSON:
{{"merge": [{{"ids": ["id", "id"], "text": "один факт вместо нескольких повторов"}}],
 "morning": "утреннее сообщение пользователю"}}

merge — только настоящие повторы и дубли одного и того же; если таких нет, пустой список.
morning — 2-6 коротких предложений от первого лица, тепло и живо, по-русски, Markdown можно. Начни с одной забавной
строчки о том, что тебе «приснилось» по мотивам недели (без выдумок о фактах). Потом то, что действительно важно:
напомни о датах и сроках, мягко спроси о прогрессе одной цели, вспомни «в этот день», если есть. Если в последние дни
пользователю было тяжело — будь бережной, без нравоучений. Если работал поздно ночью — заботливо отметь это.
Не перечисляй всё подряд и не упоминай, что это JSON или память.""",
    "en": """You are Yakumo, a nine-tailed golden kitsune and the user's assistant. It's night: you "sleep" and tidy up
your memory, and in the morning you write to the user first. Today is {today}.

Facts you remember (id: text):
{facts}

Conversations this week:
{talks}

What matters today and tomorrow (dates, promise deadlines, overdue):
{upcoming}

Open promises:
{promises}

The user's goals and plans:
{goals}

"On this day" memories:
{memories}

Mood in recent days: {mood}
Computer at night: {late}

Reply ONLY with a JSON object:
{{"merge": [{{"ids": ["id", "id"], "text": "one fact instead of several duplicates"}}],
 "morning": "morning message to the user"}}

merge — only real duplicates of the same thing; empty list if none.
morning — 2-6 short sentences in first person, warm and lively, Markdown allowed. Start with one funny line about what
you "dreamed" based on the week (don't invent facts). Then what truly matters: remind of dates and deadlines, gently
ask about progress on one goal, recall "on this day" if any. If the user had a hard time lately, be gentle, no
lecturing. If they worked late at night, note it with care. Don't list everything and don't mention JSON or memory.""",
}


class Sleep:
    def __init__(self, memory, cloud, language, learner):
        self.memory = memory
        self.cloud = cloud
        self.language = language
        self.learner = learner
        self.busy = False

    def due(self, now: float | None = None) -> bool:
        """Пора спать: сон включён, сегодня ещё не спала, после 4 утра и в чате тихо."""
        now = now or time.time()
        return (self.memory.on("sleep") and time.localtime(now).tm_hour >= WAKE_HOUR
                and self.memory.data["meta"].get("last_sleep") != dt.date.fromtimestamp(now).isoformat()
                and now - self.learner.last_chat >= IDLE)

    def tick(self) -> None:
        if self.due():
            self.run()

    def run(self) -> str | None:
        """Уснуть сейчас. Возвращает утреннее сообщение (оно же уходит во «входящие» чата) или None."""
        self.busy = True
        try:
            text = self._dream() if self.cloud and self.cloud.api_key() else None
            text = text or self._plain()
            self.memory.data["meta"]["last_sleep"] = today()
            if text:
                self.memory.data["meta"]["last_morning"] = text
                self.memory.say(text, "morning")
            else:
                self.memory.save()
            return text
        finally:
            self.busy = False

    # --- Что важно ---

    def _context(self) -> dict:
        m, lang = self.memory, self.language()
        ru = lang != "en"
        week = time.time() - 7 * 86400
        upcoming = m.upcoming(1)

        def when(x):
            if x["in_days"] < 0:
                return "просрочено" if ru else "overdue"
            return ("сегодня" if ru else "today") if x["in_days"] == 0 else ("завтра" if ru else "tomorrow")

        mood = m.mood_trend() if m.on("mood") else None
        day = m.data["days"].get(today(), {})
        return {
            "upcoming": [f"{when(x)}: {x['text']}" + (f" ({x['date']})" if x["in_days"] < 0 else "") for x in upcoming],
            "promises": [f"{'пользователь' if ru and p['who'] == 'user' else 'ты' if ru else p['who']}: {p['text']}"
                         + (f" (до {p['due']})" if p.get("due") else "") for p in m.open_promises()[:10]],
            "goals": [f["text"] for f in m.facts() if f["kind"] == "work"][:6],
            "memories": [(f"{x['ago_months']} мес. назад" if ru else f"{x['ago_months']} months ago")
                         + f": {x['title']} — {x['summary']}" for x in m.on_this_day()],
            "talks": [f"{t['title']}: {t['summary']}" for t in m.talks() if t.get("updated", 0) >= week][:10],
            "mood": (f"{mood['average']} из -2..2" + (f" ({'; '.join(mood['notes'])})" if mood["notes"] else "")
                     if mood else "—"),
            "late": (f"до {day['late_until']}" if ru else f"until {day['late_until']}") if day.get("late") else "—",
        }

    def _dream(self) -> str | None:
        lang = "en" if self.language() == "en" else "ru"
        facts = self.memory.facts()[:MAX_FACTS]
        c = self._context()
        if not facts and not any(c[k] for k in ("upcoming", "promises", "talks", "memories")):
            return None  # пока нечего вспоминать — утро без сообщения
        lines = lambda items: "\n".join(f"- {x}" for x in items) or "—"  # noqa: E731
        prompt = PROMPT[lang].format(
            today=today(), facts="\n".join(f"{f['id']}: {f['text']}" for f in facts) or "—",
            talks=lines(c["talks"]), upcoming=lines(c["upcoming"]), promises=lines(c["promises"]),
            goals=lines(c["goals"]), memories=lines(c["memories"]), mood=c["mood"], late=c["late"])
        try:
            data = parse(self.cloud.complete([{"role": "user", "content": prompt}], max_tokens=1200))
        except Exception as exc:  # noqa: BLE001 — без связи утро будет попроще
            log.warning("Память: сон без модели: %s", exc)
            return None
        known = {f["id"] for f in facts}
        for item in data.get("merge") or []:
            if (isinstance(item, dict) and isinstance(item.get("ids"), list) and isinstance(item.get("text"), str)
                    and item["text"].strip()):
                ids = [i for i in item["ids"] if i in known]
                if len(ids) >= 2 and self.memory.merge(ids, item["text"]):
                    known -= set(ids[1:])
        morning = data.get("morning")
        return morning.strip() if isinstance(morning, str) and morning.strip() else None

    def _plain(self) -> str | None:
        """Утро без Cloud.ru: просто напоминания."""
        c = self._context()
        items = c["upcoming"] + c["memories"][:1]
        if not items:
            return None
        head = "Доброе утро! Не забудь:" if self.language() != "en" else "Good morning! Don't forget:"
        return head + "\n\n" + "\n".join(f"- {x}" for x in items)
