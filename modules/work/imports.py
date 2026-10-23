"""Импорт образцов: расход ГСМ, месячная ведомость машины, Т-12 и выписка карт.

Исходники остаются в папке данных. Месячные итоги используются для сверки,
не превращаются в повторные заправки/списания. Выписка карт распределяется явно.
"""

from __future__ import annotations

import calendar
import contextlib
import datetime as dt
import hashlib
import json
import re
import time
from pathlib import Path

from .books import Book, MAX_UPLOAD
from .store import CODES, WORK_CODES, WorkError, date, ident, month_bounds, plate_key, text, units

MONTHS = ["январ", "феврал", "март", "апрел", "ма", "июн", "июл", "август", "сентябр", "октябр", "ноябр", "декабр"]
KINDS = {"summary": "Сводный расход ГСМ", "vehicle": "Месячная ведомость автомобиля",
         "attendance": "Табель сотрудников", "cards": "Выписка топливных карт"}
PLATE = re.compile(r"[АВЕКМНОРСТУХABCEHKMOPTXY]\s*\d{3}\s*[АВЕКМНОРСТУХABCEHKMOPTXY]{2}(?:\s*\d{2,3})?", re.I)


def month_from(values, override=None):
    if override:
        month_bounds(override)
        return override
    for value in values:
        s = str(value or "")
        m = re.search(r"\b(20\d{2})-(0[1-9]|1[0-2])-\d{2}", s)
        if m:
            return f"{m[1]}-{m[2]}"
        m = re.search(r"\b\d{1,2}\.(\d{1,2})\.(20\d{2})\b", s)
        if m and 1 <= int(m[1]) <= 12:
            return f"{m[2]}-{int(m[1]):02}"
        year = re.search(r"\b(20\d{2})\b", s)
        if year:
            for i, stem in enumerate(MONTHS, 1):
                if re.search(r"\b"+stem+r"[а-я]*\b", s.lower()):
                    return f"{year[1]}-{i:02}"
    raise WorkError("Не удалось определить год и месяц. Укажите период импорта вручную")


def name_like(s):
    s = text(s)
    return bool(re.match(r"^[А-ЯЁA-Z][а-яёa-z-]+\s+(?:[А-ЯЁA-Z]\s*\.?\s*){1,2}$", s))


def numeric(value, optional=True):
    return units(value, optional=optional)


def parsed(sheet, filename="", override=None):
    s = sheet
    all_text = " ".join(str(v) for (r, c), v in s.cells.items() if r < 16).lower()
    out = {"sheet": s.name, "warnings": [], "errors": [], "records": []}
    if "выписка по" in all_text or "операция" in all_text and ("азс" in all_text or "кол-во" in all_text):
        out["kind"] = "cards"
        card, seen = "", set()
        for r in range(s.height):
            line = str(s.at(r, 0, ""))
            m = re.search(r"Карта\s*(?:№|N)?\s*(\d{3,40})", line, re.I)
            if m:
                card = m[1]
                continue
            if line.strip().lower() not in ("отгрузка", "заправка"):
                continue
            try:
                if not card:
                    raise WorkError("Не найден номер карты")
                raw_day = str(s.at(r, 1, ""))
                day = raw_day[:10] if re.match(r"\d{4}-\d{2}-\d{2}", raw_day) else dt.datetime.strptime(raw_day, "%d.%m.%y" if len(raw_day) == 8 else "%d.%m.%Y").date().isoformat()
                rec = {"card": card, "date": date(day), "time": text(s.at(r, 2), 20),
                       "station": text(s.at(r, 3), 500), "product": text(s.at(r, 4), 300),
                       "price": units(s.at(r, 5), 100, optional=True), "liters": numeric(s.at(r, 6), False),
                       "amount": units(s.at(r, 7), 100, optional=True)}
                if rec["liters"] <= 0:
                    raise WorkError("Количество должно быть положительным")
                rec["fingerprint"] = hashlib.sha256(json.dumps(rec, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
                if rec["fingerprint"] in seen:
                    raise WorkError("Две полностью одинаковые операции: проверьте исходную выписку")
                seen.add(rec["fingerprint"])
                out["records"].append(rec)
            except (WorkError, ValueError) as exc:
                out["errors"].append(f"Строка {r+1}: {exc}")
        out["warnings"].append("Операции сохранятся для сверки. Остатки машин изменятся после распределения заправок по автомобилям.")
        out["period"] = sorted(set(x["date"][:7] for x in out["records"]))
    elif "анализ расхода гсм" in all_text:
        out["kind"] = "summary"
        period = month_from(list(s.cells.values())[:30], override)
        out["period"] = period
        header = next((r for (r, c), v in s.cells.items() if c == 0 and "гос" in str(v).lower() and "номер" in str(v).lower()), None)
        if header is None:
            raise WorkError("Не найдена строка заголовков сводной ведомости")
        for r in range(header+2, s.height):
            model = text(s.at(r, 1))
            if not model or str(s.at(r, 0, "")).upper() == "ИТОГО":
                continue
            try:
                for offset, kind in ((5, "ДТ"), (6, "Бензин")):
                    vals = [s.at(r, offset+n) for n in (0, 2, 4, 6, 8)]
                    if not any(v is not None and v != "" for v in vals):
                        continue
                    driver = text(s.at(r, 3))
                    if driver.lower() in ("нет водителя", "на списание"):
                        driver = ""
                    out["records"].append({"month": period, "model": model, "plate": text(s.at(r, 0)), "driver": driver,
                                           "fuel": kind, "distance": numeric(s.at(r, 4)),
                                           **dict(zip(("opening", "received", "actual", "norm", "closing"), [numeric(v) for v in vals]))})
            except WorkError as exc:
                out["errors"].append(f"Строка {r+1}: {exc}")
    elif "общий километраж" in all_text and "приход" in all_text and "расход" in all_text:
        out["kind"] = "vehicle"
        period = month_from([s.at(5, 1), s.at(32, 1), s.at(1, 3), s.name], override)
        model = text(s.at(1, 1))
        found = PLATE.search(model) or PLATE.search(filename)
        plate = found[0] if found else ""
        model = text(PLATE.sub("", model)) or "Автомобиль"
        card_value = s.at(3, 2)
        if isinstance(card_value, float) and abs(card_value) >= 10**15:
            out["errors"].append("Номер карты записан числом и мог потерять последние цифры. Сохраните его в исходной книге текстом")
        card = str(card_value).strip() if card_value is not None else ""
        if card.endswith(".0"):
            card = card[:-2]
        rate_match = re.search(r"\(?\s*(\d+(?:[.,]\d+)?)\s*[*х×]", str(s.at(30, 1, "")))
        out["period"] = period
        values = {}
        for key, row, column, address in (("distance",4,3,"D5"),("opening",5,3,"D6"),("received",27,1,"B28"),
                                         ("actual",27,4,"E28"),("norm",30,4,"E31"),("closing",33,1,"B34")):
            try:
                values[key] = numeric(s.at(row,column))
            except WorkError:
                values[key] = None
                out["errors"].append(f"Ячейка {address}: вместо числа сохранено «{text(s.at(row,column),40)}». Исправьте значение в Excel")
        out["records"] = [{"month": period, "model": model, "plate": plate, "driver": text(s.at(1, 5)), "card": card,
                           "fuel": "Другое", **values, "rate": numeric(rate_match[1]) if rate_match else None}]
        out["warnings"].append("В этой форме не указан вид топлива. Уточните его в карточке автомобиля перед вводом движений ГСМ.")
    elif "табель" in all_text or "отметки о явках" in all_text:
        out["kind"] = "attendance"
        period = month_from([v for (r, _), v in s.cells.items() if r < 12] + [s.name], override)
        out["period"] = period
        candidates = []
        for r in range(min(s.height, 25)):
            days = {int(v): c for c, v in s.row(r).items() if isinstance(v, (int, float)) and v == int(v) and 1 <= v <= 31}
            if len(days) >= 20:
                candidates.append((len(days), r, days))
        if not candidates:
            raise WorkError("На этом листе нет календаря табеля. Выберите лист с отметками сотрудников")
        _, day_row, days = max(candidates, key=lambda x: x[0])
        first_col = min(days.values())
        name_cols = [c for (r, c), v in s.cells.items() if r <= day_row and c < first_col and "фамил" in str(v).lower()]
        name_col = name_cols[-1] if name_cols else None
        for r in range(day_row+1, s.height):
            names = [(c, text(v)) for c, v in s.row(r).items() if c < first_col and (c == name_col or name_like(v))]
            names = [(c, n) for c, n in names if name_like(n) or c == name_col and n and not any(w in n.lower() for w in ("фамил", "итого", "должност", "ответствен")) and not n.isdigit()]
            if not names:
                continue
            c, name = names[0]
            for day, column in sorted(days.items()):
                if day > calendar.monthrange(int(period[:4]), int(period[5:]))[1]:
                    continue
                value = s.at(r, column)
                if value is None or str(value).strip() == "":
                    continue
                code = str(value).strip().upper()
                hours = s.at(r+1, column)
                if isinstance(value, (int, float)):
                    code, hours = "Я", value
                if code not in CODES:
                    out["errors"].append(f"Строка {r+1}, день {day}: неизвестное обозначение «{text(value, 20)}»")
                    continue
                if code in WORK_CODES and (hours is None or hours == ""):
                    out["errors"].append(f"Строка {r+1}, день {day}: нет рабочих часов")
                    continue
                try:
                    minutes = units(hours or 0, 60, maximum=24) if code in WORK_CODES else 0
                    out["records"].append({"name": name, "date": f"{period}-{day:02}", "code": code, "minutes": minutes})
                except WorkError as exc:
                    out["errors"].append(f"Строка {r+1}, день {day}: {exc}")
    else:
        raise WorkError("Форма не распознана. Поддерживаются месячные ведомости автомобиля, сводный расход ГСМ, табель и выписка карт")
    if not out["records"] and not out["errors"]:
        out["errors"].append("На выбранном листе не найдено записей для импорта")
    if out["kind"] in ("vehicle", "summary"):
        out["warnings"].append("Месячные итоги сохранятся отдельно для сверки. Они не создают повторных поступлений и списаний и не меняют действующие закрепления машин.")
        for rec in out["records"]:
            vals = [rec.get(k) for k in ("opening", "received", "actual", "closing")]
            if all(v is not None for v in vals):
                rec["balance_delta"] = vals[0]+vals[1]-vals[2]-vals[3]
                if abs(rec["balance_delta"]) > 1:
                    out["warnings"].append(f"{rec['plate'] or rec['model']}: в исходнике не сходится остаток на {rec['balance_delta']/1000:g} л")
            else:
                out["warnings"].append(f"{rec['plate'] or rec['model']}: часть итогов отсутствует. Пустые значения сохранятся пустыми")
    out["title"] = KINDS[out["kind"]]
    return out


class Imports:
    def __init__(self, work):
        self.work = work
        self.root = work.root / "sources"
        self.root.mkdir(exist_ok=True)

    def upload(self, name, data):
        name = Path(str(name).replace("\\", "/")).name
        ext = Path(name).suffix.lower()
        book = Book(data, ext)
        sha = hashlib.sha256(data).hexdigest()
        with self.work.transaction() as con:
            existing = con.execute("SELECT * FROM documents WHERE sha=? AND ext=?", (sha, ext)).fetchone()
            item_id = existing["id"] if existing else ident()
            path = self.root / (sha+ext)
            if not path.exists():
                temp = self.root / (ident()+".part")
                try:
                    temp.write_bytes(data)
                    temp.replace(path)
                finally:
                    temp.unlink(missing_ok=True)
            if not existing:
                con.execute("INSERT INTO documents VALUES(?,?,?,?,?,?)", (item_id, text(name, 250), sha, ext, len(data), int(time.time())))
        return {"id": item_id, "name": name, "sheets": book.names}

    def document(self, item_id):
        with contextlib.closing(self.work.connect()) as con:
            record = self.work.get(con, "documents", item_id)
        path = self.root / (record["sha"]+record["ext"])
        data = path.read_bytes()
        if len(data) > MAX_UPLOAD or hashlib.sha256(data).hexdigest() != record["sha"]:
            raise WorkError("Исходник изменился или повреждён. Загрузите книгу ещё раз")
        return record, data

    def inspect(self, item_id):
        record, data = self.document(item_id)
        return {"id": record["id"], "name": record["name"], "sheets": Book(data, record["ext"]).names}

    def read(self, item_id, sheet, period=None):
        record, data = self.document(item_id)
        return parsed(Book(data, record["ext"]).sheet(sheet), record["name"], period)

    def preview(self, item_id, sheet, period=None):
        result = self.read(item_id, sheet, period)
        return {**result, "count": len(result["records"]), "records": result["records"][:20]}

    def _employee(self, con, name, driver=False):
        if not name:
            return None
        matches = [r for r in con.execute("SELECT id,name FROM employees") if text(r["name"]).casefold() == text(name).casefold()]
        if len(matches) > 1:
            raise WorkError("Есть сотрудники с одинаковым именем. Уточните справочник перед импортом")
        if matches:
            if driver:
                con.execute("UPDATE employees SET is_driver=1 WHERE id=?", (matches[0]["id"],))
            return matches[0]["id"]
        return self.work._save(con, "employees", "", {"name": text(name), "is_driver": int(driver)})["id"]

    def _vehicle(self, con, rec):
        key = plate_key(rec.get("plate"))
        matches = list(con.execute("SELECT * FROM vehicles WHERE plate_key=?", (key,))) if key else [
            r for r in con.execute("SELECT * FROM vehicles WHERE plate_key='' ") if text(r["model"]).casefold() == text(rec["model"]).casefold()]
        if len(matches) > 1:
            raise WorkError("Несколько машин без номера с одинаковой моделью. Уточните госномера перед импортом")
        if matches:
            return matches[0]["id"]
        return self.work._save(con, "vehicles", "", {"model": rec["model"], "plate": rec.get("plate", ""), "plate_key": key,
                                "fuel": rec.get("fuel", "Другое"), "rate": rec.get("rate")})["id"]

    def _card(self, con, number):
        if not number:
            return None
        if not isinstance(number, str) or not re.fullmatch(r"[0-9A-Za-zА-Яа-я-]{3,40}", number):
            raise WorkError("Неверный номер карты в исходнике")
        old = con.execute("SELECT id FROM cards WHERE number=?", (number,)).fetchone()
        return old["id"] if old else self.work._save(con, "cards", "", {"number": number})["id"]

    def commit(self, item_id, sheet, period=None):
        result = self.read(item_id, sheet, period)
        if result["errors"]:
            raise WorkError("Исправьте ошибки предварительного просмотра: " + "; ".join(result["errors"][:3]))
        with self.work.transaction() as con:
            if con.execute("SELECT id FROM imports WHERE document_id=? AND sheet=?", (item_id, sheet)).fetchone():
                raise WorkError("Этот лист уже импортирован. Повторные записи не созданы")
            import_id, count, skipped = ident(), 0, 0
            con.execute("INSERT INTO imports VALUES(?,?,?,?,?,?)", (import_id, item_id, sheet, result["kind"], int(time.time()), 0))
            for rec in result["records"]:
                if result["kind"] == "cards":
                    card_id = self._card(con, rec["card"])
                    if con.execute("SELECT id FROM card_ops WHERE fingerprint=?", (rec["fingerprint"],)).fetchone():
                        skipped += 1
                        continue
                    con.execute("INSERT INTO card_ops(id,fingerprint,card_id,date,time,product,liters,price,amount,station,import_id) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                                (ident(), rec["fingerprint"], card_id, rec["date"], rec["time"], rec["product"], rec["liters"],
                                 rec["price"], rec["amount"], rec["station"], import_id))
                elif result["kind"] == "attendance":
                    employee_id = self._employee(con, rec["name"])
                    self.work._attendance(con, employee_id, rec["date"], rec["code"], rec["minutes"], source=import_id, import_mode=True)
                else:
                    vehicle_id = self._vehicle(con, rec)
                    employee_id = self._employee(con, rec.get("driver"), driver=True)
                    self._card(con, rec.get("card"))
                    con.execute("INSERT INTO monthly_reports VALUES(?,?,?,?,?,?)",
                                (ident(), rec["month"], vehicle_id, employee_id, json.dumps(rec, ensure_ascii=False), import_id))
                count += 1
            con.execute("UPDATE imports SET count=? WHERE id=?", (count, import_id))
            self.work.audit(con, "импорт", "imports", import_id, {"document_id": item_id, "sheet": sheet, "count": count, "skipped": skipped})
            return {"id": import_id, "count": count, "skipped": skipped, "warnings": result["warnings"], "period": result["period"]}
