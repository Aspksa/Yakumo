import json
import logging
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from yakumo.core.cloud import CloudService


class ApiKeyDiagnosticsTests(unittest.TestCase):
    def test_invalid_json_does_not_log_secret(self):
        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory) / "secrets.json"
            file.write_text('{"cloud_api_key": "SECRET-VALUE",', encoding="utf-8")
            cloud = CloudService(SimpleNamespace(), Path(directory) / "config.json", file)
            with self.assertLogs("yakumo.core.cloud", logging.WARNING) as captured:
                self.assertEqual(cloud.api_key(), "")
            self.assertNotIn("SECRET-VALUE", " ".join(captured.output))
            self.assertIn("JSON", " ".join(captured.output))

    def test_non_string_key_is_logged_without_value(self):
        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory) / "secrets.json"
            file.write_text(json.dumps({"cloud_api_key": ["SECRET-VALUE"]}), encoding="utf-8")
            cloud = CloudService(SimpleNamespace(), Path(directory) / "config.json", file)
            with self.assertLogs("yakumo.core.cloud", logging.WARNING) as captured:
                self.assertEqual(cloud.api_key(), "")
            self.assertNotIn("SECRET-VALUE", " ".join(captured.output))

    def test_missing_key_is_normal(self):
        with tempfile.TemporaryDirectory() as directory:
            cloud = CloudService(SimpleNamespace(), Path(directory) / "config.json",
                                 Path(directory) / "not-found.json")
            self.assertEqual(cloud.api_key(), "")


if __name__ == "__main__":
    unittest.main()
