import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

from modules.disk import store
from tools import build_portable
from yakumo.core.config import Config


class TrashRecoveryTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.disk = store.Disk(Path(self.tmp.name) / "disk")
        for name in ("first.txt", "second.txt"):
            self.disk.upload(name, io.BytesIO(name.encode()), len(name))

    def tearDown(self):
        self.tmp.cleanup()

    def test_missing_item_is_rejected_before_any_file_moves(self):
        with self.assertRaises(FileNotFoundError):
            self.disk.delete(["first.txt", "missing.txt"])
        self.assertTrue(self.disk.path("first.txt").is_file())
        self.assertEqual(self.disk.trash(), [])

    def test_later_move_failure_preserves_completed_items_for_restore(self):
        original_move = store.shutil.move

        def fail_second(src, dst):
            if Path(src).name == "second.txt":
                raise PermissionError("file is busy")
            return original_move(src, dst)

        with mock.patch.object(store.shutil, "move", side_effect=fail_second):
            with self.assertRaises(PermissionError):
                self.disk.delete(["first.txt", "second.txt"])
        self.assertTrue(self.disk.path("second.txt").is_file())
        trash = self.disk.trash()
        self.assertEqual([e["name"] for e in trash], ["first.txt"])
        restarted = store.Disk(self.disk.root)
        restarted.restore([trash[0]["id"]])
        self.assertEqual(restarted.path("first.txt").read_bytes(), b"first.txt")

    def test_journal_failure_leaves_source_untouched(self):
        with mock.patch.object(store, "_write_json", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                self.disk.delete(["first.txt"])
        self.assertTrue(self.disk.path("first.txt").is_file())
        self.assertEqual(self.disk.trash(), [])

    def test_record_exists_before_file_moves(self):
        original_move = store.shutil.move

        def inspect_journal(src, dst):
            index = json.loads((self.disk.meta / "trash.json").read_text(encoding="utf-8"))
            self.assertIn(Path(dst).parent.name, index)
            return original_move(src, dst)

        with mock.patch.object(store.shutil, "move", side_effect=inspect_journal):
            self.disk.delete(["first.txt"])
        self.assertEqual(len(self.disk.trash()), 1)

    def test_failure_after_move_still_keeps_restore_record(self):
        with mock.patch.object(self.disk, "_unlink_shares", side_effect=OSError("metadata failure")):
            with self.assertRaises(OSError):
                self.disk.delete(["first.txt"])
        trash = self.disk.trash()
        self.assertEqual([e["name"] for e in trash], ["first.txt"])
        self.disk.restore([trash[0]["id"]])
        self.assertTrue(self.disk.path("first.txt").is_file())


class ConfigRecoveryTest(unittest.TestCase):
    def test_non_object_and_broken_json_use_defaults(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "yakumo.json"
            for value in ("[]", "null", "42", '"string"', "true", "{broken"):
                with self.subTest(value=value):
                    path.write_text(value, encoding="utf-8")
                    self.assertEqual(Config.load(path), Config())

    def test_bad_fields_fall_back_without_losing_good_settings(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "yakumo.json"
            path.write_text(json.dumps({"language": "en", "port": "bad", "host": [], "workspace": 42,
                "lan": "yes", "disabled_modules": {}, "cloud_model": [], "cloud_url": {},
                "avatar_effects": [["bad"], {}, "sparkles", "sparkles"]}), encoding="utf-8")
            loaded = Config.load(path)
            self.assertEqual(loaded, Config(language="en", avatar_effects=["sparkles"]))
        with self.assertRaises(ValueError):
            Config().update({"avatar_effects": [["bad"]]})


class PortableTest(unittest.TestCase):
    def test_archive_contains_the_autostart_entry_script(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in ("Yakumo.bat", "Yakumo.pyw"):
                (root / name).write_text("entry point", encoding="utf-8")
            python_zip = root / "embedded-python.zip"
            with zipfile.ZipFile(python_zip, "w") as archive:
                archive.writestr("python312._pth", "python312.zip\n.\n")
            with mock.patch.object(build_portable, "ROOT", root), \
                    mock.patch.object(build_portable, "download", return_value=python_zip):
                result = build_portable.build("3.12.10", "amd64", root / "dist", False)
            with zipfile.ZipFile(result) as archive:
                self.assertEqual(archive.read("Yakumo/Yakumo.pyw"), b"entry point")
                self.assertIn("Yakumo/Yakumo.bat", archive.namelist())


if __name__ == "__main__":
    unittest.main()
