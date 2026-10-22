"""Ограниченный текстовый diff и сведения о версиях для интерфейса."""

from __future__ import annotations

import difflib
from pathlib import Path

MAX_DIFF_BYTES = 65536


def version_info(value: dict) -> dict:
    return {key: value.get(key) for key in ("revision", "version", "title", "channel", "message", "date", "published_at", "installed_at", "size", "archive_size")}


def file_diff(path: str, before: bytes | None, after: bytes | None, before_size: int, after_size: int) -> dict:
    result = {"path": path, "before_size": before_size, "after_size": after_size, "lines": [], "truncated": False}
    if before is None or after is None:
        return {**result, "reason": "large"}
    try:
        if b"\0" in before or b"\0" in after:
            raise UnicodeError()
        old = before.decode("utf-8-sig").splitlines()
        new = after.decode("utf-8-sig").splitlines()
    except UnicodeError:
        return {**result, "reason": "binary"}
    if len(old) + len(new) > 4000:
        return {**result, "reason": "large"}
    if old == new:
        return {**result, "reason": "format" if before != after else "equal"}
    amount = 0
    for line in difflib.unified_diff(old, new, fromfile="Локальная версия / " + path,
                                     tofile="Выбранная версия / " + path, lineterm=""):
        if len(result["lines"]) >= 800 or amount + len(line) > 100000:
            result["truncated"] = True
            break
        kind = "header" if line.startswith(("---", "+++")) and len(result["lines"]) < 2 else (
            "hunk" if line.startswith("@@") else "add" if line.startswith("+") else "remove" if line.startswith("-") else "context")
        if len(line) > 2000:
            line = line[:2000] + "…"
            result["truncated"] = True
        result["lines"].append({"kind": kind, "text": line})
        amount += len(line)
    return result


def read_small(path: Path) -> tuple[bytes | None, int]:
    if not path.exists():
        return b"", 0
    if not path.is_file():
        raise ValueError("На месте файла находится папка")
    size = path.stat().st_size
    if size > MAX_DIFF_BYTES:
        return None, size
    with path.open("rb") as stream:
        raw = stream.read(MAX_DIFF_BYTES + 1)
    return (raw if len(raw) <= MAX_DIFF_BYTES else None), len(raw)
