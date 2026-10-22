import contextlib
import json
import os
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest import mock

from yakumo.core import autostart
from yakumo.core.config import Config
from yakumo.core.settings import SettingsService
from yakumo.web.server import create_server


class SettingsApiTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.config_path = root / "config" / "yakumo.json"
        self.config = Config()
        self.service = SettingsService(self.config, self.config_path, tray_running=False, tray_available=True)
        self.server = create_server("127.0.0.1", 0, root, self.service.routes())
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.tmp.cleanup()

    def post(self, data, headers=None):
        req = urllib.request.Request(self.base + "/api/settings", data=json.dumps(data).encode("utf-8"),
                                     headers=headers or {"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())

    def test_get_and_save(self):
        got = json.loads(urllib.request.urlopen(self.base + "/api/settings").read())
        self.assertEqual(got["values"]["language"], "ru")
        res = self.post({"language": "en", "font_scale": 115, "compact": True})
        self.assertEqual(res["values"]["font_scale"], 115)
        saved = json.loads(self.config_path.read_text(encoding="utf-8"))
        self.assertEqual((saved["language"], saved["compact"]), ("en", True))

    def test_avatar_settings(self):
        got = json.loads(urllib.request.urlopen(self.base + "/api/settings").read())
        self.assertEqual(got["values"]["avatar_size"], 232)
        self.assertIn(232, got["options"]["avatar_size"])
        res = self.post({"avatar_show": False, "avatar_size": 960, "avatar_motion": "alive",
                         "avatar_glow": "pulse", "avatar_speed": "fast"})
        self.assertEqual(res["values"]["avatar_motion"], "alive")
        saved = json.loads(self.config_path.read_text(encoding="utf-8"))
        self.assertEqual((saved["avatar_show"], saved["avatar_size"]), (False, 960))
        # Убранный вариант движения в старом файле настроек сбрасывается на значение по умолчанию.
        self.config_path.write_text('{"avatar_motion": "bounce", "avatar_size": 304}', encoding="utf-8")
        old = Config.load(self.config_path)
        self.assertEqual((old.avatar_motion, old.avatar_size), ("float", 304))
        res = self.post({"avatar_effects": ["foxfire", "petals", "moon", "runes"], "avatar_fx_power": "high", "avatar_size": 2000})
        self.assertEqual(res["values"]["avatar_effects"], ["foxfire", "petals", "moon", "runes"])
        self.assertEqual(self.post({"avatar_effects": []})["values"]["avatar_effects"], [])
        for bad in ({"avatar_size": 233}, {"avatar_size": 2008}, {"avatar_motion": "sway"}, {"avatar_show": 1},
                    {"avatar_effects": "petals"}, {"avatar_effects": ["petals", "petals"]}, {"avatar_effects": ["boom"]}):
            with self.assertRaises(urllib.error.HTTPError):
                self.post(bad)

    def test_restart_needed_for_tray(self):
        res = self.post({"tray": True})
        self.assertIn("tray", res["restart_needed"])
        res = self.post({"tray": False})
        self.assertEqual(res["restart_needed"], [])

    def test_invalid_values_rejected_and_nothing_saved(self):
        for bad in ({"font_scale": 999}, {"port": 1}, {"language": "en", "tray": "yes"}, [1, 2]):
            with self.assertRaises(urllib.error.HTTPError) as err:
                self.post(bad)
            self.assertEqual(err.exception.code, 400)
        self.assertFalse(self.config_path.exists())
        self.assertEqual(self.config.language, "ru")

    def test_foreign_site_is_blocked(self):
        for headers in ({"Content-Type": "text/plain"},
                        {"Content-Type": "application/json", "Origin": "http://evil.example"}):
            with self.assertRaises(urllib.error.HTTPError) as err:
                self.post({"compact": True}, headers)
            self.assertEqual(err.exception.code, 403)
        self.assertFalse(self.config.compact)

    def test_autostart_writes_registry(self):
        reg = FakeWinreg()
        with mock.patch.dict(sys.modules, {"winreg": reg}), mock.patch.object(autostart, "supported", lambda: True):
            self.assertTrue(self.post({"autostart": True})["values"]["autostart"])
            value = reg.values[autostart.NAME]
            self.assertIn("Yakumo.pyw", value)
            self.assertIn("--no-browser", value)
            self.assertFalse(self.post({"autostart": False})["values"]["autostart"])
            self.assertNotIn(autostart.NAME, reg.values)

    def test_autostart_unsupported_is_rejected(self):
        with mock.patch.object(autostart, "supported", lambda: False):
            with self.assertRaises(urllib.error.HTTPError) as err:
                self.post({"autostart": True})
            self.assertEqual(err.exception.code, 400)


class FakeWinreg:
    """Минимальная замена winreg для проверки вне Windows."""

    HKEY_CURRENT_USER = "HKCU"
    REG_SZ = 1

    def __init__(self):
        self.values = {}

    def _key(self, *_args):
        return contextlib.nullcontext(self)

    OpenKey = CreateKey = _key

    def QueryValueEx(self, _key, name):  # noqa: N802
        if name not in self.values:
            raise FileNotFoundError(name)
        return self.values[name], self.REG_SZ

    def SetValueEx(self, _key, name, _reserved, _type, value):  # noqa: N802
        self.values[name] = value

    def DeleteValue(self, _key, name):  # noqa: N802
        if name not in self.values:
            raise FileNotFoundError(name)
        del self.values[name]


class AutostartCommandTest(unittest.TestCase):
    def test_entry_script_exists(self):
        cmd = autostart.command()
        self.assertTrue(Path(cmd[3]).is_file())
        self.assertEqual(cmd[1:3], ["-X", "utf8"])


if __name__ == "__main__":
    unittest.main()
