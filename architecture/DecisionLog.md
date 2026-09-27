---
artifact: DecisionLog
status: complete
order: 99
fills: "architectural memory — consequential decisions, not every change"
depends_on: []
filled_by: both
last_decision: D-010
---

# DecisionLog — Resonance

> Append-only. Supersede, never rewrite. Titles are the question.

### D-001 — Build order: Flows before Contracts?
- **Date:** 2026-09-27
- **Decided by:** both (inherited)
- **Status:** active
- **Decision:** Architecture → Flows → Contracts → … as in `PIPELINE.md`.
- **Alternatives:** Contracts first (rejected).
- **Reason:** A contract constrains a behavior; the behavior has to be described first.
- **Affects:** all artifacts.

### D-002 — Which stack, when the human named none?
- **Date:** 2026-09-27
- **Decided by:** AI
- **Status:** active
- **Decision:** Python ≥ 3.11, standard library only; SQLite for storage.
- **Alternatives:** A vector database (Chroma, LanceDB) — rejected: install
  weight and an embedding model. Node/TypeScript with the official MCP SDK —
  rejected: needs `npm install` before anything can be smoke-tested. A plain
  JSON file — rejected: no transactions, and two processes share the store.
- **Reason:** Smallest stack that can smoke-test with zero installs; SQLite
  gives atomic multi-table updates, which the count ledger needs (Contracts I1),
  and safe sharing between the CLI and the MCP process.
- **Affects:** Dependencies, all modules.

### D-003 — What kind of system, how deep, and which reading of the request?
- **Date:** 2026-09-27
- **Decided by:** AI (no human available to ask; SELECTOR Step A rule 1)
- **Status:** active
- **Decision:** `class: library` with CLI and MCP adapters; `depth: standard`;
  `exposure: local-single`. Reading chosen: *a local associative memory whose
  weights are computed from the operator's own text and from asserted
  relations*.
- **Alternatives:** The other plausible reading — *semantic weights from a
  pretrained embedding model* (vectors + cosine). Rejected for v1: requires a
  model download or a network API, adds a trigger (data leaving the machine if
  an API is used). The `weights.py` seam is where it would plug in without a
  rewrite. A pure relation-thesaurus (only asserted edges) — rejected: nothing
  would be "weighed", only declared.
- **Reason:** Fewest escalation triggers. The only trigger that holds is the
  second process (MCP server), which sets depth to `standard`; no network
  boundary, money, secrets, or other people's data, so not `full`.
- **Affects:** INTENT, Architecture, Interfaces.

### D-004 — What may an AI client change over MCP?
- **Date:** 2026-09-27
- **Decided by:** AI (guess — first in handover)
- **Status:** active
- **Decision:** MCP exposes reads (`context`, `recall`, `neighbors`, `stats`)
  and additive writes (`remember`, `relate`). `forget` and `unrelate` are
  CLI-only, behind `--yes` for `forget`. An AI can neutralize a bad link by
  asserting weight 0, which the operator can see and undo.
- **Alternatives:** Read-only MCP — rejected: an AI memory the AI cannot write
  to defeats the purpose. Full CRUD over MCP — rejected: lets a confused or
  prompt-injected agent erase the operator's notes.
- **Reason:** Every AI write is reversible by the operator; no AI write is
  destructive.
- **Affects:** Interfaces (MCP tools), Contracts (guardrails), mcp_server.py.

### D-005 — Store weights, or store counts and derive weights?
- **Date:** 2026-09-27
- **Decided by:** AI
- **Status:** active
- **Decision:** Persist raw windowed co-occurrence counts plus per-term mass
  and a global total. Compute learned weights at read time.
- **Alternatives:** Persist computed weights — rejected: every new note changes
  the marginals, so every stored weight touching a changed term would go stale
  and need recomputation (O(neighbors) per note, easy to get wrong).
- **Reason:** Weights can never be stale (G2); forget and import become exact
  arithmetic on counts.
- **Affects:** Architecture, Contracts (G2, I1), store.py, weights.py.

### D-006 — How is a relationship's weight computed?
- **Date:** 2026-09-27
- **Decided by:** AI
- **Status:** active
- **Decision:** Learned: `max(0, NPMI) · c/(c+2)` over a ±5-token window with
  1/distance weighting, not crossing sentence boundaries. Asserted:
  `factor(type) · weight`, overriding learned for the same pair.
- **Alternatives:** Raw counts (hubs like "people" dominate); PPMI (unbounded,
  hard to mix with asserted weights in [0, 1]); plain NPMI (single
  co-occurrences of rare words score 1.0 — the maximum).
- **Reason:** NPMI is bounded and corrects for frequency; the confidence damping
  fixes its rare-pair bias; bounded weights make multi-hop decay meaningful.
- **Affects:** weights.py, Contracts ("confidence damping must stay").

### D-007 — What grows, and what bounds it?
- **Date:** 2026-09-27
- **Decided by:** AI
- **Status:** active
- **Decision:** `pairs` is capped (`max_pairs`, default 1 000 000 ≈ 40–60 MB);
  over the cap, lowest-count pairs are pruned to 90 %. Notes are **not**
  capped: each is ≤ 100 000 chars and removed only by the operator. `terms` and
  `postings` are bounded by the notes. Relations are bounded by what is
  asserted; no history is kept. No access log exists.
- **Alternatives:** Cap notes with oldest-first eviction — rejected: silently
  deleting the operator's memory is worse than using disk. Keep all pairs —
  rejected: pair rows grow roughly with vocabulary × window and dominate size.
- **Reason:** Bounds belong on derived data, which can be recomputed; the
  operator's own data is theirs to delete.
- **Affects:** store.py, Contracts (I5, guardrails).

### D-008 — How does "pull when relevant" choose what to return?
- **Date:** 2026-09-27
- **Decided by:** AI
- **Status:** active
- **Decision:** Spreading activation from idf-weighted query terms, default 2
  hops (max 4), decay 0.5, 16 edges per node, 32 nodes per hop, 256 active
  terms. Notes are scored by the activation of the terms they contain, length-
  normalized and scaled by importance. Each result carries its path.
- **Alternatives:** Keyword match only — misses the whole point (related words).
  1-hop neighbors only — misses synonym-of-a-related-word. Personalized
  PageRank to convergence — unbounded per-query cost on a large graph.
- **Reason:** Bounded work per query (G4), multi-step association, explainable
  by construction (G3).
- **Affects:** recall.py, Flows F4, Contracts G3/G4.

### D-009 — What happens when the tokenizer changes under an existing store?
- **Date:** 2026-09-27
- **Decided by:** AI
- **Status:** active
- **Decision:** `TOKENIZER_VERSION` is stored in `meta`; on open, a mismatch
  triggers an automatic `rebuild` of derived tables (notes and relations are
  untouched), announced on stderr.
- **Alternatives:** Refuse to open until the operator runs `rebuild` — safer
  for very large stores but breaks the MCP server silently at launch.
- **Reason:** `forget` re-derives what to subtract from note text, so counts
  made by an older tokenizer would be subtracted wrongly. Rebuild only touches
  recomputable data.
- **Affects:** memory.py, Contracts ("identical tokenizer").

### D-010 — Should "zurich" find "Zürich"?
- **Date:** 2026-09-27
- **Decided by:** both (the human reported the miss; the AI chose the fold)
- **Status:** active
- **Decision:** Tokenizer v2 casefolds and drops combining marks that sit on
  Latin letters (NFKD), plus a small map for letters that do not decompose (ø,
  æ, œ, ł, đ, ð, þ). Marks on other scripts are kept. On upgrade the automatic
  rebuild also re-keys asserted relations through the same fold. A key clash
  keeps the newer assertion. A relation whose two ends become one term is
  dropped, and the count is reported on stderr and in the `rebuild` result.
- **Alternatives:** Strip every combining mark (rejected: it breaks words in
  Devanagari, Thai, and Hebrew). Keep accented and plain forms as separate
  terms linked by synonym relations (rejected: it doubles the terms and splits
  the co-occurrence mass). Leave relations as they are (rejected: they would
  silently stop matching).
- **Reason:** An AI querying memory rarely reproduces the exact diacritics the
  human typed. A missed recall looks exactly like "nothing relevant stored".
- **Affects:** text.py (TOKENIZER_VERSION 2), memory.py (rebuild),
  store.py (get_relation), Contracts, Types.
