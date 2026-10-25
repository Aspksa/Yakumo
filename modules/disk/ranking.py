"""Search lab: local BM25, optional semantic vectors and reproducible evaluation.

No cloud calls are made by this module. Callers may provide a consent-gated
embedding function; a failed embedding must never break lexical search.
"""
from __future__ import annotations

import math
import re
import time
from collections import Counter
from dataclasses import dataclass
from typing import Callable

TOKEN = re.compile(r"[^\W_]+", re.UNICODE)


def tokenize(text: str) -> list[str]:
    return [x.lower() for x in TOKEN.findall(text) if len(x) > 1]


@dataclass(frozen=True)
class Hit:
    path: str
    score: float
    source: str


class HybridRanker:
    def __init__(self, *, k1: float = 1.5, b: float = .75):
        self.k1, self.b = k1, b
        self.corpus: dict[str, Counter] = {}
        self.lengths: dict[str, int] = {}
        self.df: Counter = Counter()
        self.vectors: dict[str, tuple[float, ...]] = {}
        self.vector_model: str | None = None

    def replace(self, docs: dict[str, str]) -> None:
        self.corpus = {p: Counter(tokenize(t[:500_000])) for p, t in docs.items()}
        self.lengths = {p: sum(v.values()) for p, v in self.corpus.items()}
        self.df = Counter(w for c in self.corpus.values() for w in c)
        self.vectors.clear()
        self.vector_model = None

    def bm25(self, query: str, limit: int = 30) -> list[Hit]:
        words = set(tokenize(query))
        n = len(self.corpus)
        if not n or not words:
            return []
        avg = sum(self.lengths.values()) / n or 1
        result = []
        for path, counts in self.corpus.items():
            dl = self.lengths[path]
            score = 0.0
            for w in words:
                tf = counts.get(w, 0)
                if not tf:
                    continue
                idf = math.log(1 + (n - self.df[w] + .5) / (self.df[w] + .5))
                score += idf * (tf * (self.k1 + 1)) / (tf + self.k1 * (1 - self.b + self.b * dl / avg))
            if score > 0:
                result.append(Hit(path, round(score, 6), "bm25"))
        return sorted(result, key=lambda h: (-h.score, h.path))[:limit]

    def set_vectors(self, model: str, vectors: dict[str, list[float]]) -> None:
        # No silent comparison across embedding model versions/dimensions.
        if not model or not vectors:
            self.vectors, self.vector_model = {}, None
            return
        dimensions = {len(v) for v in vectors.values()}
        if len(dimensions) != 1 or 0 in dimensions:
            raise ValueError("inconsistent vector dimensions")
        self.vectors = {p: normalize(v) for p, v in vectors.items() if p in self.corpus}
        self.vector_model = model

    def search(self, query: str, *, embed: Callable[[str, str], list[float]] | None = None,
               limit: int = 30) -> list[Hit]:
        lexical = self.bm25(query, limit * 3)
        if not (embed and self.vector_model and self.vectors):
            return lexical[:limit]
        try:
            v = normalize(embed(query, self.vector_model))
            if any(len(x) != len(v) for x in self.vectors.values()):
                raise ValueError("embedding dimensions differ")
            semantic = sorted(((p, sum(a*b for a, b in zip(v, vec)))
                               for p, vec in self.vectors.items()),
                              key=lambda r: (-r[1], r[0]))[:limit * 3]
        except (OSError, RuntimeError, ValueError, TimeoutError):
            return lexical[:limit]
        fused: dict[str, float] = {}
        for hits in ([h.path for h in lexical], [p for p, _ in semantic]):
            for rank, p in enumerate(hits, 1):
                fused[p] = fused.get(p, 0.0) + 1 / (60 + rank)
        return [Hit(p, round(s, 7), "hybrid") for p, s in
                sorted(fused.items(), key=lambda kv: (-kv[1], kv[0]))[:limit]]


def normalize(v) -> tuple[float, ...]:
    vals = tuple(float(x) for x in v)
    mag = math.sqrt(sum(x*x for x in vals))
    if not vals or not math.isfinite(mag) or mag <= 0:
        raise ValueError("invalid embedding")
    return tuple(x/mag for x in vals)


def metrics(results: dict[str, list[str]], relevant: dict[str, set[str]], k: int = 10) -> dict:
    """Macro Recall@K and nDCG@K; empty relevance sets are excluded."""
    recall, ndcg = [], []
    for q, truth in relevant.items():
        if not truth:
            continue
        ranked = results.get(q, [])[:k]
        recall.append(len(set(ranked) & truth) / len(truth))
        dcg = sum((1 / math.log2(i + 2)) for i, p in enumerate(ranked) if p in truth)
        ideal = sum(1 / math.log2(i + 2) for i in range(min(len(truth), k)))
        ndcg.append(dcg / ideal if ideal else 0)
    return {"recall_at_k": sum(recall)/len(recall) if recall else None,
            "ndcg_at_k": sum(ndcg)/len(ndcg) if ndcg else None,
            "queries": len(recall), "k": k}


def evaluate(candidate: Callable[[str], list[str]], queries: dict[str, set[str]],
             *, k: int = 10, cost: float = 0.0) -> dict:
    start = time.perf_counter()
    found = {q: candidate(q) for q in queries}
    scores = metrics(found, queries, k)
    scores.update({"latency_ms_per_query": 1000*(time.perf_counter()-start)/max(1,len(queries)),
                   "cost": max(0., float(cost))})
    return scores


def promote(baseline: dict, candidate: dict, *, min_queries: int = 10) -> bool:
    """Conservative promotion: no regression on quality, speed or cost."""
    if min(baseline.get("queries", 0), candidate.get("queries", 0)) < min_queries:
        return False
    for key in ("recall_at_k", "ndcg_at_k"):
        if baseline.get(key) is None or candidate.get(key) is None:
            return False
        if candidate[key] + 1e-9 < baseline[key]:
            return False
    return (candidate["ndcg_at_k"] > baseline["ndcg_at_k"] + 1e-6 and
            candidate["latency_ms_per_query"] <= baseline["latency_ms_per_query"] * 1.1 and
            candidate["cost"] <= baseline["cost"])
