"""Удобство: избранное, недавние файлы и отчёт о месте (крупные файлы, дубликаты, папки).

Избранное хранится в ``<Диск>/.yakumo/favorites.json`` относительными путями
и едет следом за переименованием и переносом.
"""

from __future__ import annotations

import hashlib
import heapq
import json
import os
import threading
from collections import defaultdict
from pathlib import Path

from .store import SERVICE, Disk, DiskError, kind_of

RECENT = 60
LARGEST = 30
DUP_MIN = 1024              # файлы меньше не считаем дубликатами
DUP_GROUPS = 50
HEAD = 64 * 1024            # быстрая проверка: начало и конец файла


class Library:
    def __init__(self, disk: Disk):
        self.disk = disk
        self.path = disk.meta / "favorites.json"
        self.lock = threading.Lock()
        disk.on_move.append(self.moved)

    # --- Избранное ---

    def _read(self) -> list[str]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return [p for p in data if isinstance(p, str)] if isinstance(data, list) else []
        except (OSError, ValueError):
            return []

    def _write(self, paths: list[str]) -> None:
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(paths, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, self.path)

    def starred(self) -> set[str]:
        return set(self._read())

    def favorites(self) -> list[dict]:
        out = []
        for rel in self._read():
            try:
                out.append({**self.disk.entry(self.disk.path(rel)), "star": True})
            except (OSError, DiskError):
                continue  # удалили — просто не показываем (вернётся из корзины на место)
        return out

    def star(self, paths, on: bool) -> list[str]:
        if isinstance(paths, str):
            paths = [paths]
        if not isinstance(paths, list) or not paths:
            raise DiskError("Нужен список paths")
        with self.lock:
            current = self._read()
            for rel in paths:
                rel = self.disk.rel(self.disk.path(rel))  # проверка пути и единый вид
                if on and rel not in current:
                    current.append(rel)
                elif not on and rel in current:
                    current.remove(rel)
            self._write(current[-500:])
            return current

    def moved(self, old: str, new: str) -> None:
        with self.lock:
            current = self._read()
            changed = [new + p[len(old):] if p == old or p.startswith(old + "/") else p for p in current]
            if changed != current:
                self._write(changed)

    # --- Недавние ---

    def _files(self):
        for dirpath, dirnames, filenames in os.walk(self.disk.root):
            here = Path(dirpath)
            if here == self.disk.root:
                dirnames[:] = [d for d in dirnames if d.lower() != SERVICE]
            for name in filenames:
                path = here / name
                try:
                    st = path.stat()
                except OSError:
                    continue
                yield path, st

    def recent(self, limit: int = RECENT) -> list[dict]:
        newest = heapq.nlargest(limit, self._files(), key=lambda x: x[1].st_mtime)
        stars = self.starred()
        return [{**self._entry(p, st), "star": self.disk.rel(p) in stars} for p, st in newest]

    def _entry(self, path: Path, st) -> dict:
        return {"name": path.name, "path": self.disk.rel(path), "dir": False, "size": st.st_size,
                "mtime": int(st.st_mtime), "kind": kind_of(path.name)}

    # --- Место ---

    def space(self) -> dict:
        """Крупные файлы, дубликаты, размер папок верхнего уровня и типов файлов."""
        by_size: dict[int, list[Path]] = defaultdict(list)
        kinds: dict[str, int] = defaultdict(int)
        folders: dict[str, int] = defaultdict(int)
        largest = []
        for path, st in self._files():
            rel = self.disk.rel(path)
            kinds[kind_of(path.name)] += st.st_size
            folders[rel.split("/")[0] if "/" in rel else ""] += st.st_size
            if st.st_size >= DUP_MIN:
                by_size[st.st_size].append(path)
            item = (st.st_size, rel, path, st)
            if len(largest) < LARGEST:
                heapq.heappush(largest, item)
            elif st.st_size > largest[0][0]:
                heapq.heapreplace(largest, item)
        dups = []
        for size, paths in sorted(by_size.items(), key=lambda kv: -kv[0]):
            if len(paths) < 2:
                continue
            groups: dict[str, list[Path]] = defaultdict(list)
            for p in paths:
                try:
                    groups[_quick(p, size)].append(p)
                except OSError:
                    continue
            for same in groups.values():
                if len(same) < 2:
                    continue
                full: dict[str, list[Path]] = defaultdict(list)
                for p in same:
                    try:
                        full[_digest(p)].append(p)
                    except OSError:
                        continue
                for copies in full.values():
                    if len(copies) > 1:
                        copies.sort(key=lambda p: (p.stat().st_mtime, len(str(p))))
                        dups.append({"size": size, "wasted": size * (len(copies) - 1),
                                     "files": [self._entry(p, p.stat()) for p in copies]})
            if len(dups) >= DUP_GROUPS:
                break
        return {"largest": [self._entry(p, st) for _s, _r, p, st in sorted(largest, reverse=True)],
                "duplicates": sorted(dups, key=lambda d: -d["wasted"]),
                "folders": sorted(({"path": k, "size": v} for k, v in folders.items()), key=lambda f: -f["size"]),
                "kinds": sorted(({"kind": k, "size": v} for k, v in kinds.items()), key=lambda f: -f["size"])}


def _quick(path: Path, size: int) -> str:
    with open(path, "rb") as f:
        head = f.read(HEAD)
        if size > 2 * HEAD:
            f.seek(-HEAD, os.SEEK_END)
            head += f.read(HEAD)
    return hashlib.sha1(head).hexdigest()


def _digest(path: Path) -> str:
    h = hashlib.sha1()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()
