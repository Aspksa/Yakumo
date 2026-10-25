import unittest
from modules.brain.audit import summary


class BrainFullAuditTests(unittest.TestCase):
    def test_all_nine_areas_and_issues(self):
        data = {"facts": [{"about": ["missing"]}], "entities": [],
                "talks": [], "promises": [{"done": False}],
                "events": [], "skills": [], "versions": [],
                "thoughts": [{"status": "failed"}],
                "improvements": [{"status": "new"}]}
        report = summary(data, branches={"branches": [{"id": "logic", "xp": 0}]})
        self.assertEqual(len(report["areas"]), 9)
        self.assertEqual(report["areas"]["Карта"]["orphan_references"], 1)
        self.assertTrue(report["read_only"])
        codes = {x["code"] for x in report["issues"]}
        self.assertIn("orphan_entities", codes)
        self.assertIn("failed_thoughts", codes)
        self.assertIn("branches_without_experience", codes)
        self.assertNotIn("missing", str(report))

    def test_empty_safe(self):
        result = summary({})
        self.assertEqual(len(result["areas"]), 9)
        self.assertEqual(result["issues"], [])


if __name__ == "__main__":
    unittest.main()
