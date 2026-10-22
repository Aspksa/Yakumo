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

    def _show(self, content: bytes, fonts: dict[bytes, int]) -> str:
        out: list[str] = []
        cmap, width = {}, 1
        for tok in re.finditer(rb"/([^\s/<>\[\]()]+)\s+[\d.]+\s+Tf|(\((?:\\.|[^\\)])*\)|<[0-9A-Fa-f\s]*>)\s*(Tj|'|\")"
                               rb"|\[((?:\\.|[^\]\\])*)\]\s*TJ|(T\*|Td|TD|ET)\b", content, re.S):
            if tok[1]:
                num = fonts.get(tok[1])
                cmap, width = self._cmap(num) if num is not None else ({}, 1)
            elif tok[2]:
                if tok[3] in (b"'", b'"'):
                    out.append("\n")
                out.append(_decode(_pdf_string(tok[2]), cmap, width))
            elif tok[4] is not None:
                for part in re.finditer(rb"(\((?:\\.|[^\\)])*\)|<[0-9A-Fa-f\s]*>)|(-?[\d.]+)", tok[4]):
                    if part[1]:
                        out.append(_decode(_pdf_string(part[1]), cmap, width))
                    elif float(part[2]) < -180:  # большой отступ между словами
                        out.append(" ")
            else:
                out.append("\n" if tok[5] in (b"T*", b"ET") else " ")
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


def _decode(raw: bytes, cmap: dict[bytes, str], width: int) -> str:
    if not cmap:
        return raw.decode("cp1252", errors="replace")
    out = []
    for i in range(0, len(raw), width):
        out.append(cmap.get(raw[i:i + width], ""))
    return "".join(out)
