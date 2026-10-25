import unittest
from modules.disk.entities import extract_entities, candidate_relationships, timeline


class EntityTests(unittest.TestCase):
    def test_document_date_is_not_claimed_event_date(self):
        r = extract_entities("путевой лист.txt", "Дата 15.09.2026, автомобиль Н954МУ125")
        self.assertEqual(r["document_dates"], ["2026-09-15"])
        self.assertEqual(r["event_dates"], [])
        self.assertEqual(r["kind"], "waybill")
        self.assertTrue(r["uncertain"])

    def test_vehicle_relationship_requires_two_sources(self):
        a = extract_entities("путевой лист.txt", "Н954МУ125 15.09.2026")
        b = extract_entities("чек.txt", "Н954МУ125 15.09.2026")
        links = candidate_relationships([a, b])
        self.assertEqual(len(links), 1)
        self.assertEqual(links[0]["relation"], "mentioned_in_both")
        self.assertFalse(links[0]["verified"])
        self.assertEqual(len(timeline([a, b])), 2)

    def test_invalid_dates(self):
        r = extract_entities("отчет.txt", "Дата 31.02.2026")
        self.assertEqual(r["document_dates"], [])


if __name__ == "__main__":
    unittest.main()
