"""Provenance journal does not infer causation and retains verified IDs."""
import tempfile
import unittest
from pathlib import Path
from modules.brain.provenance import ProvenanceJournal, identifiers

def records(*ids):
    return {"facts":[{"id":i,"text":"item"} for i in ids],"skills":[{"id":"skill1"}],
            "mind":{"thoughts":[{"id":"thought1","status":"queued"}]}}

class ProvenanceTests(unittest.TestCase):
    def test_snapshot_and_created_events(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"journal.json"
            lab=ProvenanceJournal(path)
            self.assertFalse(lab.observe(records("one"))["events"])
            state=lab.observe(records("one","two"))
            self.assertEqual(len(state["events"]),1)
            self.assertEqual(state["events"][0]["source_id"],"memory:two")
            self.assertFalse(state["links"])
            self.assertEqual(len(ProvenanceJournal(path).snapshot()["events"]),1)

    def test_links_require_existing_ids_and_explicit_relation(self):
        with tempfile.TemporaryDirectory() as tmp:
            lab=ProvenanceJournal(Path(tmp)/"journal.json")
            data=records("one")
            with self.assertRaises(ValueError):
                lab.link("mind:thought1","skill:not-exists","derived_from",data)
            with self.assertRaises(ValueError):
                lab.link("mind:thought1","skill:skill1","pretends_to_cause",data)
            out=lab.link("mind:thought1","skill:skill1","related_to",data)
            self.assertEqual(out["links"][0]["origin"],"explicit")
            self.assertEqual(len(lab.link("mind:thought1","skill:skill1","related_to",data)["links"]),1)

if __name__=="__main__":
    unittest.main()
