"""Yakumo Evolution: bounded, reproducible strategy tournament.

This is evolution of retrieval policies, NOT model-weight training or code execution.
Candidates compete on automatically generated queries from available facts. The
report labels those in-sample tests as synthetic, never claims real-world accuracy.
No cloud requests, subprocesses, network, filesystem writes outside the lab.
"""
from __future__ import annotations

import json
import re
import threading
import time
from pathlib import Path

POLICIES = ("literal", "tokens", "prefix", "hybrid")
MAX_FACTS = 120
MAX_RUNS = 40
_token = re.compile(r"[^\W_]+", re.UNICODE)


def tokens(text):
    return tuple(x.lower() for x in _token.findall(str(text)))[:48]


def score(policy, query, text):
    q = tokens(query)
    t = tokens(text)
    if not q or not t:
        return 0.0
    joined = " ".join(t)
    phrase = " ".join(q)
    overlap = sum(1 for word in set(q) if word in t) / len(set(q))
    if policy == "literal":
        return float(phrase in joined)
    if policy == "tokens":
        return overlap
    if policy == "prefix":
        return sum(1 for word in set(q) if any(x.startswith(word[:4]) for x in t)) / len(set(q))
    if policy == "hybrid":
        return (overlap * .65 + float(phrase in joined) * .35)
    raise ValueError("Unknown policy")


class EvolutionLab:
    def __init__(self, path):
        self.path = Path(path)
        self.lock = threading.RLock()
        self.runs = []
        try:
            loaded = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(loaded, list):
                self.runs = [r for r in loaded if isinstance(r, dict)][-MAX_RUNS:]
        except (OSError, ValueError, TypeError):
            pass

    def status(self):
        with self.lock:
            runs = list(reversed(self.runs[-20:]))
        return {"version": 1, "mode": "sandbox", "auto_apply": False,
                "weight_training": False, "network": False,
                "policies": list(POLICIES), "runs": runs,
                "total_generations": len(self.runs)}

    def compete(self, facts):
        """A deterministic sandbox race with resource and data limits."""
        samples = []
        for fact in facts[:MAX_FACTS]:
            if not isinstance(fact, dict):
                continue
            raw = str(fact.get("text") or "")[:500]
            words = tokens(raw)
            if len(words) >= 3:
                samples.append((str(fact.get("id", len(samples))), raw, " ".join(words[:min(3, len(words))])))
        if len(samples) < 3:
            raise ValueError("Для эксперимента нужны хотя бы три непустых факта")
        results = []
        # Evaluate retrieval of the source fact; ties are explicitly counted,
        # so duplicate facts cannot silently inflate the performance measure.
        for policy in POLICIES:
            correct = 0
            latency = 0.0
            for target, _, query in samples:
                started = time.perf_counter()
                ranked = sorted(((score(policy, query, text), ident) for ident, text, _ in samples),
                                key=lambda item: (-item[0], item[1]))
                latency += (time.perf_counter() - started) * 1000
                top = ranked[0]
                if top[0] > 0 and top[1] == target:
                    correct += 1
            results.append({"name": policy, "hits": correct, "total": len(samples),
                            "accuracy": round(correct / len(samples), 4),
                            "latency_ms": round(latency, 3)})
        # Accuracy dominates; latency breaks ties. No code is deployed.
        winner = sorted(results, key=lambda r: (-r["accuracy"], r["latency_ms"], r["name"]))[0]["name"]
        entry = {"id": str(time.time_ns()), "created": int(time.time()), "generation": len(self.runs) + 1,
                 "kind": "retrieval_policy", "dataset": "synthetic queries from stored facts",
                 "sample_size": len(samples), "winner": winner, "candidates": results,
                 "applied": False, "status": "evaluated",
                 "warning": "Проверка на синтетических запросах, не оценка реальных ответов."}
        with self.lock:
            self.runs.append(entry)
            self.runs = self.runs[-MAX_RUNS:]
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.path.with_suffix(".tmp")
            temporary.write_text(json.dumps(self.runs, ensure_ascii=False, indent=2), encoding="utf-8")
            temporary.replace(self.path)
        return entry
