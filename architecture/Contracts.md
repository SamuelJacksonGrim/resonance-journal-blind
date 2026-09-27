---
artifact: Contracts
status: complete
order: 4
fills: "guarantees, assumptions, invariants, pre/post-conditions"
depends_on: [Architecture, Flows]
filled_by: both
last_decision: D-010
---

# Contracts — Resonance

## Guarantees
- **G1 — Local only.** No code path opens a network socket. The MCP server
  talks only over its own stdin/stdout.
- **G2 — Derived weights are never stale.** Learned edge weights are computed
  at read time from the current counts; there is no cached weight to
  invalidate.
- **G3 — Explainable recall.** Every returned term and every matched term on a
  returned note carries the path (seed → … → term) with the source and weight
  of each edge.
- **G4 — Bounded work per query.** A recall touches at most
  `32 frontier nodes × 16 edges × 4 hops` edge evaluations, 512 candidate rows
  per neighbor lookup, and 256 active terms, whatever the store size.
- **G5 — Bounded output.** `context` output length ≤ `budget_chars`
  (min 200, max 100 000).
- **G6 — Atomic writes.** remember, forget, relate, unrelate, prune, rebuild and
  each imported line are single SQLite transactions. `remember_many` (CLI
  `ingest`) stores its whole batch in one transaction: all or nothing.
- **G7 — Round-trip.** `export` then `import` into an empty store yields the same
  notes (ids, text, dates, importance, source), the same relations (a, b, type,
  weight; `created_at` is the import time), and
  therefore the same learned counts.

### SECURITY controls (row `always`; exposure `local-single`)
- **S1** All SQL is parameterized. The only dynamically built SQL fragment is a
  run of `?` placeholders whose length is computed from a list size.
- **S2** Input is validated in `memory.py` before any write (limits in F1–F5).
- **S3** Note text is never written to logs, stderr, or error messages.
- **S4** The database directory is created `0700` and the file (plus its WAL/SHM
  side files) `0600`.
- No secrets exist, so the secrets control has nothing to apply to.

## Assumptions
- **A1** Text is mostly English. The stopword list and plural folding are
  English; other languages still work, only less precisely.
- **A2** One operator per database file (exposure `local-single`).
- **A3** Python ≥ 3.11 with its bundled `sqlite3`, SQLite ≥ 3.33 (upsert and
  `UPDATE … FROM`). Tested on SQLite 3.45.

## Invariants
- **I1 — Count ledger.** At rest, for every term `t`:
  `mass[t] = Σ count(pairs touching t)` and `total = Σ mass = 2·Σ count`.
- **I2 — Postings ledger.** `df[t]` = number of notes with a posting for `t`;
  a term row exists iff `df > 0`.
- **I3 — No double counting.** A note's text contributes to counts at most once:
  duplicate text (same sha256 of stripped text) is not re-ingested.
- **I4 — Canonical pair key.** Pair rows are stored with `a < b` (term ids).
- **I5 — Bounds.** `pair_count ≤ max_pairs` after every write. `pair_count` is
  `meta.pair_rows`, kept exact by SQLite insert/delete triggers on `pairs`.

## Invariants that look optional but aren't
- **Masses must move with pairs, in the same transaction.** NPMI divides by
  `mass[a]·mass[b]` and normalizes by `total`. If prune or forget deletes pair
  rows without updating masses and `total`, every weight in the store drifts
  silently — no error, just subtly wrong rankings. *(Prevents: slow ranking rot
  after the first prune.)*
- **forget subtracts `min(existing, Δ)`, not Δ.** After a prune, a note's
  contribution may already be gone. Subtracting the full Δ drives masses
  negative and makes NPMI return garbage for unrelated terms.
- **Ingest and forget must use the identical tokenizer.** Forget re-derives
  what to subtract from the note text. If the tokenizer changed in between,
  it subtracts the wrong pairs. Hence `TOKENIZER_VERSION` in `meta` and the
  automatic rebuild on mismatch (F7).
- **A rebuild re-keys relations through the current fold.** Relations are
  operator data keyed by term text. Without re-keying, a tokenizer change such
  as accent folding in v2 orphans them: `zürich is_a city` never matches the
  term `zurich` again. The only failure is quiet recall misses (D-010).
- **Confidence damping must stay.** NPMI alone scores two words seen together
  once, and nowhere else, at 1.0 — the maximum. Without `c/(c+2)`, hapax pairs
  outrank well-attested ones and recall fills with noise.
- **Relations are keyed by term text, not term id.** Term ids are reassigned by
  rebuild and import; text keys keep asserted knowledge attached across both.
- **Decay < 1 and fan-out caps.** With decay ≥ 1 activation grows with every hop
  and hubs dominate; the caps are what make G4 true.

## Guardrails — do NOT
- **Don't store learned weights** "for speed". Store counts; if reads get slow,
  cache per-query in memory, never on disk (G2).
- **Don't write SQL outside `store.py`.** Need a new query? Add a method to
  `Store` and call it from the facade.
- **Don't expose `forget` or `unrelate` over MCP.** The AI may add memory and
  assert relations; removing the operator's memory stays a CLI action with
  `--yes`. If an AI needs to cancel a relation, it asserts weight 0
  (suppress), which the operator can see and reverse.
- **Don't raise edge weights in recall.** Recall consumes weights; it never
  adjusts them. A new weighting idea goes into `weights.py`.
- **Don't delete notes to enforce a bound.** Notes are the operator's data;
  bounds apply to derived tables only (D-007).

## Authority hierarchy (single source of truth)
| Decision | Sole authority | Advisors / inputs |
|---|---|---|
| What counts as a term | `text.py` | stopword list, `TOKENIZER_VERSION` |
| How strong an edge is | `weights.py` (`learned_weight`, `asserted_weight`, `combine`) | raw counts & relations from Store |
| What is persisted, and when | `store.py` | facade supplies validated deltas |
| Whether input is acceptable | `memory.py` | — |
| What is relevant to a query | `recall.py` | weights, postings |
| Whether a note is deleted | the operator via CLI `forget --yes` | — |

## Pre/Post-Conditions
| Operation | Pre | Post |
|---|---|---|
| `remember` | text valid | exactly one note with this hash exists; I1–I5 hold |
| `forget` | note id exists | note, postings gone; its counts subtracted; I1–I5 hold |
| `relate` | a, b are single distinct terms; type in enum; weight ∈ [0,1] | one relation row for (a,b); previous value returned |
| `neighbors` | term normalizes to one token | list sorted by weight desc, all weights in (0,1] |
| `recall` | query ≤ 2000 chars; 0 ≤ hops ≤ 4; 1 ≤ limit ≤ 50 | read-only; results obey G3, G4 |
| `context` | as recall; 200 ≤ budget ≤ 100 000 | read-only; len(output) ≤ budget |
| `rebuild` | — | derived tables equal a fresh ingest of all notes |
