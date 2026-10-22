"""Самообучение во сне: ночной экзамен и стиль, который Yakumo улучшает сама.

Экзамен: Yakumo строго перечитывает свои недавние ответы, ищет ошибки и
неточности и выводит из них короткие правила («уроки»), которые потом видит в
каждой подсказке. Стиль: раз в неделю по примерам разговоров и урокам она
переписывает свою инструкцию «как мне отвечать». Каждая версия хранится —
на странице «Память» можно откатиться к любой или выключить стиль совсем.

Вес самой модели не меняется (его не переобучить), растёт всё вокруг неё.
"""

from __future__ import annotations

import time

from .learn import parse
from .store import today

EXAM_SAMPLES = 4
STYLE_EVERY = 7 * 86400
STYLE_MIN_SAMPLES = 5

EXAM = {
    "ru": """Ты — строгий экзаменатор и одновременно сама Yakumo. Перечитай свои недавние ответы пользователю
и честно проверь себя: где ошибка в фактах или расчётах, где ответ неточный, слишком длинный, не по вопросу,
где стоило уточнить или признаться, что не уверена.

{samples}

Уже выведенные правила (не повторяй их):
{lessons}

Ответь ТОЛЬКО объектом JSON:
{{"score": 1-5, "review": "1-2 предложения: как ты справилась", "lessons": ["короткое правило на будущее", ...]}}
lessons — 0-3 новых правила от первого лица («Проверять расчёты через calc»), только по найденным промахам.""",
    "en": """You are a strict examiner and Yakumo herself. Re-read your recent answers to the user and check
yourself honestly: factual or calculation errors, inaccurate, too long or off-topic answers, places where you
should have asked or admitted uncertainty.

{samples}

Rules you already derived (don't repeat them):
{lessons}

Reply ONLY with a JSON object:
{{"score": 1-5, "review": "1-2 sentences on how you did", "lessons": ["a short rule for the future", ...]}}
lessons — 0-3 new rules in first person ("Check calculations with calc"), only for real misses.""",
}

STYLE = {
    "ru": """Ты — Yakumo. Раз в неделю ты улучшаешь свою инструкцию «как мне отвечать этому пользователю».

Нынешняя инструкция:
{style}

Твои уроки:
{lessons}

Что пользователь о тебе говорил (факты о ваших отношениях):
{own}

Примеры недавних разговоров:
{samples}

Перепиши инструкцию так, чтобы ответы лучше подходили именно этому пользователю: длина, тон, формат, что он ценит.
Ответь ТОЛЬКО объектом JSON: {{"style": "инструкция, 3-8 коротких пунктов, до 700 символов",
"why": "что поменялось и почему, одно предложение"}}""",
    "en": """You are Yakumo. Once a week you improve your instruction "how I answer this user".

Current instruction:
{style}

Your lessons:
{lessons}

What the user said about you (facts about your relationship):
{own}

Recent conversation samples:
{samples}

Rewrite the instruction so answers fit this particular user better: length, tone, format, what they value.
Reply ONLY with a JSON object: {{"style": "instruction, 3-8 short bullets, up to 700 characters",
"why": "what changed and why, one sentence"}}""",
}


class Growth:
    def __init__(self, memory, mind, language):
        self.memory = memory
        self.mind = mind
        self.language = language

    def _lang(self) -> str:
        return "en" if self.language() == "en" else "ru"

    def _samples(self, count: int) -> str:
        items = self.memory.data["samples"][-count:]
        return "\n\n".join(f"— {s['question'][:600]}\n→ {s['answer'][:900]}" for s in items)

    def _lessons(self) -> str:
        return "\n".join(f"- {x['text']}" for x in self.memory.data["lessons"]) or "—"

    def exam(self, force: bool = False) -> list[dict]:
        """Ночной экзамен: раз в сутки, если были новые разговоры. Возвращает новые уроки."""
        meta = self.memory.data["meta"]
        fresh = [s for s in self.memory.data["samples"] if s.get("created", 0) > meta.get("exam_at", 0)]
        if not force and (meta.get("last_exam") == today() or not fresh):
            return []
        if not self.memory.data["samples"] or not self.mind.can_think():
            return []
        lang = self._lang()
        meta["last_exam"], meta["exam_at"] = today(), int(time.time())
        item = self.mind.thought("exam", "Ночной экзамен: проверяю свои ответы" if lang == "ru"
                                 else "Night exam: checking my answers")
        try:
            data = parse(self.mind.complete([{"role": "user", "content": EXAM[lang].format(
                samples=self._samples(EXAM_SAMPLES), lessons=self._lessons())}], max_tokens=800))
        except Exception:
            self.mind.finish(item, "failed")
            raise
        added = [self.memory.lesson(x, "exam") for x in (data.get("lessons") or [])[:3]
                 if isinstance(x, str) and x.strip()]
        score = data.get("score") if type(data.get("score")) is int else None
        review = data.get("review") if isinstance(data.get("review"), str) else ""
        self.mind.finish(item, "done", (f"{score}/5. " if score else "") + review
                         + "".join(f"\n- {x['text']}" for x in added))
        return added

    def evolve(self, force: bool = False) -> dict | None:
        """Раз в неделю — новая версия стиля (старые остаются для отката)."""
        meta = self.memory.data["meta"]
        if not force and time.time() - meta.get("style_at", 0) < STYLE_EVERY:
            return None
        if len(self.memory.data["samples"]) < STYLE_MIN_SAMPLES or not self.mind.can_think():
            return None
        lang = self._lang()
        meta["style_at"] = int(time.time())
        current = self.memory.style()
        own = [f["text"] for f in self.memory.facts() if f["kind"] == "self"][:10]
        item = self.mind.thought("style", "Улучшаю свой стиль ответов" if lang == "ru" else "Improving my style")
        try:
            data = parse(self.mind.complete([{"role": "user", "content": STYLE[lang].format(
                style=current["text"] if current else "—", lessons=self._lessons(),
                own="\n".join(f"- {x}" for x in own) or "—", samples=self._samples(10))}], max_tokens=900))
        except Exception:
            self.mind.finish(item, "failed")
            raise
        text = data.get("style")
        if not isinstance(text, str) or not text.strip():
            self.mind.finish(item, "done", "Без изменений" if lang == "ru" else "No changes")
            return None
        version = self.memory.add_style(text, data.get("why") if isinstance(data.get("why"), str) else "")
        self.mind.finish(item, "done", version["why"] or version["text"][:200])
        return version
