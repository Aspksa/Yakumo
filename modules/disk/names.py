"""Понятные имена: вместо «IMG_4512.jpg» и «Скан001.pdf» — «Кошка на диване 2024-05-12.jpg».

Имя придумывается по тексту документа или описанию фото (через Cloud.ru, если
есть ключ), иначе — по первой строке текста и дате. Если вы поправили
предложенное имя, кицунэ запоминает пример и дальше пишет в вашем стиле
(``<Диск>/.yakumo/names.json``).
"""

from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path

from .store import BAD_CHARS, Disk, DiskError, kind_of, unique

MAX_ITEMS = 40
EXAMPLES = 8
NAME_LEN = 60
# То, из чего состоят имена «ни о чём»: камера, сканер, мессенджеры, «Новый документ».
GENERIC = {"img", "image", "imag", "dsc", "dscn", "dscf", "pxl", "mvimg", "vid", "video", "photo", "pic", "picture",
           "scan", "scanned", "скан", "document", "doc", "документ", "file", "файл", "untitled", "без имени",
           "безымянный", "new document", "новый документ", "новый текстовый документ", "new text document",
           "документ microsoft word", "microsoft word document", "лист microsoft excel", "книга", "book",
           "копия", "copy", "screenshot", "screen shot", "снимок экрана", "снимок", "whatsapp image",
           "whatsapp video", "img wa", "vid wa", "photo telegram", "telegram", "рисунок", "изображение", "фото",
           "видео", "wa", "p", "sam", "capture", "download", "загрузка", "out", "output", "page", "страница", "jpeg"}
STAMP = re.compile(r"(20\d{2})[-_.]?(0[1-9]|1[0-2])[-_.]?(0[1-9]|[12]\d|3[01])(?:[-_ T.]?([01]\d|2[0-3])[-_.:]?([0-5]\d))?")
KIND_WORD = {"ru": {"image": "Фото", "video": "Видео", "audio": "Запись", "pdf": "Документ", "doc": "Документ",
                    "text": "Заметка", "sheet": "Таблица", "slides": "Презентация"},
             "en": {"image": "Photo", "video": "Video", "audio": "Recording", "pdf": "Document", "doc": "Document",
                    "text": "Note", "sheet": "Spreadsheet", "slides": "Presentation"}}

PROMPT = {
    "ru": """Придумай понятные имена файлам на Диске пользователя. Имя — 2–6 слов по-русски, о чём файл: тип документа,
о ком или о чём, при необходимости дата (ГГГГ-ММ-ДД). Без расширения, без кавычек и символов < > : " / \\ | ? *.
{examples}
Файлы:
{files}

Ответь ТОЛЬКО JSON: {{"names": [{{"n": номер, "name": "имя"}}]}}. Если о файле ничего не понятно — пропусти его.""",
    "en": """Suggest clear names for files on the user's Drive. A name is 2–6 words describing the file: document type,
who or what it is about, and a date (YYYY-MM-DD) if useful. No extension, no quotes or < > : " / \\ | ? *.
{examples}
Files:
{files}

Reply ONLY with JSON: {{"names": [{{"n": number, "name": "name"}}]}}. Skip files you can't tell anything about.""",
}


def meaningless(name: str) -> bool:
    """«IMG_4512.jpg», «Скан001.pdf», «Новый документ (3).docx» — имя ничего не говорит о файле."""
    stem = Path(name).stem if "." in name else name
    core = re.sub(r"[\d_\-\s().,#№+]+", " ", stem.lower()).strip()
    core = re.sub(r"\s+", " ", core)
    return not core or core in GENERIC or bool(re.fullmatch(r"[0-9a-f\s]{12,}", stem.lower()))


def stamp(name: str, mtime: int | None = None) -> str:
    """Дата из имени (камеры пишут IMG_20240512_143000) или из времени изменения."""
    m = STAMP.search(name)
    if m:
        return f"{m[1]}-{m[2]}-{m[3]}" + (f" {m[4]}-{m[5]}" if m[4] else "")
    return time.strftime("%Y-%m-%d", time.localtime(mtime)) if mtime else ""


def clean(name: str) -> str:
    name = "".join(" " if c in BAD_CHARS else c for c in name)
    name = re.sub(r"\s+", " ", name).strip(" .-_«»\"'")
    return name[:NAME_LEN].rstrip(" .-")


def first_line(text: str) -> str:
    """Заголовок документа: первая строка, похожая на название."""
    for line in text.splitlines()[:30]:
        line = " ".join(line.split())
        letters = sum(c.isalpha() for c in line)
        if 6 <= len(line) <= 90 and letters >= len(line) * 0.6 and len(line.split()) >= 2:
            return line
    return ""


def from_photo(description: str) -> str:
    first = re.split(r"(?<=[.!?])\s", description.strip(), maxsplit=1)[0].rstrip(".!?")
    first = re.sub(r"^(на (этом )?(фото|фотографии|изображении|снимке)( изображен[аоы]?)?|this (image|photo) "
                   r"shows|the (image|photo) shows|(an? )?(image|photo) of)\s*[,:]?\s*", "", first, flags=re.I)
    words = first.split()[:6]
    return " ".join(words)[:1].upper() + " ".join(words)[1:] if words else ""


def heuristic(item: dict, lang: str) -> tuple[str, str] | None:
    """(имя без расширения, откуда оно) без нейросети."""
    when = stamp(item["name"], item.get("mtime"))
    title = first_line(item.get("text") or "")
    if title:
        return clean(title), "text"
    if item.get("photo"):
        about = from_photo(item["photo"])
        if about:
            return clean(f"{about} {when[:10]}".strip()), "photo"
    if when:
        word = KIND_WORD[lang].get(kind_of(item["name"]), KIND_WORD[lang]["doc"])
        return clean(f"{word} {when}"), "date"
    return None


class Namer:
    def __init__(self, disk: Disk, index, cloud=None, language=lambda: "ru"):
        self.disk = disk
        self.index = index
        self.cloud = cloud
        self.language = language
        self.path = disk.meta / "names.json"

    def _examples(self) -> list[dict]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return data.get("examples", []) if isinstance(data, dict) else []
        except (OSError, ValueError):
            return []

    def _learn(self, suggested: str, final: str) -> None:
        examples = [e for e in self._examples() if e.get("final") != final][-(EXAMPLES - 1):]
        examples.append({"suggested": suggested, "final": final})
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"examples": examples}, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, self.path)

    def candidates(self, rel: str, only_bad: bool = True) -> list[dict]:
        path = self.disk.path(rel)
        entries = ([e for e in self.disk.list(rel)["items"] if not e["dir"]] if path.is_dir()
                   else [self.disk.entry(path)])
        if only_bad and path.is_dir():
            entries = [e for e in entries if meaningless(e["name"])]
        out = []
        for e in sorted(entries, key=lambda e: e["name"].lower())[:MAX_ITEMS]:
            data = self.index.text_of(e["path"]) if e["kind"] != "video" else {"text": "", "photo": None}
            out.append({**e, "text": data["text"][:1500], "photo": data["photo"]})
        return out

    def suggest(self, rel: str, only_bad: bool = True) -> dict:
        lang = "en" if self.language() == "en" else "ru"
        items = self.candidates(rel, only_bad)
        names: dict[int, tuple[str, str]] = {}
        for i, item in enumerate(items):
            guess = heuristic(item, lang)
            if guess:
                names[i] = guess
        smart = [i for i, item in enumerate(items) if item["text"].strip() or item["photo"]]
        if smart and self.cloud and self.cloud.api_key():
            try:
                names.update(self._ask(items, smart, lang))
            except Exception:  # noqa: BLE001 — нет связи: остаются имена без нейросети
                pass
        out = []
        for i, item in enumerate(items):
            if i not in names or not names[i][0]:
                continue
            ext = Path(item["name"]).suffix
            name = names[i][0] + ext
            if name.lower() == item["name"].lower():
                continue
            out.append({"path": item["path"], "name": item["name"], "kind": item["kind"], "suggestion": name,
                        "source": names[i][1]})
        return {"items": out, "checked": len(items)}

    def _ask(self, items: list[dict], picked: list[int], lang: str) -> dict[int, tuple[str, str]]:
        examples = self._examples()
        ex = ""
        if examples:
            head = ("Пользователь поправлял имена так — пиши в его стиле:" if lang == "ru"
                    else "The user corrected names like this — follow their style:")
            ex = head + "\n" + "\n".join(f"- «{e['suggested']}» → «{e['final']}»" for e in examples) + "\n"
        files = []
        for i in picked:
            item = items[i]
            about = item["text"][:600] or item["photo"] or ""
            files.append(f"{i}. {item['name']} (дата {stamp(item['name'], item.get('mtime'))}): "
                         f"{' '.join(about.split())}")
        reply = self.cloud.complete([{"role": "user", "content": PROMPT[lang].format(
            examples=ex, files="\n".join(files))}], max_tokens=900, timeout=60)
        m = re.search(r"\{.*\}", reply, re.S)
        data = json.loads(m[0]) if m else {}
        out = {}
        for x in data.get("names") or []:
            if isinstance(x, dict) and isinstance(x.get("name"), str) and str(x.get("n", "")).isdigit():
                n = int(x["n"])
                if n in picked and clean(x["name"]):
                    out[n] = (clean(x["name"]), "ai")
        return out

    def apply(self, items) -> list[dict]:
        """Переименовать; если вы поправили предложенное имя — это пример для следующих раз."""
        if not isinstance(items, list):
            raise DiskError("Ожидается список")
        done = []
        for x in items[:MAX_ITEMS * 5]:
            if not isinstance(x, dict) or not isinstance(x.get("path"), str) or not isinstance(x.get("name"), str):
                continue
            src = self.disk.path(x["path"])
            name = clean(Path(x["name"]).stem) + (Path(x["name"]).suffix if Path(x["name"]).suffix else src.suffix)
            if not Path(name).stem or name == src.name:
                continue
            target = unique(src.with_name(name)) if src.with_name(name).exists() else src.with_name(name)
            done.append(self.disk.rename(x["path"], target.name))
            suggested = x.get("suggested")
            if isinstance(suggested, str) and suggested and suggested != target.name:
                self._learn(Path(suggested).stem, Path(target.name).stem)
        return done
