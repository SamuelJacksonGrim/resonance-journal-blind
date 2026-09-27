"""Spreading-activation recall over the weighted term graph.

Consumes weights; never changes them (Contracts guardrail).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from . import weights as W
from .store import Store

DECAY = 0.5            # activation kept per hop; must be < 1 so hops cannot amplify
FRONTIER_CAP = 32      # nodes expanded per hop
FANOUT = 16            # edges followed per expanded node
ACTIVE_CAP = 256       # active terms kept after each hop
MAX_HOPS = 4
TOP_TERMS = 20


@dataclass
class Step:
    term: str
    via: str | None       # predecessor term (None for a seed)
    edge: dict | None     # the edge used to arrive here


@dataclass
class Activation:
    act: dict[str, float] = field(default_factory=dict)
    best: dict[str, tuple[float, Step]] = field(default_factory=dict)
    seeds: set[str] = field(default_factory=set)

    def path(self, term: str) -> list[dict]:
        out, seen = [], set()
        while term is not None and term not in seen:
            seen.add(term)
            step = self.best[term][1]
            out.append({"term": step.term, **({"edge": step.edge} if step.edge else {"seed": True})})
            term = step.via
        return list(reversed(out))

    def explain(self, term: str) -> str:
        parts = []
        for s in self.path(term):
            if "seed" in s:
                parts.append(s["term"])
            else:
                e = s["edge"]
                label = e.get("relation") or "learned"
                parts.append(f"—{label} {e['weight']:.2f}→ {s['term']}")
        return " ".join(parts)


def neighbors(store: Store, term: str, limit: int | None = None) -> list[W.Edge]:
    """Weighted edges of `term`, strongest first (Flows F3)."""
    total = store.total()
    learned = {}
    for other, count, m_self, m_other in store.learned_candidates(term):
        w, n, c = W.learned_weight(count, m_self, m_other, total)
        learned[other] = W.Edge(other, w, "learned", count=count, npmi=n, confidence=c)
    asserted: dict[str, W.Edge] = {}
    for r in store.relations_touching(term):
        other, direction = (r["b"], "out") if r["a"] == term else (r["a"], "in")
        e = W.Edge(other, W.asserted_weight(r["type"], r["weight"]), "asserted",
                   relation=r["type"], direction=direction)
        # Both directions asserted: the stronger one speaks for the pair.
        if other not in asserted or e.weight > asserted[other].weight:
            asserted[other] = e
    edges = W.combine(learned, asserted)
    return edges[:limit] if limit else edges


def idf(n_notes: int, df: int) -> float:
    return math.log(1 + n_notes / (1 + df))


def spread(store: Store, seeds: list[str], hops: int) -> Activation:
    n_notes = store.note_count()
    stats = store.term_stats(seeds)
    raw = {t: idf(n_notes, stats[t]["df"] if t in stats else 0) for t in seeds}
    norm = sum(raw.values()) or 1.0
    A = Activation(seeds=set(seeds))
    for t, v in raw.items():
        A.act[t] = v / norm
        A.best[t] = (math.inf, Step(t, None, None))

    frontier = list(seeds)
    edge_cache: dict[str, list[W.Edge]] = {}
    for _ in range(min(hops, MAX_HOPS)):
        frontier = sorted(frontier, key=lambda t: (-A.act.get(t, 0), t))[:FRONTIER_CAP]
        reached: list[str] = []
        for a in frontier:
            if a not in edge_cache:
                edge_cache[a] = neighbors(store, a, FANOUT)
            for e in edge_cache[a]:
                contrib = A.act[a] * e.weight * DECAY
                if contrib <= 0:
                    continue
                if e.term not in A.act:
                    reached.append(e.term)
                A.act[e.term] = A.act.get(e.term, 0.0) + contrib
                if e.term not in A.best or contrib > A.best[e.term][0]:
                    A.best[e.term] = (contrib, Step(e.term, a, e.as_dict()))
        if len(A.act) > ACTIVE_CAP:
            keep = sorted(A.act, key=lambda t: (-A.act[t], t))[:ACTIVE_CAP]
            keep_set = set(keep) | A.seeds
            A.act = {t: A.act[t] for t in keep_set}
            A.best = {t: A.best[t] for t in keep_set}
            reached = [t for t in reached if t in keep_set]
        frontier = reached
        if not frontier:
            break
    return A


def score_notes(store: Store, A: Activation) -> dict[str, tuple[float, dict[str, float]]]:
    """→ {note_id: (score, {matched term: contribution})} before date filtering
    and importance (applied by the caller, which has the note rows)."""
    stats = store.term_stats(A.act)
    n_notes = store.note_count()
    by_id = {r["id"]: r["text"] for r in stats.values()}
    postings = store.postings_for(list(by_id))
    scores: dict[str, tuple[float, dict[str, float]]] = {}
    for p in postings:
        term = by_id[p["term_id"]]
        c = A.act[term] * (1 + math.log(p["tf"])) * idf(n_notes, stats[term]["df"])
        s, matched = scores.get(p["note_id"], (0.0, {}))
        matched[term] = c
        scores[p["note_id"]] = (s + c, matched)
    return scores


def top_terms(A: Activation, limit: int = TOP_TERMS) -> list[dict]:
    ranked = sorted(A.act, key=lambda t: (-A.act[t], t))[:limit]
    return [{"term": t, "activation": round(A.act[t], 5), "seed": t in A.seeds,
             "why": A.explain(t)} for t in ranked]
