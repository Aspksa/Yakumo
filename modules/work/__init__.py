"""«Работа»: гараж, путевые листы, водители, топливные карты, табель и ГСМ."""

from __future__ import annotations

import datetime as dt
import contextlib
import json
from urllib.parse import parse_qs, quote, urlsplit

from yakumo.web.server import SENT

from .books import MAX_UPLOAD
from .imports import Imports
from .reports import csv_bytes, print_page
from .store import Work, WorkError

NAME = "Работа"
VERSION = "1.0"


def query(req):
    return {k: v[0] for k, v in parse_qs(urlsplit(req.path).query).items()}


def body(req):
    d = req.read_json()
    if not isinstance(d, dict):
        raise WorkError("Нужен объект JSON")
    return d


def setup(ctx):
    work = Work(ctx.paths.data / "work")
    imports = Imports(work)
    ctx.services["work"] = work

    def state(req):
        return work.state(query(req).get("month", dt.date.today().strftime("%Y-%m")))

    def save(req):
        d = body(req)
        if not isinstance(d.get("data"), dict):
            raise WorkError("Нужны поля записи")
        return work.save_reference(d.get("kind"), d["data"])

    def cancel(req):
        d = body(req)
        return work.cancel(d.get("kind"), str(d.get("id", "")), d.get("reason"))

    def uploaded(req):
        try:
            size = int(req.headers.get("Content-Length", "-1"))
        except ValueError as exc:
            raise WorkError("Неизвестный размер файла") from exc
        if not 0 < size <= MAX_UPLOAD:
            raise WorkError("Excel-файл должен быть не больше 16 МБ")
        content = req.rfile.read(size)
        if len(content) != size:
            raise WorkError("Файл передан не полностью")
        return imports.upload(query(req).get("name", ""), content)

    def imported(req, commit=False):
        d = body(req)
        return (imports.commit if commit else imports.preview)(str(d.get("id", "")), str(d.get("sheet", "")), d.get("period") or None)

    def download(req, name, mime, content):
        req._send(200, mime, content, {"Content-Disposition": "attachment; filename*=UTF-8''"+quote(name, safe="")})
        return SENT

    def export(req):
        q = query(req)
        month, kind = q.get("month", dt.date.today().strftime("%Y-%m")), q.get("kind", "fuel")
        return download(req, f"Работа-{kind}-{month}.csv", "text/csv; charset=utf-8", csv_bytes(work.state(month), kind))

    def backup(req):
        return download(req, "Yakumo-Работа-"+dt.date.today().isoformat()+".json", "application/json; charset=utf-8",
                        json.dumps(work.backup(), ensure_ascii=False, indent=2).encode())

    def source(req):
        record, data = imports.document(query(req).get("id", ""))
        return download(req, record["name"], "application/octet-stream", data)

    def printing(req):
        q = query(req)
        return print_page(work, q.get("month", dt.date.today().strftime("%Y-%m")), q.get("kind", "fuel"), q.get("id"))

    def defaults(req):
        q = query(req)
        from .store import date
        start, end = date(q.get("start")), date(q.get("end") or q.get("start"))
        with contextlib.closing(work.connect()) as con:
            car = work.get(con, "vehicles", q.get("vehicle_id"))
            assignments = work.rows(con, "SELECT * FROM assignments WHERE vehicle_id=? AND start<=? AND (end IS NULL OR end>=?)",
                                    (car["id"], start, end))
            previous = con.execute("SELECT data FROM waybills WHERE vehicle_id=? AND status='closed' AND end<? ORDER BY end DESC LIMIT 1",
                                   (car["id"], start)).fetchone()
            return {"employee_id": assignments[0]["employee_id"] if assignments else None,
                    "rate": car["rate"], "odo_start": json.loads(previous["data"])["odo_end"] if previous else None,
                    "fuel_open": work._balance(con, car["id"], start, before=True),
                    "refueled": con.execute("SELECT COALESCE(SUM(liters),0) FROM entries WHERE vehicle_id=? AND date BETWEEN ? AND ? "
                                            "AND kind IN ('opening','receipt') AND status='posted'", (car["id"], start, end)).fetchone()[0]}

    def disk_candidates(_req):
        """Только предложения из Диска: в учёт ничего не записывается без подтверждения пользователя."""
        services = getattr(ctx, "services", {})
        disk_service = services.get("disk") if isinstance(services, dict) else None
        if disk_service is None or not hasattr(disk_service, "work_candidates"):
            return {"items": [], "available": False}
        try:
            return {"items": disk_service.work_candidates(), "available": True,
                    "warning": "Кандидаты требуют проверки по исходному документу"}
        except Exception as exc:  # noqa: BLE001
            ctx.log.warning("Работа: не удалось получить кандидатов Диска: %s", exc)
            return {"items": [], "available": False, "error": str(exc)}

    routes = {
        "/api/work": state,
        "/api/work/disk-candidates": disk_candidates,
        "POST /api/work/save": save,
        "POST /api/work/assignment": lambda r: work.assignment(body(r)),
        "POST /api/work/movement": lambda r: work.movement(body(r)),
        "POST /api/work/waybill": lambda r: work.waybill(body(r)),
        "POST /api/work/waybill/close": lambda r: work.close_waybill(str(body(r).get("id", ""))),
        "/api/work/waybill/defaults": defaults,
        "POST /api/work/cancel": cancel,
        "POST /api/work/attendance": lambda r: work.attendance(body(r)),
        "POST /api/work/cards/allocate": lambda r: work.allocate(body(r)),
        "POST /api/work/settings": lambda r: (work.settings(body(r)), {"ok": True})[1],
        "POST /api/work/import/upload": uploaded,
        "/api/work/import/book": lambda r: imports.inspect(query(r).get("id", "")),
        "POST /api/work/import/preview": imported,
        "POST /api/work/import/commit": lambda r: imported(r, True),
        "/api/work/source": source,
        "/api/work/export": export,
        "/api/work/backup": backup,
        "/api/work/print": printing,
    }
    for path, handler in routes.items():
        ctx.route(path, handler)
    ctx.web("work.css", "work.js")
    ctx.status(lambda: {"version": VERSION, "ready": True})
    ctx.chat_tool("work_report", "Учёт работы: отчёт по ГСМ за month (ГГГГ-ММ). Только проведённые операции, литры и километры в тысячных. Не включает импортированные итоги для сверки.",
                  lambda d: {"month": d.get("month") or dt.date.today().strftime("%Y-%m"), "scale": 1000,
                             "report": work.report(d.get("month") or dt.date.today().strftime("%Y-%m"))})
