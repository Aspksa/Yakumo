"""Таблицы с Диска для чата: CSV/TSV и Excel (.xlsx) — строки, отбор, суммы и группировки.

Yakumo не считает в уме: «сколько я потратил на свет за год?» — она зовёт
disk_table с отбором и суммой, и числа считает этот модуль. Только стандартная
библиотека: xlsx читается как zip с XML.
"""

from __future__ import annotations

import csv
import io
import re
import zipfile
from pathlib import Path

from .extract import decode

MAX_ROWS = 20000
SHOW_ROWS = 60
NS = r"(?:\w+:)?"


class TableError(ValueError):
    """Файл не таблица или в нём нет такого листа или колонки."""


def number(value):
    """Число из ячейки («1 234,50», «89», «12%») или None."""
    if isinstance(value, (int, float)):
        return value
    text = str(value).strip().replace(" ", "").replace(" ", "").replace("₽", "").replace("р.", "")
    if not text or not re.fullmatch(r"[-+]?\d+([.,]\d+)?%?", text):
        return None
    pct = text.endswith("%")
    n = float(text.rstrip("%").replace(",", "."))
    n = n / 100 if pct else n
    return int(n) if n.is_integer() and not pct else n


def _col_index(ref: str) -> int:
    letters = re.match(r"[A-Z]+", ref).group(0)
    n = 0
    for ch in letters:
        n = n * 26 + ord(ch) - 64
    return n - 1


def _xlsx(path: Path) -> list[dict]:
    with zipfile.ZipFile(path) as zf:
        names = zf.namelist()
        shared = []
        if "xl/sharedStrings.xml" in names:
            xml = zf.read("xl/sharedStrings.xml").decode("utf-8", errors="replace")
            for si in re.findall(rf"<{NS}si\b[^>]*>(.*?)</{NS}si>", xml, re.S):
                shared.append("".join(re.findall(rf"<{NS}t\b[^>]*>([^<]*)</{NS}t>", si)))
        titles = []
        if "xl/workbook.xml" in names:
            wb = zf.read("xl/workbook.xml").decode("utf-8", errors="replace")
            titles = re.findall(rf'<{NS}sheet\b[^>]*\bname="([^"]*)"', wb)
        sheets = sorted((n for n in names if re.fullmatch(r"xl/worksheets/sheet\d+\.xml", n)),
                        key=lambda n: int(re.search(r"(\d+)\.xml$", n).group(1)))
        out = []
        for i, name in enumerate(sheets):
            xml = zf.read(name).decode("utf-8", errors="replace")
            rows = []
            for row in re.findall(rf"<{NS}row\b[^>]*>(.*?)</{NS}row>", xml, re.S)[:MAX_ROWS]:
                cells: dict[int, object] = {}
                for attrs, body in re.findall(rf"<{NS}c\b([^>]*?)(?:/>|>(.*?)</{NS}c>)", row, re.S):
                    ref = re.search(r'\br="([A-Z]+)\d+"', attrs)
                    col = _col_index(ref.group(1)) if ref else len(cells)
                    kind = re.search(r'\bt="(\w+)"', attrs)
                    kind = kind.group(1) if kind else "n"
                    v = re.search(rf"<{NS}v>([^<]*)</{NS}v>", body or "")
                    if kind == "s" and v:
                        value = shared[int(v.group(1))] if int(v.group(1)) < len(shared) else ""
                    elif kind == "inlineStr":
                        value = "".join(re.findall(rf"<{NS}t\b[^>]*>([^<]*)</{NS}t>", body or ""))
                    elif v:
                        value = number(v.group(1))
                        value = v.group(1) if value is None else value
                    else:
                        continue
                    cells[col] = _unescape(value) if isinstance(value, str) else value
                if cells:
                    rows.append([cells.get(c, "") for c in range(max(cells) + 1)])
            out.append({"name": titles[i] if i < len(titles) else f"Лист{i + 1}", "rows": rows})
        return out


def _unescape(text: str) -> str:
    return text.replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"').replace("&apos;", "'").replace(
        "&amp;", "&")


def _csv(path: Path) -> list[dict]:
    text = decode(path.read_bytes()[:20 * 1024**2])
    sample = text[:5000]
    delimiter = "\t" if path.suffix.lower() == ".tsv" else max((";", ",", "\t"), key=sample.count)
    rows = [[number(c) if number(c) is not None else c.strip() for c in row]
            for row in csv.reader(io.StringIO(text), delimiter=delimiter)][:MAX_ROWS]
    return [{"name": path.stem, "rows": [r for r in rows if any(str(c).strip() for c in r)]}]


def read(path: Path) -> list[dict]:
    ext = path.suffix.lower()
    try:
        if ext == ".xlsx":
            return _xlsx(path)
        if ext in (".csv", ".tsv"):
            return _csv(path)
    except (OSError, zipfile.BadZipFile, KeyError, ValueError) as exc:
        raise TableError(f"Не удалось прочитать таблицу: {exc}") from exc
    raise TableError("Таблицы — только .xlsx, .csv или .tsv")


def query(path: Path, sheet=None, where=None, sum_cols=None, group_by=None) -> dict:
    """Строки таблицы с отбором («где колонка содержит текст»), суммами и группировкой."""
    sheets = read(path)
    if not sheets:
        raise TableError("В файле нет листов")
    if sheet:
        found = next((s for s in sheets if s["name"].lower() == str(sheet).lower()), None)
        if found is None:
            raise TableError(f"Нет листа «{sheet}». Листы: {', '.join(s['name'] for s in sheets)}")
    else:
        found = sheets[0]
    rows = found["rows"]
    if not rows:
        return {"sheet": found["name"], "sheets": [s["name"] for s in sheets], "columns": [], "rows": 0}
    header = [str(c).strip() or f"col{i + 1}" for i, c in enumerate(rows[0])]
    width = max(len(r) for r in rows)
    header += [f"col{i + 1}" for i in range(len(header), width)]
    data = [dict(zip(header, r + [""] * (width - len(r)))) for r in rows[1:]]

    def col(name) -> str:
        name = str(name).strip().lower()
        match = next((h for h in header if h.lower() == name), None) or next(
            (h for h in header if name in h.lower()), None)
        if match is None:
            raise TableError(f"Нет колонки «{name}». Колонки: {', '.join(header)}")
        return match

    for key, needle in (where or {}).items():
        c, needle = col(key), str(needle).lower()
        data = [r for r in data if needle in str(r[c]).lower()]
    out = {"sheet": found["name"], "sheets": [s["name"] for s in sheets], "columns": header, "rows": len(data),
           "data": data[:SHOW_ROWS], "truncated": len(data) > SHOW_ROWS}
    sums = [col(c) for c in (sum_cols or [])]
    if sums:
        out["sum"] = {c: _round(sum(number(r[c]) or 0 for r in data)) for c in sums}
    if group_by:
        g = col(group_by)
        groups: dict[str, dict] = {}
        for r in data:
            item = groups.setdefault(str(r[g]), {"rows": 0, **{c: 0 for c in sums}})
            item["rows"] += 1
            for c in sums:
                item[c] = _round(item[c] + (number(r[c]) or 0))
        out["groups"] = groups
        out.pop("data")
        out.pop("truncated")
    return out


def _round(n):
    return round(n, 2) if isinstance(n, float) else n
