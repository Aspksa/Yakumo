"""Печатные рабочие формы и CSV для Excel. Все числа — из проведённых записей."""

from __future__ import annotations

import contextlib
import csv
import html
import io
import re

from .store import WORK_CODES, WorkError, month_bounds


def num(value, scale=1000, digits=3):
    if value is None:
        return ""
    s = f"{value/scale:.{digits}f}"
    return s.rstrip("0").rstrip(".") if digits == 3 else s


def timesheet(state):
    start, end = month_bounds(state["month"])
    days = int(end[-2:])
    entries = {(x["employee_id"], x["date"]): x for x in state["attendance"]}
    rows = []
    for employee in state["employees"]:
        records = [entries.get((employee["id"], f"{state['month']}-{day:02}")) for day in range(1, days+1)]
        if not employee["active"] and not any(records):
            continue
        hours = sum(x["minutes"] for x in records if x and x["code"] in WORK_CODES)
        worked = sum(1 for x in records if x and x["code"] in WORK_CODES and x["minutes"] > 0)
        rows.append({"employee": employee, "days": records, "minutes": hours, "worked": worked})
    return rows


def grid(state, kind):
    emp = {x["id"]: x["name"] for x in state["employees"]}
    cars = {x["id"]: (x["plate"]+" "+x["model"]).strip() for x in state["vehicles"]}
    cards = {x["id"]: x["number"] for x in state["cards"]}
    if kind == "fuel":
        return ["Госномер", "Модель", "Топливо", "Остаток на начало, л", "Поступление, л", "Списание, л", "Остаток на конец, л", "Пробег по закрытым листам, км", "Расход по норме, л", "Отклонение, л", "Закрытых путевых листов"], [
            [r["plate"], r["model"], r["fuel"], *[num(r[k]) for k in ("opening", "received", "consumed", "closing", "distance", "norm", "variance")], r["waybills"]]
            for r in state["report"]]
    if kind == "attendance":
        days = int(month_bounds(state["month"])[1][-2:])
        return ["Сотрудник", "Должность", "Табельный номер", *[str(i) for i in range(1, days+1)], "Отработано дней", "Часов"], [
            [r["employee"]["name"], r["employee"]["position"], r["employee"]["personnel_no"],
             *[(x["code"]+(" / "+num(x["minutes"], 60, 2) if x["minutes"] else "")) if x else "" for x in r["days"]],
             r["worked"], num(r["minutes"], 60, 2)] for r in timesheet(state)]
    if kind == "entries":
        return ["Дата", "Автомобиль", "Водитель", "Карта", "Операция", "Литры", "Сумма, руб.", "Топливо", "Примечание", "Статус"], [
            [r["date"], cars.get(r["vehicle_id"], ""), emp.get(r["employee_id"], ""), cards.get(r["card_id"], ""),
             {"opening": "Начальный остаток", "receipt": "Поступление", "writeoff": "Списание"}.get(r["kind"], r["kind"]),
             num(r["liters"]), num(r["amount"], 100, 2), r["product"], r["note"], r["status"]] for r in state["entries"]]
    if kind == "reconciliation":
        return ["Месяц", "Автомобиль", "Водитель", "Остаток на начало, л", "Поступление, л", "Расход факт, л", "Расход норма, л", "Остаток на конец, л", "Пробег, км", "Расхождение остатка, л"], [
            [r["month"], cars.get(r["vehicle_id"], ""), emp.get(r["employee_id"], ""),
             *[num(r["data"].get(k)) for k in ("opening", "received", "actual", "norm", "closing", "distance", "balance_delta")]]
            for r in state["monthly_reports"]]
    raise WorkError("Неизвестный вид отчёта")


def csv_bytes(state, kind):
    if kind in state["limited"] or kind == "entries" and "entries" in state["limited"]:
        raise WorkError("В месяце больше 2000 операций. Полная выгрузка доступна в резервной копии JSON")
    headers, rows = grid(state, kind)
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, delimiter=";", lineterminator="\r\n")
    def cell(v, header):
        # Защита текстовых полей от исполнения как формул при открытии CSV в Excel.
        s = str(v if v is not None else "")
        if header in ("Карта", "Табельный номер") and s:
            return "'"+s
        if re.fullmatch(r"-?\d+(?:\.\d+)?", s) and (", л" in header or ", км" in header or ", руб." in header or header in ("Часов", "Литры")):
            return s.replace(".", ",")
        return "'"+s if s.lstrip().startswith(("=", "+", "@", "\t", "\r")) or s.startswith("-") and not s[1:].replace(".", "", 1).isdigit() else s
    writer.writerow(headers)
    writer.writerows([[cell(v, headers[i]) for i,v in enumerate(row)] for row in rows])
    return ("\ufeff"+stream.getvalue()).encode("utf-8")


STYLE = """body{font:14px Arial,sans-serif;color:#171717;margin:28px}h1{font-size:24px;margin-bottom:8px}
table{border-collapse:collapse;width:100%;margin:22px 0}th,td{border:1px solid #999;padding:6px;text-align:left;vertical-align:top}
th{background:#f3f3f3}p{line-height:1.5;white-space:pre-wrap}small{color:#555}button{padding:10px 18px;cursor:pointer}
.sign{margin-top:40px;display:flex;gap:60px}.status{font-weight:bold}@media print{button{display:none}body{margin:8px;font-size:11px}thead{display:table-header-group}tr{break-inside:avoid}}@page{size:A4 landscape;margin:12mm}"""


def print_page(work, month, kind, item_id=None):
    state = work.state(month)
    esc = lambda x: html.escape(str(x if x is not None else ""), quote=True)
    settings = state["settings"]
    heading = ""
    if kind == "waybill":
        with contextlib.closing(work.connect()) as con:
            wb = work.get(con, "waybills", item_id)
        import json
        d = json.loads(wb["data"])
        title = "Путевой лист № " + wb["number"]
        heading = f"<p class='status'>{esc({'draft':'Черновик','closed':'Закрыт','cancelled':'Отменён'}[wb['status']])}</p>"
        pairs = [("Период", wb["start"]+" — "+wb["end"]), ("Автомобиль", d["vehicle_model"]), ("Госномер", d["plate"]),
                 ("Водитель", d["driver_name"]), ("Маршрут и задание", d.get("route", "")),
                 ("Одометр при выезде, км", num(d["odo_start"])), ("Одометр при возвращении, км", num(d["odo_end"])),
                 ("Пробег, км", num(d.get("distance"))), ("Топливо", d["fuel"]),
                 ("Остаток при выезде, л", num(d.get("fuel_open"))), ("Поступило, л", num(d.get("refueled"))),
                 ("Остаток при возвращении, л", num(d.get("fuel_close"))), ("Расход факт, л", num(d.get("actual"))),
                 ("Норма, л/100 км", num(d.get("rate"))), ("Расход по норме, л", num(d.get("norm"))), ("Примечание", d.get("note", ""))]
        body = "<table>"+"".join(f"<tr><th>{esc(k)}</th><td>{esc(v)}</td></tr>" for k, v in pairs)+"</table>"
        body += "<div class='sign'><p>Водитель __________________</p><p>Ответственный __________________</p></div>"
    else:
        title = {"fuel": "Учёт ГСМ", "attendance": "Табель сотрудников", "reconciliation": "Сверка месячных ведомостей", "entries": "Движение ГСМ"}.get(kind)
        if not title:
            raise WorkError("Неизвестная печатная форма")
        headers, rows = grid(state, kind)
        body = "<table><thead><tr>"+"".join("<th>"+esc(v)+"</th>" for v in headers)+"</tr></thead><tbody>"
        body += "".join("<tr>"+"".join("<td>"+esc(v)+"</td>" for v in row)+"</tr>" for row in rows)+"</tbody></table>"
        body += "<p>Ответственный: "+esc(settings.get("responsible", ""))+" __________________</p>"
    return "<!doctype html><html lang='ru'><meta charset='utf-8'><title>"+esc(title)+"</title><style>"+STYLE+"</style><body>" \
           +"<button type='button' onclick='window.print()'>Печать / сохранить PDF</button><h1>"+esc(title)+"</h1>" \
           +"<p>"+esc(settings.get("organization", ""))+"\n"+esc(settings.get("department", ""))+"</p>" \
           +("<p>Месяц: "+esc(month)+"</p>" if kind != "waybill" else "")+heading+body+"</body></html>"
