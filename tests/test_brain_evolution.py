"""Tests for EvolutionLab sandbox and deterministic scoring."""
import tempfile
import unittest
from pathlib import Path

from modules.brain.evolution import EvolutionLab, score


class EvolutionTests(unittest.TestCase):
    def test_scoring(self):
        self.assertGreater(score("tokens", "красная машина", "большая красная машина"), 0.5)
        self.assertEqual(score("literal", "несуществующее", "текст"), 0.0)

    def test_runs_persist_without_application(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "evolution.json"
            lab = EvolutionLab(target)
            facts = [
                {"id": "a", "text": "красная машина стоит дома"},
                {"id": "b", "text": "синяя книга лежит рядом"},
                {"id": "c", "text": "зелёное дерево растет возле дома"},
            ]
            result = lab.compete(facts)
            self.assertFalse(result["applied"])
            self.assertEqual(len(result["candidates"]), 4)
            self.assertEqual(EvolutionLab(target).status()["total_generations"], 1)

    def test_reject_too_few_facts(self):
        with tempfile.TemporaryDirectory() as directory:
            lab = EvolutionLab(Path(directory) / "e.json")
            with self.assertRaises(ValueError):
                lab.compete([{"text": "one two three"}])


if __name__ == "__main__":
    unittest.main()
