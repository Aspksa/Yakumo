"""Локальный учёт работы: справочники, закрепления, документы и движение топлива.

Все изменения одной операции и запись её истории фиксируются одной транзакцией.
Литры хранятся в тысячных, деньги — в копейках. Заправка и расход — разные записи.
"""

from __future__ import annotations

import calendar
import contextlib
import datetime as dt
import json
import re
import sqlite3
import threading
import time
import uuid
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path


class WorkError(ValueError):
    pass


FUELS = ("Бензин", "ДТ", "Газ", "Другое")
CODES = {"Я": "Явка", "Н": "Ночная работа", "РВ": "Работа в выходной", "С": "Сверхурочная работа",
         "К": "Командировка", "ОТ": "Отпуск", "ОД": "Дополнительный отпуск", "Б": "Больничный",
         "В": "Выходной", "НН": "Неявка, причина не установлена", "ДО": "Отпуск без оплаты"}
WORK_CODES = {"Я", "Н", "РВ", "С", "К"}
TABLES = ("employees", "vehicles", "cards", "assignments", "entries", "waybills", "attendance",
          "documents", "imports", "monthly_reports", "card_ops", "audit", "settings")


def text(value, limit=200):
    return " ".join(str(value or "").split())[:limit]


def ident():
    return uuid.uuid4().hex


def units(value, scale=1000, *, optional=False, maximum=10**10):
    if value is None or value == "":
        if optional:
            return None
        raise WorkError("Заполните числовое поле")
    if isinstance(value, bool):
        raise WorkError("Нужно число")
    try:
        n = Decimal(str(value).replace(" ", "").replace("\u00a0", "").replace(",", "."))
        if not n.is_finite() or n < 0 or n > maximum:
            raise WorkError("Число должно быть неотрицательным и не слишком большим")
        return int((n * scale).quantize(Decimal(1), rounding=ROUND_HALF_UP))
    except (InvalidOperation, ValueError, OverflowError) as exc:
        raise WorkError("Неверный формат числа") from exc


def date(value):
    try:
        d = dt.date.fromisoformat(str(value))
        if d.year < 1900 or d.year > 2200:
            raise ValueError()
        return d.isoformat()
    except ValueError as exc:
        raise WorkError("Нужна дата в формате ГГГГ-ММ-ДД") from exc


def month_bounds(value):
    if not re.fullmatch(r"\d{4}-\d{2}", str(value)):
        raise WorkError("Нужен месяц в формате ГГГГ-ММ")
    start = date(str(value) + "-01")
    d = dt.date.fromisoformat(start)
    end = d.replace(day=calendar.monthrange(d.year, d.month)[1]).isoformat()
    return start, end


def plate_key(value):
    return re.sub(r"[\s-]", "", text(value).upper()).translate(str.maketrans("ABCEHKMOPTXY", "АВСЕНКМОРТХУ"))


def fuel(value):
    s = text(value).upper()
    if "ДИЗ" in s or "ДТ" in s:
        return "ДТ"
    if "БЕНЗ" in s or "АИ" in s or "AI" in s:
        return "Бензин"
    if "ГАЗ" in s or "ПРОПАН" in s or "МЕТАН" in s:
        return "Газ"
    return "Другое"


SCHEMA = """
CREATE TABLE IF NOT EXISTS employees (
 id TEXT PRIMARY KEY, name TEXT NOT NULL, position TEXT NOT NULL DEFAULT '', personnel_no TEXT NOT NULL DEFAULT '',
 is_driver INTEGER NOT NULL DEFAULT 0, active INTEGER NOT NULL DEFAULT 1, note TEXT NOT NULL DEFAULT '');
CREATE TABLE IF NOT EXISTS vehicles (
 id TEXT PRIMARY KEY, model TEXT NOT NULL, plate TEXT NOT NULL DEFAULT '', plate_key TEXT NOT NULL DEFAULT '',
 fuel TEXT NOT NULL, rate INTEGER, winter_rate INTEGER, tank INTEGER, active INTEGER NOT NULL DEFAULT 1,
 note TEXT NOT NULL DEFAULT '');
CREATE UNIQUE INDEX IF NOT EXISTS vehicle_plate ON vehicles(plate_key) WHERE plate_key <> '';
CREATE TABLE IF NOT EXISTS cards (
 id TEXT PRIMARY KEY, number TEXT NOT NULL UNIQUE, provider TEXT NOT NULL DEFAULT '',
 employee_id TEXT REFERENCES employees(id), active INTEGER NOT NULL DEFAULT 1, note TEXT NOT NULL DEFAULT '');
CREATE TABLE IF NOT EXISTS assignments (
 id TEXT PRIMARY KEY, employee_id TEXT NOT NULL REFERENCES employees(id), vehicle_id TEXT NOT NULL REFERENCES vehicles(id),
 start TEXT NOT NULL, end TEXT, note TEXT NOT NULL DEFAULT '');
CREATE TABLE IF NOT EXISTS documents (
 id TEXT PRIMARY KEY, name TEXT NOT NULL, sha TEXT NOT NULL, ext TEXT NOT NULL, size INTEGER NOT NULL,
 created INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS entries (
 id TEXT PRIMARY KEY, date TEXT NOT NULL, vehicle_id TEXT NOT NULL REFERENCES vehicles(id),
 employee_id TEXT REFERENCES employees(id), card_id TEXT REFERENCES cards(id), kind TEXT NOT NULL,
 liters INTEGER NOT NULL, amount INTEGER, product TEXT NOT NULL DEFAULT '', note TEXT NOT NULL DEFAULT '',
 source_key TEXT UNIQUE, status TEXT NOT NULL DEFAULT 'posted', created INTEGER NOT NULL, reason TEXT NOT NULL DEFAULT '');
CREATE INDEX IF NOT EXISTS entries_vehicle_date ON entries(vehicle_id,date,status);
CREATE TABLE IF NOT EXISTS waybills (
 id TEXT PRIMARY KEY, number TEXT NOT NULL UNIQUE, start TEXT NOT NULL, end TEXT NOT NULL,
 employee_id TEXT NOT NULL REFERENCES employees(id), vehicle_id TEXT NOT NULL REFERENCES vehicles(id),
 status TEXT NOT NULL DEFAULT 'draft', data TEXT NOT NULL, created INTEGER NOT NULL, reason TEXT NOT NULL DEFAULT '');
CREATE TABLE IF NOT EXISTS attendance (
 employee_id TEXT NOT NULL REFERENCES employees(id), date TEXT NOT NULL, code TEXT NOT NULL, minutes INTEGER NOT NULL,
 note TEXT NOT NULL DEFAULT '', source TEXT NOT NULL DEFAULT '', PRIMARY KEY(employee_id,date));
CREATE TABLE IF NOT EXISTS imports (
 id TEXT PRIMARY KEY, document_id TEXT NOT NULL REFERENCES documents(id), sheet TEXT NOT NULL, kind TEXT NOT NULL,
 created INTEGER NOT NULL, count INTEGER NOT NULL, UNIQUE(document_id,sheet));
CREATE TABLE IF NOT EXISTS monthly_reports (
 id TEXT PRIMARY KEY, month TEXT NOT NULL, vehicle_id TEXT NOT NULL REFERENCES vehicles(id),
 employee_id TEXT REFERENCES employees(id), data TEXT NOT NULL, import_id TEXT NOT NULL REFERENCES imports(id));
CREATE TABLE IF NOT EXISTS card_ops (
 id TEXT PRIMARY KEY, fingerprint TEXT NOT NULL UNIQUE, card_id TEXT NOT NULL REFERENCES cards(id), date TEXT NOT NULL,
 time TEXT NOT NULL DEFAULT '', product TEXT NOT NULL, liters INTEGER NOT NULL, price INTEGER, amount INTEGER,
 station TEXT NOT NULL DEFAULT '', entry_id TEXT REFERENCES entries(id), import_id TEXT NOT NULL REFERENCES imports(id));
CREATE TABLE IF NOT EXISTS audit (
 seq INTEGER PRIMARY KEY AUTOINCREMENT, at INTEGER NOT NULL, action TEXT NOT NULL, kind TEXT NOT NULL,
 item_id TEXT NOT NULL, detail TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
"""


class Work:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "work.sqlite3"
        self.lock = threading.RLock()
        with contextlib.closing(self.connect()) as con:
            con.executescript(SCHEMA)
            con.execute("PRAGMA user_version=1")

    def connect(self):
        con = sqlite3.connect(self.path, timeout=15)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys=ON")
        return con

    @contextlib.contextmanager
    def transaction(self):
        with self.lock, contextlib.closing(self.connect()) as con:
            try:
                con.execute("BEGIN IMMEDIATE")
                yield con
                con.commit()
            except sqlite3.IntegrityError as exc:
                con.rollback()
                raise WorkError("Такая запись уже существует или связана с другими документами") from exc
            except BaseException:
                con.rollback()
                raise

    @staticmethod
    def rows(con, sql, args=()):
        return [dict(r) for r in con.execute(sql, args)]

    @staticmethod
    def get(con, table, item_id):
        if table not in TABLES:
            raise WorkError("Неизвестный справочник")
        row = con.execute(f"SELECT * FROM {table} WHERE id=?", (str(item_id),)).fetchone()
        if row is None:
            raise WorkError("Запись не найдена. Обновите страницу")
        return dict(row)

    @staticmethod
    def audit(con, action, kind, item_id, detail):
        con.execute("INSERT INTO audit(at,action,kind,item_id,detail) VALUES(?,?,?,?,?)",
                    (int(time.time()), action, kind, item_id, json.dumps(detail, ensure_ascii=False)))

    def _save(self, con, table, item_id, fields):
        if item_id:
            old = self.get(con, table, item_id)
            con.execute(f"UPDATE {table} SET " + ",".join(k + "=?" for k in fields) + " WHERE id=?",
                        (*fields.values(), item_id))
        else:
            old, item_id = None, ident()
            con.execute(f"INSERT INTO {table}(id," + ",".join(fields) + ") VALUES(" + ",".join("?" for _ in range(len(fields)+1)) + ")",
                        (item_id, *fields.values()))
        self.audit(con, "изменение" if old else "создание", table, item_id, {"before": old, "after": fields})
        return self.get(con, table, item_id)

    def save_reference(self, kind, data):
        if kind not in ("employees", "vehicles", "cards"):
            raise WorkError("Неизвестный справочник")
        with self.transaction() as con:
            item_id = text(data.get("id"))
            old = self.get(con, kind, item_id) if item_id else {}
            d = {**old, **data}
            fields = {"active": int(d.get("active", True) in (True, 1)), "note": text(d.get("note"), 1500)}
            if kind == "employees":
                fields.update(name=text(d.get("name")), position=text(d.get("position")),
                              personnel_no=text(d.get("personnel_no"), 50), is_driver=int(d.get("is_driver", False) in (True, 1)))
                if not fields["name"]:
                    raise WorkError("Укажите имя сотрудника")
                if fields["personnel_no"] and con.execute("SELECT id FROM employees WHERE personnel_no=? AND id<>?",
                                                           (fields["personnel_no"], item_id)).fetchone():
                    raise WorkError("Табельный номер уже занят")
                if item_id and (not fields["is_driver"] or not fields["active"]) and con.execute(
                        "SELECT id FROM assignments WHERE employee_id=? AND (end IS NULL OR end>=?)",
                        (item_id, dt.date.today().isoformat())).fetchone():
                    raise WorkError("Сначала завершите закрепление автомобиля за водителем")
            elif kind == "vehicles":
                fields.update(model=text(d.get("model")), plate=text(d.get("plate"), 40),
                              plate_key=plate_key(d.get("plate")), fuel=d.get("fuel", "Бензин"))
                if not fields["model"] or fields["fuel"] not in FUELS:
                    raise WorkError("Укажите модель и вид топлива")
                for key in ("rate", "winter_rate", "tank"):
                    # Снаружи справочника величины выражены в литрах, в базе — в тысячных.
                    value = data[key] if key in data else (old.get(key) / 1000 if old.get(key) is not None else None)
                    fields[key] = units(value, optional=True, maximum=100000)
                if old and old["fuel"] != fields["fuel"] and con.execute(
                        "SELECT id FROM entries WHERE vehicle_id=? LIMIT 1", (item_id,)).fetchone():
                    raise WorkError("Вид топлива машины с историей движения менять нельзя")
                if item_id and not fields["active"] and con.execute(
                        "SELECT id FROM assignments WHERE vehicle_id=? AND (end IS NULL OR end>=?)",
                        (item_id, dt.date.today().isoformat())).fetchone():
                    raise WorkError("Сначала завершите закрепление автомобиля")
            else:
                raw_number = d.get("number")
                if not isinstance(raw_number, str):
                    raise WorkError("Номер топливной карты нужно передавать текстом")
                number = re.sub(r"\s", "", raw_number)
                if not re.fullmatch(r"[0-9A-Za-zА-Яа-я-]{3,40}", number):
                    raise WorkError("Проверьте номер топливной карты")
                if old and old["number"] != number and (con.execute("SELECT id FROM card_ops WHERE card_id=? LIMIT 1", (item_id,)).fetchone()
                        or con.execute("SELECT id FROM entries WHERE card_id=? LIMIT 1", (item_id,)).fetchone()):
                    raise WorkError("У карты есть история операций. Для другого номера создайте новую карту")
                driver = d.get("employee_id") or None
                if driver and not self.get(con, "employees", driver)["is_driver"]:
                    raise WorkError("Карту можно закрепить за водителем")
                fields.update(number=number, employee_id=driver, provider=text(d.get("provider")))
            return self._save(con, kind, item_id, fields)

    def assignment(self, data):
        with self.transaction() as con:
            item_id = text(data.get("id"))
            old = self.get(con, "assignments", item_id) if item_id else {}
            d = {**old, **data}
            driver = self.get(con, "employees", d.get("employee_id"))
            car = self.get(con, "vehicles", d.get("vehicle_id"))
            if not driver["is_driver"] or not driver["active"] or not car["active"]:
                raise WorkError("Нужны действующие водитель и автомобиль")
            start, end = date(d.get("start")), date(d["end"]) if d.get("end") else None
            if end and end < start:
                raise WorkError("Дата окончания раньше начала")
            clash = con.execute("SELECT id FROM assignments WHERE id<>? AND (employee_id=? OR vehicle_id=?) "
                                "AND start<=? AND (end IS NULL OR end>=?)",
                                (item_id, driver["id"], car["id"], end or "9999-12-31", start)).fetchone()
            if clash:
                raise WorkError("В этот период водитель или автомобиль уже закреплены. Сначала завершите прежнее закрепление")
            if old and con.execute("SELECT id FROM waybills WHERE status='closed' AND employee_id=? AND vehicle_id=? "
                                   "AND start>=? AND end<=? AND (start<? OR end>?)",
                                   (old["employee_id"], old["vehicle_id"], old["start"], old["end"] or "9999-12-31",
                                    start, end or "9999-12-31")).fetchone():
                raise WorkError("Изменение затрагивает закрытый путевой лист")
            if old and (driver["id"] != old["employee_id"] or car["id"] != old["vehicle_id"]):
                raise WorkError("Для другой пары создайте новое закрепление")
            return self._save(con, "assignments", item_id, {"employee_id": driver["id"], "vehicle_id": car["id"],
                              "start": start, "end": end, "note": text(d.get("note"), 1000)})

    @staticmethod
    def _balance(con, vehicle_id, until=None, before=False):
        clause = " AND date" + ("<?" if before else "<=?") if until else ""
        r = con.execute("SELECT COALESCE(SUM(CASE kind WHEN 'writeoff' THEN -liters ELSE liters END),0) "
                        "FROM entries WHERE vehicle_id=? AND status='posted'" + clause,
                        (vehicle_id, until) if until else (vehicle_id,)).fetchone()
        return r[0]

    @staticmethod
    def _valid_balances(con, vehicle_id):
        balance = 0
        for r in con.execute("SELECT date,SUM(CASE kind WHEN 'writeoff' THEN -liters ELSE liters END) AS delta "
                             "FROM entries WHERE vehicle_id=? AND status='posted' GROUP BY date ORDER BY date", (vehicle_id,)):
            balance += r["delta"]
            if balance < 0:
                raise WorkError(f"На {r['date']} получается отрицательный остаток топлива. Проверьте начальный остаток и поступления")

    @staticmethod
    def _closed_before(con, vehicle_id, day):
        return con.execute("SELECT number FROM waybills WHERE vehicle_id=? AND status='closed' AND end>=? LIMIT 1",
                           (vehicle_id, day)).fetchone()

    def _movement(self, con, d, source_key=None, closing=False):
        car = self.get(con, "vehicles", d.get("vehicle_id"))
        day, kind = date(d.get("date")), d.get("kind")
        if kind not in ("opening", "receipt", "writeoff"):
            raise WorkError("Вид операции: начальный остаток, поступление или списание")
        if not closing and self._closed_before(con, car["id"], day):
            raise WorkError("Период уже закрыт путевым листом. Сначала отмените затронутые путевые листы")
        opening = con.execute("SELECT date FROM entries WHERE vehicle_id=? AND kind='opening' AND status='posted'", (car["id"],)).fetchone()
        if kind != "opening" and opening and day < opening["date"]:
            raise WorkError("Движение топлива не может предшествовать начальному остатку")
        liters = units(d.get("liters"), maximum=1000000)
        if not liters and kind != "opening":
            raise WorkError("Количество топлива должно быть больше нуля")
        if kind == "opening" and con.execute("SELECT id FROM entries WHERE vehicle_id=? AND status='posted' "
                                             "AND (kind='opening' OR date<?) LIMIT 1", (car["id"], day)).fetchone():
            raise WorkError("Начальный остаток должен быть единственным и предшествовать движениям топлива")
        driver, card = d.get("employee_id") or None, d.get("card_id") or None
        if driver and not self.get(con, "employees", driver)["is_driver"]:
            raise WorkError("Выберите водителя")
        if card:
            self.get(con, "cards", card)
        item_id = ident()
        fields = {"date": day, "vehicle_id": car["id"], "employee_id": driver, "card_id": card,
                  "kind": kind, "liters": liters, "amount": units(d.get("amount"), 100, optional=True),
                  "product": text(d.get("product")), "note": text(d.get("note"), 1500),
                  "source_key": source_key, "created": int(time.time())}
        con.execute("INSERT INTO entries(id," + ",".join(fields) + ") VALUES(" + ",".join("?" for _ in range(len(fields)+1)) + ")",
                    (item_id, *fields.values()))
        self._valid_balances(con, car["id"])
        self.audit(con, "проведение", "entries", item_id, fields)
        return self.get(con, "entries", item_id)

    def movement(self, data):
        with self.transaction() as con:
            return self._movement(con, data)

    def cancel(self, kind, item_id, reason):
        reason = text(reason, 1000)
        if kind not in ("entries", "waybills") or not reason:
            raise WorkError("Укажите причину отмены")
        with self.transaction() as con:
            item = self.get(con, kind, item_id)
            if item["status"] == "cancelled":
                return item
            if kind == "entries":
                if (item.get("source_key") or "").startswith("waybill:"):
                    raise WorkError("Отмените путевой лист, который создал списание")
                if self._closed_before(con, item["vehicle_id"], item["date"]):
                    raise WorkError("Операция влияет на закрытый путевой лист. Сначала отмените его")
            else:
                later = con.execute("SELECT id FROM waybills WHERE vehicle_id=? AND status='closed' AND start>?",
                                    (item["vehicle_id"], item["end"])).fetchone()
                if later and item["status"] == "closed":
                    raise WorkError("Сначала отмените более поздние путевые листы этой машины")
                con.execute("UPDATE entries SET status='cancelled',reason=? WHERE source_key=?", (reason, "waybill:"+item_id))
            con.execute(f"UPDATE {kind} SET status='cancelled',reason=? WHERE id=?", (reason, item_id))
            self._valid_balances(con, item["vehicle_id"])
            self.audit(con, "отмена", kind, item_id, {"reason": reason})
            return self.get(con, kind, item_id)

    def _waybill_values(self, con, d, item_id=""):
        car = self.get(con, "vehicles", d.get("vehicle_id"))
        driver = self.get(con, "employees", d.get("employee_id"))
        start, end = date(d.get("start")), date(d.get("end") or d.get("start"))
        if end < start:
            raise WorkError("Возвращение раньше выезда")
        if not con.execute("SELECT id FROM assignments WHERE vehicle_id=? AND employee_id=? AND start<=? "
                           "AND (end IS NULL OR end>=?)", (car["id"], driver["id"], start, end)).fetchone():
            raise WorkError("Сначала закрепите эту машину за водителем на весь период путевого листа")
        if con.execute("SELECT id FROM waybills WHERE vehicle_id=? AND id<>? AND status<>'cancelled' AND start<=? AND end>=?",
                       (car["id"], item_id, end, start)).fetchone():
            raise WorkError("У машины уже есть путевой лист за пересекающийся период")
        odo_start, odo_end = units(d.get("odo_start")), units(d.get("odo_end"), optional=True)
        if odo_end is not None and odo_end < odo_start:
            raise WorkError("Показание при возвращении меньше показания при выезде")
        rate = units(d.get("rate"), optional=True, maximum=10000)
        rate = car["rate"] if rate is None else rate
        return car, driver, start, end, odo_start, odo_end, rate

    def waybill(self, d):
        with self.transaction() as con:
            item_id = text(d.get("id"))
            old = self.get(con, "waybills", item_id) if item_id else None
            if old and old["status"] != "draft":
                raise WorkError("Изменять можно только черновик путевого листа")
            car, driver, start, end, a, b, rate = self._waybill_values(con, d, item_id)
            number = text(d.get("number"), 80)
            if not number:
                raise WorkError("Укажите номер путевого листа")
            values = {"odo_start": a, "odo_end": b, "rate": rate,
                      "fuel_close": units(d.get("fuel_close"), optional=True), "route": text(d.get("route"), 2000),
                      "note": text(d.get("note"), 1500), "vehicle_model": car["model"], "plate": car["plate"],
                      "driver_name": driver["name"], "fuel": car["fuel"]}
            if values["fuel_close"] is not None and car["tank"] is not None and values["fuel_close"] > car["tank"]:
                raise WorkError("Остаток при возвращении больше объёма бака")
            return self._save(con, "waybills", item_id, {"number": number, "start": start, "end": end,
                              "vehicle_id": car["id"], "employee_id": driver["id"], "data": json.dumps(values, ensure_ascii=False),
                              "created": old["created"] if old else int(time.time())})

    def close_waybill(self, item_id):
        with self.transaction() as con:
            wb = self.get(con, "waybills", item_id)
            if wb["status"] == "closed":
                return wb
            if wb["status"] != "draft":
                raise WorkError("Путевой лист отменён")
            if con.execute("SELECT id FROM waybills WHERE vehicle_id=? AND status='closed' AND start>?", (wb["vehicle_id"], wb["end"])).fetchone():
                raise WorkError("Сначала отмените более поздние путевые листы: они используют остаток топлива этого периода")
            v = json.loads(wb["data"])
            self._waybill_values(con, {**wb, **v, "odo_start": v["odo_start"]/1000,
                                      "odo_end": v["odo_end"]/1000 if v["odo_end"] is not None else None,
                                      "rate": v["rate"]/1000 if v["rate"] is not None else None}, item_id)
            if v["odo_end"] is None or v["fuel_close"] is None:
                raise WorkError("Для закрытия заполните одометр и остаток топлива при возвращении")
            for prev in con.execute("SELECT start,end,data FROM waybills WHERE vehicle_id=? AND status='closed'", (wb["vehicle_id"],)):
                pv = json.loads(prev["data"])
                if (prev["end"] < wb["start"] and pv["odo_end"] > v["odo_start"]) or (
                        prev["start"] > wb["end"] and pv["odo_start"] < v["odo_end"]):
                    raise WorkError("Показания одометра противоречат другому закрытому путевому листу")
            if con.execute("SELECT id FROM entries WHERE vehicle_id=? AND date BETWEEN ? AND ? AND kind='writeoff' AND status='posted'",
                           (wb["vehicle_id"], wb["start"], wb["end"])).fetchone():
                raise WorkError("В периоде уже есть списание топлива. Исключите двойной расход перед закрытием")
            opening = self._balance(con, wb["vehicle_id"], wb["start"], before=True)
            received = con.execute("SELECT COALESCE(SUM(liters),0) FROM entries WHERE vehicle_id=? AND date BETWEEN ? AND ? "
                                   "AND kind IN ('receipt','opening') AND status='posted'",
                                   (wb["vehicle_id"], wb["start"], wb["end"])).fetchone()[0]
            actual = opening + received - v["fuel_close"]
            if actual < 0:
                raise WorkError("Остаток больше начального топлива и поступлений. Сначала внесите недостающие заправки")
            distance = v["odo_end"] - v["odo_start"]
            norm = int((Decimal(distance) * v["rate"] / 100000).quantize(Decimal(1), rounding=ROUND_HALF_UP)) if v["rate"] is not None else None
            v.update(fuel_open=opening, refueled=received, actual=actual, distance=distance, norm=norm)
            if actual:
                self._movement(con, {"vehicle_id": wb["vehicle_id"], "employee_id": wb["employee_id"], "date": wb["end"],
                                     "kind": "writeoff", "liters": actual/1000, "note": "Путевой лист " + wb["number"]},
                               "waybill:"+item_id, closing=True)
            con.execute("UPDATE waybills SET status='closed',data=? WHERE id=?", (json.dumps(v, ensure_ascii=False), item_id))
            self.audit(con, "закрытие", "waybills", item_id, v)
            return self.get(con, "waybills", item_id)

    def attendance(self, data):
        with self.transaction() as con:
            employee = self.get(con, "employees", data.get("employee_id"))
            start, end = date(data.get("start") or data.get("date")), date(data.get("end") or data.get("date") or data.get("start"))
            if end < start or (dt.date.fromisoformat(end)-dt.date.fromisoformat(start)).days > 366:
                raise WorkError("Выберите период не больше года")
            code = text(data.get("code"), 10).upper()
            if code and code not in CODES:
                raise WorkError("Выберите обозначение из списка")
            minutes = units(data.get("hours", 0), 60, maximum=24)
            if code not in WORK_CODES and minutes:
                raise WorkError("Для этого обозначения рабочие часы не указываются")
            day, count = dt.date.fromisoformat(start), 0
            while day.isoformat() <= end:
                if not data.get("weekdays_only") or day.weekday() < 5:
                    self._attendance(con, employee["id"], day.isoformat(), code, minutes, text(data.get("note"), 500))
                    count += 1
                day += dt.timedelta(days=1)
            self.audit(con, "заполнение", "attendance", employee["id"], {"start": start, "end": end, "code": code, "minutes": minutes, "count": count})
            return {"count": count}

    @staticmethod
    def _attendance(con, employee_id, day, code, minutes, note="", source="", import_mode=False):
        old = con.execute("SELECT code,minutes FROM attendance WHERE employee_id=? AND date=?", (employee_id, day)).fetchone()
        if import_mode and old:
            if old["code"] != code or old["minutes"] != minutes:
                raise WorkError(f"В табеле уже есть другая отметка за {day}. Импорт остановлен без изменения данных")
            return
        if not code:
            con.execute("DELETE FROM attendance WHERE employee_id=? AND date=?", (employee_id, day))
        else:
            con.execute("INSERT INTO attendance(employee_id,date,code,minutes,note,source) VALUES(?,?,?,?,?,?) "
                        "ON CONFLICT(employee_id,date) DO UPDATE SET code=excluded.code,minutes=excluded.minutes,note=excluded.note,source=excluded.source",
                        (employee_id, day, code, minutes, note, source))

    def allocate(self, data):
        start, end = date(data.get("start")), date(data.get("end"))
        if end < start:
            raise WorkError("Неверный период")
        with self.transaction() as con:
            card = self.get(con, "cards", data.get("card_id"))
            car = self.get(con, "vehicles", data.get("vehicle_id"))
            driver_id = data.get("employee_id") or card["employee_id"]
            if driver_id:
                self.get(con, "employees", driver_id)
            ops = self.rows(con, "SELECT o.* FROM card_ops o LEFT JOIN entries e ON e.id=o.entry_id "
                            "WHERE o.card_id=? AND o.date BETWEEN ? AND ? AND (o.entry_id IS NULL OR e.status='cancelled') ORDER BY o.date,o.time,o.id",
                            (card["id"], start, end))
            for op in ops:
                if fuel(op["product"]) != car["fuel"]:
                    raise WorkError("Вид топлива операции не совпадает с автомобилем. Выберите подходящую машину")
                entry = self._movement(con, {"date": op["date"], "vehicle_id": car["id"], "employee_id": driver_id,
                                             "card_id": card["id"], "kind": "receipt", "liters": op["liters"]/1000,
                                             "amount": op["amount"]/100 if op["amount"] is not None else None,
                                             "product": op["product"], "note": op["station"]}, "card:"+op["id"]+":"+ident())
                con.execute("UPDATE card_ops SET entry_id=? WHERE id=?", (entry["id"], op["id"]))
            return {"count": len(ops)}

    def report(self, month, con=None):
        if con is None:
            with contextlib.closing(self.connect()) as con:
                con.execute("BEGIN")
                return self.report(month, con)
        start, end = month_bounds(month)
        out = []
        for car in self.rows(con, "SELECT * FROM vehicles ORDER BY plate,model"):
            amounts = {r["kind"]: r["n"] for r in con.execute(
                "SELECT kind,SUM(liters) n FROM entries WHERE vehicle_id=? AND status='posted' AND date BETWEEN ? AND ? GROUP BY kind",
                (car["id"], start, end))}
            opening = self._balance(con, car["id"], start, before=True) + amounts.get("opening", 0)
            received, consumed = amounts.get("receipt", 0), amounts.get("writeoff", 0)
            docs = [json.loads(r["data"]) for r in con.execute(
                "SELECT data FROM waybills WHERE vehicle_id=? AND status='closed' AND end BETWEEN ? AND ?", (car["id"], start, end))]
            distance = sum(d["distance"] for d in docs)
            norm = sum(d["norm"] for d in docs) if docs and all(d["norm"] is not None for d in docs) else None
            out.append({"vehicle_id": car["id"], "model": car["model"], "plate": car["plate"], "fuel": car["fuel"],
                        "opening": opening, "received": received, "consumed": consumed, "closing": opening+received-consumed,
                        "distance": distance, "norm": norm, "variance": consumed-norm if norm is not None else None,
                        "waybills": len(docs)})
        return out

    def state(self, month):
        start, end = month_bounds(month)
        with contextlib.closing(self.connect()) as con:
            con.execute("BEGIN")
            out = {"month": month, "codes": CODES, "fuels": FUELS,
                   **{t: self.rows(con, f"SELECT * FROM {t} ORDER BY rowid") for t in ("employees", "vehicles", "cards", "assignments")}}
            out["report"] = self.report(month, con)
            out["balances"] = {v["id"]: self._balance(con, v["id"], dt.date.today().isoformat()) for v in out["vehicles"]}
            out["entries"] = self.rows(con, "SELECT * FROM entries WHERE date BETWEEN ? AND ? ORDER BY date DESC,created DESC LIMIT 2001", (start, end))
            out["waybills"] = self.rows(con, "SELECT * FROM waybills WHERE start<=? AND end>=? ORDER BY start DESC LIMIT 2001", (end, start))
            for wb in out["waybills"]:
                wb["data"] = json.loads(wb["data"])
            out["attendance"] = self.rows(con, "SELECT * FROM attendance WHERE date BETWEEN ? AND ?", (start, end))
            out["card_ops"] = self.rows(con, "SELECT * FROM card_ops WHERE date BETWEEN ? AND ? ORDER BY date,time LIMIT 2001", (start, end))
            out["monthly_reports"] = self.rows(con, "SELECT * FROM monthly_reports WHERE month=?", (month,))
            for record in out["monthly_reports"]:
                record["data"] = json.loads(record["data"])
            out["documents"] = self.rows(con, "SELECT * FROM documents ORDER BY created DESC LIMIT 100")
            out["imports"] = self.rows(con, "SELECT * FROM imports ORDER BY created DESC LIMIT 100")
            out["audit"] = self.rows(con, "SELECT * FROM audit ORDER BY seq DESC LIMIT 60")
            out["settings"] = {r["key"]: r["value"] for r in con.execute("SELECT * FROM settings")}
            out["limited"] = [k for k in ("entries", "waybills", "card_ops") if len(out[k]) > 2000]
            for k in out["limited"]:
                out[k] = out[k][:2000]
            return out

    def settings(self, data):
        with self.transaction() as con:
            for key in ("organization", "department", "responsible"):
                if key in data:
                    con.execute("INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)", (key, text(data[key], 300)))
            self.audit(con, "настройки", "settings", "", {k: text(data[k], 300) for k in data if k in ("organization", "department", "responsible")})

    def backup(self):
        with self.lock, contextlib.closing(self.connect()) as con:
            con.execute("BEGIN")
            return {"format": "yakumo-work-1", "created": int(time.time()),
                    "tables": {t: self.rows(con, f"SELECT * FROM {t}") for t in TABLES}}
