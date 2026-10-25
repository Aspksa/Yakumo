"""Текст из файлов для умного поиска: документы, таблицы, презентации, PDF, книги.

Только стандартная библиотека. Если установлен pypdf, PDF читается им,
иначе — встроенным упрощённым разборщиком (подходит для PDF из Word и браузеров).
"""

from __future__ import annotations

import html
import re
import zipfile
import zlib
from pathlib import Path

MAX_CHARS = 300_000           # сколько текста хранить на файл
MAX_TEXT_FILE = 4 * 1024**2   # текстовые файлы читаем с начала, не целиком
MAX_FILE = 200 * 1024**2      # файлы больше не разбираем

TEXT_EXT = {".txt", ".md", ".log", ".csv", ".tsv", ".json", ".xml", ".yml", ".yaml", ".ini", ".cfg", ".conf",
            ".toml", ".py", ".js", ".ts", ".css", ".bat", ".cmd", ".ps1", ".sh", ".c", ".h", ".cpp", ".cs",
            ".java", ".go", ".rs", ".sql", ".srt"}
HTML_EXT = {".html", ".htm", ".xhtml"}
ZIP_XML = {
    ".docx": ("word/document.xml",), ".xlsx": ("xl/sharedStrings.xml", "xl/worksheets/"),
    ".pptx": ("ppt/slides/",), ".odt": ("content.xml",), ".ods": ("content.xml",), ".odp": ("content.xml",),
    ".epub": (".xhtml", ".html", ".htm"),
}
SUPPORTED = TEXT_EXT | HTML_EXT | set(ZIP_XML) | {".pdf", ".fb2", ".rtf"}


def can_extract(name: str) -> bool:
    return Path(name).suffix.lower() in SUPPORTED


def extract(path: Path) -> str:
    """Текст файла или пустая строка; ошибки разбора не выходят наружу."""
    ext = path.suffix.lower()
    try:
        if path.stat().st_size > MAX_FILE:
            return ""
        if ext in TEXT_EXT:
            text = decode(_head(path))
        elif ext in HTML_EXT:
            text = strip_tags(decode(_head(path)))
        elif ext == ".fb2":
            text = strip_tags(decode(_head(path, MAX_FILE)))
        elif ext == ".rtf":
            text = rtf_text(_head(path, MAX_FILE).decode("latin-1"))
        elif ext == ".pdf":
            text = pdf_text(path)
        elif ext in ZIP_XML:
            text = zip_text(path, ZIP_XML[ext])
        else:
            return ""
    except Exception:  # noqa: BLE001 — битый файл не должен ломать индекс
        return ""
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text).strip()
    return text[:MAX_CHARS]


def _head(path: Path, limit: int = MAX_TEXT_FILE) -> bytes:
    with open(path, "rb") as f:
        return f.read(limit)


def decode(raw: bytes) -> str:
    """UTF-8, UTF-16 с меткой или windows-1251 (старые файлы Блокнота)."""
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        return raw.decode("utf-16", errors="replace")
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        if exc.start > len(raw) - 4:  # файл обрезан посреди буквы
            return raw[:exc.start].decode("utf-8-sig")
    return raw.decode("cp1251", errors="replace")


def strip_tags(markup: str) -> str:
    markup = re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", markup)
    markup = re.sub(r"(?i)</(p|div|h\d|li|tr|br|title|section|si|text:p|text:h|w:p|a:p)\s*>|<br\s*/?>", "\n", markup)
    markup = re.sub(r"(?i)<(w:tab|text:tab|text:s)\b[^>]*/?>", " ", markup)
    return html.unescape(re.sub(r"<[^>]+>", "", markup))


def zip_text(path: Path, parts: tuple[str, ...]) -> str:
    out = []
    with zipfile.ZipFile(path) as zf:
        names = sorted(zf.namelist(), key=_natural)
        for name in names:
            if any(name == p or (p.endswith("/") and name.startswith(p) and name.endswith(".xml"))
                   or (p.startswith(".") and name.lower().endswith(p)) for p in parts):
                info = zf.getinfo(name)
                if info.file_size > 50 * 1024**2:
                    continue
                xml = zf.read(name).decode("utf-8", errors="replace")
                if "worksheets/" in name:  # в листах — числа и строки прямо в ячейках (общие строки — отдельно)
                    cells = re.findall(r"<c\b([^>]*)>(.*?)</c>", xml, re.S)
                    xml = " ".join(" ".join(re.findall(r"<(?:v|t)>([^<]*)</(?:v|t)>", body))
                                   for attrs, body in cells if 't="s"' not in attrs)
                out.append(strip_tags(xml))
                if sum(map(len, out)) > MAX_CHARS:
                    break
    return "\n".join(out)


def _natural(name: str):
    return [int(p) if p.isdigit() else p for p in re.split(r"(\d+)", name)]


def rtf_text(rtf: str) -> str:
    def hexchar(m):
        return bytes([int(m[1], 16)]).decode("cp1251", errors="replace")

    def uni(m):
        n = int(m[1])
        return chr(n + 65536 if n < 0 else n)

    rtf = re.sub(r"\\'([0-9a-fA-F]{2})", hexchar, rtf)
    rtf = re.sub(r"\\u(-?\d+)\??", uni, rtf)
    rtf = re.sub(r"\\(par|line)\b ?", "\n", rtf)
    rtf = re.sub(r"\{\\\*[^{}]*\}", "", rtf)
    rtf = re.sub(r"\{\\(fonttbl|colortbl|stylesheet|info)[^{}]*(\{[^{}]*\}[^{}]*)*\}", "", rtf)
    rtf = re.sub(r"\\[a-zA-Z]+-?\d* ?", "", rtf)
    return rtf.replace("{", "").replace("}", "")


# --- PDF ---

def pdf_text(path: Path) -> str:
    try:
        import pypdf  # необязательная библиотека: читает больше видов PDF
    except ImportError:
        return SimplePdf(path.read_bytes()).text()
    reader = pypdf.PdfReader(str(path))
    out = []
    for page in reader.pages:
        out.append(page.extract_text() or "")
        if sum(map(len, out)) > MAX_CHARS:
            break
    return "\n".join(out)


def pdf_images(path: Path, limit: int = 3) -> list[tuple[bytes, str]]:
    """Картинки страниц скана (JPEG как есть, несжатые серые и цветные — в PNG), чтобы распознать текст."""
    if path.stat().st_size > MAX_FILE:
        return []
    pdf = SimplePdf(path.read_bytes())
    out = []
    for body in pdf.objects.values():
        if not re.search(rb"/Subtype\s*/Image\b", body):
            continue
        width, height = re.search(rb"/Width\s+(\d+)", body), re.search(rb"/Height\s+(\d+)", body)
        if not width or not height or int(width[1]) < 300 or int(height[1]) < 300:
            continue  # значки и логотипы
        m = re.search(rb"stream\r?\n", body)
        if not m:
            continue
        head, raw = body[:m.start()], body[m.end():]
        raw = raw[:raw.rfind(b"endstream")] if b"endstream" in raw else raw
        if b"/DCTDecode" in head:
            out.append((raw.rstrip(b"\r\n"), "image/jpeg"))
        elif b"/FlateDecode" in head and re.search(rb"/BitsPerComponent\s+8", head):
            channels = 3 if b"/DeviceRGB" in head else 1 if b"/DeviceGray" in head else 0
            pixels = pdf.stream(body)
            w, h = int(width[1]), int(height[1])
            if channels and pixels and len(pixels) >= w * h * channels:
                out.append((png(pixels, w, h, channels), "image/png"))
        if len(out) >= limit:
            break
    return out


def png(pixels: bytes, width: int, height: int, channels: int) -> bytes:
    import struct

    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
    row = width * channels
    raw = b"".join(b"\x00" + pixels[y * row:(y + 1) * row] for y in range(height))
    color = 2 if channels == 3 else 0
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, color, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b""))


class FontInfo:
    """Шрифт PDF: как читать коды текста и сколько места занимает каждый глиф."""

    def __init__(self, cmap: dict[bytes, str], code_width: int, widths: dict[int, float], fallback: float):
        self.cmap = cmap
        self.code_width = max(1, code_width)
        self.widths = widths
        self.fallback = fallback or 500.0

    def width(self, code: int) -> float:
        """Ширина глифа в тысячных долях em; для пропущенных в /W — средняя по шрифту."""
        value = self.widths.get(code)
        return self.fallback if value is None else value

    def decode(self, raw: bytes) -> tuple[str, float]:
        """Текст куска и его ширина в тысячных долях em."""
        if not self.cmap:
            text, total = [], 0.0
            for byte in raw:
                text.append(bytes([byte]).decode("cp1252", errors="replace"))
                total += self.width(byte)
            return "".join(text), total
        step = self.code_width
        text, total = [], 0.0
        for i in range(0, len(raw) - step + 1, step):
            code = raw[i:i + step]
            text.append(self.cmap.get(code, ""))
            total += self.width(int.from_bytes(code, "big"))
        return "".join(text), total


def pdf_array(body: bytes, key: bytes) -> bytes | None:
    """Содержимое массива [...] после /ключ, с учётом вложенных массивов."""
    start = re.search(rb"/" + key + rb"\s*\[", body)
    if not start:
        return None
    i, depth = start.end(), 1
    while i < len(body) and depth:
        char = body[i:i + 1]
        depth += 0 if char not in b"[]" else (1 if char == b"[" else -1)
        i += 1
    return body[start.end():i - 1]


def numbers(blob: bytes) -> list[float]:
    return [float(value) for value in re.findall(rb"-?\d*\.?\d+", blob)]


def _number(body: bytes, key: bytes) -> float | None:
    m = re.search(rb"/" + key + rb"\s+(-?\d*\.?\d+)", body)
    return float(m[1]) if m else None


def cid_widths(array: bytes) -> dict[int, float]:
    """/W CID-шрифта: `c [w...]` или `first last w` — в словарь «код → ширина»."""
    tokens = re.findall(rb"\[|\]|-?\d*\.?\d+", array)
    widths: dict[int, float] = {}
    i = 0
    while i < len(tokens):
        if tokens[i] in (b"[", b"]"):
            i += 1
            continue
        first = int(float(tokens[i]))
        i += 1
        if i < len(tokens) and tokens[i] == b"[":
            i += 1
            code = first
            while i < len(tokens) and tokens[i] != b"]":
                widths[code] = float(tokens[i])
                code, i = code + 1, i + 1
            i += 1
        elif i + 1 < len(tokens):
            last, value = int(float(tokens[i])), float(tokens[i + 1])
            i += 2
            for code in range(first, min(last, first + 65535) + 1):
                widths[code] = value
    return widths


class SimplePdf:
    """Упрощённое чтение текста PDF: объекты, сжатые потоки, шрифты с таблицей ToUnicode."""

    def __init__(self, data: bytes):
        self.data = data
        self.objects: dict[int, bytes] = {}
        for m in re.finditer(rb"(\d+)\s+\d+\s+obj\b(.*?)\bendobj", data, re.S):
            self.objects[int(m[1])] = m[2]
        for body in list(self.objects.values()):  # объекты внутри сжатых ObjStm (PDF 1.5+)
            if b"/ObjStm" in body:
                self._unpack_objstm(body)
        self.cmaps: dict[int, tuple[dict[bytes, str], int]] = {}
        self.fonts: dict[int, FontInfo] = {}

    def _unpack_objstm(self, body: bytes) -> None:
        raw = self.stream(body)
        first = re.search(rb"/First\s+(\d+)", body)
        n = re.search(rb"/N\s+(\d+)", body)
        if raw is None or not first or not n:
            return
        nums = list(map(int, raw[:int(first[1])].split()))
        pairs = list(zip(nums[0::2], nums[1::2]))[:int(n[1])]
        for i, (num, off) in enumerate(pairs):
            start = int(first[1]) + off
            end = int(first[1]) + pairs[i + 1][1] if i + 1 < len(pairs) else len(raw)
            self.objects.setdefault(num, raw[start:end])

    def stream(self, body: bytes) -> bytes | None:
        m = re.search(rb"stream\r?\n", body)
        if not m:
            return None
        raw = body[m.end():]
        end = raw.rfind(b"endstream")
        raw = raw[:end] if end >= 0 else raw
        head = body[:m.start()]
        if b"/FlateDecode" in head:
            try:
                return zlib.decompressobj().decompress(raw)
            except zlib.error:
                return None
        if b"/Filter" in head:
            return None  # картинки и редкие фильтры не нужны
        return raw

    def ref(self, body: bytes, key: bytes) -> int | None:
        m = re.search(rb"/" + key + rb"\s+(\d+)\s+\d+\s+R", body)
        return int(m[1]) if m else None

    def text(self) -> str:
        out = []
        for num, body in self.objects.items():
            if not re.search(rb"/Type\s*/Page\b", body):
                continue
            fonts = self._page_fonts(body)
            contents = re.search(rb"/Contents\s*(\[[^\]]*\]|\d+\s+\d+\s+R)", body)
            if not contents:
                continue
            for ref in re.findall(rb"(\d+)\s+\d+\s+R", contents[1]):
                raw = self.stream(self.objects.get(int(ref), b""))
                if raw:
                    out.append(self._show(raw, fonts))
            if sum(map(len, out)) > MAX_CHARS:
                break
        return "\n".join(out)

    def _page_fonts(self, page: bytes) -> dict[bytes, int]:
        res = page
        rid = self.ref(page, b"Resources")
        if rid is not None:
            res = self.objects.get(rid, b"")
        fid = self.ref(res, b"Font")
        if fid is not None:
            font_dict = self.objects.get(fid, b"")
        else:
            m = re.search(rb"/Font\s*<<(.*?)>>", res, re.S)
            font_dict = m[1] if m else b""
        return {name: int(num) for name, num in re.findall(rb"/([^\s/<>\[\]()]+)\s+(\d+)\s+\d+\s+R", font_dict)}

    def _cmap(self, font_num: int) -> tuple[dict[bytes, str], int]:
        if font_num in self.cmaps:
            return self.cmaps[font_num]
        result: tuple[dict[bytes, str], int] = ({}, 1)
        tu = self.ref(self.objects.get(font_num, b""), b"ToUnicode")
        raw = self.stream(self.objects.get(tu, b"")) if tu is not None else None
        if raw:
            result = parse_cmap(raw)
        self.cmaps[font_num] = result
        return result

    def _font(self, font_num: int) -> FontInfo:
        """Шрифт с ширинами глифов: без них не понять, где кончается слово."""
        if font_num in self.fonts:
            return self.fonts[font_num]
        body = self.objects.get(font_num, b"")
        cmap, code_width = self._cmap(font_num)
        widths: dict[int, float] = {}
        fallback = 500.0
        if b"/Type0" in body:  # CID-шрифт: ширины в потомке, недостающие — по /DW
            descendant = re.search(rb"/DescendantFonts\s*\[\s*(\d+)\s+\d+\s+R", body)
            sub = self.objects.get(int(descendant[1]), b"") if descendant else b""
            fallback = _number(sub, b"DW") or 1000.0
            array = pdf_array(sub, b"W")
            if array:
                widths = cid_widths(array)
        else:
            array = pdf_array(body, b"Widths")
            if array:
                first = _number(body, b"FirstChar") or 0
                for i, value in enumerate(numbers(array)):
                    widths[int(first) + i] = value
            matrix = pdf_array(body, b"FontMatrix")  # Type3: ширины в долях глифа
            if matrix:
                scale = (numbers(matrix) or [0.001])[0]
                widths = {code: value * scale * 1000 for code, value in widths.items()}
        known = [value for value in widths.values() if value]
        info = FontInfo(cmap, code_width, widths, sum(known) / len(known) if known else fallback)
        self.fonts[font_num] = info
        return info

    def _show(self, content: bytes, fonts: dict[bytes, int]) -> str:
        """Текст одного потока: строки и слова по геометрии, а не по каждому оператору.

        PDF из браузеров и Word режет строку на куски и ставит каждый `Td`/`BT`:
        если считать каждый сдвиг пробелом, слово рассыпается на буквы. Поэтому
        куски сначала собираются в строку, и зазор становится пробелом только там,
        где в строке нет настоящих пробельных глифов (иначе это кернинг).
        """
        out: list[str] = []
        line: list[tuple[float, str]] = []   # (зазор перед куском в долях em, текст)
        font = FontInfo({}, 1, {}, 500)
        size, leading = 12.0, 0.0
        line_x = line_y = cursor = 0.0
        last_y: float | None = None
        last_size = 0.0    # размер шрифта прошлого куска: по нему меряем междустрочный шаг
        forced = False   # T*, ' и " начинают новую строку
        pending = 0.0    # сдвиг от последнего оператора позиционирования, в долях em
        gap = 0.0        # сдвиг внутри TJ, в тысячных долях em
        fresh = True     # следующий кусок начнётся от line_x, а не от конца прошлого

        def flush() -> None:
            """Собрать строку: зазор — пробел, если в строке нет своих пробелов."""
            if line:
                limit = 0.9 if any(" " in text for _, text in line) else 0.18
                out.append("".join((" " if value > limit else "") + text for value, text in line))
                line.clear()

        def put(text: str, advance: float) -> None:
            """Дописать кусок в текущую строку, при необходимости начав новую."""
            nonlocal cursor, last_y, last_size, forced, pending, gap, fresh
            if text:
                step = last_size or size
                if last_y is not None:
                    dy = line_y - last_y
                    if forced or abs(dy) >= max(step * 0.5, 0.6):
                        flush()
                        out.append("\n\n" if abs(dy) >= step * 1.8 else "\n")
                value = 0.0 if not line or last_y is None else gap / 1000 + pending
                line.append((value, text))
                cursor = (line_x if fresh else cursor) + advance / 1000 * size
                last_y, last_size = line_y, size
            forced, pending, gap, fresh = False, 0.0, 0.0, False

        pattern = (rb"/([^\s/<>\[\]()]+)\s+(-?[\d.]+)\s+Tf"                                    # 1, 2
                   rb"|(-?[\d.]+)\s+(-?[\d.]+)\s+(Td|TD)"                                        # 3, 4, 5
                   rb"|(-?[\d.]+)\s+(-?[\d.]+)\s+(-?[\d.]+)\s+(-?[\d.]+)\s+(-?[\d.]+)\s+(-?[\d.]+)\s+Tm"  # 6..11
                   rb"|(BT|T\*)"                                                                   # 12
                   rb"|(\((?:\\.|[^\\)])*\)|<[0-9A-Fa-f\s]*>)\s*(Tj|'|\")"                   # 13, 14
                   rb"|\[((?:\\.|[^\]\\])*)\]\s*TJ")                                          # 15
        for tok in re.finditer(pattern, content, re.S):
            if tok[1]:
                num = fonts.get(tok[1])
                font = self._font(num) if num is not None else FontInfo({}, 1, {}, 500)
                size = abs(float(tok[2])) or size
            elif tok[5]:
                line_x += float(tok[3])
                line_y += float(tok[4])
                if tok[5] == b"TD":
                    leading = -float(tok[4])
                pending = (line_x - cursor) / size if size else 0.0
                fresh = True
            elif tok[11] is not None:
                line_x, line_y = float(tok[10]), float(tok[11])
                pending = (line_x - cursor) / size if size else 0.0
                fresh = True
            elif tok[12] == b"BT":      # новый блок текста: своя система координат
                line_x = line_y = 0.0
            elif tok[12]:               # T*
                line_y -= leading
                pending = (line_x - cursor) / size if size else 0.0
                forced, fresh = True, True
            elif tok[13]:
                if tok[14] in (b"'", b'"'):
                    line_y -= leading
                    pending = (line_x - cursor) / size if size else 0.0
                    forced, fresh = True, True
                text, advance = font.decode(_pdf_string(tok[13]))
                put(text, advance)
            elif tok[15] is not None:
                for part in re.finditer(rb"(\((?:\\.|[^\\)])*\)|<[0-9A-Fa-f\s]*>)|(-?[\d.]+)", tok[15]):
                    if part[1]:
                        text, advance = font.decode(_pdf_string(part[1]))
                        put(text, advance)
                    else:
                        gap += -float(part[2])
        flush()
        return re.sub(r" *\n *", "\n", "".join(out))


def parse_cmap(raw: bytes) -> tuple[dict[bytes, str], int]:
    mapping: dict[bytes, str] = {}
    width = 1
    space = re.search(rb"begincodespacerange\s*<([0-9A-Fa-f]+)>", raw)
    if space:
        width = max(1, len(space[1]) // 2)

    def uni(hexstr: bytes) -> str:
        b = bytes.fromhex(hexstr.decode())
        return b.decode("utf-16-be", errors="replace")

    for block in re.findall(rb"beginbfchar(.*?)endbfchar", raw, re.S):
        for src, dst in re.findall(rb"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]*)>", block):
            mapping[bytes.fromhex(src.decode())] = uni(dst)
    for block in re.findall(rb"beginbfrange(.*?)endbfrange", raw, re.S):
        for lo, hi, dst in re.findall(rb"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>\s*(<[0-9A-Fa-f]+>|\[[^\]]*\])", block):
            a, b = int(lo, 16), int(hi, 16)
            n = len(lo) // 2
            if b - a > 65535:
                continue
            if dst.startswith(b"["):
                for i, d in enumerate(re.findall(rb"<([0-9A-Fa-f]+)>", dst)):
                    mapping[(a + i).to_bytes(n, "big")] = uni(d)
            else:
                base = int(dst[1:-1], 16)
                dlen = len(dst[1:-1]) // 2
                for i in range(b - a + 1):
                    mapping[(a + i).to_bytes(n, "big")] = uni(f"{base + i:0{dlen * 2}X}".encode())
    return mapping, width


def _pdf_string(token: bytes) -> bytes:
    if token.startswith(b"<"):
        hexs = re.sub(rb"\s", b"", token[1:-1])
        return bytes.fromhex((hexs + b"0" * (len(hexs) % 2)).decode())
    s = token[1:-1]
    out = bytearray()
    i = 0
    escapes = {b"n": b"\n", b"r": b"\r", b"t": b"\t", b"b": b"\b", b"f": b"\f"}
    while i < len(s):
        c = s[i:i + 1]
        if c == b"\\" and i + 1 < len(s):
            nxt = s[i + 1:i + 2]
            if nxt in escapes:
                out += escapes[nxt]
                i += 2
            elif nxt.isdigit():
                m = re.match(rb"[0-7]{1,3}", s[i + 1:])
                out.append(int(m[0], 8) & 255)
                i += 1 + len(m[0])
            elif nxt in b"\r\n":
                i += 2
            else:
                out += nxt
                i += 2
        else:
            out += c
            i += 1
    return bytes(out)
