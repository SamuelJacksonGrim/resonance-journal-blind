# System Flow — Resonance

Ingest (remember):
```
text → validate (≤100k chars) → hash → duplicate? ──yes──▶ return existing id (no count change)
                                         │no
                                         ▼
       sentences → terms → windowed pairs (±5, weight 1/d)
                                         ▼
       ONE transaction: note row, postings, terms.df/mass, pairs, meta.total
                                         ▼
       pairs > max_pairs? ──yes──▶ prune lowest counts to 90% cap, recompute mass/total
```

Recall:
```
query → terms → seeds (idf-weighted, sum 1)
      → hop 1..H: for top 32 frontier nodes, top 16 edges each:
            act[b] += act[a] · w(a,b) · 0.5      (keep best path to b)
      → trim to 256 active terms
      → notes: Σ act(t)·(1+ln tf)·idf(t) / √|note terms| · (0.5+importance)
      → filter since/until → top k with matched terms + paths
```
