"""Свой код: Yakumo читает собственные файлы программы и знает, как она устроена.

Код только читается, никогда не меняется. Файлы программы (ядро, модули,
веб-версия, запуск) режутся на кусочки: в Python по функциям и классам, в
остальных файлах по строкам. Поиск идёт по смыслу, если в Cloud.ru есть модель
эмбеддингов, иначе по словам и именам. «Карта меня» собирается из описаний
модулей и файлов (docstring, NAME, VERSION) без запросов к модели и
обновляется, когда меняются файлы, например после обновления. Настройки,
ключи, данные, Диск и Python рядом с программой не читаются.
Хранится в brain/code.json.
"""

from __future__ import annotations

import ast
import base64
import json
import logging
import os
import re
import threading
from array import array
from pathlib import Path

from .semantic import dot, pack

log = logging.getLogger("yakumo.modules.brain")

ROOTS = ("yakumo", "modules", "tools", "launcher")
TOP = ("README.md", "Yakumo.bat", "Yakumo.pyw")
EXTENSIONS = {".py", ".pyw", ".js", ".css", ".html", ".md", ".txt", ".bat", ".ps1"}
SKIP_DIRS = {"__pycache__", ".git", ".venv", "python", "node_modules", "avatars"}
MAX_FILE = 400_000
MAX_CHUNK = 2500     # символов кода в кусочке
LINES = 60           # строк в кусочке для не-Python
MAX_READ = 200       # строк за одно чтение
PER_SYNC = 96
BATCH = 32
MIN_SCORE = 0.4
WORD = re.compile(r"[A-Za-zА-Яа-яЁё][A-Za-zА-Яа-яЁё0-9]{2,}")


def terms(text: str) -> set[str]:
    """Основы слов и частей имён: disk_sort_plan → disk, sort, plan; camelCase тоже делится."""
    text = re.sub(r"([a-z])([A-Z])", r"\1 \2", text).replace("_", " ")
    return {w.lower()[:5] for w in WORD.findall(text)}  # грубая основа: «разбирает» и «разбор» сходятся


def first_paragraph(doc: str | None, limit: int = 300) -> str:
    if not doc:
        return ""
    return " ".join(doc.strip().split("\n\n")[0].split())[:limit]


def python_chunks(source: str) -> list[dict]:
    """Функции и классы; у больших классов — каждый метод отдельно."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    lines = source.splitlines()
    out = []

    def add(node, prefix=""):
        start = getattr(node, "lineno", 1)
        if getattr(node, "decorator_list", None):
            start = min(d.lineno for d in node.decorator_list)
        end = getattr(node, "end_lineno", start)
        name = prefix + getattr(node, "name", "")
        if isinstance(node, ast.ClassDef) and end - start > LINES * 2:
            out.append({"name": name, "start": start, "end": node.body[0].lineno,
                        "text": "\n".join(lines[start - 1:node.body[0].lineno])[:MAX_CHUNK]})
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    add(child, name + ".")
            return
        out.append({"name": name, "start": start, "end": end, "text": "\n".join(lines[start - 1:end])[:MAX_CHUNK]})

    head = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            add(node)
        else:
            head.append(node)
    if head:  # описание файла, константы и импорты — одним кусочком в начале
        end = max(getattr(n, "end_lineno", 1) for n in head)
        out.insert(0, {"name": "", "start": 1, "end": end, "text": "\n".join(lines[:end])[:MAX_CHUNK]})
    return out


def text_chunks(source: str) -> list[dict]:
    lines = source.splitlines()
    out = []
    for i in range(0, len(lines), LINES):
        part = lines[i:i + LINES]
        found = next((m.group(1) for m in (re.search(r"function\s+(\w+)|^\s*([.#]?[\w-]+)\s*\{", x) for x in part) if m), "")
        out.append({"name": found or "", "start": i + 1, "end": i + len(part), "text": "\n".join(part)[:MAX_CHUNK]})
    return [c for c in out if c["text"].strip()]


class Code:
    def __init__(self, app, path: Path, semantic):
        self.app = Path(app).resolve() if app else None
        self.path = path
        self.semantic = semantic
        self.lock = threading.Lock()
        self.files: dict[str, list] = {}   # путь -> [mtime, размер]
        self.items: list[dict] = []        # {"path", "name", "start", "end", "text", "v"}
        self.map: dict = {}
        self.model: str | None = None
        self._load()

    # --- Файл ---

    def _load(self) -> None:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            self.files, self.model, self.map = data["files"], data.get("model"), data.get("map") or {}
            for c in data["chunks"]:
                v = None
                if c.get("v"):
                    v = array("f")
                    v.frombytes(base64.b64decode(c["v"]))
                self.items.append({**{k: c[k] for k in ("path", "name", "start", "end", "text")}, "v": v})
        except (OSError, ValueError, KeyError, TypeError):
            self.files, self.items, self.map = {}, [], {}

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = {"model": self.model, "files": self.files, "map": self.map,
                "chunks": [{**{k: c[k] for k in ("path", "name", "start", "end", "text")},
                            "v": base64.b64encode(c["v"].tobytes()).decode("ascii") if c["v"] is not None else None}
                           for c in self.items]}
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, self.path)

    # --- Какие файлы читать ---

    def sources(self) -> dict[str, Path]:
        if self.app is None or not self.app.is_dir():
            return {}
        found = {}
        for name in TOP:
            if (self.app / name).is_file():
                found[name] = self.app / name
        for root in ROOTS:
            base = self.app / root
            if not base.is_dir():
                continue
            for folder, dirs, names in os.walk(base):
                dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS and not d.startswith("."))
                for name in sorted(names):
                    full = Path(folder) / name
                    if full.suffix.lower() in EXTENSIONS and not full.is_symlink():
                        found[full.relative_to(self.app).as_posix()] = full
        return found

    def _file(self, rel: str) -> Path:
        """Путь к файлу программы из индекса; всё остальное читать нельзя."""
        if rel not in self.files or self.app is None:
            raise ValueError("Такого файла в моём коде нет" if rel else "Нужен путь к файлу")
        return self.app / rel

    # --- Разбор ---

    def sync(self, vectors: bool = True) -> int:
        """Новые и изменённые файлы — заново в кусочки, удалённые — из индекса; карта; затем порция векторов."""
        with self.lock:
            sources = self.sources()
            changed = False
            stamps = {}
            for rel, full in sources.items():
                try:
                    st = full.stat()
                except OSError:
                    continue
                if st.st_size <= MAX_FILE:
                    stamps[rel] = [int(st.st_mtime), st.st_size]
            gone = [p for p in self.files if self.files[p] != stamps.get(p)]
            if gone:
                gone_set = set(gone)
                self.items = [c for c in self.items if c["path"] not in gone_set]
                for p in gone:
                    del self.files[p]
                changed = True
            for rel, stamp in stamps.items():
                if rel in self.files:
                    continue
                try:
                    source = sources[rel].read_text(encoding="utf-8-sig", errors="replace")
                except OSError:
                    continue
                parts = python_chunks(source) if rel.endswith((".py", ".pyw")) else text_chunks(source)
                self.items += [{"path": rel, **c, "v": None} for c in parts]
                self.files[rel] = stamp
                changed = True
            if changed or not self.map:
                self.map = self._build_map(sources)
                changed = True
            done = self._vectors() if vectors else 0
            if changed or done:
                self._save()
            return done

    def _vectors(self) -> int:
        semantic = self.semantic
        model = getattr(semantic, "model", None)
        if model != self.model:
            self.model = model
            for c in self.items:
                c["v"] = None
        if not model or not semantic.ready():
            return 0
        done = 0
        todo = [c for c in self.items if c["v"] is None][:PER_SYNC]
        try:
            for i in range(0, len(todo), BATCH):
                part = todo[i:i + BATCH]
                texts = [f"{c['path']} {c['name']}\n{c['text'][:1500]}" for c in part]
                for c, vec in zip(part, semantic.cloud.embed(texts, model)):
                    c["v"] = pack(vec)
                    done += 1
        except Exception as exc:  # noqa: BLE001 — доделаем в следующий раз
            log.warning("Свой код: векторы не посчитаны: %s", exc)
        return done

    # --- Карта меня ---

    def _build_map(self, sources: dict[str, Path]) -> dict:
        modules, core = {}, []
        for rel, full in sources.items():
            if not rel.endswith((".py", ".pyw")):
                continue
            try:
                tree = ast.parse(full.read_text(encoding="utf-8-sig", errors="replace"))
            except (OSError, SyntaxError):
                continue
            doc = first_paragraph(ast.get_docstring(tree))
            consts = {t.id: n.value.value for n in tree.body if isinstance(n, ast.Assign)
                      for t in n.targets if isinstance(t, ast.Name) and t.id in ("NAME", "VERSION")
                      and isinstance(n.value, ast.Constant) and isinstance(n.value.value, str)}
            parts = rel.split("/")
            if parts[0] == "modules" and len(parts) >= 2:
                key = parts[1].removesuffix(".py")
                entry = modules.setdefault(key, {"id": key, "name": key, "version": "", "about": "", "files": []})
                entry["files"].append({"path": rel, "about": first_paragraph(doc, 160), "lines": self._lines(rel)})
                if len(parts) == 2 or parts[-1] == "__init__.py":
                    entry.update(name=consts.get("NAME", key), version=consts.get("VERSION", ""), about=doc)
            elif parts[0] == "yakumo" or len(parts) == 1:
                core.append({"path": rel, "about": first_paragraph(doc, 160), "lines": self._lines(rel)})
        for entry in modules.values():
            entry["files"] += [{"path": rel, "about": "", "lines": self._lines(rel)} for rel in sources
                               if rel.startswith(f"modules/{entry['id']}/") and not rel.endswith(".py")]
        return {"modules": sorted(modules.values(), key=lambda m: m["id"]), "core": core,
                "files": len(sources), "chunks": len(self.items)}

    def _lines(self, rel: str) -> int:
        return max((c["end"] for c in self.items if c["path"] == rel), default=0)

    def overview(self, limit: int = 12) -> list[str]:
        """Строки для подсказки чата: модуль — что делает."""
        return [f"{m['name']}" + (f" {m['version']}" if m.get("version") else "") + (f" — {m['about'][:140]}" if m.get("about") else "")
                for m in self.map.get("modules", [])[:limit]]

    # --- Поиск и чтение ---

    def search(self, query: str, limit: int = 5) -> list[dict]:
        """Кусочки своего кода по смыслу или по словам: [{"path", "name", "start", "end", "text", "score"}]."""
        vec = None
        if self.model and any(c["v"] is not None for c in self.items):
            vec = self.semantic.query_vector(query)
        if vec is not None:
            scored = [(dot(vec, c["v"]), c) for c in self.items if c["v"] is not None and len(c["v"]) == len(vec)]
            scored = [(s, c) for s, c in scored if s >= MIN_SCORE]
        else:
            q = terms(query)
            scored = []
            for c in self.items if q else []:
                name = terms(f"{c['path']} {c['name']}")
                hits = len(q & terms(c["text"])) + 2 * len(q & name)
                if hits:
                    scored.append((hits / len(q), c))
        scored.sort(key=lambda x: -x[0])
        return [{**{k: c[k] for k in ("path", "name", "start", "end", "text")}, "score": round(s, 3)}
                for s, c in scored[:limit]]

    def read(self, rel: str, start: int = 1, end: int | None = None) -> dict:
        full = self._file(str(rel or "").replace("\\", "/").lstrip("/"))
        lines = full.read_text(encoding="utf-8-sig", errors="replace").splitlines()
        start = max(1, int(start or 1))
        end = min(len(lines), int(end or start + MAX_READ - 1), start + MAX_READ - 1)
        return {"path": rel, "start": start, "end": end, "total": len(lines),
                "text": "\n".join(f"{n}: {line}" for n, line in enumerate(lines[start - 1:end], start))}

    def around(self, place: str, radius: int = 25) -> dict | None:
        """«modules/disk/extract.py:120 (pdf_text)» → строки вокруг этого места."""
        m = re.match(r"\s*([\w./-]+):(\d+)", place or "")
        if not m or m.group(1) not in self.files:
            return None
        line = int(m.group(2))
        return self.read(m.group(1), line - radius, line + radius)

    def status(self) -> dict:
        return {"files": len(self.files), "chunks": len(self.items),
                "vectors": sum(c["v"] is not None for c in self.items), "model": self.model}
