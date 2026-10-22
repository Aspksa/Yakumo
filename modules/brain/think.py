"""Сильное мышление: для сложной задачи Yakumo думает в несколько голов.

Три «внутренних голоса» решают задачу независимо (аналитик, скептик,
практик), затем «критик» сравнивает их решения, находит ошибки и собирает
один лучший ответ. Так ошибки одного подхода ловятся другими, а ответ
получается точнее, чем с первого раза. Вызывается инструментом deep_think:
Yakumo сама зовёт его для расчётов, планов, анализа и выбора.
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor

from .learn import parse

log = logging.getLogger("yakumo.modules.brain")

VOICES = {
    "ru": (("Аналитик", "Разбери задачу строго и по шагам, проверь каждое число и вывод."),
           ("Скептик", "Ищи подвохи, неучтённые условия и где обычно ошибаются; реши с их учётом."),
           ("Практик", "Реши так, как это лучше всего сделать в жизни: просто, конкретно, с примером.")),
    "en": (("Analyst", "Solve strictly step by step, check every number and conclusion."),
           ("Skeptic", "Look for traps, missed conditions and common mistakes; solve with them in mind."),
           ("Practitioner", "Solve it the way that works best in real life: simple, concrete, with an example.")),
}

DRAFT = {
    "ru": "Ты — Yakumo, внутренний голос «{voice}». {how}\n\nЗадача: {task}\n\nЧто известно: {context}\n\n"
          "Реши задачу. Пиши кратко: ход решения и итог.",
    "en": "You are Yakumo, inner voice “{voice}”. {how}\n\nTask: {task}\n\nKnown: {context}\n\n"
          "Solve it. Be brief: reasoning and result.",
}

CRITIC = {
    "ru": """Ты — Yakumo-критик. Три внутренних голоса решили задачу независимо.

Задача: {task}
Что известно: {context}

{drafts}

Сравни решения: где они расходятся, кто ошибся и почему, что упущено. Затем собери один лучший ответ.
Ответь ТОЛЬКО объектом JSON:
{{"answer": "лучший ответ пользователю, Markdown можно", "confidence": 1-5,
 "disagreements": "где голоса разошлись и чем это решилось (или пусто)",
 "lesson": "общее правило на будущее, если нашлась типичная ошибка (или null)"}}""",
    "en": """You are Yakumo the critic. Three inner voices solved the task independently.

Task: {task}
Known: {context}

{drafts}

Compare: where they disagree, who is wrong and why, what is missing. Then build one best answer.
Reply ONLY with a JSON object:
{{"answer": "the best answer for the user, Markdown allowed", "confidence": 1-5,
 "disagreements": "where the voices disagreed and how it was settled (or empty)",
 "lesson": "a general rule for the future if a typical mistake was found (or null)"}}""",
}


class DeepThink:
    def __init__(self, memory, cloud, language):
        self.memory = memory
        self.cloud = cloud
        self.language = language

    def run(self, task: str, context: str = "") -> dict:
        if not self.cloud or not self.cloud.api_key():
            return {"error": "Нет ключа Cloud.ru"}
        lang = "en" if self.language() == "en" else "ru"
        task, context = task.strip()[:4000], (context or "—").strip()[:4000]

        def draft(voice):
            name, how = voice
            text = self.cloud.complete([{"role": "user", "content": DRAFT[lang].format(
                voice=name, how=how, task=task, context=context)}], max_tokens=1200)
            return name, text.strip()

        with ThreadPoolExecutor(3) as pool:
            drafts = [d for d in pool.map(self._safe(draft), VOICES[lang]) if d]
        if not drafts:
            return {"error": "Не удалось подумать: нет связи с Cloud.ru"}
        listing = "\n\n".join(f"[{name}]\n{text[:3000]}" for name, text in drafts)
        try:
            data = parse(self.cloud.complete([{"role": "user", "content": CRITIC[lang].format(
                task=task, context=context, drafts=listing)}], max_tokens=2000))
        except Exception as exc:  # noqa: BLE001 — критик не ответил: отдать черновик аналитика
            log.warning("Память: критик не ответил: %s", exc)
            return {"answer": drafts[0][1], "voices": len(drafts)}
        lesson = data.get("lesson")
        if isinstance(lesson, str) and lesson.strip() and self.memory.enabled:
            self.memory.lesson(lesson, "think")
        confidence = data.get("confidence") if type(data.get("confidence")) is int else None
        return {"answer": data.get("answer") if isinstance(data.get("answer"), str) else drafts[0][1],
                "confidence": confidence, "disagreements": data.get("disagreements") or "",
                "voices": len(drafts),
                "note": ("Перескажи ответ пользователю своими словами. Если уверенность ниже 4 — честно скажи, "
                         "в чём сомневаешься." if lang == "ru" else
                         "Retell the answer in your own words. If confidence is below 4, say what you doubt.")}

    @staticmethod
    def _safe(fn):
        def wrapped(arg):
            try:
                return fn(arg)
            except Exception as exc:  # noqa: BLE001
                log.warning("Память: голос не ответил: %s", exc)
                return None
        return wrapped
