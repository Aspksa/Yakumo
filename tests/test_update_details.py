import base64
import errno
import io
import json
import threading
import time
import unittest
import urllib.error
from email.message import Message
from types import SimpleNamespace
from unittest import mock

from modules.update import Updater
from modules.update import details, installer, source
from tests import test_update as fixtures

catalog, entry, zip_bytes, REVISION = fixtures.catalog, fixtures.entry, fixtures.zip_bytes, fixtures.REVISION


def request(**body):
    return SimpleNamespace(read_json=lambda: body)


def headers(**values):
    result = Message()
    for key, value in values.items():
        result[key.replace("_", "-")] = str(value)
    return result


class GitHubDetailsTest(unittest.TestCase):
    def test_release_description_keeps_tag_date_and_full_commit_message(self):
        files = {name: b"test" for name in source.REQUIRED}
        tree = {"tree": [{"path": p, "sha": i["git_sha"], "size": i["size"], "type": "blob", "mode": "100644"}
                         for p, i in catalog(files)["files"].items()]}
        commit = {"sha": REVISION, "commit": {"tree": {"sha": "b" * 40}, "message": "Заголовок\n\nПодробности",
                                             "committer": {"date": "2026-10-22T12:00:00Z"}}}
        client = source.GitHub()
        release = {"tag_name": "v1.2", "name": "Выпуск 1.2", "body": "Изменения выпуска\nВторая строка",
                   "published_at": "2026-10-22T12:30:00Z"}
        with mock.patch.object(client, "json", side_effect=[release, commit, tree]):
            result = client.resolve("release")
        self.assertEqual(result["version"], "v1.2")
        self.assertEqual(result["notes"], release["body"])
        self.assertEqual(result["notes_kind"], "release")
        self.assertEqual(result["published_at"], release["published_at"])
        with mock.patch.object(client, "json", side_effect=[commit, tree]):
            result = client.resolve("main")
        self.assertEqual(result["notes"], "Заголовок\n\nПодробности")
        self.assertEqual(result["version"], REVISION[:10])

    def test_comparison_is_pinned_bounded_and_preserves_multiline_notes(self):
        client = source.GitHub()
        commits = [{"sha": REVISION, "commit": {"message": "Первое\n\nПодробности"}} for _ in range(35)]
        with mock.patch.object(client, "json", return_value={"commits": commits, "total_commits": 35, "status": "ahead"}) as call:
            result = client.compare("b" * 40, REVISION)
        self.assertEqual(len(result["commits"]), 30)
        self.assertEqual(result["total"], 35)
        self.assertIn("b" * 40 + "..." + REVISION, call.call_args.args[0])
        self.assertIn("Подробности", result["commits"][0]["message"])

    def test_blob_is_verified_and_large_files_are_not_fetched(self):
        raw = "<script>пример</script>\n".encode()
        client = source.GitHub()
        info = entry(raw)
        with mock.patch.object(client, "json", return_value={"encoding": "base64", "content": base64.encodebytes(raw).decode()}):
            self.assertEqual(client.blob(info), raw)
            with self.assertRaisesRegex(ValueError, "Контрольная сумма"):
                client.blob({**info, "git_sha": "b" * 40})
        with mock.patch.object(client, "json") as call:
            with self.assertRaises(ValueError):
                client.blob({**info, "size": 65537})
            call.assert_not_called()

    def test_quota_is_observed_on_success_without_extra_requests(self):
        client = source.GitHub("fake-test-token")
        response = mock.Mock()
        response.geturl.return_value = source.API + "/commits/main"
        response.headers = headers(X_RateLimit_Limit=60, X_RateLimit_Remaining=57, X_RateLimit_Used=3, X_RateLimit_Reset=2000000000)
        observer = mock.Mock()
        client.on_rate_limit = observer
        with mock.patch.object(client.opener, "open", return_value=response) as call:
            self.assertIs(client.open("/commits/main"), response)
        self.assertEqual(call.call_count, 1)
        self.assertEqual(observer.call_args.args[0]["remaining"], 57)
        self.assertEqual(client.rate_limit["used"], 3)

    def test_rate_error_survives_and_prevents_another_request_until_reset(self):
        client = source.GitHub("fake-token")
        quota = headers(X_RateLimit_Limit=60, X_RateLimit_Remaining=0, X_RateLimit_Reset=2000000000)
        failure = urllib.error.HTTPError(source.API, 403, "Forbidden", quota, io.BytesIO(b"fake-token"))
        with mock.patch.object(client.opener, "open", side_effect=failure) as call:
            with self.assertRaises(installer.UpdateError) as exc:
                client.open("/commits/main")
            with self.assertRaises(installer.UpdateError):
                client.open("/commits/main")
        self.assertEqual(call.call_count, 1)
        info = installer.error_info(exc.exception)
        self.assertEqual(info["code"], "github_rate_limit")
        self.assertEqual(info["retry_at"], 2000000000)
        self.assertNotIn("fake-token", json.dumps(info))

    def test_secondary_limit_and_access_error_have_different_advice(self):
        client = source.GitHub()
        with mock.patch.object(client.opener, "open", side_effect=urllib.error.HTTPError(
                source.API, 429, "Too Many Requests", headers(Retry_After=120), io.BytesIO())):
            with self.assertRaises(installer.UpdateError) as exc:
                client.open("/commits/main")
        self.assertEqual(exc.exception.code, "github_rate_limit")
        self.assertGreaterEqual(exc.exception.retry_at, time.time() + 115)
        client = source.GitHub()
        with mock.patch.object(client.opener, "open", side_effect=urllib.error.HTTPError(
                source.API, 403, "Forbidden", headers(X_RateLimit_Remaining=50), io.BytesIO(b'{"message":"access denied"}'))):
            with self.assertRaises(installer.UpdateError) as exc:
                client.open("/commits/main")
        self.assertEqual(exc.exception.code, "github_access")

    def test_redirect_observes_api_quota_and_never_forwards_token(self):
        observe = mock.Mock()
        req = source.urllib.request.Request(source.API + "/zipball/" + REVISION, headers={"Authorization": "Bearer fake"})
        quota = headers(X_RateLimit_Remaining=12)
        result = source.GitHubRedirect(observe).redirect_request(req, None, 302, "Found", quota,
                    "https://codeload.github.com/Aspksa/Yakumo/legacy.zip/" + REVISION)
        observe.assert_called_once_with(quota)
        self.assertIsNone(result.get_header("Authorization"))


class DiffTest(unittest.TestCase):
    def test_added_removed_and_format_only_changes(self):
        result = details.file_diff("пример.py", b"old\n", b"new\n", 4, 4)
        self.assertTrue(any(line == {"kind": "remove", "text": "-old"} for line in result["lines"]))
        self.assertTrue(any(line == {"kind": "add", "text": "+new"} for line in result["lines"]))
        self.assertTrue(details.file_diff("new.txt", b"", b"new", 0, 3)["lines"])
        self.assertTrue(details.file_diff("old.txt", b"old", b"", 3, 0)["lines"])
        self.assertEqual(details.file_diff("a.bat", b"a\r\n", b"a\n", 3, 2)["reason"], "format")

    def test_binary_large_and_long_output_are_bounded(self):
        self.assertEqual(details.file_diff("x.png", b"a\0", b"b", 2, 1)["reason"], "binary")
        self.assertEqual(details.file_diff("x", None, b"", 100000, 0)["reason"], "large")
        before, after = ("a\n" * 1000).encode(), ("b\n" * 1000).encode()
        result = details.file_diff("x", before, after, len(before), len(after))
        self.assertTrue(result["truncated"])
        self.assertLessEqual(len(result["lines"]), 800)


class UpdaterDetailsTest(unittest.TestCase):
    setUp = fixtures.UpdaterTest.setUp
    tearDown = fixtures.UpdaterTest.tearDown

    def test_preview_uses_local_edits_and_verified_stage_and_blocks_unknown_paths(self):
        path = self.app / "yakumo" / "app.py"
        path.parent.mkdir()
        path.write_bytes(b"VALUE=1\n")
        self.updater._check()
        self.client.blob.side_effect = lambda expected: next(raw for raw in self.files.values() if entry(raw)["git_sha"] == expected["git_sha"])
        result = self.updater.diff(request(path="yakumo/app.py", revision=REVISION))
        self.assertIn({"kind": "remove", "text": "-VALUE=1"}, result["lines"])
        self.assertIn({"kind": "add", "text": "+VALUE=2"}, result["lines"])
        self.updater._prepare()
        self.client.blob.reset_mock()
        result = self.updater.diff(request(path="yakumo/new.py", revision=REVISION))
        self.assertIn({"kind": "add", "text": "+NEW=1"}, result["lines"])
        self.client.blob.assert_not_called()
        for name in ("../outside", "config/secrets.json", "yakumo/unknown.py"):
            with self.assertRaises(ValueError):
                self.updater.diff(request(path=name, revision=REVISION))
        with self.assertRaises(ValueError):
            self.updater.diff(request(path="yakumo/app.py", revision="b" * 40))
        self.assertFalse(self.updater._busy())

    def test_removed_file_diff_does_not_access_github(self):
        path = self.app / "old.txt"
        path.write_bytes(b"old text\n")
        installer.atomic_json(self.updater.root / "installed.json", {"app": str(self.app), "revision": "b" * 40,
                              "files": {"old.txt": entry(b"old text\n")}})
        self.updater._check()
        result = self.updater.diff(request(path="old.txt", revision=REVISION))
        self.assertIn({"kind": "remove", "text": "-old text"}, result["lines"])
        self.client.blob.assert_not_called()

    def test_file_list_is_paginated_and_state_remains_small(self):
        self.latest["files"].update({f"example-{n}.txt": entry(b"text") for n in range(100)})
        self.updater._check()
        first = self.updater.changes(request(revision=REVISION))
        second = self.updater.changes(request(revision=REVISION, offset=50))
        self.assertEqual(first["total"], 102)
        self.assertEqual(len(first["items"]), 50)
        self.assertTrue({x["path"] for x in first["items"]}.isdisjoint({x["path"] for x in second["items"]}))
        self.assertNotIn("items", self.updater.state()["changes"])

    def test_preparation_progress_has_bytes_speed_then_file_names(self):
        observations = []
        original = self.updater._set_progress

        def observe(*args, **kwargs):
            original(*args, **kwargs)
            observations.append(dict(self.updater.progress))

        def download(revision, destination, progress):
            raw = zip_bytes(self.files)
            destination.write_bytes(raw)
            progress(len(raw), len(raw))
            observations.append(dict(self.updater.progress))

        self.client.download.side_effect = download
        self.updater._check()
        with mock.patch.object(self.updater, "_set_progress", side_effect=observe):
            self.updater._prepare()
        downloaded = next(x for x in observations if x["unit"] == "bytes" and x["done"])
        self.assertGreater(downloaded["speed"], 0)
        self.assertEqual(downloaded["done"], downloaded["total"])
        self.assertEqual(self.updater.progress["done"], 2)
        self.assertEqual(self.updater.progress["unit"], "files")
        self.assertGreater(self.updater.state()["latest"]["archive_size"], 0)

    def test_history_survives_recreation_and_excludes_commands_and_file_contents(self):
        self.updater.root.joinpath("jobs", "1" * 32).mkdir(parents=True)
        installer.atomic_json(self.updater.root / "jobs" / ("1" * 32) / "job.json", {
            "app": str(self.app), "id": "1" * 32, "kind": "install", "phase": "done", "started": 10, "finished": 20,
            "from_version": {"revision": "b" * 40, "version": "v1"}, "to_version": {"revision": REVISION, "version": "v2"},
            "message": "Обновление установлено", "command": ["secret-command"], "files": {"secret-content": {}}})
        fresh = Updater(self.ctx, lambda _: self.client)
        result = fresh.history(request())
        self.assertEqual(result["items"][0]["from_version"]["version"], "v1")
        self.assertEqual(result["items"][0]["to_version"]["version"], "v2")
        self.assertNotIn("secret", json.dumps(result))
        self.assertEqual(result["next_offset"], 1)

    def test_legacy_installation_history_recovers_source_version_from_backup(self):
        job_id = "2" * 32
        installer.atomic_json(self.updater.root / "jobs" / job_id / "job.json", {
            "app": str(self.app), "id": job_id, "phase": "done", "installed": {"revision": REVISION, "files": {}}})
        installer.atomic_json(self.updater.root / "backups" / job_id / "backup.json", {"installed": {"revision": "b" * 40}})
        item = self.updater.history(request())["items"][0]
        self.assertEqual(item["from_version"]["revision"], "b" * 40)
        self.assertEqual(item["to_version"]["revision"], REVISION)

    def test_slow_preview_keeps_status_responsive_and_blocks_install_preparation(self):
        self.updater._check()
        entered, release = threading.Event(), threading.Event()

        def read_blob(expected):
            entered.set()
            release.wait(3)
            return self.files["yakumo/app.py"]

        self.client.blob.side_effect = read_blob
        results = []
        thread = threading.Thread(target=lambda: results.append(self.updater.diff(request(path="yakumo/app.py", revision=REVISION))))
        thread.start()
        try:
            self.assertTrue(entered.wait(1))
            started = time.monotonic()
            self.assertTrue(self.updater.state()["busy"])
            self.assertLess(time.monotonic() - started, .75)
            with self.assertRaises(ValueError):
                self.updater.prepare()
        finally:
            release.set()
            thread.join(3)
        self.assertEqual(results[0]["revision"], REVISION)

    def test_rate_cache_survives_restart_is_not_refetched_and_is_cleared_on_token_change(self):
        installer.atomic_json(self.updater.root / "github-limit.json", {"remaining": 45, "limit": 60})
        fresh = Updater(self.ctx, lambda _: self.client)
        self.assertEqual(fresh.state()["rate_limit"]["remaining"], 45)
        self.client.resolve.assert_not_called()
        fresh.save_token(request(token="fake-test-token"))
        self.assertEqual(fresh.state()["rate_limit"], {})

    def test_comparison_failure_preserves_successful_file_check(self):
        installer.atomic_json(self.updater.root / "installed.json", {"app": str(self.app), "revision": "b" * 40, "files": {}})
        self.client.compare.side_effect = installer.UpdateError("github_rate_limit", "Лимит исчерпан", "Подождите", 2000000000)
        self.updater._check()
        state = self.updater.state()
        self.assertTrue(state["available"])
        self.assertEqual(state["notes_warning"]["code"], "github_rate_limit")
        self.assertFalse(state["error"])

    def test_error_advice_masks_token_and_distinguishes_file_and_disk_errors(self):
        self.updater.save_token(request(token="fake-test-token"))
        self.assertNotIn("fake-test-token", json.dumps(self.updater._error(ValueError("Ошибка fake-test-token"))))
        self.assertEqual(installer.error_info(PermissionError("file locked"))["code"], "file_access")
        self.assertEqual(installer.error_info(OSError(errno.ENOSPC, "disk full"))["code"], "disk_full")
        self.assertNotIn("private-body", json.dumps(installer.error_info(RuntimeError("private-body"))))


if __name__ == "__main__":
    unittest.main()
