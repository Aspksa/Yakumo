"""Инструменты «Диска» для чата: Yakumo ищет, читает и предлагает разложить файлы.

Чтение (поиск, список, текст файла) выполняется сразу. Изменения (папки,
перенос, переименование, корзина, новый текстовый файл) попадают в план,
который пользователь подтверждает кнопкой в чате.

Файлы, которые написала Yakumo, отдаются «Памяти» (ctx.memory.authored): если вы
потом поправите такой файл, Yakumo сравнит версии и поймёт, что делать иначе.
"""

from __future__ import annotations

import difflib
import io
import time

from . import tables
from .extract import extract
from .store import Disk, DiskError

READ_LIMIT = 12000  # символов текста файла для модели
WRITE_LIMIT = 200_000  # символов в файле, который пишет Yakumo
WRITE_EXT = (".md", ".txt")
DIFF_LIMIT = 10000     # символов разницы версий для модели


def _when(t: int) -> str:
    return time.strftime("%Y-%m-%d %H:%M", time.localtime(t))


def _paths(args: dict) -> list[str]:
    paths = args.get("paths")
    if isinstance(paths, str):
        paths = [paths]
    if not isinstance(paths, list) or not paths or not all(isinstance(p, str) for p in paths):
        raise DiskError("Нужен список paths")
    return paths


def register(ctx, disk: Disk, index, search) -> None:
    ru = lambda: ctx.config.language != "en"  # noqa: E731
    q = lambda s: f"«{s}»" if ru() else f"“{s}”"  # noqa: E731
    name_of = lambda p: (p or "").replace("\\", "/").rstrip("/").split("/")[-1] or ("Диск" if ru() else "Drive")  # noqa: E731

    def find(args):
        query = str(args.get("query", ""))
        found = search(query, limit=25)
        items = [{"path": i["path"], "folder": i["dir"], "size": i["size"], "modified": _when(i["mtime"]),
                  "found_in": i.get("match", "name"), "snippet": i.get("snippet")} for i in found["items"]]
        # Память подсказывает, о каком файле речь: «мой договор» — это аренда в Москве, лежит там-то.
        memory = getattr(ctx, "memory", None)
        if memory:
            remembered = [{"fact": f["text"], "files": f["files"]} for f in memory.recall(query, 8)["facts"]
                          if f.get("files")]
            if remembered:
                return {"files": items, "from_memory": remembered}
        return items

    def listing(args):
        res = disk.list(args.get("path") or "")
        items = sorted(res["items"], key=lambda i: (not i["dir"], i["name"].lower()))
        return {"path": res["path"], "total": len(items),
                "items": [{"name": i["name"], "folder": i["dir"], "size": i["size"], "modified": _when(i["mtime"])}
                          for i in items[:300]]}

    def read(args):
        rel = str(args.get("path", ""))
        path = disk.path(rel)
        if path.is_dir():
            raise DiskError("Это папка: используй disk_list")
        data = index.text_of(disk.rel(path))
        text = data["text"]
        return {"path": disk.rel(path), "size": path.stat().st_size, "photo_description": data["photo"],
                "text": text[:READ_LIMIT], "truncated": len(text) > READ_LIMIT,
                "note": None if text or data["photo"] else "текст из этого файла не извлекается"}

    def write(args):
        rel, text = str(args.get("path", "")).strip().strip("/"), args.get("text")
        if not rel.lower().endswith(WRITE_EXT):
            raise DiskError("Можно создать только .md или .txt")
        if not isinstance(text, str) or not text.strip() or len(text) > WRITE_LIMIT:
            raise DiskError("Нужен текст файла")
        data = text.encode("utf-8")
        entry = disk.upload(rel, io.BytesIO(data), len(data))  # имя занято — допишет (2), старое не трогает
        memory = getattr(ctx, "memory", None)
        if memory:
            memory.authored(entry["path"], text)
        return {"path": entry["path"]}

    def table(args):
        rel = str(args.get("path", ""))
        where = args.get("where") if isinstance(args.get("where"), dict) else None
        sums = args.get("sum")
        sums = [sums] if isinstance(sums, str) else sums if isinstance(sums, list) else None
        try:
            return {"path": rel, **tables.query(disk.path(rel), args.get("sheet"), where, sums, args.get("group_by"))}
        except tables.TableError as exc:
            raise DiskError(str(exc)) from exc

    def compare(args):
        a, b = disk.path(str(args.get("a", ""))), disk.path(str(args.get("b", "")))
        old, new = extract(a), extract(b)
        if not old and not new:
            raise DiskError("Из этих файлов не извлекается текст")
        lines = list(difflib.unified_diff(old.splitlines(), new.splitlines(), disk.rel(a), disk.rel(b),
                                          lineterm="", n=1))
        text = "\n".join(lines)
        return {"a": disk.rel(a), "b": disk.rel(b), "same": not lines,
                "similarity": round(difflib.SequenceMatcher(None, old[:20000], new[:20000]).ratio(), 3),
                "added_lines": sum(1 for x in lines if x.startswith("+") and not x.startswith("+++")),
                "removed_lines": sum(1 for x in lines if x.startswith("-") and not x.startswith("---")),
                "diff": text[:DIFF_LIMIT], "truncated": len(text) > DIFF_LIMIT,
                "note": "- строки из a, + строки из b. Объясни пользователю главные отличия по смыслу."}

    def info(_args):
        u = disk.usage()
        return {"used_bytes": u["used"], "trash_bytes": u["trash"], "free_bytes": u["free"],
                "total_bytes": u["total"], "files": u["files"], "folders": u["folders"]}

    def mkdir(args):
        return disk.makedirs(str(args.get("path", "")))

    def move(args):
        return disk.move(_paths(args), str(args.get("to", "")))

    def rename(args):
        return disk.rename(str(args.get("path", "")), str(args.get("name", "")))

    def delete(args):
        return {"count": disk.delete(_paths(args))}

    def many(args) -> str:
        try:
            paths = _paths(args)
        except DiskError:
            return "?"
        return q(name_of(paths[0])) if len(paths) == 1 else (
            f"{len(paths)} файлов" if ru() else f"{len(paths)} items")

    tools = [
        ("disk_search", "поиск файлов на Диске пользователя по имени, тексту внутри документов и описаниям фото. "
                        'args: {"query": "слова"}', find, False,
         lambda a: (f"Ищу на Диске: {q(a.get('query', ''))}" if ru() else f"Searching Drive: {q(a.get('query', ''))}")),
        ("disk_list", 'содержимое папки. args: {"path": "папка/внутри" или "" для корня}', listing, False,
         lambda a: (f"Смотрю папку {q(name_of(a.get('path')))}" if ru() else f"Opening {q(name_of(a.get('path')))}")),
        ("disk_read", "текст документа (txt, docx, xlsx, pptx, pdf и др.) или описание фото, чтобы пересказать "
                      'или ответить по нему. args: {"path": "путь/к/файлу"}', read, False,
         lambda a: (f"Читаю {q(name_of(a.get('path')))}" if ru() else f"Reading {q(name_of(a.get('path')))}")),
        ("disk_table", 'таблица Excel/CSV: строки, отбор, суммы и группировки (считать только так, не в уме). '
                       'args: {"path": "путь.xlsx", "sheet": "лист (необязательно)", "where": {"колонка": "текст"}, '
                       '"sum": ["колонка"], "group_by": "колонка"}', table, False,
         lambda a: (f"Считаю по таблице {q(name_of(a.get('path')))}" if ru() else f"Reading table {q(name_of(a.get('path')))}")),
        ("disk_compare", 'сравнить две версии документа: что добавлено и что удалено. args: {"a": "старый путь", '
                         '"b": "новый путь"}', compare, False,
         lambda a: (f"Сравниваю {q(name_of(a.get('a')))} и {q(name_of(a.get('b')))}" if ru()
                    else f"Comparing {q(name_of(a.get('a')))} and {q(name_of(a.get('b')))}")),
        ("disk_info", "сколько места занято и свободно, сколько файлов. args: {}", info, False,
         lambda a: "Смотрю место на Диске" if ru() else "Checking Drive space"),
        ("disk_mkdir", 'создать папку (и недостающие родительские). args: {"path": "Фото/2024"}', mkdir, True,
         lambda a: (f"Создать папку {q(a.get('path', ''))}" if ru() else f"Create folder {q(a.get('path', ''))}")),
        ("disk_move", 'переместить файлы или папки в папку. args: {"paths": ["путь", ...], "to": "папка" или ""}',
         move, True,
         lambda a: (f"Переместить {many(a)} → {q(name_of(a.get('to')))}" if ru()
                    else f"Move {many(a)} → {q(name_of(a.get('to')))}")),
        ("disk_rename", 'переименовать. args: {"path": "путь", "name": "новое имя.расширение"}', rename, True,
         lambda a: (f"Переименовать {q(name_of(a.get('path')))} → {q(a.get('name', ''))}" if ru()
                    else f"Rename {q(name_of(a.get('path')))} → {q(a.get('name', ''))}")),
        ("disk_write", 'создать текстовый файл на Диске (.md или .txt): конспект, план, письмо, таблицу в Markdown. '
                       'args: {"path": "Папка/имя.md", "text": "содержимое"}', write, True,
         lambda a: (f"Создать файл {q(name_of(a.get('path')))}" if ru() else f"Create file {q(name_of(a.get('path')))}")),
        ("disk_delete", 'удалить в корзину (можно восстановить). args: {"paths": ["путь", ...]}', delete, True,
         lambda a: (f"Удалить в корзину {many(a)}" if ru() else f"Move to trash {many(a)}")),
    ]
    for name, description, run, change, title in tools:
        ctx.chat_tool(name, description, run, change=change, title=title)
