import json
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.parse
import urllib.request
import zlib
from http.server import ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace

from tests.test_disk_smart import FILES, KEY, MODULES, FakeCloud, tiny_png
from yakumo.core.cloud import CloudService
from yakumo.core.config import Config
from yakumo.core.modules import Context, load_all
from yakumo.web.server import create_server


class ScriptedCloud(FakeCloud):
    """Cloud.ru, который отвечает по смыслу запроса: распознаёт сканы, придумывает имена, пишет конспекты."""

    def do_POST(self):  # noqa: N802
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        FakeCloud.requests.append(body)
        content = body["messages"][0]["content"]
        prompt = content if isinstance(content, str) else content[0]["text"]
        if "Перепиши весь текст" in prompt:
            reply = "ООО «Ромашка»\nКассовый чек\nИТОГО: 1 250,00 ₽\n12.05.2024"
        elif "Опиши это изображение" in prompt:
            reply = "На фото кассовый чек из магазина на столе."
        elif "Придумай понятные имена" in prompt:
            reply = json.dumps({"names": [{"n": 1, "name": "Договор аренды с Петровым"}]}, ensure_ascii=False)
        elif "Это часть" in prompt:
            reply = "- главное из части"
        elif "Составь конспект" in prompt:
            reply = "Договор аренды квартиры.\n\n## Главное\n- 35 000 ₽ в месяц"
        else:
            reply = "…"
        self._json({"choices": [{"message": {"content": reply}}]})


def scanned_pdf() -> bytes:
    """PDF без текстового слоя: одна серая картинка страницы, как из сканера."""
    w, h = 320, 320
    pixels = zlib.compress(bytes([200]) * (w * h))
    image = (f"<< /Type /XObject /Subtype /Image /Width {w} /Height {h} /ColorSpace /DeviceGray "
             f"/BitsPerComponent 8 /Filter /FlateDecode /Length {len(pixels)} >>\nstream\n").encode() + pixels + b"\nendstream"
    objects = [b"<< /Type /Catalog /Pages 2 0 R >>", b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
               b"<< /Type /Page /Parent 2 0 R /Resources << /XObject << /Im0 4 0 R >> >> /Contents 5 0 R >>",
               image, b"<< /Length 30 >>\nstream\nq 320 0 0 320 0 0 cm /Im0 Do Q\nendstream"]
    out = b"%PDF-1.4\n"
    for i, obj in enumerate(objects, 1):
        out += f"{i} 0 obj\n".encode() + obj + b"\nendobj\n"
    return out + b"trailer << /Root 1 0 R >>\n%%EOF"


class OrderTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.fake = ThreadingHTTPServer(("127.0.0.1", 0), ScriptedCloud)
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

    def get(self, url_path, **params):
        url = self.base + url_path + ("?" + urllib.parse.urlencode(params) if params else "")
        with urllib.request.urlopen(url) as r:
            return json.loads(r.read())

    def post(self, url_path, data):
        req = urllib.request.Request(self.base + url_path, data=json.dumps(data).encode(),
                                     headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read().decode())

    def upload(self, rel, content: bytes):
        req = urllib.request.Request(self.base + "/api/disk/upload?" + urllib.parse.urlencode({"path": rel}),
                                     data=content, headers={"X-Yakumo": "1"}, method="POST")
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read())

    def wait(self, check, timeout=10):
        end = time.time() + timeout
        while time.time() < end:
            if check():
                return
            time.sleep(0.05)
        self.fail("не дождались")

    def said(self):
        return [x["text"] for x in self.ctx.memory._memory.data.get("inbox", [])]

    # --- 1–3: живая структура, правила, уроки ---

    def test_kitsune_notices_habit_and_proposes_rule(self):
        year = time.strftime("%Y")
        self.post("/api/disk/mkdir", {"path": "", "name": "Финансы"})
        self.post("/api/disk/mkdir", {"path": "Финансы", "name": year})
        for name in ("чек магнит.txt", "чек пятёрочка.txt", "чек аптека.txt"):
            self.upload(name, "Покупка".encode())
            self.post("/api/disk/move", {"paths": [name], "to": f"Финансы/{year}"})
        order = self.get("/api/disk/order")
        self.assertEqual(len(order["proposals"]), 1)
        p = order["proposals"][0]
        self.assertEqual((p["words"], p["to"], p["target"]), (["чек"], "Финансы/{год}", f"Финансы/{year}"))
        self.assertTrue(any("заметила" in t for t in self.said()))
        rule = self.post("/api/disk/order/answer", {"id": p["id"], "accept": True})["rule"]
        self.assertEqual(rule["source"], "learned")
        # Новый чек сам уезжает в нужную папку.
        res = self.upload("Чек_лента.txt", "Покупка".encode())
        self.assertEqual(res["path"], f"Финансы/{year}/Чек_лента.txt")
        self.assertEqual(res["placed"]["rule"], rule["id"])
        # Принятое предложение уходит из списка.
        self.assertEqual(self.get("/api/disk/order")["proposals"], [])

    def test_rule_by_text_and_learning_from_corrections(self):
        rule = self.post("/api/disk/order/rule", {"words": ["договор"], "kinds": ["pdf"], "to": "Документы",
                                                   "tell": "Проверь срок договора."})
        res = self.upload("Загрузки/скан.pdf", (FILES / "договор-libreoffice.pdf").read_bytes())  # слово — в тексте
        self.assertEqual(res["path"], "Документы/скан.pdf")
        self.assertTrue(any("Проверь срок договора" in t for t in self.said()))
        self.assertEqual(self.upload("Загрузки/счёт.pdf", (FILES / "квитанция-chrome.pdf").read_bytes())["path"],
                         "Загрузки/счёт.pdf")  # не подходит — лежит, где положили
        # Пользователь дважды перекладывает в «Документы/Аренда»: правило меняет папку.
        self.post("/api/disk/mkdir", {"path": "Документы", "name": "Аренда"})
        self.post("/api/disk/move", {"paths": ["Документы/скан.pdf"], "to": "Документы/Аренда"})
        self.assertEqual(self.get("/api/disk/order")["rules"][0]["to"], "Документы")
        res = self.upload("скан2.pdf", (FILES / "договор-libreoffice.pdf").read_bytes())
        self.assertEqual(res["path"], "Документы/скан2.pdf")
        self.post("/api/disk/move", {"paths": ["Документы/скан2.pdf"], "to": "Документы/Аренда"})
        order = self.get("/api/disk/order")
        self.assertEqual(order["rules"][0]["to"], "Документы/Аренда")
        self.assertIn("Поняла", order["lessons"][0]["text"])
        self.assertTrue(any("Аренда" in x["text"] for x in self.ctx.memory._memory.data["lessons"]))
        self.assertEqual(self.upload("скан3.pdf", (FILES / "договор-libreoffice.pdf").read_bytes())["path"],
                         "Документы/Аренда/скан3.pdf")
        self.assertTrue(self.post("/api/disk/order/delete", {"id": rule["id"]})["ok"])

    def test_plan_sorts_existing_inbox(self):
        self.upload("Загрузки/IMG_1.png", tiny_png())
        self.upload("Загрузки/заметка.txt", b"text")
        self.post("/api/disk/order/rule", {"kinds": ["image"], "to": "Фото/{год}"})
        moves = self.get("/api/disk/order/plan")["moves"]
        self.assertEqual([(m["path"], m["to"]) for m in moves], [("Загрузки/IMG_1.png", f"Фото/{time.strftime('%Y')}")])
        done = self.post("/api/disk/order/apply", {"moves": moves})
        self.assertTrue((self.root / done[0]["path"]).exists())

    def test_bad_rules_are_refused(self):
        for bad in ({"to": "Документы"}, {"words": ["чек"], "to": ""}, {"words": ["чек"], "to": "../x"},
                    {"words": ["чек"], "to": "A/CON"}):
            req = urllib.request.Request(self.base + "/api/disk/order/rule", data=json.dumps(bad).encode(),
                                         headers={"Content-Type": "application/json"}, method="POST")
            with self.assertRaises(urllib.error.HTTPError) as err:
                urllib.request.urlopen(req)
            self.assertEqual(err.exception.code, 400, bad)

    # --- 12: понятные имена ---

    def test_clear_names(self):
        self.upload("Сканы/Скан001.docx", (FILES / "договор.docx").read_bytes())
        self.upload("Сканы/IMG_20240512_143000.jpg", tiny_png())
        self.upload("Сканы/Отпуск.txt", b"text")
        found = self.get("/api/disk/names", path="Сканы")
        by = {i["name"]: i for i in found["items"]}
        self.assertEqual(found["checked"], 2)  # «Отпуск» — уже понятное имя
        self.assertEqual(by["Скан001.docx"]["suggestion"], "Договор аренды с Петровым.docx")
        self.assertEqual(by["Скан001.docx"]["source"], "ai")
        self.assertEqual(by["IMG_20240512_143000.jpg"]["suggestion"], "Фото 2024-05-12 14-30.jpg")
        done = self.post("/api/disk/names", {"items": [
            {"path": "Сканы/Скан001.docx", "name": "Аренда — договор.docx", "suggested": "Договор аренды с Петровым.docx"}]})
        self.assertEqual(done[0]["path"], "Сканы/Аренда — договор.docx")
        examples = json.loads((self.root / ".yakumo" / "names.json").read_text(encoding="utf-8"))["examples"]
        self.assertEqual(examples, [{"suggested": "Договор аренды с Петровым", "final": "Аренда — договор"}])

    # --- 13: текст со сканов и чеков ---

    def test_scans_are_recognised_only_when_enabled(self):
        self.upload("Сканы/чек.pdf", scanned_pdf())
        self.upload("Фото/чек.png", tiny_png())
        self.upload("Фото/кот.png", tiny_png())
        self.wait(lambda: not self.get("/api/disk/smart")["running"])
        self.assertEqual(self.get("/api/disk/search", q="ромашка")["items"], [])
        self.post("/api/disk/smart", {"ocr": True})
        self.wait(lambda: self.get("/api/disk/smart")["ocr_done"] == 2)
        found = {i["path"]: i for i in self.get("/api/disk/search", q="ромашка итого")["items"]}
        self.assertEqual(set(found), {"Сканы/чек.pdf", "Фото/чек.png"})  # кот не похож на документ
        self.assertEqual(found["Сканы/чек.pdf"]["match"], "text")
        sent = [r for r in FakeCloud.requests if "Перепиши" in json.dumps(r, ensure_ascii=False)]
        self.assertTrue(sent[0]["messages"][0]["content"][1]["image_url"]["url"].startswith("data:image/png"))
        # Текст скана доступен «Мозгу» как документ.
        docs = {p: t for p, _m, t in self.ctx.services["disk"].documents()}
        self.assertIn("1 250,00", docs["Сканы/чек.pdf"])

    # --- 15, 16: похожие файлы и конспект ---

    def test_related_files(self):
        lease = "Договор аренды квартиры. Арендодатель Иван Петров. Квартира на Тверской улице, оплата ежемесячно."
        self.upload("Документы/договор.txt", lease.encode())
        self.upload("Документы/расписка.txt", "Расписка: Иван Петров получил оплату за квартиру на Тверской.".encode())
        self.upload("Рецепты/борщ.txt", "Свёкла, капуста, картофель, морковь.".encode())
        self.upload("Разное/ключи.txt", "просто заметка".encode())
        self.wait(lambda: self.get("/api/disk/smart")["texts"] == 4)
        self.ctx.memory.remember("Ключи от квартиры у Ивана Петрова", about=["Иван Петров"], files=["Разное/ключи.txt"])
        self.ctx.memory.remember("Арендодатель — Иван Петров", about=["Иван Петров"], files=["Документы/договор.txt"])
        res = self.get("/api/disk/related", path="Документы/договор.txt")
        paths = [f["path"] for f in res["files"]]
        self.assertIn("Документы/расписка.txt", paths)
        self.assertIn("Разное/ключи.txt", paths)  # связаны через память: тот же человек
        self.assertNotIn("Рецепты/борщ.txt", paths)
        self.assertEqual(res["facts"], ["Арендодатель — Иван Петров"])

    def test_summary_is_saved_next_to_file(self):
        long = "\n".join(f"Пункт {i}. Арендатор платит 35 000 рублей до пятого числа месяца." for i in range(500))
        self.upload("Документы/договор.txt", long.encode())
        res = self.post("/api/disk/summary", {"path": "Документы/договор.txt"})
        self.assertEqual(res["path"], "Документы/договор — конспект.md")
        text = (self.root / res["path"]).read_text(encoding="utf-8")
        self.assertIn("## Главное", text)
        self.assertIn("[договор.txt](договор.txt)", text)
        prompts = [json.dumps(r, ensure_ascii=False) for r in FakeCloud.requests]
        self.assertEqual(sum("Это часть" in p for p in prompts), 3)  # длинный текст читается частями
        self.assertIn("Документы/договор — конспект.md", [d["path"] for d in self.ctx.memory._memory.data["drafts"]])

if __name__ == "__main__":
    unittest.main()
