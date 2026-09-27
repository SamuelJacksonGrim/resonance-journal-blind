---
artifact: Architecture
status: complete
order: 2
fills: "structural blueprint — subsystems, boundaries, data & control flow"
depends_on: []
filled_by: both
last_decision: D-005
---

# Architecture — Resonance

## Purpose
Resonance is a local associative memory. It keeps **notes** (passages of text)
and a **weighted term graph** over the words in them. Edge weights come from two
sources: **learned** weights, derived at read time from windowed co-occurrence
counts (confidence-damped NPMI), and **asserted** relations (typed, weighted
facts such as `car synonym automobile`) that an operator or AI states
explicitly and that override the learned weight for that pair. Retrieval is
**spreading activation**: query words seed activation, it flows along the
strongest edges for up to `hops` steps with decay, and notes are ranked by the
activation of the terms they contain. Every result carries the path that
reached it.

## Major Subsystems
- **Text** (`resonance/text.py`) — deterministic normalization: sentence split,
  tokenize, stopword drop, conservative plural folding, windowed pair
  extraction with 1/distance weighting. Pure; no I/O.
- **Weights** (`resonance/weights.py`) — the single authority on how strong an
  edge is: NPMI, confidence damping, relation-type factors, asserted-overrides-
  learned. Pure; no I/O.
- **Store** (`resonance/store.py`) — the only module that speaks SQL. Owns the
  SQLite file, schema, transactions, count bookkeeping, pruning.
- **Recall** (`resonance/recall.py`) — spreading activation, note scoring,
  explanation paths, prompt-context packing.
- **Memory facade** (`resonance/memory.py`) — `Resonance`, the public library
  API. Validates input at the boundary and orchestrates Text → Store,
  Store → Weights → Recall.
- **Adapters** — `resonance/cli.py` (operator, all verbs) and
  `resonance/mcp_server.py` (AI client, read + additive verbs, stdio JSON-RPC).

## Boundaries
- **Trust boundary:** everything entering through the facade (note text, query
  strings, relation arguments, MCP JSON) is untrusted until `memory.py`
  validates it. Adapters never touch the Store directly.
- **Process boundary:** the MCP server is a second process sharing the SQLite
  file with any CLI invocation. SQLite WAL mode + a busy timeout serialize
  writers. No network listener exists anywhere.
- **Data boundary:** nothing leaves the machine. Export writes a local file the
  operator names.

## Data Flow
```
text ──Text.sentences──▶ sentences of terms ──Text.analyze──▶ {(a,b): Δcount}
      └─────────────────────────────────────▶ {term: tf}
Δcounts, tf ──Store (one transaction)──▶ pairs, terms.mass, meta.total, postings

query ──Text──▶ seed terms ──Store.learned_candidates, relations_touching──▶ counts + relations
      ──Weights (learned_weight, combine)──▶ weighted edges ──Recall.spread──▶ activation map
      ──Store.postings_for──▶ note scores ──▶ RecallResult (terms, notes, paths)
```
Learned weights are **never stored**; only raw counts are. Weights are computed
at read time from the current counts, so they can never be stale.

## Control Flow
Control originates only in an adapter (CLI command or MCP `tools/call`) or in a
host program calling `Resonance`. The facade calls downward; nothing calls
upward; no background threads or timers exist.

## High-Level Diagram
See [`diagrams/architecture_graph.md`](diagrams/architecture_graph.md) and
[`diagrams/system_flow.md`](diagrams/system_flow.md).
