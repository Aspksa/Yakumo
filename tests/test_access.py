import http.client
import json
import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from yakumo.core.access import AccessControl, MAX_ATTEMPTS, SESSION_SECONDS
from yakumo.core.config import Config
from yakumo.core.modules import Context, load_all
from yakumo.web.server import create_server

PASSWORD = "test-password-for-lan"


class AccessTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        (self.base / "index.html").write_text("Yakumo private UI", encoding="utf-8")
        paths = SimpleNamespace(app=self.base, data=self.base / "data")
        self.ctx = Context(paths=paths, config=Config(lan=True))
        infos = load_all(self.ctx, [Path(__file__).resolve().parents[1] / "modules"])
        self.assertTrue(all(i.error is None for i in infos))
        self.root = paths.data / "disk"
        (self.root / "private.txt").write_text("private test data", encoding="utf-8")
        self.access = AccessControl(self.base / "config" / "access.json")
        routes = {**self.ctx.routes, **{p: lambda _req: {"private": True} for p in
                  ("/api/status", "/api/settings", "/api/modules", "/api/cloud")}}
        self.server = create_server("127.0.0.1", 0, self.base, routes, access=self.access)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        # Настоящий HTTP, но с точкой зрения другого устройства в LAN.
        self.remote = mock.patch.object(self.access, "is_local", return_value=False)
        self.remote.start()

    def tearDown(self):
        self.remote.stop()
        self.server.shutdown()
        self.server.server_close()
        self.ctx.stop()
        for hook in self.ctx.stop_hooks:
            owner = getattr(hook, "__self__", None)
            thread = getattr(owner, "thread", None)
            if thread:
                thread.join(3)
        self.tmp.cleanup()

    def call(self, path, data=None, cookie=None, method=None, headers=None):
        headers = dict(headers or {})
        if data is not None:
            data = json.dumps(data).encode("utf-8")
            headers.setdefault("Content-Type", "application/json")
        if cookie:
            headers["Cookie"] = cookie
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
        try:
            connection.request(method or ("POST" if data is not None else "GET"), path, body=data, headers=headers)
            response = connection.getresponse()
            return response.status, dict(response.getheaders()), response.read()
        finally:
            connection.close()

    def set_password(self, value=PASSWORD):
        with mock.patch.object(self.access, "is_local", return_value=True):
            status, _, body = self.call("/api/auth/password", {"password": value})
        self.assertEqual(status, 200, body)

    def login(self, value=PASSWORD):
        status, headers, body = self.call("/api/auth/login", {"password": value})
        self.assertEqual(status, 200, body)
        return headers["Set-Cookie"].split(";")[0]

    def test_remote_access_is_closed_before_and_after_password_setup(self):
        for configured in (False, True):
            if configured:
                self.set_password()
            for path in ("/api/status", "/api/settings", "/api/modules", "/api/cloud", "/api/disk/list",
                         "/api/disk/file?path=private.txt", "/api/disk/trash", "/api/disk/shares"):
                with self.subTest(path=path, configured=configured):
                    self.assertEqual(self.call(path)[0], 401)
            self.assertEqual(self.call("/api/disk/file?path=private.txt", method="HEAD")[0], 401)
            self.assertEqual(self.call("/api/disk/mkdir", {"path": "", "name": "blocked"})[0], 401)
            status, headers, _ = self.call("/")
            self.assertEqual((status, headers["Location"]), (303, "/login"))
            self.assertFalse((self.root / "blocked").exists())

    def test_login_cookie_allows_read_write_and_logout_revokes_it(self):
        self.set_password()
        status, headers, _ = self.call("/api/auth/login", {"password": PASSWORD})
        self.assertEqual(status, 200)
        self.assertIn("HttpOnly", headers["Set-Cookie"])
        self.assertIn("SameSite=Strict", headers["Set-Cookie"])
        self.assertEqual(headers["Cache-Control"], "no-store")
        cookie = headers["Set-Cookie"].split(";")[0]
        self.assertEqual(self.call("/api/disk/file?path=private.txt", cookie=cookie)[2], b"private test data")
        self.assertEqual(self.call("/api/disk/mkdir", {"path": "", "name": "allowed"}, cookie=cookie)[0], 200)
        self.assertTrue((self.root / "allowed").is_dir())
        self.assertEqual(self.call("/api/auth/logout", {}, cookie=cookie)[0], 200)
        self.assertEqual(self.call("/api/status", cookie=cookie)[0], 401)
        self.assertEqual(self.call("/api/status", cookie="yakumo_session=forged")[0], 401)

    def test_password_is_local_only_persisted_as_hash_and_revokes_sessions(self):
        self.set_password()
        cookie = self.login()
        self.assertEqual(self.call("/api/auth/password", {"password": "remote-new-password"}, cookie=cookie)[0], 403)
        saved = self.access.path.read_text(encoding="utf-8")
        self.assertNotIn(PASSWORD, saved)
        self.assertIsNotNone(AccessControl(self.access.path).password)
        self.set_password("different-local-password")
        self.assertEqual(self.call("/api/status", cookie=cookie)[0], 401)
        self.assertEqual(self.call("/api/auth/login", {"password": PASSWORD})[0], 401)
        self.login("different-local-password")

    def test_clear_password_closes_remote_signin(self):
        self.set_password()
        cookie = self.login()
        self.set_password("")
        self.assertEqual(self.call("/api/status", cookie=cookie)[0], 401)
        self.assertEqual(self.call("/api/auth/login", {"password": PASSWORD})[0], 401)
        self.assertFalse(self.access.path.exists())

    def test_session_expires(self):
        self.set_password()
        cookie = self.login()
        with mock.patch("yakumo.core.access.time.monotonic", return_value=time.monotonic() + SESSION_SECONDS + 1):
            self.assertEqual(self.call("/api/status", cookie=cookie)[0], 401)

    def test_login_attempts_are_limited_and_foreign_origin_is_rejected(self):
        self.set_password()
        self.assertEqual(self.call("/api/auth/login", {"password": PASSWORD},
                                  headers={"Origin": "http://untrusted.example"})[0], 403)
        for _ in range(MAX_ATTEMPTS):
            self.assertEqual(self.call("/api/auth/login", {"password": "wrong"})[0], 401)
        status, headers, _ = self.call("/api/auth/login", {"password": PASSWORD})
        self.assertEqual(status, 429)
        self.assertIn("Retry-After", headers)

    def test_only_explicit_share_is_public(self):
        (self.root / "Shared").mkdir()
        (self.root / "Shared" / "public.txt").write_text("shared test data", encoding="utf-8")
        with mock.patch.object(self.access, "is_local", return_value=True):
            status, _, body = self.call("/api/disk/share", {"path": "Shared"})
        self.assertEqual(status, 200)
        token = json.loads(body)["token"]
        self.assertEqual(self.call(f"/api/disk/s?t={token}")[0], 200)
        self.assertEqual(self.call(f"/api/disk/s?t={token}&p=public.txt")[2], b"shared test data")
        self.assertEqual(self.call(f"/api/disk/s?t={token}&p=../private.txt")[0], 400)
        self.assertEqual(self.call("/api/disk/s?t=wrong")[0], 404)
        self.assertEqual(self.call("/api/disk/file?path=private.txt")[0], 401)
        self.assertEqual(self.call("/api/disk/shares")[0], 401)

    def test_local_owner_still_opens_directly_and_bad_host_is_rejected(self):
        with mock.patch.object(self.access, "is_local", return_value=True):
            self.assertEqual(self.call("/")[0], 200)
            self.assertEqual(self.call("/api/status")[0], 200)
            self.assertEqual(self.call("/api/status", headers={"Host": f"untrusted.example:{self.server.server_port}"})[0], 403)
        status, _, body = self.call("/api/auth")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body), {"local": False, "password_set": False, "authenticated": False})
        self.assertIn("Сетевой доступ закрыт", self.call("/login")[2].decode("utf-8"))
        self.set_password()
        self.assertIn('autocomplete="current-password"', self.call("/login")[2].decode("utf-8"))

    def test_peer_detection_uses_socket_addresses_not_forwarded_headers(self):
        request = SimpleNamespace(client_address=("192.0.2.4", 1234),
                                  connection=SimpleNamespace(getsockname=lambda: ("192.0.2.1", 8765)),
                                  headers={"X-Forwarded-For": "127.0.0.1", "Host": "localhost:8765"})
        self.assertFalse(AccessControl.is_local(request))
        request.client_address = ("192.0.2.1", 1234)
        self.assertTrue(AccessControl.is_local(request))
        request.client_address = ("127.0.0.1", 1234)
        self.assertTrue(AccessControl.is_local(request))

    def test_bad_password_file_keeps_remote_access_closed(self):
        for value in ("[]", "null", '{"version":1,"salt":"bad","hash":"bad"}'):
            self.access.path.parent.mkdir(parents=True, exist_ok=True)
            self.access.path.write_text(value, encoding="utf-8")
            self.assertIsNone(AccessControl(self.access.path).password)


if __name__ == "__main__":
    unittest.main()
