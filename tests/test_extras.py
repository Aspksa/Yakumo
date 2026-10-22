import json
import tempfile
import threading
import unittest
import urllib.request
from pathlib import Path

from yakumo.core.instance import InstanceLock
from yakumo.core.modules import Context, discover, load_all
from yakumo.web.server import create_server


class InstanceTest(unittest.TestCase):
    def test_second_lock_fails_and_sees_url(self):
        with tempfile.TemporaryDirectory() as tmp:
            first, second = InstanceLock(Path(tmp)), InstanceLock(Path(tmp))
            self.assertTrue(first.acquire())
            first.publish("http://localhost:1234/")
            self.assertFalse(second.acquire())
            self.assertEqual(second.running_url(), "http://localhost:1234/")
            first.release()
            self.assertTrue(second.acquire())
            second.release()


class ModulesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_loads_file_and_package_and_survives_errors(self):
        (self.dir / "good.py").write_text(
            "NAME = 'Хороший'\ndef setup(ctx):\n    ctx.route('/api/good', lambda r: {'ok': True})\n",
            encoding="utf-8")
        (self.dir / "bad.py").write_text("raise RuntimeError('сломан')\n", encoding="utf-8")
        (self.dir / "pkg").mkdir()
        (self.dir / "pkg" / "__init__.py").write_text(
            "from .helper import VALUE\ndef setup(ctx):\n    ctx.status(lambda: VALUE)\n", encoding="utf-8")
        (self.dir / "pkg" / "helper.py").write_text("VALUE = 42\n", encoding="utf-8")
        (self.dir / "_skip.py").write_text("raise SystemExit\n", encoding="utf-8")
        (self.dir / "off.py").write_text("def setup(ctx): raise AssertionError\n", encoding="utf-8")

        ctx = Context(paths=None, config=None)
        infos = {i.name: i for i in load_all(ctx, [self.dir], disabled=["off"])}
        self.assertEqual(set(infos), {"good", "bad", "pkg"})
        self.assertIsNone(infos["good"].error)
        self.assertEqual(infos["good"].title, "Хороший")
        self.assertIn("сломан", infos["bad"].error)
        self.assertIn("/api/good", ctx.routes)
        self.assertEqual(ctx.status_hooks["pkg"](), 42)

    def test_first_dir_wins(self):
        other = self.dir / "other"
        other.mkdir()
        (self.dir / "m.py").write_text("", encoding="utf-8")
        (other / "m.py").write_text("", encoding="utf-8")
        self.assertEqual(discover([self.dir, other]), [("m", self.dir / "m.py")])

    def test_example_module(self):
        ctx = Context(paths=None, config=None)
        root = Path(__file__).resolve().parents[1] / "modules"
        infos = load_all(ctx, [root])
        self.assertTrue(all(i.error is None for i in infos))
        self.assertIn("/api/hello", ctx.routes)


class ServerTest(unittest.TestCase):
    def test_routes_and_static(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "index.html").write_text("<h1>ok</h1>", encoding="utf-8")
            routes = {"/api/x": lambda r: {"x": 1}, "/page": lambda r: "<p>привет</p>",
                      "/boom": lambda r: 1 / 0}
            server = create_server("127.0.0.1", 0, tmp, routes)
            threading.Thread(target=server.serve_forever, daemon=True).start()
            base = f"http://127.0.0.1:{server.server_address[1]}"
            try:
                self.assertEqual(json.loads(urllib.request.urlopen(base + "/api/x?a=1").read()), {"x": 1})
                self.assertIn("привет", urllib.request.urlopen(base + "/page").read().decode())
                self.assertIn(b"ok", urllib.request.urlopen(base + "/").read())
                with self.assertRaises(urllib.error.HTTPError) as err:
                    urllib.request.urlopen(base + "/boom")
                self.assertEqual(err.exception.code, 500)
            finally:
                server.shutdown()
                server.server_close()


if __name__ == "__main__":
    unittest.main()
