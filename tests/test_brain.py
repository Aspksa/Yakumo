import json
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace

from yakumo.core.cloud import CloudService
from yakumo.core.config import Config
from yakumo.core.modules import Context, load_all
from yakumo.web.server import create_server

MODULES = Path(__file__).resolve().parents[1] / "modules"
KEY = "good-key-1234567"


class FakeCloud(BaseHTTPRequestHandler):
    """Подставной Cloud.ru: чат отвечает заготовками потоком, разбор беседы — заготовленным JSON."""
    replies: list[str] = []
    learned: dict = {}
    requests: list[dict] = []

    def _json(self, data):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  # noqa: N802
        self._json({"data": [{"id": "Qwen/Qwen3-235B-A22B-Instruct-2507"}]})

    def do_POST(self):  # noqa: N802
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        FakeCloud.requests.append(body)
        if not body.get("stream"):
            text = "Вот память:\n```json\n" + json.dumps(FakeCloud.learned, ensure_ascii=False) + "\n```"
            self._json({"choices": [{"message": {"content": text}}]})
            return
        text = FakeCloud.replies.pop(0) if FakeCloud.replies else "…"
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.end_headers()
        for i in range(0, len(text), 7):
            chunk = {"choices": [{"delta": {"content": text[i:i + 7]}}]}
            self.wfile.write(f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n".encode())
        self.wfile.write(b"data: [DONE]\n\n")

    def log_message(self, *args):
        pass


class BrainTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.fake = ThreadingHTTPServer(("127.0.0.1", 0), FakeCloud)
        threading.Thread(target=self.fake.serve_forever, daemon=True).start()
        FakeCloud.replies, FakeCloud.requests, FakeCloud.learned = [], [], {}
        config = Config(cloud_url=f"http://127.0.0.1:{self.fake.server_address[1]}/v1",
                        cloud_model="Qwen/Qwen3-235B-A22B-Instruct-2507")
        (base / "config").mkdir()
        (base / "config" / "secrets.json").write_text(json.dumps({"cloud_api_key": KEY}), encoding="utf-8")
        cloud = CloudService(config, base / "config" / "yakumo.json", base / "config" / "secrets.json")
        self.data = base / "YakumoData"
        self.ctx = Context(paths=SimpleNamespace(app=base, data=self.data, workspace=base), config=config, cloud=cloud)
        infos = load_all(self.ctx, [MODULES], ["disk", "update", "hello"])
        self.assertTrue(all(i.error is None for i in infos), [i.error for i in infos])
        self.learn = sys.modules["yakumo_modules.brain.learn"]
        self.learn.DELAY = 0.1
        cloud.tools = self.ctx.chat_tools
        cloud.context_hooks = self.ctx.chat_contexts
        cloud.listeners = self.ctx.chat_listeners
        self.server = create_server("127.0.0.1", 0, base, {**self.ctx.routes, **cloud.routes()})
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}"

    def tearDown(self):
        self.ctx.stop()
        self.learn.DELAY = 20
        for s in (self.server, self.fake):
            s.shutdown()
            s.server_close()
        self.tmp.cleanup()

    def get(self, path):
        with urllib.request.urlopen(self.base + path) as r:
            return json.loads(r.read())

    def post(self, path, data, raw=False):
        req = urllib.request.Request(self.base + path, data=json.dumps(data).encode(),
                                     headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req) as r:
            body = r.read().decode()
        return body if raw else json.loads(body)

    def chat(self, messages, chat_id="c1"):
        body = self.post("/api/chat", {"messages": messages, "chat_id": chat_id}, raw=True)
        events = [json.loads(line) for line in body.splitlines() if line]
        return "".join(e.get("delta", "") for e in events), events

    def wait_for(self, check, timeout=5.0):
        end = time.time() + timeout
        while time.time() < end:
            if check():
                return
            time.sleep(0.05)
        self.fail("не дождались")

    def system_prompt(self):
        return next(r for r in FakeCloud.requests if r.get("stream"))["messages"][0]["content"]

    def test_learns_from_chat_and_remembers_in_next_one(self):
        FakeCloud.learned = {"new": [{"text": "Пользователя зовут Аня", "kind": "person", "importance": 3},
                                     {"text": "Любит зелёный чай", "kind": "likes", "importance": 2}],
                             "seen": [], "outdated": [], "title": "Знакомство", "summary": "Аня рассказала о себе."}
        FakeCloud.replies = ["Приятно познакомиться, Аня!"]
        self.chat([{"role": "user", "content": "Привет, я Аня и люблю зелёный чай"}])
        self.wait_for(lambda: len(self.get("/api/brain")["talks"]) == 1)
        state = self.get("/api/brain")
        self.assertEqual({f["text"] for f in state["facts"]}, {"Пользователя зовут Аня", "Любит зелёный чай"})
        self.assertEqual(state["talks"][0]["title"], "Знакомство")
        self.assertTrue((self.data / "brain" / "memory.json").is_file())
        learn_prompt = next(r for r in FakeCloud.requests if not r.get("stream"))["messages"][0]["content"]
        self.assertIn("Привет, я Аня", learn_prompt)

        # Новая беседа: память и конспект прошлой — в подсказке.
        FakeCloud.requests, FakeCloud.replies = [], ["Конечно, Аня."]
        self.chat([{"role": "user", "content": "Как меня зовут?"}], chat_id="c2")
        prompt = self.system_prompt()
        self.assertIn("Пользователя зовут Аня", prompt)
        self.assertIn("«Знакомство»: Аня рассказала о себе.", prompt)

    def test_outdated_facts_are_replaced_and_duplicates_merged(self):
        old = self.post("/api/brain/fact", {"text": "Живёт в Казани", "kind": "person"})["facts"][0]
        again = self.post("/api/brain/fact", {"text": "живёт в Казани"})["facts"]
        self.assertEqual(len(again), 1)
        self.assertEqual(again[0]["seen"], 2)
        FakeCloud.learned = {"new": [{"text": "Живёт в Москве", "kind": "person", "importance": 3}],
                             "outdated": [old["id"], "чужой-id"], "title": "Переезд", "summary": "Переехала."}
        self.chat([{"role": "user", "content": "Я переехала в Москву"}])
        self.wait_for(lambda: self.get("/api/brain")["talks"])
        self.assertEqual([f["text"] for f in self.get("/api/brain")["facts"]], ["Живёт в Москве"])

    def test_chat_tools_remember_recall_and_forget(self):
        FakeCloud.replies = ['<tool>{"name": "memory_remember", "args": {"text": "Пьёт чай без сахара", '
                             '"kind": "likes"}}</tool>', "Запомнила!"]
        text, events = self.chat([{"role": "user", "content": "Запомни: я пью чай без сахара"}])
        self.assertEqual(text, "Запомнила!")
        self.assertIn({"status": "Запоминаю: Пьёт чай без сахара"}, events)
        fact = self.get("/api/brain")["facts"][0]
        self.assertEqual((fact["text"], fact["source"], fact["importance"]), ("Пьёт чай без сахара", "chat", 3))

        FakeCloud.replies = ['<tool>{"name": "memory_recall", "args": {"query": "сахар"}}</tool>', "Помню."]
        self.chat([{"role": "user", "content": "Что я говорила про сахар?"}])
        self.assertIn("Пьёт чай без сахара", FakeCloud.requests[-1]["messages"][-1]["content"])

        # «Забыть» — только по подтверждению, как изменения файлов.
        FakeCloud.replies = [f'<tool>{{"name": "memory_forget", "args": {{"ids": ["{fact["id"]}"]}}}}</tool>Забуду.']
        _text, events = self.chat([{"role": "user", "content": "Забудь про чай"}])
        card = next(e["card"] for e in events if "card" in e)
        self.assertEqual(card["actions"][0]["title"], "Забыть «Пьёт чай без сахара»")
        self.assertEqual(len(self.get("/api/brain")["facts"]), 1)
        self.post("/api/chat/apply", {"actions": card["actions"]})
        self.assertEqual(self.get("/api/brain")["facts"], [])

    def test_turned_off_memory_stays_out_of_chat(self):
        self.post("/api/brain/fact", {"text": "Секретный проект Феникс", "kind": "work"})
        self.post("/api/brain/settings", {"enabled": False})
        FakeCloud.replies = ["Ок"]
        self.chat([{"role": "user", "content": "Привет"}])
        time.sleep(0.4)
        self.assertNotIn("Феникс", self.system_prompt())
        self.assertFalse([r for r in FakeCloud.requests if not r.get("stream")])  # и сама не учится

    def test_page_edit_pin_export_import_and_clear(self):
        f = self.post("/api/brain/fact", {"text": "Учится на дизайнера", "kind": "work"})["facts"][0]
        state = self.post("/api/brain/fact", {"id": f["id"], "text": "Учится на дизайнера интерьеров", "pinned": True})
        self.assertEqual(state["facts"][0]["text"], "Учится на дизайнера интерьеров")
        self.assertEqual(state["facts"][0]["score"], 10.0)
        dump = self.get("/api/brain/export")
        self.post("/api/brain/clear", {"all": True})
        self.assertEqual(self.get("/api/brain")["facts"], [])
        res = self.post("/api/brain/import", dump)
        self.assertEqual(res["facts"], 1)
        self.assertTrue(res["state"]["facts"][0]["pinned"])
        self.assertEqual(self.post("/api/brain/import", dump)["facts"], 0)  # повторный импорт не дублирует
        for path, data in (("/api/brain/import", {"facts": []}), ("/api/brain/fact", {"text": "  "}),
                           ("/api/brain/clear", {}), ("/api/brain/settings", {"enabled": "да"})):
            with self.assertRaises(urllib.error.HTTPError) as err:
                self.post(path, data)
            self.assertEqual(err.exception.code, 400, path)

    def test_old_minor_facts_fade_and_are_forgotten(self):
        store = sys.modules["yakumo_modules.brain.store"]
        memory = store.Memory(self.data / "m.json")
        old = time.time() - 200 * 86400
        minor = memory.add("Смотрел вчера фильм", importance=1, source="auto")
        keep = memory.add("Зовут Аня", importance=3, source="auto")
        mine = memory.add("Любит котов", importance=1, source="manual")
        for f in (minor, keep, mine):
            f["last_seen"] = int(old)
        self.assertLess(memory.score(minor), memory.score(keep))
        memory.add("Новый факт", source="auto")  # при добавлении память чистится
        self.assertEqual({f["text"] for f in memory.facts()}, {"Зовут Аня", "Любит котов", "Новый факт"})


if __name__ == "__main__":
    unittest.main()
