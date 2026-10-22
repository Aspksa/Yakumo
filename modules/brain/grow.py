"""Самообучение во сне: ночной экзамен и стиль, который Yakumo улучшает сама.

Экзамен: Yakumo строго перечитывает свои недавние ответы, ищет ошибки и
неточности и выводит из них короткие правила («уроки»), которые потом видит в
каждой подсказке. Стиль: раз в неделю по примерам разговоров и урокам она
переписывает свою инструкцию «как мне отвечать». Каждая версия хранится —
на странице «Память» можно откатиться к любой или выключить стиль совсем.

Из чата: 👍 под ответом делает его образцом (по образцам улучшается стиль),
👎 — Yakumo разбирает, что было не так, и выводит урок. Любопытство: раз в
день Yakumo сама находит пробел в памяти и задаёт вам один вопрос. Во сне уроки
консолидируются: повторы склеиваются, частные случаи обобщаются. Рост мозга
считается по дням: «нейроны» (всё, что Yakumo знает) и связи между ними.

Предсказание: раз в день Yakumo по датам, обещаниям, привычкам дня недели и
недавним разговорам решает, что вам понадобится, и готовит это заранее в фоне.
Учёба на правках: если вы поправили файл, который написала Yakumo, она
сравнивает версии и выводит, что делать иначе.

Вес самой модели не меняется (его не переобучить), растёт всё вокруг неё.
"""

from __future__ import annotations

import datetime as dt
import difflib
import time

from .learn import parse
from .store import today

EXAM_SAMPLES = 4
CONSOLIDATE_EVERY = 3 * 86400
CONSOLIDATE_MIN = 8   # уроков, начиная с которых их стоит сжимать
MAX_BEST = 20         # образцов с 👍
EDIT_SETTLE = 10 * 60      # файл не меняли столько секунд — правка закончена, можно учиться
EDIT_WAIT = 30 * 86400     # дольше ждать правок нет смысла
MAX_DIFF = 6000
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


FEEDBACK = {
    "ru": """Ты — Yakumo. Пользователь поставил 👎 твоему ответу.

Вопрос пользователя: {question}
Твой ответ: {answer}
Комментарий пользователя: {note}

Честно разбери, что было не так (ошибка, тон, длина, не по вопросу, выдумка), и выведи правило на будущее.
Ответь ТОЛЬКО объектом JSON: {{"why": "что было не так, одно предложение", "lesson": "правило от первого лица"}}""",
    "en": """You are Yakumo. The user gave your answer a 👎.

User's question: {question}
Your answer: {answer}
User's comment: {note}

Honestly analyse what went wrong (error, tone, length, off-topic, made up) and derive a rule for the future.
Reply ONLY with a JSON object: {{"why": "what went wrong, one sentence", "lesson": "a rule in first person"}}""",
}

CURIOUS = {
    "ru": """Ты — Yakumo, любопытная кицунэ-помощница. Вот что ты знаешь о пользователе:
{facts}

Недавние разговоры:
{talks}

Найди один самый полезный пробел: чего тебе не хватает, чтобы помогать лучше (важное, но неизвестное; давно не
обновлявшееся; незаконченное дело). Придумай ОДИН короткий тёплый вопрос пользователю. Не спрашивай о паролях,
деньгах и здоровье, если он сам об этом не говорил. Ответь ТОЛЬКО объектом JSON:
{{"question": "вопрос пользователю", "why": "какой пробел он закрывает"}}""",
    "en": """You are Yakumo, a curious kitsune assistant. What you know about the user:
{facts}

Recent conversations:
{talks}

Find the single most useful gap: what you lack to help better (important but unknown; long not updated; an
unfinished matter). Write ONE short warm question to the user. Don't ask about passwords, money or health unless
they brought it up. Reply ONLY with a JSON object: {{"question": "the question", "why": "which gap it closes"}}""",
}

CONSOLIDATE = {
    "ru": """Ты — Yakumo. Вот правила, которые ты вывела себе в разное время (id: текст, сколько раз подтверждалось):
{lessons}

Консолидируй их: склей повторы и близкие правила, обобщи частные случаи, убери устаревшие и противоречивые
(оставь более новое). Должно стать меньше, но сильнее. Ответь ТОЛЬКО объектом JSON:
{{"lessons": [{{"text": "правило", "from": ["id", ...]}}]}}""",
    "en": """You are Yakumo. Rules you derived for yourself at different times (id: text, times confirmed):
{lessons}

Consolidate them: merge duplicates and close rules, generalise special cases, drop outdated and contradicting ones
(keep the newer). Fewer but stronger. Reply ONLY with a JSON object:
{{"lessons": [{{"text": "rule", "from": ["id", ...]}}]}}""",
}


EDITS = {
    "ru": """Ты — Yakumo. Ты написала файл «{path}», а пользователь потом его поправил. Вот что он изменил
(- твоё, + его):

{diff}

Пойми, чего он хочет от таких текстов: стиль, длина, структура, слова, факты. Ответь ТОЛЬКО объектом JSON:
{{"changes": "что он поменял, одно предложение", "lessons": ["правило на будущее от первого лица", ...]}}
lessons — 0-2 общих правила, а не пересказ правок.""",
    "en": """You are Yakumo. You wrote the file “{path}” and the user edited it afterwards. Their changes
(- yours, + theirs):

{diff}

Understand what they want from such texts: style, length, structure, wording, facts. Reply ONLY with a JSON object:
{{"changes": "what they changed, one sentence", "lessons": ["a rule for the future in first person", ...]}}
lessons — 0-2 general rules, not a retelling of the edits.""",
}

FORESEE = {
    "ru": """Ты — Yakumo, заботливая помощница. Сегодня {today}, {weekday}. Подумай наперёд: что пользователю
понадобится сегодня и завтра, и что ты можешь подготовить заранее, пока он занят.

Ближайшие даты и сроки:
{upcoming}

Открытые обещания:
{promises}

Обычно по этим дням недели за компьютером: {habits}

Его навыки (повторяющиеся дела): {skills}

Дела и планы:
{goals}

Недавние разговоры:
{talks}

Выбери 0-2 самых полезных вещи. Ничего не выдумывай: только то, что следует из данных выше.
Ответь ТОЛЬКО объектом JSON:
{{"needs": [{{"what": "что подготовить, коротко", "why": "почему это понадобится",
  "task": "подробная задача для фоновой работы с документами Диска и памятью, или null, если достаточно напомнить"}}]}}""",
    "en": """You are Yakumo, a caring assistant. Today is {today}, {weekday}. Think ahead: what will the user
need today and tomorrow, and what can you prepare in advance while they are busy.

Upcoming dates and deadlines:
{upcoming}

Open promises:
{promises}

Usually at the computer on this weekday: {habits}

Their skills (recurring tasks): {skills}

Work and plans:
{goals}

Recent conversations:
{talks}

Pick 0-2 most useful things. Don't make anything up: only what follows from the data above.
Reply ONLY with a JSON object:
{{"needs": [{{"what": "what to prepare, briefly", "why": "why it will be needed",
  "task": "a detailed task for background work with Drive documents and memory, or null if a reminder is enough"}}]}}""",
}
WEEKDAYS = {"ru": ("понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"),
            "en": ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")}


def same_text(a: str, b: str) -> bool:
    return " ".join(a.split()) == " ".join(b.split())


def diff(old: str, new: str) -> str:
    lines = difflib.unified_diff(old.splitlines(), new.splitlines(), lineterm="", n=1)
    return "\n".join(line for line in lines if not line.startswith(("---", "+++")))[:MAX_DIFF]


class Growth:
    def __init__(self, memory, mind, language, services: dict | None = None, tasks=None):
        self.memory = memory
        self.mind = mind
        self.language = language
        self.services = services if services is not None else {}  # ctx.services: Диск
        self.tasks = tasks                                         # фоновые задачи для предсказаний

    def _lang(self) -> str:
        return "en" if self.language() == "en" else "ru"

    def _samples(self, count: int) -> str:
        best = self.memory.data["best"][-count // 2:] if count > 1 else []
        items = best + self.memory.data["samples"][-(count - len(best)):]
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

    # --- Из чата: 👍 и 👎 ---

    def rate(self, question: str, answer: str, good: bool, note: str = "") -> None:
        question, answer = str(question)[:1500], str(answer)[:2500]
        if not answer.strip():
            raise ValueError("Нет ответа")
        if good:
            self.memory.add_item("best", {"question": question, "answer": answer}, MAX_BEST)
        else:
            self.memory.add_item("feedback", {"question": question, "answer": answer,
                                              "note": " ".join(str(note or "").split())[:500]}, 30)

    def digest(self) -> int:
        """Разобрать ответы с 👎: что было не так → урок. Без ключа или бюджета подождут."""
        done = 0
        while self.memory.data["feedback"] and self.mind.can_think():
            fb = self.memory.data["feedback"][0]
            lang = self._lang()
            item = self.mind.thought("feedback", "Разбираю ответ с 👎" if lang == "ru" else "Analysing a 👎 answer")
            try:
                data = parse(self.mind.complete([{"role": "user", "content": FEEDBACK[lang].format(
                    question=fb["question"], answer=fb["answer"], note=fb.get("note") or "—")}], max_tokens=400))
            except Exception:
                self.mind.finish(item, "failed")
                raise
            finally:
                self.memory.delete_items("feedback", [fb["id"]])
            lesson = data.get("lesson")
            if isinstance(lesson, str) and lesson.strip():
                self.memory.lesson(lesson, "feedback")
            why = data.get("why") if isinstance(data.get("why"), str) else ""
            self.mind.finish(item, "done", why + (f"\n- {lesson}" if isinstance(lesson, str) else ""))
            done += 1
        return done

    # --- Любопытство ---

    def curious(self, force: bool = False) -> str | None:
        """Раз в день — один вопрос пользователю, чтобы закрыть пробел в памяти."""
        meta = self.memory.data["meta"]
        facts = [f for f in self.memory.facts() if not f.get("archived")]
        if not force and (meta.get("last_question") == today() or len(facts) < 3):
            return None
        if not self.mind.can_think():
            return None
        lang = self._lang()
        meta["last_question"] = today()
        item = self.mind.thought("curious", "Ищу, чего я о тебе не знаю" if lang == "ru" else "Looking for gaps")
        talks = [f"{t['title']}: {t['summary']}" for t in self.memory.talks()[:6]]
        try:
            data = parse(self.mind.complete([{"role": "user", "content": CURIOUS[lang].format(
                facts="\n".join(f"- {f['text']}" for f in facts[:60]),
                talks="\n".join(f"- {t}" for t in talks) or "—")}], max_tokens=300))
        except Exception:
            self.mind.finish(item, "failed")
            raise
        question = data.get("question")
        if not isinstance(question, str) or not question.strip():
            self.mind.finish(item, "done", "—")
            return None
        self.memory.say(question.strip(), "question")
        self.mind.finish(item, "done", question.strip() + (f"\n({data['why']})" if isinstance(data.get("why"), str) else ""))
        return question.strip()

    # --- Консолидация уроков ---

    def consolidate(self, force: bool = False) -> int | None:
        meta = self.memory.data["meta"]
        lessons = self.memory.data["lessons"]
        if not force and (len(lessons) < CONSOLIDATE_MIN or time.time() - meta.get("lessons_at", 0) < CONSOLIDATE_EVERY):
            return None
        if len(lessons) < 2 or not self.mind.can_think():
            return None
        lang = self._lang()
        meta["lessons_at"] = int(time.time())
        item = self.mind.thought("consolidate", "Укрепляю уроки: склеиваю и обобщаю" if lang == "ru"
                                 else "Strengthening lessons: merging and generalising")
        try:
            data = parse(self.mind.complete([{"role": "user", "content": CONSOLIDATE[lang].format(
                lessons="\n".join(f"{x['id']}: {x['text']} ({x.get('seen', 1)})" for x in lessons))}],
                max_tokens=1200))
        except Exception:
            self.mind.finish(item, "failed")
            raise
        seen = {x["id"]: x.get("seen", 1) for x in lessons}
        out = []
        for x in data.get("lessons") or []:
            if isinstance(x, dict) and isinstance(x.get("text"), str) and x["text"].strip():
                ids = [i for i in x.get("from") or [] if i in seen]
                out.append((x["text"], sum(seen[i] for i in ids) or 1))
        if not out:  # модель ничего не вернула — старые уроки не трогаем
            self.mind.finish(item, "done", "Без изменений" if lang == "ru" else "No changes")
            return None
        before = len(lessons)
        self.memory.replace_lessons(out)
        self.mind.finish(item, "done", f"{before} → {len(out)}")
        return len(out)

    # --- Рост мозга ---

    def census(self, chunks: int = 0) -> dict:
        """Сколько сегодня «нейронов» (всё, что Yakumo знает) и связей между ними."""
        m = self.memory.data
        neurons = {"facts": len(m["facts"]), "entities": len(m["entities"]), "lessons": len(m["lessons"]),
                   "notes": len(m["notes"]), "skills": len(m["skills"]), "talks": len(m["talks"]),
                   "tools": sum(t.get("status") == "on" for t in m["user_tools"]), "documents": chunks}
        links = len(self.memory.links()) + sum(len(f.get("about", [])) + len(f.get("files", [])) for f in m["facts"])
        snap = {"neurons": sum(neurons.values()), "links": links, "parts": neurons}
        with self.memory.lock:
            self.memory.day()["brain"] = snap
            self.memory.save()
        return snap

    def history(self, days: int = 30) -> list[dict]:
        return [{"date": k, "neurons": v["brain"]["neurons"], "links": v["brain"]["links"]}
                for k, v in sorted(self.memory.data["days"].items())[-days:] if v.get("brain")]

    # --- Учёба на правках файлов ---

    def edits(self) -> int:
        """Файлы, которые написала Yakumo: если пользователь их поправил, понять, что делать иначе."""
        disk = self.services.get("disk")
        if not disk or not hasattr(disk, "current"):
            return 0
        learned = 0
        for d in list(self.memory.data["drafts"]):
            now = disk.current(d["path"])
            if now is None or time.time() - d["at"] > EDIT_WAIT:
                self.memory.delete_items("drafts", [d["id"]])
                continue
            mtime, text = now
            if mtime <= d["at"] + 2 or same_text(text, d["text"]) or time.time() - mtime < EDIT_SETTLE:
                continue
            if not self.mind.can_think():
                break
            lang = self._lang()
            name = d["path"].split("/")[-1]
            item = self.mind.thought("edit", f"Учусь на твоих правках: {name}" if lang == "ru"
                                     else f"Learning from your edits: {name}")
            try:
                data = parse(self.mind.complete([{"role": "user", "content": EDITS[lang].format(
                    path=d["path"], diff=diff(d["text"], text))}], max_tokens=500))
            except Exception:
                self.mind.finish(item, "failed")
                raise
            finally:
                self.memory.delete_items("drafts", [d["id"]])
            added = [self.memory.lesson(x, "edit") for x in (data.get("lessons") or [])[:2]
                     if isinstance(x, str) and x.strip()]
            changes = data.get("changes") if isinstance(data.get("changes"), str) else ""
            self.mind.finish(item, "done", changes + "".join(f"\n- {x['text']}" for x in added))
            learned += 1
        return learned

    # --- Предсказание ---

    def _habits(self, lang: str) -> str:
        """Программы, за которыми пользователь обычно сидит в этот день недели (последние 4 недели)."""
        today_ = dt.date.today()
        total: dict[str, int] = {}
        for weeks in range(1, 5):
            day = self.memory.data["days"].get((today_ - dt.timedelta(weeks=weeks)).isoformat(), {})
            for app, minutes in (day.get("apps") or {}).items():
                total[app] = total.get(app, 0) + minutes
        top = sorted(total.items(), key=lambda x: -x[1])[:5]
        return ", ".join(f"{a} ~{m // 4} мин" if lang == "ru" else f"{a} ~{m // 4} min" for a, m in top) or "—"

    def foresee(self, force: bool = False) -> list[dict]:
        """Раз в день: что понадобится пользователю — подготовить заранее (фоновая задача) или напомнить."""
        meta = self.memory.data["meta"]
        if not force and meta.get("last_foresee") == today():
            return []
        if not self.mind.can_think():
            return []
        m, lang = self.memory, self._lang()
        upcoming = [f"{x['date']}: {x['text']}" for x in m.upcoming(2)]
        promises = [f"{p['text']}" + (f" (до {p['due']})" if p.get("due") else "") for p in m.open_promises()[:8]]
        talks = [f"{t['title']}: {t['summary']}" for t in m.talks()[:5]]
        goals = [f["text"] for f in m.facts() if f["kind"] == "work" and not f.get("archived")][:8]
        if not (upcoming or promises or talks or goals):
            return []
        meta["last_foresee"] = today()
        item = self.mind.thought("foresee", "Думаю наперёд: что тебе понадобится" if lang == "ru"
                                 else "Thinking ahead: what you'll need")
        lines = lambda xs: "\n".join(f"- {x}" for x in xs) or "—"  # noqa: E731
        try:
            data = parse(self.mind.complete([{"role": "user", "content": FORESEE[lang].format(
                today=today(), weekday=WEEKDAYS[lang][dt.date.today().weekday()], upcoming=lines(upcoming),
                promises=lines(promises), habits=self._habits(lang),
                skills=", ".join(s["name"] for s in m.data["skills"][:10]) or "—", goals=lines(goals),
                talks=lines(talks))}], max_tokens=700))
        except Exception:
            self.mind.finish(item, "failed")
            raise
        done = []
        for need in (data.get("needs") or [])[:2]:
            if not isinstance(need, dict) or not isinstance(need.get("what"), str) or not need["what"].strip():
                continue
            what, why = need["what"].strip()[:120], str(need.get("why") or "").strip()
            task = need.get("task") if isinstance(need.get("task"), str) and need["task"].strip() else None
            if task and self.tasks is not None and self.mind.can_think():
                self.tasks.add(task + (f"\n\nЗачем: {why}" if why else ""),
                               ("Заранее: " if lang == "ru" else "In advance: ") + what)
            else:
                self.memory.say((f"Подумала наперёд: {what}." if lang == "ru" else f"Thinking ahead: {what}.")
                                + (f" {why}" if why else ""), "foresee")
            done.append({"what": what, "why": why, "task": bool(task)})
        self.mind.finish(item, "done", "\n".join(f"- {x['what']}" for x in done) or "—")
        return done
