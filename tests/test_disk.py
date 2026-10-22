import io
import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path
from types import SimpleNamespace

from yakumo.core.modules import Context, load_all
from yakumo.web.server import create_server

MODULES = Path(__file__).resolve().parents[1] / "modules"


class DiskTest(unittest.TestCase):
    """Модуль «Диск» через настоящий веб-сервер, как его видит браузер."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        paths = SimpleNamespace(app=base / "Программа", data=base / "Программа" / "YakumoData", workspace=base)
        paths.app.mkdir()
        ctx = Context(paths=paths, config=SimpleNamespace(lan=False))
        infos = load_all(ctx, [MODULES])
        self.assertTrue(all(i.error is None for i in infos), [i.error for i in infos])
        self.root = paths.data / "disk"  # портативный режим: данные рядом с программой
        self.server = create_server("127.0.0.1", 0, base, ctx.routes)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.tmp.cleanup()

    def call(self, url_path, data=None, headers=None, method=None, **params):
        url = self.base + url_path + ("?" + urllib.parse.urlencode(params) if params else "")
        body = data
        hdrs = dict(headers or {})
        if isinstance(data, (dict, list)):
            body = json.dumps(data).encode("utf-8")
            hdrs["Content-Type"] = "application/json"
        req = urllib.request.Request(url, data=body, headers=hdrs, method=method)
        try:
            with urllib.request.urlopen(req) as r:
                return r.status, dict(r.headers), r.read()
        except urllib.error.HTTPError as e:
            return e.code, dict(e.headers), e.read()

    def json(self, url_path, data=None, **params):
        code, _, body = self.call(url_path, data, **params)
        self.assertEqual(code, 200, body.decode("utf-8", "replace"))
        return json.loads(body)

    def upload(self, rel, content: bytes):
        return self.call("/api/disk/upload", content, path=rel,
                         headers={"X-Yakumo": "1", "Content-Type": "application/octet-stream"}, method="POST")

    def names(self, path=""):
        return sorted(i["name"] for i in self.json("/api/disk/list", path=path)["items"])

    def test_favorites_recent_and_space(self):
        import os
        import time
        self.upload("Документы/отчёт.docx", b"A" * 5000)
        self.upload("Документы/копия отчёта.docx", b"A" * 5000)
        self.upload("Фото/большое.jpg", b"B" * 9000)
        self.upload("заметка.txt", b"hi")
        os.utime(self.root / "Фото" / "большое.jpg", (time.time() - 3600, time.time() - 3600))
        self.json("/api/disk/favorite", {"paths": ["Документы/отчёт.docx", "Фото"]})
        stars = {i["path"] for i in self.json("/api/disk/favorites")}
        self.assertEqual(stars, {"Документы/отчёт.docx", "Фото"})
        self.assertTrue(next(i for i in self.json("/api/disk/list", path="")["items"] if i["name"] == "Фото")["star"])
        # Избранное едет вслед за переименованием.
        self.json("/api/disk/rename", {"path": "Документы", "name": "Бумаги"})
        self.assertIn("Бумаги/отчёт.docx", {i["path"] for i in self.json("/api/disk/favorites")})
        self.json("/api/disk/favorite", {"paths": ["Фото"], "on": False})
        self.assertEqual([i["path"] for i in self.json("/api/disk/favorites")], ["Бумаги/отчёт.docx"])
        recent = [i["path"] for i in self.json("/api/disk/recent")]
        self.assertEqual(recent[-1], "Фото/большое.jpg")  # самое старое — в конце
        space = self.json("/api/disk/space")
        self.assertEqual(space["largest"][0]["path"], "Фото/большое.jpg")
        dup, = space["duplicates"]
        self.assertEqual(({f["name"] for f in dup["files"]}, dup["wasted"]), ({"отчёт.docx", "копия отчёта.docx"}, 5000))
        self.assertNotIn(".yakumo", json.dumps(space, ensure_ascii=False))

    def test_upload_list_download_russian(self):
        code, _, body = self.upload("Фото/Море 2024/закат.jpg", b"0123456789")
        self.assertEqual(code, 200, body)
        self.assertEqual(json.loads(body)["path"], "Фото/Море 2024/закат.jpg")
        self.assertTrue((self.root / "Фото" / "Море 2024" / "закат.jpg").is_file())
        self.assertEqual(self.names(), ["Фото"])
        item, = self.json("/api/disk/list", path="Фото/Море 2024")["items"]
        self.assertEqual((item["kind"], item["size"]), ("image", 10))
        # Тот же файл ещё раз — рядом появляется копия, старый не затирается.
        self.upload("Фото/Море 2024/закат.jpg", b"x")
        self.assertEqual(self.names("Фото/Море 2024"), ["закат (2).jpg", "закат.jpg"])

        code, headers, body = self.call("/api/disk/file", path="Фото/Море 2024/закат.jpg", download="1")
        self.assertEqual((code, body), (200, b"0123456789"))
        self.assertIn("filename*=UTF-8''%D0%B7%D0%B0%D0%BA%D0%B0%D1%82.jpg", headers["Content-Disposition"])
        code, headers, body = self.call("/api/disk/file", path="Фото/Море 2024/закат.jpg",
                                        headers={"Range": "bytes=2-5"})
        self.assertEqual((code, body, headers["Content-Range"]), (206, b"2345", "bytes 2-5/10"))
        code, _, body = self.call("/api/disk/file", path="Фото/Море 2024/закат.jpg", headers={"Range": "bytes=-3"})
        self.assertEqual((code, body), (206, b"789"))

    def test_upload_needs_own_header_and_safe_names(self):
        code, _, _ = self.call("/api/disk/upload", b"x", path="a.txt",
                               headers={"Content-Type": "application/octet-stream"}, method="POST")
        self.assertEqual(code, 403)  # чужой сайт не может загрузить файл
        for bad in ("../наружу.txt", "a/CON.txt", "что?.txt", ".yakumo/trash.json"):
            code, _, _ = self.upload(bad, b"x")
            self.assertEqual(code, 400, bad)
        self.assertEqual(self.call("/api/disk/file", path="../../etc/passwd")[0], 400)
        self.assertEqual(self.call("/api/disk/file", path="нет.txt")[0], 404)

    def test_folders_rename_move_copy(self):
        self.json("/api/disk/mkdir", {"path": "", "name": "Документы"})
        self.json("/api/disk/mkdir", {"path": "", "name": "Архив"})
        code, _, body = self.call("/api/disk/mkdir", {"path": "", "name": "Документы"})
        self.assertEqual(code, 400)
        self.assertIn("уже есть", json.loads(body)["error"])
        self.upload("Документы/отчёт.docx", b"doc")
        self.json("/api/disk/rename", {"path": "Документы/отчёт.docx", "name": "Отчёт за май.docx"})
        self.assertEqual(self.names("Документы"), ["Отчёт за май.docx"])
        self.json("/api/disk/copy", {"paths": ["Документы/Отчёт за май.docx"], "to": "Архив"})
        self.json("/api/disk/move", {"paths": ["Документы"], "to": "Архив"})
        self.assertEqual(self.names(), ["Архив"])
        self.assertEqual(self.names("Архив"), ["Документы", "Отчёт за май.docx"])
        code, _, _ = self.call("/api/disk/move", {"paths": ["Архив"], "to": "Архив/Документы"})
        self.assertEqual(code, 400)  # папку в саму себя нельзя
        found = self.json("/api/disk/search", q="ОТЧЁТ")["items"]
        self.assertEqual(sorted(i["path"] for i in found),
                         ["Архив/Документы/Отчёт за май.docx", "Архив/Отчёт за май.docx"])

    def test_trash_restore_purge(self):
        self.upload("Папка/один.txt", b"1")
        self.upload("два.txt", b"22")
        self.assertEqual(self.json("/api/disk/delete", {"paths": ["Папка", "два.txt"]})["count"], 2)
        self.assertEqual(self.names(), [])
        trash = self.json("/api/disk/trash")
        self.assertEqual(sorted(i["name"] for i in trash), ["Папка", "два.txt"])
        info = self.json("/api/disk/info")
        self.assertEqual((info["used"], info["trash"]), (0, 3))
        papka = next(i for i in trash if i["name"] == "Папка")
        self.json("/api/disk/restore", {"ids": [papka["id"]]})
        self.assertEqual(self.names("Папка"), ["один.txt"])
        self.assertEqual(self.call("/api/disk/purge", {})[0], 400)  # без явного «всё» ничего не стираем
        self.assertEqual(self.json("/api/disk/purge", {"all": True})["count"], 1)
        self.assertEqual(self.json("/api/disk/trash"), [])

    def test_share_link_survives_rename(self):
        self.upload("Музыка/песня.mp3", b"la-la")
        token = self.json("/api/disk/share", {"path": "Музыка"})["token"]
        self.json("/api/disk/rename", {"path": "Музыка", "name": "Песни"})
        code, headers, body = self.call("/api/disk/s", t=token)
        self.assertEqual(code, 200)
        self.assertIn("песня.mp3", body.decode("utf-8"))
        self.assertEqual(self.call("/api/disk/s", t=token, p="песня.mp3")[2], b"la-la")
        self.assertEqual(self.call("/api/disk/s", t=token, p="../../x")[0], 400)
        code, headers, body = self.call("/api/disk/s", t=token, zip="1")
        with zipfile.ZipFile(io.BytesIO(body)) as zf:
            self.assertEqual(zf.read("Песни/песня.mp3"), b"la-la")
        self.assertEqual(self.json("/api/disk/shares")[0]["path"], "Песни")
        self.json("/api/disk/unshare", {"token": token})
        self.assertEqual(self.call("/api/disk/s", t=token)[0], 404)

    def test_html_is_not_run_as_page(self):
        self.upload("страница.html", b"<script>alert(1)</script>")
        _, headers, _ = self.call("/api/disk/file", path="страница.html")
        self.assertTrue(headers["Content-Type"].startswith("text/plain"))
        self.upload("рисунок.svg", b"<svg/>")
        _, headers, _ = self.call("/api/disk/file", path="рисунок.svg")
        self.assertEqual(headers["Content-Security-Policy"], "sandbox")


if __name__ == "__main__":
    unittest.main()
