import sqlite3
import threading
import unittest

from modules.disk.semantic_disk import SemanticDisk


class FakeCloud:
    models = ["BAAI/bge-m3"]
    def api_key(self):
        return "test-token"
    def model_kind(self, model):
        return "embedding"
    def embedding_model(self):
        return "BAAI/bge-m3"
    def embed(self, strings, model, timeout=30):
        return [[1.0, 0.0] if "аренда" in x else [0.0, 1.0] for x in strings]


class SemanticDiskTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:", check_same_thread=False)
        self.lock = threading.Lock()
        self.db.execute("CREATE TABLE files(path TEXT PRIMARY KEY,text TEXT,ocr TEXT,photo TEXT)")
        self.db.execute("INSERT INTO files VALUES('договор.txt','аренда помещения','','')")
        self.db.commit()
        self.search = SemanticDisk(self.db, self.lock, FakeCloud())

    def tearDown(self):
        self.db.close()

    def test_manual_index_and_semantic_search(self):
        self.assertEqual(self.search.status()["vectors"], 0)
        self.assertEqual(self.search.refresh()["processed"], 1)
        self.assertEqual(self.search.search("аренда")[0]["path"], "договор.txt")

    def test_rename(self):
        self.search.refresh()
        self.search.rename("договор.txt", "новый.txt")
        self.assertEqual(self.db.execute("SELECT path FROM disk_vectors").fetchone()[0], "новый.txt")

    def test_embedding_failure_uses_empty_result(self):
        self.search.refresh()
        self.search.cloud.embed = lambda *a, **k: (_ for _ in ()).throw(TimeoutError())
        self.assertEqual(self.search.search("аренда"), [])


if __name__ == "__main__":
    unittest.main()
