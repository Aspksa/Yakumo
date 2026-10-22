import importlib.util
import json
import shutil
import struct
import sys
import tempfile
import threading
import time
import unittest
import urllib.parse
import urllib.request
import zlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace

from yakumo.core.cloud import CloudService
from yakumo.core.config import Config
from yakumo.core.modules import Context, load_all
from yakumo.web.server import create_server

MODULES = Path(__file__).resolve().parents[1] / "modules"
FILES = Path(__file__).resolve().parent / "files"
KEY = "good-key-1234567"
def tiny_png() -> bytes:
    """Картинка 2×2 без Pillow: тесты не зависят от необязательных библиотек."""
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
    raw = b"".join(b"\x00" + b"\xff\x80\x00" * 2 for _ in range(2))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 2, 2, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


class FakeCloud(BaseHTTPRequestHandler):
    """Подставной Cloud.ru: по очереди отдаёт заготовленные ответы, картинки описывает одной фразой."""
    replies: list[str] = []
    requests: list[dict] = []

    def _json(self, data):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  # noqa: N802
        self._json({"data": [{"id": "Qwen/Qwen3-235B-A22B-Instruct-2507"}, {"id": "Qwen/Qwen2.5-VL-72B-Instruct"}]})

    def do_POST(self):  # noqa: N802
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        FakeCloud.requests.append(body)
        if not body.get("stream"):
            self._json({"choices": [{"message": {"content": "На фото рыжая кошка спит на диване."}}]})
            return
        text = FakeCloud.replies.pop(0) if FakeCloud.replies else "…"
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.end_headers()
        for i in range(0, len(text), 7):  # кусками, как настоящий поток: тег инструмента режется посередине
            chunk = {"choices": [{"delta": {"content": text[i:i + 7]}}]}
            self.wfile.write(f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n".encode())
        self.wfile.write(b"data: [DONE]\n\n")

    def log_message(self, *args):
        pass


class ExtractTest(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location("disk_extract", MODULES / "disk" / "extract.py")
        self.extract = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.extract)

    def test_documents(self):
        for name, expected in (("договор-libreoffice.pdf", "Арендатор: Иван Петров"),
                               ("квитанция-chrome.pdf", "Электроэнергия за май 2024"),
                               ("договор.docx", "Договор аренды квартиры"),
                               ("договор.rtf", "35 000 рублей"),
                               ("цены.xlsx", "Молоко;89")):
            self.assertIn(expected, self.extract.extract(FILES / name), name)

    def test_old_notepad_text_in_cp1251(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp, "заметка.txt")
            path.write_bytes("Купить молоко".encode("cp1251"))
            self.assertEqual(self.extract.extract(path), "Купить молоко")


class SmartDiskTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.fake = ThreadingHTTPServer(("127.0.0.1", 0), FakeCloud)
        threading.Thread(target=self.fake.serve_forever, daemon=True).start()
        FakeCloud.replies, FakeCloud.requests = [], []
        config = Config(cloud_url=f"http://127.0.0.1:{self.fake.server_address[1]}/v1",
                        cloud_model="Qwen/Qwen3-235B-A22B-Instruct-2507")
        (base / "config").mkdir()
        (base / "config" / "secrets.json").write_text(json.dumps({"cloud_api_key": KEY}), encoding="utf-8")
        cloud = CloudService(config, base / "config" / "yakumo.json", base / "config" / "secrets.json")
        paths = SimpleNamespace(app=base, data=base / "YakumoData", workspace=base)
        self.ctx = Context(paths=paths, config=config, cloud=cloud)
        sys.modules.pop("yakumo_modules.disk.index", None)
        infos = load_all(self.ctx, [MODULES])
        self.assertTrue(all(i.error is None for i in infos), [i.error for i in infos])
        sys.modules["yakumo_modules.disk.index"].DEBOUNCE = 0.05
        cloud.tools = self.ctx.chat_tools
        self.root = base / "YakumoData" / "disk"
        self.server = create_server("127.0.0.1", 0, base, {**self.ctx.routes, **cloud.routes()})
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}"

    def tearDown(self):
        self.ctx.stop()
        for s in (self.server, self.fake):
            s.shutdown()
            s.server_close()
        time.sleep(0.1)
        self.tmp.cleanup()

    def get(self, path, **params):
        url = self.base + path + ("?" + urllib.parse.urlencode(params) if params else "")
        with urllib.request.urlopen(url) as r:
            return json.loads(r.read())

    def post(self, path, data, raw=False):
        req = urllib.request.Request(self.base + path, data=json.dumps(data).encode(),
                                     headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req) as r:
            body = r.read().decode()
        return body if raw else json.loads(body)

    def put_file(self, rel, src: Path | bytes):
        target = self.root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(src, bytes):
            target.write_bytes(src)
        else:
            shutil.copy(src, target)
        self.post("/api/disk/mkdir", {"path": "", "name": "_poke"})  # любое изменение будит индекс
        self.post("/api/disk/delete", {"paths": ["_poke"]})

    def wait(self, check, timeout=10):
        end = time.time() + timeout
        while time.time() < end:
            if check():
                return
            time.sleep(0.05)
        self.fail("не дождались индекса")

    def test_search_inside_documents(self):
        self.put_file("Документы/скан.pdf", FILES / "договор-libreoffice.pdf")
        self.put_file("Счета/май.pdf", FILES / "квитанция-chrome.pdf")
        self.wait(lambda: self.get("/api/disk/smart")["texts"] == 2)
        found = self.get("/api/disk/search", q="аренда квартир")["items"]
        self.assertEqual([i["path"] for i in found], ["Документы/скан.pdf"])
        self.assertEqual(found[0]["match"], "text")
        self.assertIn("Договор аренды квартиры", found[0]["snippet"])
        found = self.get("/api/disk/search", q="электроэнергию")["items"]  # другая форма слова
        self.assertEqual([i["path"] for i in found], ["Счета/май.pdf"])
        # Переименование не теряет найденный текст.
        self.post("/api/disk/rename", {"path": "Счета", "name": "Квитанции"})
        found = self.get("/api/disk/search", q="электроэнергия")["items"]
        self.assertEqual([i["path"] for i in found], ["Квитанции/май.pdf"])

    def test_photos_are_described_only_when_enabled(self):
        self.put_file("Фото/IMG_0001.png", tiny_png())
        self.wait(lambda: not self.get("/api/disk/smart")["running"])
        self.assertEqual(self.get("/api/disk/search", q="кошка")["items"], [])
        self.assertFalse(any("image_url" in json.dumps(r) for r in FakeCloud.requests))  # без согласия не отправляем
        state = self.post("/api/disk/smart", {"photos": True})
        self.assertEqual(state["vision_model"], "Qwen/Qwen2.5-VL-72B-Instruct")
        self.wait(lambda: self.get("/api/disk/smart")["photos_done"] == 1)
        found = self.get("/api/disk/search", q="рыжую кошку")["items"]
        self.assertEqual([(i["path"], i["match"]) for i in found], [("Фото/IMG_0001.png", "photo")])
        sent = [r for r in FakeCloud.requests if not r.get("stream")][0]
        self.assertEqual(sent["model"], "Qwen/Qwen2.5-VL-72B-Instruct")
        self.assertTrue(sent["messages"][0]["content"][1]["image_url"]["url"].startswith("data:image/"))

    def chat(self, text):
        body = self.post("/api/chat", {"messages": [{"role": "user", "content": text}]}, raw=True)
        return [json.loads(line) for line in body.splitlines() if line]

    def test_chat_finds_reads_and_proposes_plan(self):
        self.put_file("Загрузки/договор.docx", FILES / "договор.docx")
        self.put_file("Загрузки/цены.xlsx", FILES / "цены.xlsx")
        self.wait(lambda: self.get("/api/disk/smart")["texts"] == 2)
        FakeCloud.replies = [
            'Сейчас поищу.\n<tool>{"name": "disk_search", "args": {"query": "аренда"}}</tool>',
            '<tool>{"name": "disk_read", "args": {"path": "Загрузки/договор.docx"}}</tool>',
            'Нашла [договор](disk:Загрузки/договор.docx): аренда за 35 000 ₽. Предлагаю убрать его в Документы.\n'
            '<tool>{"name": "disk_mkdir", "args": {"path": "Документы/Аренда"}}</tool>\n'
            '<tool>{"name": "disk_move", "args": {"paths": ["Загрузки/договор.docx"], "to": "Документы/Аренда"}}</tool>',
        ]
        events = self.chat("Найди договор аренды и наведи порядок")
        text = "".join(e.get("delta", "") for e in events)
        self.assertNotIn("<tool", text)
        self.assertIn("Сейчас поищу.", text)
        self.assertIn("[договор](disk:Загрузки/договор.docx)", text)
        self.assertEqual([e["status"] for e in events if "status" in e],
                         ["Ищу на Диске: «аренда»", "Читаю «договор.docx»"])
        plan = next(e["card"] for e in events if "card" in e)
        self.assertEqual([a["title"] for a in plan["actions"]],
                         ["Создать папку «Документы/Аренда»", "Переместить «договор.docx» → «Аренда»"])
        self.assertEqual(events[-1], {"done": True})
        # Модель видела результаты поиска и текст файла, но ничего не изменилось без подтверждения.
        self.assertIn("Загрузки/договор.docx", FakeCloud.requests[1]["messages"][-1]["content"])
        self.assertIn("35 000 рублей", FakeCloud.requests[2]["messages"][-1]["content"])
        self.assertTrue((self.root / "Загрузки" / "договор.docx").exists())
        self.assertIn("disk_search", FakeCloud.requests[0]["messages"][0]["content"])

        res = self.post("/api/chat/apply", {"actions": [{"tool": a["tool"], "args": a["args"]} for a in plan["actions"]]})
        self.assertTrue(all(r["ok"] for r in res["results"]), res)
        self.assertTrue((self.root / "Документы" / "Аренда" / "договор.docx").exists())
        # Прямо выполнять можно только инструменты, которые ждут подтверждения; чтение через apply не вызвать.
        res = self.post("/api/chat/apply", {"actions": [{"tool": "disk_read", "args": {"path": "x"}}]})
        self.assertFalse(res["results"][0]["ok"])

    def test_bad_tool_call_is_reported_to_model(self):
        FakeCloud.replies = ['<tool>{"name": "disk_search", "args": </tool>', "Не получилось, уточните запрос."]
        events = self.chat("найди")
        self.assertEqual("".join(e.get("delta", "") for e in events), "Не получилось, уточните запрос.")
        self.assertIn("неверный JSON", FakeCloud.requests[1]["messages"][-1]["content"])


if __name__ == "__main__":
    unittest.main()
