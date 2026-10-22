"""Понимание файлов: похожие и связанные файлы, конспект длинного документа.

Похожие ищутся по общим редким словам (умный поиск Диска), по смыслу (база
знаний «Мозга», если он включён) и по памяти: если в «Мозге» есть факт об
Иване Петрове со ссылкой на договор, рядом с договором покажется и расписка,
о которой тоже есть факт про Ивана Петрова.

Конспект пишется через Cloud.ru: длинный текст читается частями, потом части
сводятся в один конспект и сохраняются рядом с файлом: «<имя> — конспект.md».
"""

from __future__ import annotations

import io
import time

from .store import Disk, DiskError, unique

PART = 12000        # символов текста в одной части
MAX_PARTS = 8       # дальше начало и конец: конспект книги целиком — работа для фоновой задачи
SUMMARY_TOKENS = 1600

PROMPT = {
    "ru": {
        "part": "Это часть {n} из {total} документа «{name}». Выпиши главное: факты, цифры, даты, решения, выводы. "
                "Кратко, списком, по-русски.\n\n{text}",
        "final": "Составь конспект документа «{name}» по-русски в Markdown: сначала 2–3 предложения, о чём он; потом "
                 "«## Главное» списком; потом, если есть, «## Цифры и сроки» и «## Что сделать». Только по тексту, без "
                 "выдумок. Без заголовка первого уровня.\n\n{text}",
        "file": "конспект", "title": "Конспект", "source": "Источник", "made": "Составлено",
    },
    "en": {
        "part": "This is part {n} of {total} of the document “{name}”. Write down the key points: facts, numbers, dates, "
                "decisions, conclusions. Brief bullet list.\n\n{text}",
        "final": "Write a summary of the document “{name}” in Markdown: first 2–3 sentences on what it is; then "
                 "“## Key points” as a list; then, if any, “## Numbers and dates” and “## To do”. Only from the text. "
                 "No top-level heading.\n\n{text}",
        "file": "summary", "title": "Summary", "source": "Source", "made": "Made",
    },
}


def summarize(cloud, text: str, name: str, lang: str = "ru") -> str:
    P = PROMPT["en" if lang == "en" else "ru"]
    parts = [text[i:i + PART] for i in range(0, len(text), PART)]
    if len(parts) > MAX_PARTS:
        parts = parts[:MAX_PARTS - 2] + parts[-2:]
    if len(parts) == 1:
        joined = parts[0]
    else:
        notes = [cloud.complete([{"role": "user", "content": P["part"].format(n=i + 1, total=len(parts), name=name,
                                                                              text=part)}], max_tokens=700, timeout=120)
                 for i, part in enumerate(parts)]
        joined = "\n\n".join(f"[{i + 1}]\n{n.strip()}" for i, n in enumerate(notes))
    return cloud.complete([{"role": "user", "content": P["final"].format(name=name, text=joined)}],
                          max_tokens=SUMMARY_TOKENS, timeout=180).strip()


def save_summary(disk: Disk, index, cloud, rel: str, lang: str = "ru", memory=None) -> dict:
    if not cloud or not cloud.api_key():
        raise DiskError("Для конспекта нужен ключ Cloud.ru (Настройки → Cloud.ru)")
    path = disk.path(rel)
    if path.is_dir():
        raise DiskError("Конспект делается для файла")
    data = index.text_of(disk.rel(path))
    text = data["text"] or data["photo"] or ""
    if len(text.strip()) < 200:
        raise DiskError("В файле слишком мало текста для конспекта")
    P = PROMPT["en" if lang == "en" else "ru"]
    body = summarize(cloud, text, path.name, lang)
    md = (f"# {P['title']}: {path.stem}\n\n_{P['source']}: [{path.name}]({path.name.replace(' ', '%20')}) · "
          f"{P['made']} {time.strftime('%Y-%m-%d')}_\n\n{body}\n")
    target = unique(path.with_name(f"{path.stem} — {P['file']}.md"))
    raw = md.encode("utf-8")
    entry = disk.upload(disk.rel(target), io.BytesIO(raw), len(raw))
    if memory:
        memory.authored(entry["path"], md)
    return {**entry, "source": disk.rel(path)}


def related(disk: Disk, index, memory, rel: str, limit: int = 8) -> dict:
    path = disk.path(rel)
    rel = disk.rel(path)
    found: dict[str, dict] = {}

    def add(p: str, why: str, score: float) -> None:
        if p == rel or p in found:
            if p in found:
                found[p]["score"] += score
            return
        try:
            entry = disk.entry(disk.path(p))
        except (OSError, DiskError):
            return
        if not entry["dir"]:
            found[p] = {**entry, "why": why, "score": score}

    for hit in index.similar(rel, limit * 2):
        add(hit["path"], "words:" + ", ".join(hit["words"]), hit["score"])
    facts = []
    if memory and getattr(memory, "enabled", False):
        all_facts = memory.facts()
        mine = [f for f in all_facts if rel in (f.get("files") or [])]
        facts = [f["text"] for f in mine][:6]
        about = {a for f in mine for a in f.get("about") or []}
        for f in all_facts:  # те же люди и места — в других файлах
            if about & set(f.get("about") or []):
                for p in f.get("files") or []:
                    add(p, "memory:" + f["text"][:80], 6.0)
        similar = getattr(memory, "similar", None)
        if similar:
            data = index.text_of(rel)
            query = f"{path.stem} {data['text'][:1500] or data['photo'] or ''}"
            try:
                for chunk in similar(query, limit * 2):
                    add(chunk["path"], "meaning", 4.0 * chunk.get("score", 0.5))
            except Exception:  # noqa: BLE001 — нет связи с Cloud.ru: обойдёмся словами и памятью
                pass
    items = sorted(found.values(), key=lambda f: -f["score"])[:limit]
    return {"path": rel, "files": items, "facts": facts}

