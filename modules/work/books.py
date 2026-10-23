"""Ограниченное чтение Excel без установки пакетов, макросов и внешних ссылок.

XLSX читается по XML-связям книги, без разворачивания пустых колонок до XFD.
Старые XLS: контейнер CFB и ячейки BIFF5/8, включая строки SST с продолжениями.
Значения формул берутся только из сохранённого Excel результата.
"""

from __future__ import annotations

import datetime as dt
import io
import posixpath
import re
import struct
import zipfile
from xml.etree import ElementTree as ET

from .store import WorkError

MAX_UPLOAD = 16 * 1024**2
MAX_XML = 32 * 1024**2
MAX_CELLS = 300000
NS = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


def xml(data):
    if len(data) > MAX_XML or b"<!DOCTYPE" in data.upper() or b"<!ENTITY" in data.upper():
        raise WorkError("Слишком большой или неподдерживаемый XML в книге")
    return ET.fromstring(data)


def col(ref):
    n = 0
    for c in re.match(r"[A-Za-z]+", ref).group(0).upper():
        n = n * 26 + ord(c) - 64
    return n - 1


def numeric(s):
    try:
        return int(s) if re.fullmatch(r"[+-]?\d+", s) else float(s)
    except (ValueError, OverflowError):
        return s


class Sheet:
    def __init__(self, name, cells):
        self.name, self.cells = name, cells
        self.height = max((r for r, _ in cells), default=-1) + 1

    def at(self, row, column, default=None):
        return self.cells.get((row, column), default)

    def row(self, row):
        return {c: v for (r, c), v in self.cells.items() if r == row}


class Book:
    def __init__(self, data: bytes, ext: str):
        if not data or len(data) > MAX_UPLOAD:
            raise WorkError("Размер Excel-файла должен быть от 1 байта до 16 МБ")
        self.data, self.ext = data, ext.lower()
        self.shared, self.date_styles, self.epoch1904 = [], set(), False
        self.parts, self.offsets = {}, {}
        try:
            if self.ext == ".xlsx":
                self._xlsx_metadata()
            elif self.ext == ".xls":
                self._xls_metadata()
            else:
                raise WorkError("Выберите Excel-файл .xlsx или .xls")
        except WorkError:
            raise
        except (KeyError, ValueError, IndexError, struct.error, ET.ParseError, zipfile.BadZipFile, UnicodeError, LookupError, OverflowError, RuntimeError) as exc:
            raise WorkError("Не удалось прочитать книгу Excel. Проверьте файл или сохраните его как .xlsx") from exc
        if not self.names or len(self.names) > 120 or len(set(self.names)) != len(self.names):
            raise WorkError("В книге нет доступных листов или слишком много листов")

    def _xlsx_metadata(self):
        with zipfile.ZipFile(io.BytesIO(self.data)) as z:
            infos = z.infolist()
            if len(infos) > 3000 or sum(i.file_size for i in infos) > 100 * 1024**2 or any(i.file_size > MAX_XML for i in infos):
                raise WorkError("Книга слишком велика после распаковки")
            if any(i.flag_bits & 1 for i in infos):
                raise WorkError("Защищённую паролем книгу нужно сохранить без пароля")
            wb = xml(z.read("xl/workbook.xml"))
            rels = xml(z.read("xl/_rels/workbook.xml.rels"))
            targets = {r.get("Id"): r.get("Target") for r in rels if r.get("TargetMode") != "External"}
            for s in wb.findall("s:sheets/s:sheet", NS):
                target = targets.get(s.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"))
                if not target:
                    continue
                path = posixpath.normpath(target.lstrip("/") if target.startswith("/") else "xl/"+target)
                if path.startswith("xl/worksheets/") and path in z.namelist():
                    self.parts[s.get("name")] = path
            self.names = list(self.parts)
            prop = wb.find("s:workbookPr", NS)
            self.epoch1904 = prop is not None and prop.get("date1904") in ("1", "true")
            if "xl/sharedStrings.xml" in z.namelist():
                strings = xml(z.read("xl/sharedStrings.xml"))
                self.shared = ["".join(t.text or "" for t in si.iter("{"+NS["s"]+"}t")) for si in strings]
            if "xl/styles.xml" in z.namelist():
                styles = xml(z.read("xl/styles.xml"))
                formats = {int(f.get("numFmtId")): f.get("formatCode", "") for f in styles.findall("s:numFmts/s:numFmt", NS)}
                for i, xf in enumerate(styles.findall("s:cellXfs/s:xf", NS)):
                    fmt_id = int(xf.get("numFmtId", 0))
                    code = re.sub(r'"[^"]*"|\[[^]]*\]|\\.', "", formats.get(fmt_id, "")).lower()
                    if fmt_id in range(14, 23) or ("d" in code and ("m" in code or "y" in code)):
                        self.date_styles.add(i)

    def sheet(self, name):
        if name not in self.names:
            raise WorkError("Выберите лист из книги")
        try:
            return self._xlsx_sheet(name) if self.ext == ".xlsx" else self._xls_sheet(name)
        except WorkError:
            raise
        except (ValueError, IndexError, KeyError, struct.error, ET.ParseError, UnicodeError, LookupError, OverflowError, RuntimeError, zipfile.BadZipFile) as exc:
            raise WorkError("Лист содержит неподдерживаемые данные. Сохраните его как обычную книгу .xlsx") from exc

    def _xlsx_sheet(self, name):
        with zipfile.ZipFile(io.BytesIO(self.data)) as z:
            root = xml(z.read(self.parts[name]))
        cells = {}
        for c in root.findall("s:sheetData/s:row/s:c", NS):
            ref, kind = c.get("r", ""), c.get("t", "n")
            if not re.fullmatch(r"[A-Z]+[1-9]\d*", ref):
                continue
            v = c.find("s:v", NS)
            if kind == "inlineStr":
                value = "".join(t.text or "" for t in c.iter("{"+NS["s"]+"}t"))
            elif v is None or v.text is None:
                continue  # нет сохранённого результата формулы — это не ноль
            elif kind == "s":
                value = self.shared[int(v.text)]
            elif kind in ("str", "e", "d"):
                value = v.text
            else:
                value = numeric(v.text)
                if int(c.get("s", "0")) in self.date_styles and isinstance(value, (int, float)):
                    base = dt.datetime(1904, 1, 1) if self.epoch1904 else dt.datetime(1899, 12, 30)
                    value = (base + dt.timedelta(days=value)).isoformat()
            if value != "":
                cells[(int(re.search(r"\d+", ref).group(0))-1, col(ref))] = value
            if len(cells) > MAX_CELLS:
                raise WorkError("В листе слишком много заполненных ячеек")
        return Sheet(name, cells)

    def _xls_metadata(self):
        stream = compound_stream(self.data)
        self.stream, self.biff, self.encoding = stream, 0x0500, "cp1251"
        records = list(biff_records(stream))
        if records and records[0][1] == 0x0809:
            self.biff = struct.unpack_from("<H", records[0][2])[0]
        if self.biff not in (0x0500, 0x0600):
            raise WorkError("Этот старый формат XLS не поддерживается. Сохраните книгу как .xlsx")
        if any(code == 0x002F for _, code, _ in records):
            raise WorkError("Защищённую паролем книгу нужно сохранить без пароля")
        for _, code, d in records:
            if code == 0x0042 and len(d) >= 2:
                n = struct.unpack_from("<H", d)[0]
                self.encoding = {1200: "utf-16le", 65001: "utf-8", 32769: "cp1252"}.get(n, "cp"+str(n))
        for i, (_, code, d) in enumerate(records):
            if code == 0x0085 and len(d) >= 7 and d[5] == 0:
                offset, length = struct.unpack_from("<I", d)[0], d[6]
                if self.biff == 0x0600:
                    wide = d[7] & 1
                    name = d[8:8+length*(2 if wide else 1)].decode("utf-16le" if wide else "latin1")
                else:
                    name = d[7:7+length].decode(self.encoding)
                self.offsets[name] = offset
            elif code == 0x00FC:
                pieces = [d[8:]]
                for _, nextcode, nd in records[i+1:]:
                    if nextcode != 0x003C:
                        break
                    pieces.append(nd)
                count = struct.unpack_from("<I", d, 4)[0]
                if count > MAX_CELLS:
                    raise WorkError("Слишком много строковых значений в книге")
                reader = Strings(pieces)
                self.shared = [reader.string() for _ in range(count)]
        self.names = list(self.offsets)

    def _xls_sheet(self, name):
        cells = {}
        for _, code, d in biff_records(self.stream, self.offsets[name]):
            if code == 0x000A:
                break
            if len(d) < 6:
                continue
            row, column = struct.unpack_from("<HH", d)
            value = None
            if code == 0x0203 and len(d) >= 14:
                value = struct.unpack_from("<d", d, 6)[0]
            elif code == 0x027E and len(d) >= 10:
                value = rk(struct.unpack_from("<I", d, 6)[0])
            elif code == 0x00BD and len(d) >= 12:
                for i in range((len(d)-6)//6):
                    cells[(row, column+i)] = rk(struct.unpack_from("<I", d, 6+i*6)[0])
            elif code == 0x00FD and len(d) >= 10:
                value = self.shared[struct.unpack_from("<I", d, 6)[0]]
            elif code == 0x0204 and len(d) >= 8:
                count = struct.unpack_from("<H", d, 6)[0]
                if self.biff == 0x0600:
                    wide = d[8] & 1
                    value = d[9:9+count*(2 if wide else 1)].decode("utf-16le" if wide else "latin1")
                else:
                    value = d[8:8+count].decode(self.encoding)
            elif code == 0x0006 and len(d) >= 14 and d[12:14] != b"\xff\xff":
                value = struct.unpack_from("<d", d, 6)[0]
            if value is not None:
                cells[(row, column)] = value
            if len(cells) > MAX_CELLS:
                raise WorkError("В листе слишком много заполненных ячеек")
        return Sheet(name, cells)


def rk(n):
    value = (n >> 2) - (1 << 30) if n & 2 and n & 0x80000000 else n >> 2 if n & 2 else struct.unpack("<d", struct.pack("<II", 0, n & 0xFFFFFFFC))[0]
    return value / 100 if n & 1 else value


def biff_records(data, start=0):
    pos = start
    while pos + 4 <= len(data):
        code, length = struct.unpack_from("<HH", data, pos)
        if pos + 4 + length > len(data):
            raise WorkError("Обрыв записи в XLS")
        yield pos, code, data[pos+4:pos+4+length]
        pos += 4 + length


class Strings:
    def __init__(self, pieces):
        self.pieces, self.index, self.pos = pieces, 0, 0

    def take(self, n):
        out = bytearray()
        while n:
            if self.pos == len(self.pieces[self.index]):
                self.index += 1
                self.pos = 0
            piece = self.pieces[self.index]
            size = min(n, len(piece)-self.pos)
            out.extend(piece[self.pos:self.pos+size])
            self.pos += size
            n -= size
        return bytes(out)

    def string(self):
        count = struct.unpack("<H", self.take(2))[0]
        flags = self.take(1)[0]
        rich = struct.unpack("<H", self.take(2))[0] if flags & 8 else 0
        ext = struct.unpack("<I", self.take(4))[0] if flags & 4 else 0
        wide, parts = flags & 1, []
        while count:
            if self.pos == len(self.pieces[self.index]):
                self.index += 1
                self.pos = 0
                wide = self.take(1)[0] & 1
            size = min(count, (len(self.pieces[self.index])-self.pos)//(2 if wide else 1))
            if not size:
                raise WorkError("Неподдерживаемое продолжение строки в XLS")
            parts.append(self.take(size*(2 if wide else 1)).decode("utf-16le" if wide else "latin1"))
            count -= size
        self.take(rich*4+ext)
        return "".join(parts)


def compound_stream(data):
    if data[:8] != bytes.fromhex("d0cf11e0a1b11ae1") or len(data) < 512:
        raise WorkError("Это не бинарная книга XLS. Сохраните файл как .xlsx")
    shift = struct.unpack_from("<H", data, 30)[0]
    if shift not in (9, 12):
        raise WorkError("Неподдерживаемый контейнер XLS")
    size, total = 1 << shift, len(data) // (1 << shift) - 1

    def sector(n):
        if not 0 <= n < total:
            raise WorkError("Повреждённая цепочка XLS")
        return data[(n+1)*size:(n+2)*size]

    fat_ids = [n for n in struct.unpack_from("<109I", data, 76) if n < 0xFFFFFFFA]
    difat, count = struct.unpack_from("<II", data, 68)
    seen = set()
    for _ in range(min(count, total+1)):
        if difat in seen:
            raise WorkError("Цикл в контейнере XLS")
        seen.add(difat)
        entries = struct.unpack("<"+"I"*(size//4), sector(difat))
        fat_ids.extend(n for n in entries[:-1] if n < 0xFFFFFFFA)
        difat = entries[-1]
    if len(fat_ids) > total+1:
        raise WorkError("Некорректная таблица секторов XLS")
    fat = []
    for n in fat_ids:
        fat.extend(struct.unpack("<"+"I"*(size//4), sector(n)))

    def chain(start, table, read, limit):
        out, used = bytearray(), set()
        while start < 0xFFFFFFFA:
            if start in used or start >= len(table) or len(out) > limit:
                raise WorkError("Повреждённая или слишком большая цепочка XLS")
            used.add(start)
            out.extend(read(start))
            start = table[start]
        return bytes(out)

    directory = chain(struct.unpack_from("<I", data, 48)[0], fat, sector, MAX_UPLOAD)
    streams, root = {}, None
    for pos in range(0, len(directory)-127, 128):
        d = directory[pos:pos+128]
        length = struct.unpack_from("<H", d, 64)[0]
        if length < 2 or length > 64:
            continue
        name = d[:length-2].decode("utf-16le")
        item = (struct.unpack_from("<I", d, 116)[0], struct.unpack_from("<Q", d, 120)[0])
        if d[66] == 5:
            root = item
        elif d[66] == 2:
            streams[name] = item
    item = streams.get("Workbook") or streams.get("Book")
    if not item or item[1] > MAX_UPLOAD:
        raise WorkError("В XLS не найден поток книги")
    if item[1] >= struct.unpack_from("<I", data, 56)[0]:
        return chain(item[0], fat, sector, MAX_UPLOAD)[:item[1]]
    if root is None:
        raise WorkError("Нет мини-потока XLS")
    mini = chain(root[0], fat, sector, MAX_UPLOAD)[:root[1]]
    mf = chain(struct.unpack_from("<I", data, 60)[0], fat, sector, MAX_UPLOAD)
    minifat = list(struct.unpack("<"+"I"*(len(mf)//4), mf))
    return chain(item[0], minifat, lambda n: mini[n*64:(n+1)*64], MAX_UPLOAD)[:item[1]]
