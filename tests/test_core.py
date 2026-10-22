import socket
import tempfile
import unittest
from pathlib import Path

from yakumo.core import network, storage
from yakumo.core.config import Config
from yakumo.core.paths import build_paths


class StorageTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_explicit_dir(self):
        choice = storage.choose_storage(self.base / "data")
        self.assertEqual(choice.data_root, (self.base / "data").resolve())
        self.assertEqual(choice.reason, "задан явно")

    def test_portable_marker(self):
        (self.base / storage.PORTABLE_MARKER).touch()
        choice = storage.choose_storage(base=self.base, min_free=0, media=[])
        self.assertEqual(choice.data_root, self.base.resolve() / storage.DATA_DIR_NAME)

    def test_prefers_non_system_medium_with_most_space(self):
        small = storage.Medium(self.base / "a", free=10, total=100)
        big = storage.Medium(self.base / "b", free=50, total=100)
        media = sorted([small, big], key=lambda m: (m.system, -m.free))
        choice = storage.choose_storage(base=self.base / "app", min_free=20, media=media)
        self.assertEqual(choice.data_root, self.base / "b" / storage.DATA_DIR_NAME)

    def test_skips_media_without_space(self):
        tiny = storage.Medium(self.base / "a", free=1, total=100)
        choice = storage.choose_storage(base=self.base / "app", min_free=20, media=[tiny])
        self.assertEqual(choice.reason, "резервный вариант")

    def test_list_media_not_empty(self):
        self.assertTrue(storage.list_media())


class PathsAndConfigTest(unittest.TestCase):
    def test_paths_and_config_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            choice = storage.choose_storage(tmp)
            paths = build_paths(choice).ensure()
            self.assertTrue(paths.logs.is_dir())
            self.assertTrue(paths.workspace.is_dir())
            Config(port=9000, lan=True).save(paths.config_file)
            loaded = Config.load(paths.config_file)
            self.assertEqual((loaded.port, loaded.lan), (9000, True))


class NetworkTest(unittest.TestCase):
    def test_busy_port_is_skipped(self):
        with socket.socket() as busy:
            busy.bind(("127.0.0.1", 0))
            busy.listen()
            port = busy.getsockname()[1]
            self.assertFalse(network.is_port_free("127.0.0.1", port))
            self.assertNotEqual(network.find_free_port("127.0.0.1", port), port)

    def test_choose_endpoint_default_localhost(self):
        ep = network.choose_endpoint()
        self.assertEqual(ep.host, "127.0.0.1")
        self.assertTrue(network.is_port_free(ep.host, ep.port))
        self.assertTrue(ep.url.startswith("http://localhost:"))

    def test_unknown_host_falls_back(self):
        ep = network.choose_endpoint(host="203.0.113.7")
        self.assertEqual(ep.host, "127.0.0.1")


if __name__ == "__main__":
    unittest.main()
