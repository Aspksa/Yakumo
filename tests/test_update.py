import hashlib
import io
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.request
import uuid
import warnings
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from modules.update import Updater, setup
from modules.update import installer, source
from yakumo.bootstrap import recover_pending
from yakumo.core.config import Config
from yakumo.core.instance import InstanceLock
from yakumo.core.modules import Context
from yakumo.core.network import find_free_port
from yakumo.web.server import create_server

ROOT = Path(__file__).resolve().parents[1]
REVISION = "a" * 40


def entry(raw):
    return {"git_sha": hashlib.sha1(f"blob {len(raw)}\0".encode() + raw).hexdigest(),
            "sha256": hashlib.sha256(raw).hexdigest(), "size": len(raw), "mode": 0o644}


def catalog(files):
    return {"revision": REVISION, "channel": "main", "title": "main", "message": "test update",
            "files": {name: entry(raw) for name, raw in files.items()}, "size": sum(map(len, files.values()))}


def zip_bytes(files):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("Aspksa-Yakumo-test/", b"")
        for name, raw in files.items():
            zf.writestr("Aspksa-Yakumo-test/" + name, raw)
    return stream.getvalue()


class SourceTest(unittest.TestCase):
    def test_archive_checks_contents_and_rejects_tampering(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive = root / "update.zip"
            files = {"yakumo/app.py": b"VALUE = 1\n", "tests/заметка.txt": "привет".encode()}
            archive.write_bytes(zip_bytes(files))
            result = source.unpack(archive, root / "stage", catalog(files)["files"], lambda *_: None)
            self.assertEqual(result["yakumo/app.py"]["sha256"], entry(files["yakumo/app.py"])["sha256"])
            archive.write_bytes(zip_bytes({**files, "yakumo/app.py": b"VALUE = 2\n"}))
            with self.assertRaisesRegex(ValueError, "Контрольная сумма"):
                source.unpack(archive, root / "bad", catalog(files)["files"], lambda *_: None)

    def test_archive_accepts_crlf_from_gitattributes(self):
        # GitHub собирает zipball через git archive и переводит строки по eol=crlf.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive = root / "update.zip"
            blob = b"@echo off\nstart Yakumo.pyw\n"
            archive.write_bytes(zip_bytes({"Yakumo.bat": blob.replace(b"\n", b"\r\n")}))
            result = source.unpack(archive, root / "stage", {"Yakumo.bat": entry(blob)}, lambda *_: None)
            self.assertEqual((root / "stage" / "Yakumo.bat").read_bytes(), blob.replace(b"\n", b"\r\n"))
            self.assertTrue(source.matches(root / "stage" / "Yakumo.bat", entry(blob)))
            self.assertEqual(result["Yakumo.bat"]["size"], len(blob) + 2)
            archive.write_bytes(zip_bytes({"Yakumo.bat": b"@echo on\r\nstart Yakumo.pyw\r\n"}))
            with self.assertRaisesRegex(ValueError, "Контрольная сумма"):
                source.unpack(archive, root / "bad", {"Yakumo.bat": entry(blob)}, lambda *_: None)

    def test_archive_rejects_traversal_duplicate_and_missing_files(self):
        cases = [({"../escape.txt": b"x"}, {}), ({"yakumo/a.py": b"x"}, {"yakumo/a.py": entry(b"x"), "yakumo/b.py": entry(b"x")})]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for i, (files, expected) in enumerate(cases):
                archive = root / f"{i}.zip"
                archive.write_bytes(zip_bytes(files))
                with self.assertRaises(ValueError):
                    source.unpack(archive, root / str(i), expected, lambda *_: None)
            self.assertFalse((root / "escape.txt").exists())
            archive = root / "duplicate.zip"
            with warnings.catch_warnings(), zipfile.ZipFile(archive, "w") as zf:
                warnings.simplefilter("ignore", UserWarning)
                zf.writestr("repo/yakumo/a.py", b"x=1")
                zf.writestr("repo/yakumo/a.py", b"x=1")
            with self.assertRaises(ValueError):
                source.unpack(archive, root / "duplicate", {"yakumo/a.py": entry(b"x=1")}, lambda *_: None)

    def test_archive_rejects_symlinks_and_bad_python(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive = root / "update.zip"
            with zipfile.ZipFile(archive, "w") as zf:
                info = zipfile.ZipInfo("repo/yakumo/a.py")
                info.create_system = 3
                info.external_attr = 0o120777 << 16
                zf.writestr(info, b"outside")
            with self.assertRaises(ValueError):
                source.unpack(archive, root / "stage", {"yakumo/a.py": entry(b"outside")}, lambda *_: None)
            archive.write_bytes(zip_bytes({"yakumo/a.py": b"def broken(\n"}))
            with self.assertRaises(SyntaxError):
                source.unpack(archive, root / "syntax", {"yakumo/a.py": entry(b"def broken(\n")}, lambda *_: None)

    def test_redirect_does_not_send_token_to_download_host(self):
        request = urllib.request.Request(source.API + "/zipball/" + REVISION,
                                         headers={"Authorization": "Bearer test-token"})
        result = source.GitHubRedirect().redirect_request(request, None, 302, "Found", {},
                    "https://codeload.github.com/Aspksa/Yakumo/legacy.zip/" + REVISION)
        self.assertIsNone(result.get_header("Authorization"))
        with self.assertRaises(ValueError):
            source.GitHubRedirect().redirect_request(request, None, 302, "Found", {}, "https://untrusted.example/archive")

    def test_resolve_uses_immutable_tree_and_rejects_truncated_catalog(self):
        files = {name: b"test" for name in source.REQUIRED}
        tree = {"truncated": False, "tree": [{"path": path, "sha": info["git_sha"], "mode": "100644",
                "type": "blob", "size": info["size"]} for path, info in catalog(files)["files"].items()]}
        client = source.GitHub()
        with mock.patch.object(client, "json", side_effect=[{"sha": REVISION, "commit": {"tree": {"sha": "b" * 40}}}, tree]) as get:
            self.assertEqual(client.resolve("main")["revision"], REVISION)
            self.assertIn("b" * 40, get.call_args.args[0])
        with mock.patch.object(client, "json", side_effect=[{"sha": REVISION, "commit": {"tree": {"sha": "b" * 40}}}, {**tree, "truncated": True}]):
            with self.assertRaisesRegex(ValueError, "неполный"):
                client.resolve("main")


class InstallerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.app, self.root = self.base / "Программа с пробелом", self.base / "данные"
        self.app.mkdir()
        self.root.mkdir()
        (self.app / "old.txt").write_bytes(b"old")
        (self.app / "gone.txt").write_bytes(b"removed by update")
        self.id = uuid.uuid4().hex
        self.stage_id = uuid.uuid4().hex
        stage = self.root / "stages" / self.stage_id
        stage.mkdir(parents=True)
        self.new = {"old.txt": b"new", "new.txt": b"new file"}
        for name, raw in self.new.items():
            (stage / name).write_bytes(raw)
        self.job = {"id": self.id, "stage": self.stage_id, "app": str(self.app), "root": str(self.root),
                    "files": {name: entry(raw) for name, raw in self.new.items()}, "remove": ["gone.txt"],
                    "installed": {"app": str(self.app), "revision": REVISION, "files": {}}, "protected": [],
                    "parent_pid": 99999999, "command": [sys.executable], "instance_info": str(self.base / "instance.json")}
        folder = self.root / "jobs" / self.id
        folder.mkdir(parents=True)
        shutil.copy2(ROOT / "modules" / "update" / "installer.py", folder / "worker.py")
        self.path = folder / "job.json"
        installer.atomic_json(self.path, self.job)

    def tearDown(self):
        self.tmp.cleanup()

    def test_install_and_restore_preserve_data_and_unknown_files(self):
        for name in ("YakumoData", "YakumoDisk", "python"):
            (self.app / name).mkdir()
            (self.app / name / "keep.txt").write_text("keep", encoding="utf-8")
        (self.app / "custom.txt").write_text("custom", encoding="utf-8")
        installer.validate_plan(self.job)
        backup = installer.make_backup(self.job, self.app, self.root)
        installer.apply_files(self.job, self.app, self.root, self.path)
        self.assertEqual((self.app / "old.txt").read_bytes(), b"new")
        self.assertFalse((self.app / "gone.txt").exists())
        installer.restore_backup(backup, self.root, self.app)
        self.assertEqual((self.app / "old.txt").read_bytes(), b"old")
        self.assertFalse((self.app / "new.txt").exists())
        self.assertTrue((self.app / "gone.txt").is_file())
        self.assertEqual((self.app / "custom.txt").read_text(), "custom")
        for name in ("YakumoData", "YakumoDisk", "python"):
            self.assertEqual((self.app / name / "keep.txt").read_text(), "keep")

    def test_tampered_stage_and_protected_paths_are_rejected_before_install(self):
        (self.root / "stages" / self.stage_id / "old.txt").write_bytes(b"tampered")
        with self.assertRaises(ValueError):
            installer.validate_plan(self.job)
        self.assertEqual((self.app / "old.txt").read_bytes(), b"old")
        for name in (".", "../x", "/x", "C:/x", "foo\\bar", "YakumoData/config.json", "python/python.exe", "config/secrets.json", "portable"):
            with self.subTest(path=name), self.assertRaises(ValueError):
                installer.safe_target(self.app, name)
        with self.assertRaises(ValueError):
            installer.safe_target(self.app, "MyData/secrets.json", ["MyData"])

    def test_failed_healthcheck_restores_old_files_and_restarts_previous_version(self):
        process = mock.Mock()
        process.poll.return_value = 0
        with mock.patch.object(installer, "wait_parent"), mock.patch.object(installer, "launch", return_value=process), \
                mock.patch.object(installer, "healthy", side_effect=[ValueError("failed startup"), None]), \
                mock.patch.object(installer, "pid_alive", return_value=False):
            self.assertEqual(installer.run(self.path), 1)
        self.assertEqual((self.app / "old.txt").read_bytes(), b"old")
        self.assertFalse((self.app / "new.txt").exists())
        self.assertEqual(installer.read_json(self.path)["phase"], "rolled_back")

    def test_busy_file_does_not_prevent_restoring_successful_replacements(self):
        original = installer.atomic_copy

        def blocked(src, dst, mode=None):
            if Path(dst) == self.app / "new.txt":
                raise PermissionError("locked by another program")
            return original(src, dst, mode)

        backup = installer.make_backup(self.job, self.app, self.root)
        with mock.patch.object(installer, "atomic_copy", side_effect=blocked):
            with self.assertRaises(PermissionError):
                installer.apply_files(self.job, self.app, self.root, self.path)
            installer.restore_backup(backup, self.root, self.app, set(self.job["applied"]))
        self.assertEqual((self.app / "old.txt").read_bytes(), b"old")

    def test_bootstrap_recovers_interrupted_install_before_core_import(self):
        installer.make_backup(self.job, self.app, self.root)
        installer.apply_files(self.job, self.app, self.root, self.path)
        self.job.update(phase="installing", worker_pid=99999999)
        installer.atomic_json(self.path, self.job)
        installer.atomic_json(self.app / installer.MARKER, {"job": str(self.path), "worker": str(self.path.parent / "worker.py")})
        recover_pending(self.app)
        self.assertEqual((self.app / "old.txt").read_bytes(), b"old")
        self.assertFalse((self.app / "new.txt").exists())
        self.assertFalse((self.app / installer.MARKER).exists())

    def test_recovery_finds_data_after_drive_letter_change(self):
        installer.make_backup(self.job, self.app, self.root)
        installer.apply_files(self.job, self.app, self.root, self.path)
        self.job.update(phase="installing", worker_pid=99999999)
        installer.atomic_json(self.path, self.job)
        # Данные переехали (как при новой букве диска), а в задании остался старый путь.
        moved = self.base / "новая буква"
        self.root.rename(moved)
        job_path = moved / "jobs" / self.id / "job.json"
        self.assertEqual(installer.recover_if_needed(job_path, self.app), 0)
        self.assertEqual((self.app / "old.txt").read_bytes(), b"old")
        self.assertFalse((self.app / "new.txt").exists())
        self.assertTrue(installer.same_app(str(self.app) + "/", self.app))


class UpdaterTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.app = self.base / "app"
        self.app.mkdir()
        self.files = {"yakumo/app.py": b"VALUE=2\n", "yakumo/new.py": b"NEW=1\n"}
        self.latest = catalog(self.files)
        self.ctx = Context(paths=SimpleNamespace(app=self.app, data=self.base / "data", workspace=self.base / "workspace"), config=Config())
        client = mock.Mock()
        client.resolve.return_value = self.latest
        client.download.side_effect = lambda revision, destination, progress: destination.write_bytes(zip_bytes(self.files))
        self.updater = Updater(self.ctx, lambda token: client)
        self.client = client

    def tearDown(self):
        self.updater.stop()
        if self.updater.thread:
            self.updater.thread.join(5)
        self.tmp.cleanup()

    def test_check_prepare_and_current_detection(self):
        self.updater._check()
        self.assertTrue(self.updater.state()["available"])
        self.updater._prepare()
        self.assertTrue(self.updater.state()["prepared"])
        self.assertFalse((self.app / "yakumo" / "new.py").exists())
        for name, raw in self.files.items():
            path = self.app / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
        self.updater._check()
        self.assertFalse(self.updater.state()["available"])
        self.assertEqual(self.updater.state()["current"], REVISION)

    def test_channel_change_invalidates_prepared_install_and_token_is_never_returned(self):
        self.updater._check()
        self.updater._prepare()
        self.updater.save_settings(SimpleNamespace(read_json=lambda: {"channel": "release"}))
        self.assertFalse(self.updater.state()["prepared"])
        with self.assertRaises(ValueError):
            self.updater.install()
        result = self.updater.save_token(SimpleNamespace(read_json=lambda: {"token": "test-token-not-a-real-secret"}))
        self.assertTrue(result["has_token"])
        self.assertNotIn("test-token-not-a-real-secret", json.dumps(result))

    def test_remote_authenticated_client_cannot_change_updater(self):
        self.ctx.current = "update"
        self.ctx.current_dir = ROOT / "modules" / "update"
        setup(self.ctx)
        server = create_server("127.0.0.1", 0, self.app, self.ctx.routes)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            access = server.RequestHandlerClass.func.access if hasattr(server.RequestHandlerClass, "func") else None
            self.assertIsNotNone(access)
            access.sessions["test-session"] = time.monotonic() + 100
            access.password = {"configured": True}
            with mock.patch.object(access, "is_local", return_value=False):
                req = urllib.request.Request(f"http://127.0.0.1:{server.server_port}/api/update/check", data=b"{}",
                    headers={"Content-Type": "application/json", "Cookie": "yakumo_session=test-session"})
                with self.assertRaises(urllib.error.HTTPError) as exc:
                    urllib.request.urlopen(req)
                self.assertEqual(exc.exception.code, 403)
        finally:
            server.shutdown()
            server.server_close()
            self.ctx.stop()


class RestartIntegrationTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="yakumo-update-")
        self.app = Path(self.tmp.name) / "Yakumo с пробелом"
        self.app.mkdir()
        for folder in ("yakumo", "modules"):
            shutil.copytree(ROOT / folder, self.app / folder, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        data = self.app / "YakumoData"
        (data / "config").mkdir(parents=True)
        (data / "config" / "secrets.json").write_text('{"cloud_api_key":"test-local-key"}', encoding="utf-8")
        (data / "disk").mkdir()
        (data / "disk" / "keep.txt").write_text("keep my files", encoding="utf-8")
        (self.app / "modules" / "custom.py").write_text('NAME="Custom"\ndef setup(ctx): pass\n', encoding="utf-8")
        self.info = InstanceLock(self.app).info_path
        self.port = find_free_port("127.0.0.1", 19865)
        self.base = f"http://127.0.0.1:{self.port}"
        self.output = (Path(self.tmp.name) / "app.log").open("w", encoding="utf-8")
        self.process = subprocess.Popen([sys.executable, "-m", "yakumo", "--data-dir", str(data), "--no-browser", "--no-tray", "--port", str(self.port)],
            cwd=self.app, stdout=self.output, stderr=subprocess.STDOUT)
        self.wait(lambda: self.get("/api/update"))
        key = hashlib.sha256(str(self.app.resolve()).encode()).hexdigest()[:16]
        self.updates = data / "updates" / key

    def tearDown(self):
        info = installer.read_json(self.info)
        pid = info.get("pid")
        if pid and installer.pid_alive(pid):
            if os.name == "nt":
                subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True)
            else:
                os.kill(pid, signal.SIGINT)
                self.wait(lambda: not installer.pid_alive(pid), timeout=8)
        if self.process.poll() is None:
            self.process.terminate()
        self.process.wait(timeout=8)
        self.output.close()
        self.tmp.cleanup()

    def wait(self, check, timeout=20):
        deadline = time.monotonic() + timeout
        last = None
        while time.monotonic() < deadline:
            try:
                result = check()
                if result:
                    return result
            except (OSError, ValueError) as exc:
                last = exc
            time.sleep(.1)
        self.fail(f"timeout: {last}; log: {(Path(self.tmp.name) / 'app.log').read_text(encoding='utf-8')}")

    def get(self, path):
        base = installer.read_json(self.info).get("url", self.base).rstrip("/")
        with urllib.request.urlopen(base + path, timeout=2) as response:
            return json.load(response)

    def post(self, action):
        base = installer.read_json(self.info).get("url", self.base).rstrip("/")
        req = urllib.request.Request(base + "/api/update/" + action, data=b"{}", headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=5) as response:
            return json.load(response)

    def prepare(self, raw):
        stage = uuid.uuid4().hex
        folder = self.updates / "stages" / stage / "modules"
        folder.mkdir(parents=True)
        (folder / "hello.py").write_bytes(raw)
        files = {"modules/hello.py": entry(raw)}
        installer.atomic_json(self.updates / "catalog.json", {"revision": REVISION, "channel": "main"})
        installer.atomic_json(self.updates / "ready.json", {"id": stage, "revision": REVISION, "channel": "main",
            "files": files, "remove": [], "installed": {"app": str(self.app.resolve()), "revision": REVISION, "files": files}})

    def test_real_install_restart_and_manual_rollback(self):
        old = (self.app / "modules" / "hello.py").read_bytes()
        self.prepare(b'NAME="Hello updated"\nVERSION="2.0"\ndef setup(ctx): pass\n')
        self.post("install")
        self.process.wait(timeout=15)  # в том числе освобождаем PID родителя на POSIX
        self.wait(lambda: self.get("/api/update").get("phase") == "done")
        self.assertEqual(self.get("/api/update")["current"], REVISION)
        if os.name != "nt":
            self.assertEqual(installer.read_json(self.info)["url"].rstrip("/").replace("localhost", "127.0.0.1"), self.base)
        self.assertIn(b'VERSION="2.0"', (self.app / "modules" / "hello.py").read_bytes())
        self.assertTrue((self.app / "modules" / "custom.py").is_file())
        self.assertEqual((self.app / "YakumoData" / "disk" / "keep.txt").read_text(), "keep my files")
        self.assertIn("test-local-key", (self.app / "YakumoData" / "config" / "secrets.json").read_text())
        self.post("rollback")
        self.wait(lambda: self.get("/api/update").get("phase") == "done" and (self.app / "modules" / "hello.py").read_bytes() == old)
        self.assertFalse((self.app / installer.MARKER).exists())

    def test_real_bad_module_is_automatically_rolled_back(self):
        old = (self.app / "modules" / "hello.py").read_bytes()
        self.prepare(b'NAME="Bad"\ndef setup(ctx): raise RuntimeError("bad update")\n')
        self.post("install")
        self.process.wait(timeout=15)
        self.wait(lambda: self.get("/api/update").get("phase") == "rolled_back")
        self.assertEqual((self.app / "modules" / "hello.py").read_bytes(), old)
        self.assertTrue(all(not m["error"] for m in self.get("/api/modules")))


if __name__ == "__main__":
    unittest.main()
