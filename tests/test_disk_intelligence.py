"""Regression tests for local smart-search intelligence."""
import json
import sqlite3
import threading
import unittest
from modules.disk.intelligence import Intelligence, dates


class IntelligenceTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:", check_same_thread=False)
        self.db.execute("CREATE TABLE files(path TEXT PRIMARY KEY)")
        self.lock = threading.Lock()
        self.engine = Intelligence(self.db, self.lock)

    def add(self, path, text, photo="", ocr=""):
        self.db.execute("INSERT INTO files(path) VALUES(?)", (path,))
        self.engine.update(path, text, photo, ocr)

    def tearDown(self):
        self.db.close()

    def test_invalid_dates_are_ignored(self):
        self.assertEqual(dates("31.02.2026, 15.09.2026"), ["2026-09-15"])

    def test_links_and_timeline_are_local(self):
        self.add("гараж/счет.pdf", "Toyota Hilux 15.09.2026 дизель")
        self.add("гараж/чек.pdf", "Toyota Hilux 15.09.2026 топливо")
        links = self.engine.links("гараж/счет.pdf")
        self.assertEqual(links[0]["path"], "гараж/чек.pdf")
        self.assertFalse(links[0]["verified"])
        self.assertEqual(len(self.engine.timeline()), 2)
        self.assertEqual(self.engine.discoveries()[0]["confidence"], "hypothesis")
        self.assertEqual(self.engine.status()["cloud_requests"], 0)

    def test_rename_and_cleanup(self):
        self.add("old/чек.pdf", "ГСМ 10.10.2026")
        self.engine.rename("old", "new")
        self.assertEqual(self.engine.snapshot()[0]["path"], "new/чек.pdf")
        self.db.execute("DELETE FROM files")
        self.engine.remove_missing()
        self.assertEqual(self.engine.snapshot(), [])

    def test_existing_index_database_preserved(self):
        # Legacy files table must remain untouched during metadata initialization.
        self.add("old/файл.txt", "дата 12.10.2026")
        before = self.db.execute("SELECT path FROM files").fetchall()
        again = Intelligence(self.db, self.lock)
        self.assertEqual(again.status()["indexed"], 1)
        self.assertEqual(self.db.execute("SELECT path FROM files").fetchall(), before)

    def test_concurrent_writes_and_reads(self):
        import concurrent.futures
        self.db.execute("PRAGMA busy_timeout=1000")
        self.db.execute("DELETE FROM files")
        self.db.commit()
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
            futures = [pool.submit(self.engine.update, f"folder/{i}.pdf", f"Toyota 15.09.2026 {i}")
                       for i in range(30)]
            futures += [pool.submit(self.engine.snapshot, 50) for _ in range(10)]
            for task in futures:
                task.result()
        self.assertEqual(self.engine.status()["indexed"], 30)

    def test_metadata_does_not_include_raw_document_text(self):
        self.add("акт.txt", "Секретно 01.10.2026")
        rows = self.engine.snapshot()
        self.assertNotIn("text", rows[0])
        self.assertEqual(rows[0]["modality"], "document")


if __name__ == "__main__":
    unittest.main()
