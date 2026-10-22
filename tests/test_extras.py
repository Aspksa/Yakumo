import json
import tempfile
import threading
import unittest
import urllib.parse
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


class RussianTest(unittest.TestCase):
    """Русские пути, имена, настройки и адреса."""

    def test_bat_is_ascii_and_messages_are_utf8(self):
        root = Path(__file__).resolve().parents[1]
        (root / "Yakumo.bat").read_bytes().decode("ascii")
        for name in ("no_python.txt", "offer_python.txt", "download_failed.txt", "failed.txt"):
            text = (root / "launcher" / name).read_bytes().decode("utf-8")
            self.assertRegex(text, "[а-яА-Я]")
            self.assertFalse(text.startswith("\ufeff"))
            self.assertIn(name, (root / "Yakumo.bat").read_text(encoding="ascii"))

    def test_python_download_script(self):
        root = Path(__file__).resolve().parents[1]
        raw = (root / "launcher" / "get_python.ps1").read_bytes()
        # Windows PowerShell 5.1 читает файл без BOM в ANSI и портит кириллицу.
        self.assertTrue(raw.startswith(b"\xef\xbb\xbf"))
        text = raw.decode("utf-8-sig")
        self.assertIn("Lib\\site-packages", text)
        self.assertIn("get_python.ps1", (root / "Yakumo.bat").read_text(encoding="ascii"))

    def test_config_with_bom_from_notepad(self):
        from yakumo.core.config import Config
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "yakumo.json"
            path.write_bytes('\ufeff{"workspace": "D:\\\\Документы", "port": 9001}'.encode("utf-8"))
            cfg = Config.load(path)
            self.assertEqual((cfg.workspace, cfg.port), ("D:\\Документы", 9001))
            cfg.save(path)
            self.assertIn("Документы", path.read_text(encoding="utf-8"))

    def test_cyrillic_data_dir_and_workspace(self):
        from yakumo.core.paths import build_paths
        from yakumo.core.storage import choose_storage
        with tempfile.TemporaryDirectory() as tmp:
            choice = choose_storage(Path(tmp) / "Мои данные")
            paths = build_paths(choice, str(Path(tmp) / "Рабочая папка")).ensure()
            self.assertTrue(paths.workspace.is_dir())
            self.assertTrue((Path(tmp) / "Мои данные" / "logs").is_dir())

    def test_module_in_cyrillic_folder_with_cyrillic_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "модули"
            folder.mkdir()
            (folder / "привет.py").write_text(
                "NAME = 'Привет'\ndef setup(ctx):\n    ctx.route('/api/привет', lambda r: {'текст': 'мир'})\n",
                encoding="utf-8")
            ctx = Context(paths=None, config=None)
            infos = load_all(ctx, [folder])
            self.assertIsNone(infos[0].error)
            self.assertIn("/api/привет", ctx.routes)

    def test_cyrillic_route_and_static_charset(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "заметка.txt").write_text("Привет", encoding="utf-8")
            routes = {"/api/привет": lambda r: {"текст": "мир"}}
            server = create_server("127.0.0.1", 0, tmp, routes)
            threading.Thread(target=server.serve_forever, daemon=True).start()
            base = f"http://127.0.0.1:{server.server_address[1]}"
            quote = urllib.parse.quote
            try:
                with urllib.request.urlopen(base + quote("/api/привет")) as resp:
                    self.assertEqual(json.loads(resp.read().decode("utf-8")), {"текст": "мир"})
                with urllib.request.urlopen(base + quote("/заметка.txt")) as resp:
                    self.assertIn("charset=utf-8", resp.headers["Content-Type"])
                    self.assertEqual(resp.read().decode("utf-8"), "Привет")
            finally:
                server.shutdown()
                server.server_close()

    def test_cyrillic_hostname_does_not_crash(self):
        from unittest import mock
        from yakumo.core import network
        with mock.patch("socket.gethostname", return_value="ИВАН-ПК"), \
             mock.patch("socket.getaddrinfo", side_effect=UnicodeError("idna")):
            self.assertIn("127.0.0.1", network.local_addresses())

    def test_non_utf8_console_does_not_crash(self):
        import os
        import subprocess
        import sys
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as tmp:
            env = {**os.environ, "PYTHONIOENCODING": "ascii", "PYTHONUTF8": "0"}
            out = subprocess.run([sys.executable, "-m", "yakumo", "--info", "--data-dir", str(Path(tmp) / "Данные")],
                                 cwd=root, env=env, capture_output=True)
            self.assertEqual(out.returncode, 0, out.stderr.decode("utf-8", "replace"))
            self.assertIn(b"Yakumo", out.stdout)
