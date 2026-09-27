---
artifact: Interfaces
status: complete
order: 7
fills: "plug points — the contracts between modules that make them swappable"
depends_on: [Types, Contracts]
filled_by: both
last_decision: D-004
---

# Interfaces — Resonance

## Interface List

### Resonance (library API) — `resonance.Resonance`
- **Purpose:** the only public surface; every adapter goes through it.
- **Inputs → Outputs:**
  - `remember(text, source=None, importance=0.5, created_at=None, note_id=None) → {id, duplicate, terms}`
  - `remember_many(texts, source=None, importance=0.5) → {notes, duplicates}`
  - `forget(note_id) → {id, forgotten}` · raises `NotFound`
  - `relate(a, b, type="related", weight=1.0) → {a, b, type, weight, previous?}`
  - `unrelate(a, b) → {a, b, removed}` · raises `NotFound`
  - `neighbors(term, limit=20) → {term, neighbors: [Edge]}`
  - `recall(query, limit=5, hops=2, since=None, until=None) → RecallResult`
  - `context(query, budget_chars=4000, limit=8, hops=2, since=None, until=None) → str`
  - `export(fh) → {notes, relations}` · `import_(lines) → {notes, duplicates, relations, errors}`
  - `rebuild() → {notes, pruned_pairs}` · `stats() → {...}`
- **Errors:** `ValidationError` (input rejected, nothing written), `NotFound`.
- **Upholds:** G2, G3, G5, G6, G7; S2, S3.
- **Implemented by:** `memory.py`. **Consumed by:** `cli.py`, `mcp_server.py`, host programs.

### Store — `resonance.store.Store`
- **Purpose:** persistence and the count ledger. Swappable for another backend
  only if it keeps Contracts I1–I5 in one transaction per write.
- **Key methods:** `tx()`, `add_contribution(note_id, pairs, tf)`,
  `remove_contribution(note_id, pairs)`, `prune_if_needed()`,
  `recompute_mass()`, `learned_candidates(term)`, `relations_touching(term)`,
  `postings_for(term_ids)`, `upsert_relation(...)`, `term_stats(texts)`.
- **Upholds:** I1–I5, G6, S1, S4.
- **Implemented by:** `store.py`. **Consumed by:** `memory.py`, `recall.py` (reads only).

### Edge weighting — `resonance.weights`
- **Purpose:** the seam where a different notion of "semantic strength" (e.g.
  embedding cosine) would plug in.
- **Inputs → Outputs:** `learned_weight(count, mass_a, mass_b, total) → (w, npmi, conf)`;
  `asserted_weight(type, weight) → w`; `combine(learned, asserted) → [Edge]`.
- **Upholds:** weights ∈ [0, 1]; asserted overrides learned.
- **Implemented by:** `weights.py`. **Consumed by:** `recall.py`.

### Text analysis — `resonance.text`
- **Inputs → Outputs:** `analyze(text) → (pair deltas, tf)`, `terms(text) → [str]`,
  `single_term(text) → str | None`.
- **Upholds:** determinism for a given `TOKENIZER_VERSION`.
- **Implemented by:** `text.py`. **Consumed by:** `memory.py`.

### MCP tools (stdio JSON-RPC 2.0, protocol `2025-06-18`)
- **Methods:** `initialize`, `notifications/*` (ignored), `ping`, `tools/list`, `tools/call`.
- **Tools:** `context`, `recall`, `neighbors`, `remember` (`text, source?, importance?`),
  `relate`, `stats`. Unknown arguments are rejected. `forget` / `unrelate`
  are not offered (D-004).
- **Errors:** tool failures → `result.isError = true`; protocol errors →
  JSON-RPC `-32700 / -32600 / -32601 / -32602 / -32603`.
- **Implemented by:** `mcp_server.py`. **Consumed by:** any MCP client.

### CLI — `resonance` / `python -m resonance`
- Verbs: `remember, ingest, recall, context, neighbors, relate, unrelate,
  forget --yes, export, import, rebuild, stats`; global `--db`, `--json`.
- Exit codes: 0 ok · 1 not found / file error / import had errors · 2 invalid input or missing `--yes`.
