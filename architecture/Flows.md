---
artifact: Flows
status: complete
order: 3
fills: "behavioral blueprint — request, event, execution, error, state-update flows"
depends_on: [Architecture]
filled_by: both
last_decision: D-008
---

# Flows — Resonance

## Request Flow

### F1 — remember(text, source?, importance=0.5, created_at?)
1. Facade validates: `text` non-empty after strip, ≤ 100 000 chars;
   `importance` in [0, 1]; `source` ≤ 200 chars; `created_at` ISO-8601 if given.
2. `content_hash = sha256(text.strip())`. If a note with that hash exists,
   return its id with `duplicate: true`. **No counts change** (C-I3).
3. Text: split into sentences on `. ! ? ; :` and newlines; tokenize each;
   drop stopwords and tokens shorter than 2 chars; fold plurals.
4. Text: for every pair of positions `i < j` in the same sentence with
   `j − i ≤ 5`, emit `Δcount(a,b) += 1/(j−i)` for `a ≠ b`, key ordered
   `(min, max)`. Also `tf[term] += 1`.
5. Store, **one transaction**: insert note; upsert terms (`df += 1` per unique
   term); insert postings; upsert pairs; `mass[a] += Δ`, `mass[b] += Δ`;
   `total += 2Δ`.
6. If `pair_count > max_pairs` → F6 (prune).
7. Return `{id, duplicate: false, terms: n_unique}`.

**Bulk variant — `remember_many(texts)` / CLI `ingest`:** validate every text
first (one bad text rejects the batch before any write), then steps 2–5 for each
text inside **one** transaction, then step 6 once. Commit (fsync) dominates
ingest cost, so this is ~3× faster than repeated `remember`.

### F2 — relate(a, b, type, weight)
1. Facade normalizes `a` and `b` through the same Text pipeline; each must be
   exactly one term, and `a ≠ b`. `type ∈ {synonym, antonym, is_a, part_of,
   related}`; `weight ∈ [0, 1]`.
2. Store upserts `relations(a, b)` (ordered as given — direction is kept for
   display). Returns the previous `(type, weight)` if one was overwritten so
   the caller can restore it.
3. `weight = 0` is legal: it **suppresses** the learned edge between `a` and `b`.

### F3 — neighbors(term, limit=20)
1. Normalize `term` (one term).
2. Store returns up to 512 learned candidates (highest raw count first) with
   `count, mass(a), mass(b), total`, plus every asserted relation touching the
   term (either direction).
3. Weights computes each edge; asserted overrides learned for that pair.
4. Drop weight ≤ 0; sort desc; return top `limit` with evidence
   (`count`, `npmi`, `confidence`, `relation`, `source: learned|asserted`).

### F4 — recall(query, limit=5, hops=2, since?, until?)
1. Normalize query (≤ 2000 chars). Seeds = query terms known to the store
   (vocabulary or relations). No seeds → empty result, not an error.
2. Seed activation ∝ `idf(t) = ln(1 + N_notes / (1 + df(t)))`, normalized to sum 1.
3. For hop 1..`hops` (max 4): take the ≤ 32 highest-activation nodes first
   reached on the previous hop; for each, take its top 16 edges (F3 steps 2–4);
   `act[b] += act[a] · w · 0.5`. Record, per node, the single predecessor that
   contributed most (the explanation path).
4. Keep the 256 most-activated terms.
5. Fetch postings for active terms; score each note
   `Σ act(t)·(1+ln tf)·idf(t) / √(unique terms in note) · (0.5 + importance)`.
6. Apply `since`/`until` on `created_at`; return top `limit` notes and top 20
   terms, each note with its matched terms and their paths.

### F5 — context(query, budget_chars=4000, …)
Runs F4, then packs a plain-text block: one header line of the top related
terms, then notes in rank order as `[id · date · score] text`. Stops before the
block would exceed `budget_chars`; a note that does not fit is truncated with
`…` only if at least 200 chars remain, otherwise omitted. Output length is
always ≤ `budget_chars`.

## Event Flow
None. There is no pub/sub, no background work, no timers. Every state change
happens inside a synchronous facade call.

## Execution Flow
Library: host constructs `Resonance(path)` → calls verbs → `close()`.
CLI: parse args → open → one verb → print (text or `--json`) → close.
MCP: open once → loop reading one JSON-RPC message per stdin line → dispatch
`initialize | tools/list | tools/call | ping` → write one line per response →
exit on EOF.

## Error Flow
- **Invalid input** → `ValidationError` from the facade before any write. CLI:
  message on stderr, exit 2. MCP: tool result with `isError: true` and the
  message (never the note text).
- **Unknown note id** (forget) → `NotFound`; exit 1 / `isError`.
- **SQLite busy** beyond 5 s timeout → the transaction rolls back; error
  surfaces; the store is unchanged.
- **Any exception inside an ingest/forget transaction** → rollback; counts,
  postings and notes stay mutually consistent (C-I1).
- **Malformed JSON-RPC** → error `-32700`/`-32600`; unknown method → `-32601`;
  the server keeps running.
- **Tokenizer version change** detected on open → automatic F7 rebuild
  (derived data only; notes and relations untouched).

## State-Update Flow

### F6 — prune (bound on the pair table)
When `pair_count > max_pairs` (default 1 000 000): delete the lowest-count
pairs (ties broken by `(a, b)`) until `pair_count ≤ 0.9 · max_pairs`; then
recompute every `mass` from `pairs` and `total = Σ mass`, in the same
transaction.

### F8 — forget(note_id) — operator only
In one transaction: re-derive the note's pairs and tf with the current
tokenizer; for each pair subtract `removed = min(existing, Δ)` from the pair,
from both masses and `2·removed` from `total`; delete pairs ≤ 1e-9; delete its
postings; `df −= 1`; delete terms with `df = 0`; delete the note. Relations are
not touched (they are keyed by term text, not by note).

### F7 — rebuild
One transaction: clear `pairs`, `postings`, `terms`, reset `total`; re-run
F1 steps 3–5 for every note in `created_at` order; store the tokenizer version;
then F6 if over cap.

### F9 — export / import
Export writes JSONL: one `{"kind":"note", id, text, source, importance,
created_at}` or `{"kind":"relation", a, b, type, weight, created_at}` per line.
Import validates each line, runs F1 (keeping `id` and `created_at`) or F2.
Duplicates (same hash) are skipped and counted. Learned weights are never
exported — they are rebuilt by ingest.
