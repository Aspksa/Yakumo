import unittest
from modules.disk.ranking import HybridRanker, metrics, promote


class SearchLabTests(unittest.TestCase):
    def test_local_search_works_offline(self):
        r = HybridRanker()
        r.replace({"a.pdf": "заправка дизель топливо Hilux", "b.pdf": "аренда квартиры"})
        self.assertEqual(r.search("дизель")[0].path, "a.pdf")

    def test_semantic_fallback_on_failure(self):
        r = HybridRanker()
        r.replace({"a": "договор аренды", "b": "автомобиль"})
        r.set_vectors("v1", {"a": [1, 0], "b": [0, 1]})
        found = r.search("аренды", embed=lambda *_: (_ for _ in ()).throw(TimeoutError()))
        self.assertEqual(found[0].path, "a")

    def test_dimension_guard(self):
        r = HybridRanker()
        r.replace({"a": "один", "b": "два"})
        with self.assertRaises(ValueError):
            r.set_vectors("v1", {"a": [1], "b": [1, 2]})

    def test_metrics(self):
        r = metrics({"q": ["a", "b"]}, {"q": {"a"}}, k=2)
        self.assertAlmostEqual(r["recall_at_k"], 1)
        self.assertAlmostEqual(r["ndcg_at_k"], 1)

    def test_never_promote_on_single_query(self):
        a = {"queries": 1, "recall_at_k": 1., "ndcg_at_k": .5,
             "latency_ms_per_query": 5., "cost": 0.}
        b = {**a, "ndcg_at_k": 1.}
        self.assertFalse(promote(a, b))


if __name__ == "__main__":
    unittest.main()
