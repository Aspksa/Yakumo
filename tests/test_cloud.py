import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from yakumo.core.cloud import CloudService
from yakumo.core.config import Config
from yakumo.web.server import create_server

GOOD_KEY = "good-key-1234567"


class FakeCloud(BaseHTTPRequestHandler):
    """Подставной Cloud.ru: каталог моделей и потоковый чат в формате OpenAI."""
    last_body = None

    def _auth(self):
        if self.headers.get("Authorization") != f"Bearer {GOOD_KEY}":
            self._json(401, {"error": {"message": "invalid api key"}})
            return False
        return True

    def _json(self, code, data):
        body = json.dumps(data).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  # noqa: N802
        if self._auth():
            self._json(200, {"data": [{"id": "ai-sage/GigaChat3-10B-A1.8B"}, {"id": "other/model"}]})

    def do_POST(self):  # noqa: N802
        if not self._auth():
            return
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        FakeCloud.last_body = body
        if body["model"] == "missing/model":
            self._json(404, {"error": {"message": "model not found"}})
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.end_headers()
        for part in ("При", "вет!"):
            chunk = {"choices": [{"delta": {"content": part}}]}
            self.wfile.write(f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n".encode())
        self.wfile.write(b"data: [DONE]\n\n")

    def log_message(self, *args):
        pass


class CloudApiTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.fake = ThreadingHTTPServer(("127.0.0.1", 0), FakeCloud)
        threading.Thread(target=self.fake.serve_forever, daemon=True).start()
        self.config = Config(cloud_url=f"http://127.0.0.1:{self.fake.server_address[1]}/v1")
        self.config_path = root / "config" / "yakumo.json"
        self.secrets = root / "config" / "secrets.json"
        self.service = CloudService(self.config, self.config_path, self.secrets)
        self.server = create_server("127.0.0.1", 0, root, self.service.routes())
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}"

    def tearDown(self):
        for s in (self.server, self.fake):
            s.shutdown()
            s.server_close()
        self.tmp.cleanup()

    def post(self, path, data, headers=None, raw=False):
        req = urllib.request.Request(self.base + path, data=json.dumps(data).encode("utf-8"),
                                     headers=headers or {"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req) as resp:
            body = resp.read().decode("utf-8")
        return body if raw else json.loads(body)

    def chat(self, messages):
        body = self.post("/api/chat", {"messages": messages}, raw=True)
        return [json.loads(line) for line in body.splitlines() if line]

    def test_key_is_saved_but_never_returned(self):
        state = json.loads(urllib.request.urlopen(self.base + "/api/cloud").read())
        self.assertFalse(state["has_key"])
        state = self.post("/api/cloud", {"api_key": f"  {GOOD_KEY} "})
        self.assertEqual((state["has_key"], state["key_hint"]), (True, "…4567"))
        self.assertNotIn(GOOD_KEY, json.dumps(state))
        self.assertEqual(json.loads(self.secrets.read_text())["cloud_api_key"], GOOD_KEY)
        self.assertFalse(self.config_path.exists())  # ключ не попадает в yakumo.json
        self.assertFalse(self.post("/api/cloud", {"api_key": ""})["has_key"])
        self.assertFalse(self.secrets.exists())

    def test_connection_check_and_default_model(self):
        self.post("/api/cloud", {"api_key": "wrong-key-0000"})
        res = self.post("/api/cloud/test", {})
        self.assertEqual((res["ok"], res["error"]), (False, "bad_key"))
        self.post("/api/cloud", {"api_key": GOOD_KEY})
        res = self.post("/api/cloud/test", {})
        self.assertTrue(res["ok"])
        self.assertEqual(res["models"], ["ai-sage/GigaChat3-10B-A1.8B", "other/model"])
        self.assertEqual(res["model"], "ai-sage/GigaChat3-10B-A1.8B")
        self.assertEqual(self.post("/api/cloud", {"model": "other/model"})["model"], "other/model")
        saved = json.loads(self.config_path.read_text(encoding="utf-8"))
        self.assertEqual(saved["cloud_model"], "other/model")

    def test_chat_streams_reply(self):
        self.post("/api/cloud", {"api_key": GOOD_KEY})
        events = self.chat([{"role": "user", "content": "Привет"}])
        self.assertEqual("".join(e.get("delta", "") for e in events), "Привет!")
        self.assertEqual(events[-1], {"done": True})
        sent = FakeCloud.last_body
        self.assertTrue(sent["stream"])
        self.assertEqual(sent["messages"][0]["role"], "system")
        self.assertEqual(sent["messages"][1:], [{"role": "user", "content": "Привет"}])

    def test_chat_errors(self):
        self.assertEqual(self.chat([{"role": "user", "content": "x"}]), [{"error": "no_key"}])
        self.post("/api/cloud", {"api_key": GOOD_KEY, "model": "missing/model"})
        self.assertEqual(self.chat([{"role": "user", "content": "x"}]), [{"error": "bad_model"}])
        self.config.cloud_url = "http://127.0.0.1:9/v1"  # никто не слушает
        self.assertEqual(self.chat([{"role": "user", "content": "x"}]), [{"error": "network"}])

    def test_bad_requests(self):
        for path, bad in (("/api/chat", {"messages": []}), ("/api/chat", {"messages": [{"role": "system", "content": "x"}]}),
                          ("/api/cloud", {"api_key": "a b"}), ("/api/cloud", {"other": 1})):
            with self.assertRaises(urllib.error.HTTPError) as err:
                self.post(path, bad)
            self.assertEqual(err.exception.code, 400)
        with self.assertRaises(urllib.error.HTTPError) as err:
            self.post("/api/cloud", {"api_key": GOOD_KEY},
                      {"Content-Type": "application/json", "Origin": "http://evil.example"})
        self.assertEqual(err.exception.code, 403)
        self.assertFalse(self.secrets.exists())


if __name__ == "__main__":
    unittest.main()
