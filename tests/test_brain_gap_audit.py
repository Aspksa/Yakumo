"""Tests for Cloud.ru gap audit privacy, deduplication and failure semantics."""
import unittest
from types import SimpleNamespace
from modules.brain.improve import Improvements


class FakeMemory:
    def __init__(self):
        self.items = []
        self.data = {"meta": {}, "improvements": self.items}
    def improvement(self, value):
        if any(x["key"] == value["key"] for x in self.items):
            return None
        self.items.append(value)
        return value
    def save(self):
        pass


class FakeMind:
    def __init__(self, reply):
        self.reply = reply
        self.prompt = ""
    def can_think(self):
        return True
    def thought(self, *_):
        return "test"
    def finish(self, *_):
        pass
    def complete(self, messages, **_):
        self.prompt = messages[0]["content"]
        return self.reply


class FakeCode:
    def search(self, _query, _limit):
        return [{"path": "yakumo/worker.py", "start": 10, "end": 12,
                 "text": "password = 'test-secret'\nif retry: pass\n"}]


class AuditTests(unittest.TestCase):
    def test_adds_unverified_suggestion_and_redacts(self):
        m = FakeMemory()
        mind = FakeMind('{"ideas":[{"title":"Очередь повторов","problem":"Нужны повторы",'
                        '"want":"Тест 503","module":"Ядро","priority":"high",'
                        '"evidence":"yakumo/worker.py:11"}]}')
        improve = Improvements(m, mind, lambda: "ru", code=FakeCode())
        self.assertEqual(improve.audit_gaps(force=True), 1)
        self.assertEqual(improve.audit_gaps(force=True), 0)
        self.assertNotIn("test-secret", mind.prompt)
        self.assertIn("не проверено", m.items[0]["detail"])
        self.assertEqual(m.data["meta"]["last_gap_audit"], __import__("datetime").date.today().isoformat())
        m.items[0]["status"] = "done"
        self.assertEqual(improve.audit_gaps(force=True), 0)
        self.assertEqual(m.items[0]["status"], "done")


if __name__ == "__main__":
    unittest.main()
