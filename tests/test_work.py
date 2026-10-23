import concurrent.futures
import datetime as dt
import io
import json
import struct
import tempfile
import threading
import unittest
from unittest import mock
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path
from types import SimpleNamespace
from xml.sax.saxutils import escape

from modules.work.books import Book, Strings
from modules.work.imports import Imports, parsed
from modules.work.reports import csv_bytes, print_page, timesheet
from modules.work.store import Work, WorkError, units
from yakumo.core.modules import Context, load_all
from yakumo.core.access import AccessControl
from yakumo.web.server import create_server


def xlsx(cells, name="Учёт", other=None):
    """Небольшой синтетический XLSX, без документов и персональных данных пользователя."""
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("xl/workbook.xml", '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="'+escape(name)+'" sheetId="1" r:id="rId9"/></sheets></workbook>')
        z.writestr("xl/_rels/workbook.xml.rels", '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId9" Target="worksheets/custom.xml"/></Relationships>')
        rows = {}
        for ref, value in cells.items():
            row = int("".join(c for c in ref if c.isdigit()))
            body = '<v>'+str(value)+'</v>' if isinstance(value, (int, float)) else '<is><t>'+escape(str(value))+'</t></is>'
            rows.setdefault(row, []).append('<c r="'+ref+'"'+(' t="inlineStr"' if isinstance(value, str) else '')+'>'+body+'</c>')
        z.writestr("xl/worksheets/custom.xml", '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>'+''.join('<row r="'+str(r)+'">'+''.join(v)+'</row>' for r, v in sorted(rows.items()))+'</sheetData></worksheet>')
        for key, value in (other or {}).items():
            z.writestr(key, value)
    return stream.getvalue()


def monthly(**updates):
    return {"B2": "Тестовая машина А 123 ВС", "D2": "Сентябрь 2026", "F2": "Иванов И.И.",
            "B4": "№ карты", "C4": "0012345678901234567", "B5": "Общий километраж", "D5": 100,
            "B6": "Остаток на 01.09.2026", "D6": 10, "B8": "Приход", "E8": "Расход", "B28": 20,
            "E28": 15, "B31": "(15*км/100)", "E31": 15, "B33": "Остаток на 30.09.2026", "B34": 15, **updates}


def card_cells(products=None):
    cells = {"A1": "Выписка по пластиковым картам", "A7": "Карта № 0012345678901234567", "A8": "Операция",
             "D8": "АЗС", "G8": "Кол-во"}
    for r, product in enumerate(products or ["Бензин АИ-95", "Бензин АИ-95"], 9):
        cells.update({f"A{r}": "Отгрузка", f"B{r}": f"{r-8:02}.09.26", f"C{r}": "12:00:00", f"D{r}": "Тестовая АЗС",
                      f"E{r}": product, f"F{r}": 70.11, f"G{r}": 10.125, f"H{r}": 709.86})
    return cells


def old_xls(cells):
    def rec(code, data=b""):
        return struct.pack("<HH", code, len(data))+data
    bof = rec(0x0809, struct.pack("<HH", 0x0500, 5))
    name = b"Sheet1"
    bounds = lambda offset: rec(0x85, struct.pack("<IBBB", offset, 0, 0, len(name))+name)
    head = bof+bounds(0)+rec(0xA)
    head = bof+bounds(len(head))+rec(0xA)
    sheet = rec(0x0809, struct.pack("<HH", 0x0500, 0x10))
    for (r, c), value in cells.items():
        prefix = struct.pack("<HHH", r, c, 0)
        if isinstance(value, str):
            b = value.encode("cp1251")
            sheet += rec(0x204, prefix+struct.pack("<H", len(b))+b)
        else:
            sheet += rec(0x203, prefix+struct.pack("<d", value))
    stream = (head+sheet+rec(0xA)).ljust(4096, b"\0")
    header = bytearray(512)
    header[:8] = bytes.fromhex("d0cf11e0a1b11ae1")
    struct.pack_into("<HHHH", header, 24, 0x3E, 3, 0xFFFE, 9)
    struct.pack_into("<H", header, 32, 6)
    struct.pack_into("<I", header, 44, 1)
    struct.pack_into("<I", header, 48, 0)
    struct.pack_into("<I", header, 56, 4096)
    struct.pack_into("<I", header, 60, 0xFFFFFFFE)
    struct.pack_into("<I", header, 68, 0xFFFFFFFE)
    struct.pack_into("<109I", header, 76, 1, *([0xFFFFFFFF]*108))
    directory = bytearray(512)
    for pos, name, kind, start, length in ((0, "Root Entry", 5, 0xFFFFFFFE, 0), (128, "Workbook", 2, 2, len(stream))):
        b = (name+"\0").encode("utf-16le")
        directory[pos:pos+len(b)] = b
        struct.pack_into("<H", directory, pos+64, len(b))
        directory[pos+66] = kind
        struct.pack_into("<I", directory, pos+116, start)
        struct.pack_into("<Q", directory, pos+120, length)
    fat = [0xFFFFFFFE, 0xFFFFFFFD, *range(3, 10), 0xFFFFFFFE]+[0xFFFFFFFF]*118
    return bytes(header)+bytes(directory)+struct.pack("<128I", *fat)+stream


class WorkTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="Работа с пробелами ")
        self.addCleanup(self.tmp.cleanup)
        self.work = Work(Path(self.tmp.name))
        self.imports = Imports(self.work)
        self.car = self.work.save_reference("vehicles", {"model": "Тестовая машина", "plate": "А 123 ВС", "fuel": "Бензин", "rate": "10", "tank": 200})
        self.driver = self.work.save_reference("employees", {"name": "Иванов И.И.", "is_driver": True})
        self.work.assignment({"employee_id": self.driver["id"], "vehicle_id": self.car["id"], "start": "2026-01-01"})

    def state(self):
        return self.work.state("2026-09")

    def movement(self, kind, liters, day="2026-09-01", **kw):
        return self.work.movement({"vehicle_id": self.car["id"], "date": day, "kind": kind, "liters": liters, **kw})

    def waybill(self, **kw):
        return self.work.waybill({"number": "ПЛ-1", "start": "2026-09-01", "end": "2026-09-01", "employee_id": self.driver["id"],
                                  "vehicle_id": self.car["id"], "odo_start": 100, "odo_end": 200, "fuel_close": 90, **kw})

    def test_decimal_and_nonfinite_input(self):
        self.assertEqual(units("1 234,5675"), 1234568)
        self.assertEqual(units("1.005", 100), 101)
        for value in ("NaN", "Infinity", -1, True, "bad"):
            with self.assertRaises(WorkError): units(value)

    def test_plate_and_card_identifiers(self):
        with self.assertRaises(WorkError):
            self.work.save_reference("vehicles", {"model": "Дубль", "plate": "A123BC", "fuel": "Бензин"})
        c = self.work.save_reference("cards", {"number": "0012345678901234567", "employee_id": self.driver["id"]})
        self.assertEqual(c["number"], "0012345678901234567")
        with self.assertRaises(WorkError): self.work.save_reference("cards", {"number": 1234567890123456789})

    def test_assignment_overlap_and_transfer(self):
        second = self.work.save_reference("employees", {"name": "Петров П.П.", "is_driver": True})
        with self.assertRaises(WorkError):
            self.work.assignment({"employee_id": second["id"], "vehicle_id": self.car["id"], "start": "2026-09-02"})
        a = self.state()["assignments"][0]
        self.work.assignment({**a, "end": "2026-09-01"})
        self.work.assignment({"employee_id": second["id"], "vehicle_id": self.car["id"], "start": "2026-09-02"})
        self.assertEqual(len(self.state()["assignments"]), 2)

    def test_negative_balance_is_atomic(self):
        self.movement("opening", 10)
        before = self.work.backup()
        with self.assertRaises(WorkError): self.movement("writeoff", 11)
        after = self.work.backup()
        self.assertEqual(before["tables"], after["tables"])

    def test_opening_chronology(self):
        self.movement("opening", 10, "2026-09-02")
        with self.assertRaises(WorkError): self.movement("receipt", 5, "2026-09-01")
        with self.assertRaises(WorkError): self.movement("opening", 5, "2026-09-03")

    def test_cancel_cannot_make_future_balance_negative(self):
        r = self.movement("receipt", 20)
        self.movement("writeoff", 15, "2026-09-02")
        with self.assertRaises(WorkError): self.work.cancel("entries", r["id"], "Ошибка ввода")
        self.assertEqual(self.state()["balances"][self.car["id"]], 5000)
        self.assertTrue(all(x["status"] == "posted" for x in self.state()["entries"]))

    def test_waybill_closure_snapshot_and_report(self):
        self.movement("opening", 100)
        self.movement("receipt", 50)
        wb = self.waybill(odo_end=300, fuel_close=130)
        self.work.close_waybill(wb["id"])
        d = self.state()
        closed = d["waybills"][0]["data"]
        self.assertEqual((closed["distance"], closed["actual"], closed["norm"]), (200000, 20000, 20000))
        self.assertEqual(d["report"][0]["closing"], 130000)
        self.work.save_reference("vehicles", {"id": self.car["id"], "model": "Новое имя", "rate": 99})
        self.assertEqual(self.state()["waybills"][0]["data"]["vehicle_model"], "Тестовая машина")
        with self.assertRaises(WorkError): self.waybill(id=wb["id"])

    def test_concurrent_close_does_not_double_writeoff(self):
        self.movement("opening", 100)
        wb = self.waybill()
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(lambda _: self.work.close_waybill(wb["id"]), range(2)))
        d = self.state()
        self.assertEqual(len([e for e in d["entries"] if e["kind"] == "writeoff"]), 1)
        self.assertEqual(d["balances"][self.car["id"]], 90000)

    def test_failed_closure_keeps_draft_and_ledger(self):
        self.movement("opening", 5)
        wb = self.waybill(fuel_close=10)
        with self.assertRaises(WorkError): self.work.close_waybill(wb["id"])
        self.assertEqual(self.state()["waybills"][0]["status"], "draft")
        self.assertEqual(len(self.state()["entries"]), 1)

    def test_manual_consumption_and_closed_period_protection(self):
        self.movement("opening", 100)
        self.movement("writeoff", 5)
        wb = self.waybill()
        with self.assertRaises(WorkError): self.work.close_waybill(wb["id"])
        entry = next(e for e in self.state()["entries"] if e["kind"] == "writeoff")
        self.work.cancel("entries", entry["id"], "Расход будет по путевому")
        self.work.close_waybill(wb["id"])
        with self.assertRaises(WorkError): self.movement("receipt", 5)
        self.work.cancel("waybills", wb["id"], "Исправление")
        self.assertEqual(self.state()["balances"][self.car["id"]], 100000)

    def test_assignment_cannot_remove_closed_document_coverage(self):
        self.movement("opening", 100)
        wb = self.waybill()
        self.work.close_waybill(wb["id"])
        a = self.state()["assignments"][0]
        with self.assertRaises(WorkError): self.work.assignment({**a, "end": "2026-08-31"})

    def test_later_waybill_must_be_cancelled_first(self):
        self.movement("opening", 100)
        older = self.waybill()
        later = self.waybill(number="ПЛ-2", start="2026-09-02", end="2026-09-02", odo_start=200, odo_end=300, fuel_close=80)
        self.work.close_waybill(later["id"])
        with self.assertRaises(WorkError): self.work.close_waybill(older["id"])
        self.work.cancel("waybills", older["id"], "Черновик не использован")
        self.assertEqual(next(w for w in self.state()["waybills"] if w["id"] == later["id"])["status"], "closed")

    def test_attendance_leap_year_and_hours(self):
        self.work.attendance({"employee_id": self.driver["id"], "date": "2028-02-29", "code": "Я", "hours": "7.5"})
        s = self.work.state("2028-02")
        self.assertEqual(timesheet(s)[0]["minutes"], 450)
        for d in ({"date": "2026-02-29", "code": "Я", "hours": 8}, {"date": "2026-09-01", "code": "Б", "hours": 8}, {"date": "2026-09-01", "code": "Я", "hours": 25}):
            with self.assertRaises(WorkError): self.work.attendance({"employee_id": self.driver["id"], **d})

    def test_attendance_fill_and_clear(self):
        d = {"employee_id": self.driver["id"], "start": "2026-09-04", "end": "2026-09-07", "code": "Я", "hours": 8, "weekdays_only": True}
        self.assertEqual(self.work.attendance(d)["count"], 2)
        self.work.attendance({"employee_id": self.driver["id"], "date": "2026-09-04", "code": "", "hours": 0})
        self.assertEqual(len(self.state()["attendance"]), 1)

    def test_monthly_import_is_previewed_and_not_a_second_ledger(self):
        doc = self.imports.upload("ведомость.xlsx", xlsx(monthly(), "Старое название 2024"))
        before = len(self.state()["vehicles"])
        p = self.imports.preview(doc["id"], doc["sheets"][0])
        self.assertEqual(p["period"], "2026-09")
        self.assertEqual(len(self.state()["vehicles"]), before)
        self.imports.commit(doc["id"], doc["sheets"][0])
        self.assertEqual(len(self.state()["entries"]), 0)
        self.assertEqual(len(self.state()["monthly_reports"]), 1)
        self.assertEqual(self.state()["cards"][0]["number"], "0012345678901234567")
        with self.assertRaises(WorkError): self.imports.commit(doc["id"], doc["sheets"][0])

    def test_source_formula_error_and_balance_mismatch_are_visible(self):
        book = Book(xlsx(monthly(B34="#VALUE!")), ".xlsx")
        p = parsed(book.sheet(book.names[0]))
        self.assertTrue(any("B34" in e for e in p["errors"]))
        book = Book(xlsx(monthly(B34=99)), ".xlsx")
        p = parsed(book.sheet(book.names[0]))
        self.assertEqual(p["records"][0]["balance_delta"], -84000)
        self.assertTrue(any("не сходится" in w for w in p["warnings"]))

    def test_card_import_allocation_and_dedup(self):
        raw = xlsx(card_cells())
        doc = self.imports.upload("выписка.xlsx", raw)
        self.assertEqual(self.imports.commit(doc["id"], doc["sheets"][0])["count"], 2)
        c = self.state()["cards"][0]
        args = {"card_id": c["id"], "vehicle_id": self.car["id"], "employee_id": self.driver["id"], "start": "2026-09-01", "end": "2026-09-30"}
        self.assertEqual(len(self.state()["entries"]), 0)
        self.assertEqual(self.work.allocate(args)["count"], 2)
        self.assertEqual(self.work.allocate(args)["count"], 0)
        self.assertEqual(self.state()["balances"][self.car["id"]], 20250)
        doc2 = self.imports.upload("другой-отчёт.xlsx", xlsx(card_cells(), "Другой лист"))
        result = self.imports.commit(doc2["id"], doc2["sheets"][0])
        self.assertEqual((result["count"], result["skipped"]), (0, 2))

    def test_allocation_rolls_back_entire_batch_on_wrong_product(self):
        doc = self.imports.upload("выписка.xlsx", xlsx(card_cells(["Бензин АИ-95", "Топливо дизельное ДТ"])))
        self.imports.commit(doc["id"], doc["sheets"][0])
        with self.assertRaises(WorkError): self.work.allocate({"card_id": self.state()["cards"][0]["id"], "vehicle_id": self.car["id"], "start": "2026-09-01", "end": "2026-09-30"})
        self.assertEqual(self.state()["entries"], [])
        self.assertTrue(all(o["entry_id"] is None for o in self.state()["card_ops"]))

    def test_cancelled_card_receipt_can_be_corrected_without_losing_history(self):
        doc = self.imports.upload("выписка.xlsx", xlsx(card_cells()))
        self.imports.commit(doc["id"], doc["sheets"][0])
        card = self.state()["cards"][0]
        args = {"card_id": card["id"], "vehicle_id": self.car["id"], "start": "2026-09-01", "end": "2026-09-30"}
        self.work.allocate(args)
        entry = self.state()["entries"][0]
        self.work.cancel("entries", entry["id"], "Уточнение поступления")
        self.assertEqual(self.work.allocate(args)["count"], 1)
        self.assertEqual(self.state()["balances"][self.car["id"]], 20250)
        self.assertEqual(len(self.state()["entries"]), 3)
        with self.assertRaises(WorkError):
            self.work.save_reference("cards", {"id": card["id"], "number": "9999999999999999999"})

    def test_csv_preserves_card_identifiers_and_decimal_cents(self):
        card = self.work.save_reference("cards", {"number": "0012345678901234567"})
        self.movement("receipt", "1.125", amount="12.30", card_id=card["id"])
        result = csv_bytes(self.state(), "entries").decode("utf-8-sig")
        self.assertIn("'0012345678901234567", result)
        self.assertIn("1,125", result)
        self.assertIn("12,30", result)

    def test_import_attendance_conflict_is_atomic(self):
        cells = {"A1": "ТАБЕЛЬ", "A2": "Сентябрь 2026", "B4": "Фамилия", "A7": 1, "B7": "Иванов И.И."}
        for i in range(1, 31):
            column = ""; n = i+2
            while n: n, r = divmod(n-1, 26); column = chr(65+r)+column
            cells[column+"5"] = i
        cells.update({"C7": "Я", "C8": 8, "D7": "Я", "D8": 8})
        self.work.attendance({"employee_id": self.driver["id"], "date": "2026-09-02", "code": "Б", "hours": 0})
        doc = self.imports.upload("табель.xlsx", xlsx(cells))
        before = self.work.backup()["tables"]
        with self.assertRaises(WorkError): self.imports.commit(doc["id"], doc["sheets"][0])
        self.assertEqual(before, self.work.backup()["tables"])

    def test_csv_and_print_escape_untrusted_text(self):
        self.work.save_reference("vehicles", {"id": self.car["id"], "model": "=DDE()"})
        self.assertIn("'=DDE()", csv_bytes(self.state(), "fuel").decode("utf-8-sig"))
        self.work.settings({"organization": "<script>alert(1)</script>"})
        page = print_page(self.work, "2026-09", "fuel")
        self.assertNotIn("<script>", page)
        self.assertIn("&lt;script&gt;", page)

    def test_reopen_storage_and_backup(self):
        self.movement("opening", "12.125")
        again = Work(self.work.root)
        self.assertEqual(again.state("2026-09")["balances"][self.car["id"]], 12125)
        self.assertEqual(again.backup()["format"], "yakumo-work-1")


class BooksTest(unittest.TestCase):
    def test_old_xls_without_codepage_uses_cyrillic(self):
        raw = old_xls({(0, 0): "Выписка по пластиковым картам", (6, 0): "Карта № 0012345678901234567",
                       (7, 0): "Операция", (7, 3): "АЗС", (7, 6): "Кол-во", (8, 0): "Отгрузка", (8, 1): "01.09.26",
                       (8, 2): "12:30:00", (8, 3): "Тестовая АЗС", (8, 4): "Бензин АИ-95", (8, 5): 75.01, (8, 6): 12.5, (8, 7): 937.63})
        b = Book(raw, ".xls")
        p = parsed(b.sheet("Sheet1"))
        self.assertEqual((len(p["records"]), p["records"][0]["liters"]), (1, 12500))
        self.assertEqual(p["records"][0]["card"], "0012345678901234567")

    def test_sst_unicode_continuation(self):
        reader = Strings([struct.pack("<HB", 3, 1)+"А".encode("utf-16le"), b"\x01"+"Б".encode("utf-16le"), b"\x00c"])
        self.assertEqual(reader.string(), "АБc")

    def test_malformed_files_are_rejected(self):
        for raw, ext in ((b"not excel", ".xls"), (b"not zip", ".xlsx"), (b"123", ".xlsm")):
            with self.assertRaises(WorkError): Book(raw, ext)
        raw = bytearray(old_xls({(0, 0): "test"}))
        struct.pack_into("<I", raw, 1024+2*4, 2)
        with self.assertRaises(WorkError): Book(bytes(raw), ".xls")

    def test_xlsx_relationships_and_sparse_cells(self):
        b = Book(xlsx({"B2": "значение", "XFD1000000": "далеко"}), ".xlsx")
        self.assertEqual(b.sheet(b.names[0]).at(1, 1), "значение")
        self.assertEqual(len(b.sheet(b.names[0]).cells), 2)


class WorkAPITest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        ctx = Context(paths=SimpleNamespace(data=root), config=SimpleNamespace())
        modules = Path(__file__).resolve().parents[1] / "modules"
        disabled = [p.name if p.is_dir() else p.stem for p in modules.iterdir() if p.name != "work"]
        infos = load_all(ctx, [modules], disabled=disabled)
        self.assertEqual([(i.name, i.error) for i in infos], [("work", None)])
        self.access = AccessControl(root / "access.json")
        self.server = create_server("127.0.0.1", 0, root, ctx.routes, access=self.access)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"

    def call(self, path, data=None, raw=False):
        headers = {"X-Yakumo": "1"} if raw else {"Content-Type": "application/json"}
        payload = data if raw else json.dumps(data).encode() if data is not None else None
        req = urllib.request.Request(self.url+path, data=payload, headers=headers)
        try:
            with urllib.request.urlopen(req) as r: return r.status, dict(r.headers), r.read()
        except urllib.error.HTTPError as e: return e.code, dict(e.headers), e.read()

    def test_api_validation_and_assets(self):
        self.assertEqual(self.call("/api/work?month=2026-09")[0], 200)
        self.assertEqual(self.call("/api/work?month=2026-13")[0], 400)
        self.assertEqual(self.call("/api/work/save", [])[0], 400)
        self.assertEqual(self.call("/modules/work/work.js")[0], 200)
        self.assertEqual(self.call("/modules/work/work.css")[0], 200)

    def test_upload_preview_commit_and_download(self):
        code, _, data = self.call("/api/work/import/upload?name="+urllib.parse.quote("Пример.xlsx"), xlsx(monthly()), raw=True)
        self.assertEqual(code, 200, data)
        d = json.loads(data)
        args = {"id": d["id"], "sheet": d["sheets"][0]}
        self.assertEqual(self.call("/api/work/import/preview", args)[0], 200)
        self.assertEqual(self.call("/api/work/import/commit", args)[0], 200)
        self.assertEqual(self.call("/api/work/import/commit", args)[0], 400)
        code, headers, data = self.call("/api/work/source?id="+d["id"])
        self.assertEqual(code, 200)
        self.assertTrue(headers["Content-Disposition"].startswith("attachment;"))
        self.assertTrue(zipfile.is_zipfile(io.BytesIO(data)))
        self.assertEqual(self.call("/api/work/source?id=../../nope")[0], 400)

    def test_exports(self):
        code, headers, data = self.call("/api/work/export?kind=fuel&month=2026-09")
        self.assertEqual(code, 200)
        self.assertTrue(data.startswith(b"\xef\xbb\xbf"))
        self.assertIn("attachment", headers["Content-Disposition"])
        self.assertEqual(json.loads(self.call("/api/work/backup")[2])["format"], "yakumo-work-1")
        self.assertIn("Табель сотрудников", self.call("/api/work/print?kind=attendance&month=2026-09")[2].decode())

    def test_lan_requires_login_for_data_source_and_writes(self):
        with mock.patch.object(self.access, "is_local", return_value=False):
            for path in ("/api/work", "/api/work/backup", "/api/work/source?id=anything", "/api/work/print?kind=fuel"):
                self.assertEqual(self.call(path)[0], 401)
            self.assertEqual(self.call("/api/work/save", {"kind": "employees", "data": {"name": "Нельзя"}})[0], 401)
