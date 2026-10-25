import unittest
from modules.disk.entities import extract_entities, candidate_relationships, timeline, work_candidates


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


    def test_work_candidates_are_unverified_and_evidence_based(self):
        r = extract_entities("путевой лист 01.txt",
                             "Водитель: Иванов Иван Иванович, автомобиль Н954МУ125. ДТ 45,5 л, 3 200 руб. 15.09.2026")
        self.assertEqual(r["drivers"], ["Иванов Иван Иванович"])
        self.assertTrue(r["fuel"])
        self.assertEqual(r["liters"], [45.5])
        self.assertEqual(r["amounts"], [3200.0])
        grouped = extract_entities("заправка.txt", "ДТ 1 250,5 л")
        self.assertEqual(grouped["liters"], [1250.5])
        items = work_candidates([r])
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["vehicle"], "Н954МУ125")
        self.assertEqual(items[0]["driver"], "Иванов Иван Иванович")
        self.assertFalse(items[0]["verified"])
        self.assertEqual(items[0]["action"], "review_before_import")


if __name__ == "__main__":
    unittest.main()
