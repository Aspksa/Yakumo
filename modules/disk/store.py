"""Хранилище «Диска»: файлы и папки внутри одной корневой папки.

Все пути внутри — относительные (``Фото/2024/море.jpg``), поэтому при смене
буквы переносного диска ничего не ломается. Служебные данные (корзина,
ссылки, недокачанные файлы) лежат в ``<корень>/.yakumo`` и в списках не видны.
"""

from __future__ import annotations

import json
import mimetypes
import os
import secrets
import shutil
import sys
import threading
import time
import uuid
from pathlib import Path
from typing import BinaryIO, Iterable

SERVICE = ".yakumo"
CHUNK = 1024 * 1024
RESERVE = 64 * 1024 * 1024  # сколько места оставить свободным при загрузке
BAD_CHARS = set('<>:"/\\|?*') | {chr(c) for c in range(32)}
# Имена, которые Windows не даёт создать ни в одной папке.
RESERVED = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}

KINDS = {
    "image": "jpg jpeg png gif webp bmp svg ico heic heif avif tif tiff",
    "video": "mp4 webm mkv mov avi wmv m4v 3gp ogv mpg mpeg",
    "audio": "mp3 wav ogg oga flac m4a aac opus wma",
    "pdf": "pdf",
    "text": "txt md log csv tsv json xml yml yaml ini cfg conf toml py js ts css html htm bat cmd ps1 sh c h cpp "
            "cs java go rs sql srt",
    "doc": "doc docx odt rtf",
    "sheet": "xls xlsx ods",
    "slides": "ppt pptx odp",
    "archive": "zip rar 7z tar gz bz2 xz",
    "book": "epub fb2 djvu mobi",
    "app": "exe msi apk",
}
KIND_BY_EXT = {ext: kind for kind, exts in KINDS.items() for ext in exts.split()}
MIME = {".mkv": "video/x-matroska", ".webp": "image/webp", ".heic": "image/heic", ".avif": "image/avif",
        ".m4a": "audio/mp4", ".flac": "audio/flac", ".opus": "audio/ogg", ".md": "text/markdown",
        ".fb2": "application/xml", ".epub": "application/epub+zip"}


class DiskError(ValueError):
    """Понятная пользователю ошибка (уходит в ответ как 400)."""


def kind_of(name: str) -> str:
    return KIND_BY_EXT.get(Path(name).suffix.lower().lstrip("."), "file")


def mime_of(name: str) -> str:
    ext = Path(name).suffix.lower()
    return MIME.get(ext) or mimetypes.guess_type(name)[0] or "application/octet-stream"


def check_name(name: str) -> str:
    """Имя файла или папки, допустимое в Windows."""
    if not isinstance(name, str):
        raise DiskError("Нужно имя")
    name = name.strip()
    if not name or name in (".", ".."):
        raise DiskError("Пустое имя")
    if len(name) > 255:
        raise DiskError("Слишком длинное имя")
    bad = sorted(set(name) & BAD_CHARS)
    if bad:
        shown = " ".join(c if c.isprintable() else "?" for c in bad)
        raise DiskError(f"Недопустимые символы в имени: {shown}")
    if name.endswith("."):
        raise DiskError("Имя не может заканчиваться точкой")
    if name.split(".")[0].upper().rstrip() in RESERVED:
        raise DiskError(f"Windows не разрешает имя «{name}»")
    if name.lower() == SERVICE:
        raise DiskError("Это имя занято служебной папкой")
    return name


def split_rel(rel: str | None) -> list[str]:
    """«Фото\\2024/море.jpg» -> ["Фото", "2024", "море.jpg"]; выход из корня запрещён."""
    parts = [p for p in (rel or "").replace("\\", "/").split("/") if p not in ("", ".")]
    if ".." in parts:
        raise DiskError("Недопустимый путь")
    return parts


def unique(path: Path) -> Path:
    """Свободное имя рядом: «отчёт.docx» -> «отчёт (2).docx»."""
    if not path.exists():
        return path
    stem, suffix = (path.name, "") if path.is_dir() else (path.stem, path.suffix)
    n = 2
    while True:
        cand = path.with_name(f"{stem} ({n}){suffix}")
        if not cand.exists():
            return cand
        n += 1


class Disk:
    def __init__(self, root: Path):
        self.root = Path(os.path.realpath(root))
        self.meta = self.root / SERVICE
        self.trash_dir = self.meta / "trash"
        self.tmp_dir = self.meta / "tmp"
        for d in (self.root, self.trash_dir, self.tmp_dir):
            d.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self._used: dict | None = None
        # Недокачанные файлы от прошлого запуска.
        for part in self.tmp_dir.glob("*.part"):
            part.unlink(missing_ok=True)

    # --- Пути ---

    def path(self, rel: str | None, must_exist: bool = True) -> Path:
        parts = split_rel(rel)
        if parts and parts[0].lower() == SERVICE:
            raise DiskError("Недопустимый путь")
        path = self.root.joinpath(*parts)
        # Ссылки и точки соединения не должны уводить за пределы «Диска».
        real, root = os.path.normcase(os.path.realpath(path)), os.path.normcase(self.root)
        if os.path.commonpath([real, root]) != root:
            raise DiskError("Недопустимый путь")
        if must_exist and not path.exists():
            raise FileNotFoundError(rel)
        return path

    def rel(self, path: Path) -> str:
        return path.relative_to(self.root).as_posix()

    def entry(self, path: Path) -> dict:
        st = path.stat()
        is_dir = path.is_dir()
        return {"name": path.name, "path": self.rel(path), "dir": is_dir,
                "size": None if is_dir else st.st_size, "mtime": int(st.st_mtime),
                "kind": "folder" if is_dir else kind_of(path.name)}

    def _children(self, folder: Path) -> Iterable[Path]:
        for child in folder.iterdir():
            if folder == self.root and child.name.lower() == SERVICE:
                continue
            yield child

    def _changed(self) -> None:
        self._used = None

    # --- Просмотр ---

    def list(self, rel: str | None) -> dict:
        folder = self.path(rel)
        if not folder.is_dir():
            raise DiskError("Это не папка")
        items = []
        for child in self._children(folder):
            try:
                items.append(self.entry(child))
            except OSError:
                continue  # файл заняли или удалили во время чтения
        return {"path": self.rel(folder) if folder != self.root else "", "items": items}

    def search(self, query: str, rel: str | None = None, limit: int = 500) -> dict:
        query = (query or "").strip().casefold()
        if not query:
            return {"items": [], "more": False}
        start = self.path(rel)
        found: list[dict] = []
        for dirpath, dirnames, filenames in os.walk(start):
            here = Path(dirpath)
            if here == self.root:
                dirnames[:] = [d for d in dirnames if d.lower() != SERVICE]
            for name in [*dirnames, *filenames]:
                if query in name.casefold():
                    try:
                        found.append(self.entry(here / name))
                    except OSError:
                        continue
                    if len(found) >= limit:
                        return {"items": found, "more": True}
        return {"items": found, "more": False}

    def usage(self) -> dict:
        du = shutil.disk_usage(self.root)
        with self.lock:
            if self._used is None:
                files = folders = size = 0
                for dirpath, dirnames, filenames in os.walk(self.root):
                    if Path(dirpath) == self.root:
                        dirnames[:] = [d for d in dirnames if d.lower() != SERVICE]
                    folders += len(dirnames)
                    files += len(filenames)
                    size += sum(_size(Path(dirpath) / f) for f in filenames)
                trash = sum(_size(Path(dp) / f) for dp, _, fs in os.walk(self.trash_dir) for f in fs)
                self._used = {"used": size, "trash": trash, "files": files, "folders": folders}
            return {**self._used, "free": du.free, "total": du.total}

    # --- Изменения ---

    def mkdir(self, parent: str | None, name: str) -> dict:
        folder = self.path(parent)
        with self.lock:
            target = folder / check_name(name)
            if target.exists():
                raise DiskError(f"«{target.name}» уже есть")
            target.mkdir()
            self._changed()
            return self.entry(target)

    def rename(self, rel: str, name: str) -> dict:
        src = self.path(rel)
        if src == self.root:
            raise DiskError("Корень переименовать нельзя")
        with self.lock:
            dst = src.with_name(check_name(name))
            # Смена только регистра букв («фото» -> «Фото») в Windows — то же имя.
            if dst.exists() and dst.name.lower() != src.name.lower():
                raise DiskError(f"«{dst.name}» уже есть")
            src.rename(dst)
            self._relink(self.rel(src), self.rel(dst))
            return self.entry(dst)

    def move(self, rels: list[str], to: str | None, copy: bool = False) -> list[dict]:
        dest = self.path(to)
        if not dest.is_dir():
            raise DiskError("Нужно выбрать папку")
        done = []
        with self.lock:
            for rel in _as_list(rels):
                src = self.path(rel)
                if src == self.root:
                    raise DiskError("Корень переместить нельзя")
                if src.is_dir() and (dest == src or src in dest.parents):
                    raise DiskError(f"Папку «{src.name}» нельзя положить в саму себя")
                if not copy and src.parent == dest:
                    done.append(self.entry(src))
                    continue
                target = unique(dest / src.name)
                if copy:
                    if src.is_dir():
                        shutil.copytree(src, target)
                    else:
                        shutil.copy2(src, target)
                else:
                    shutil.move(str(src), str(target))
                    self._relink(self.rel(src), self.rel(target))
                done.append(self.entry(target))
            self._changed()
        return done

    def upload(self, rel: str, stream: BinaryIO, length: int) -> dict:
        """Записать файл из потока; rel может содержать подпапки (загрузка папки)."""
        parts = split_rel(rel)
        if not parts:
            raise DiskError("Нужно имя файла")
        names = [check_name(p) for p in parts]
        if length < 0:
            raise DiskError("Неизвестен размер файла")
        if length > shutil.disk_usage(self.root).free - RESERVE:
            raise DiskError("Не хватает места на диске")
        part = self.tmp_dir / f"{uuid.uuid4().hex}.part"
        try:
            with open(part, "wb") as out:
                left = length
                while left:
                    chunk = stream.read(min(CHUNK, left))
                    if not chunk:
                        raise DiskError("Загрузка прервалась")
                    out.write(chunk)
                    left -= len(chunk)
            with self.lock:
                folder = self.path("/".join(names[:-1]), must_exist=False)
                folder.mkdir(parents=True, exist_ok=True)
                target = unique(folder / names[-1])
                os.replace(part, target)
                self._changed()
                return self.entry(target)
        finally:
            part.unlink(missing_ok=True)

    # --- Корзина ---

    def _trash_index(self) -> dict:
        return _read_json(self.meta / "trash.json")

    def delete(self, rels: list[str]) -> int:
        with self.lock:
            index = self._trash_index()
            count = 0
            for rel in _as_list(rels):
                src = self.path(rel)
                if src == self.root:
                    raise DiskError("Корень удалить нельзя")
                entry = self.entry(src)
                if src.is_dir():
                    entry["size"] = _tree_size(src)
                tid = uuid.uuid4().hex[:12]
                (self.trash_dir / tid).mkdir()
                shutil.move(str(src), str(self.trash_dir / tid / src.name))
                index[tid] = {**entry, "id": tid, "deleted": int(time.time())}
                self._unlink_shares(entry["path"])
                count += 1
            _write_json(self.meta / "trash.json", index)
            self._changed()
            return count

    def trash(self) -> list[dict]:
        index = self._trash_index()
        return sorted((v for k, v in index.items() if (self.trash_dir / k).exists()),
                      key=lambda e: -e["deleted"])

    def restore(self, ids: list[str]) -> list[dict]:
        with self.lock:
            index = self._trash_index()
            done = []
            for tid in _as_list(ids):
                item = index.get(tid)
                if not item:
                    continue
                src = self.trash_dir / tid / item["name"]
                if src.exists():
                    # Папку, где лежал файл, могли удалить: создаём заново.
                    target = unique(self.path(item["path"], must_exist=False))
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(src), str(target))
                    done.append(self.entry(target))
                shutil.rmtree(self.trash_dir / tid, ignore_errors=True)
                index.pop(tid)
            _write_json(self.meta / "trash.json", index)
            self._changed()
            return done

    def purge(self, ids: list[str] | None, everything: bool = False) -> int:
        """Удалить навсегда; everything — очистить корзину."""
        with self.lock:
            index = self._trash_index()
            targets = list(index) if everything else [i for i in _as_list(ids) if i in index]
            if everything:  # заодно то, что попало в корзину без записи
                targets += [p.name for p in self.trash_dir.iterdir() if p.name not in index]
            for tid in targets:
                _rmtree(self.trash_dir / tid)
                index.pop(tid, None)
            _write_json(self.meta / "trash.json", index)
            self._changed()
            return len(targets)

    # --- Ссылки ---

    def _shares(self) -> dict:
        return _read_json(self.meta / "shares.json")

    def share(self, rel: str) -> dict:
        path = self.path(rel)
        if path == self.root:
            raise DiskError("Корень открыть по ссылке нельзя")
        with self.lock:
            shares = self._shares()
            rel = self.rel(path)
            for token, item in shares.items():
                if item["path"] == rel:
                    return {"token": token, **item}
            token = secrets.token_urlsafe(12)
            shares[token] = {"path": rel, "created": int(time.time())}
            _write_json(self.meta / "shares.json", shares)
            return {"token": token, **shares[token]}

    def unshare(self, token: str) -> None:
        with self.lock:
            shares = self._shares()
            if shares.pop(token, None):
                _write_json(self.meta / "shares.json", shares)

    def shares(self) -> list[dict]:
        out = []
        for token, item in self._shares().items():
            try:
                out.append({"token": token, "created": item["created"], **self.entry(self.path(item["path"]))})
            except (OSError, DiskError):
                continue
        return sorted(out, key=lambda e: -e["created"])

    def shared(self, token: str, sub: str | None = None) -> Path:
        """Путь по ссылке (для папки можно указать файл внутри неё)."""
        item = self._shares().get(token or "")
        if not item:
            raise FileNotFoundError(token)
        base = self.path(item["path"])
        path = self.path("/".join([item["path"], *split_rel(sub)])) if sub else base
        return path

    def _relink(self, old: str, new: str) -> None:
        """Ссылки на переименованный или перенесённый путь продолжают работать."""
        shares = self._shares()
        changed = False
        for item in shares.values():
            if item["path"] == old or item["path"].startswith(old + "/"):
                item["path"] = new + item["path"][len(old):]
                changed = True
        if changed:
            _write_json(self.meta / "shares.json", shares)

    def _unlink_shares(self, rel: str) -> None:
        shares = self._shares()
        keep = {t: v for t, v in shares.items() if not (v["path"] == rel or v["path"].startswith(rel + "/"))}
        if len(keep) != len(shares):
            _write_json(self.meta / "shares.json", keep)


def _as_list(value) -> list[str]:
    if isinstance(value, str):
        return [value]
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise DiskError("Ожидается список путей")
    return value


def _size(path: Path) -> int:
    try:
        return path.stat().st_size
    except OSError:
        return 0


def _tree_size(folder: Path) -> int:
    return sum(_size(Path(dp) / f) for dp, _, fs in os.walk(folder) for f in fs)


def _rmtree(path: Path) -> None:
    """Удалить и файлы «только для чтения» (в Windows их иначе не удалить)."""
    def retry(func, p, _exc):
        os.chmod(p, 0o666)
        func(p)

    if not path.is_dir():
        path.unlink(missing_ok=True)
    elif sys.version_info >= (3, 12):
        shutil.rmtree(path, onexc=retry)
    else:
        shutil.rmtree(path, onerror=retry)


def _read_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _write_json(path: Path, data: dict) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, path)
