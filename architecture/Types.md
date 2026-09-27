---
artifact: Types
status: complete
order: 5
fills: "core domain types, primitives, enums, identifiers, structural schemas"
depends_on: [Contracts]
filled_by: both
last_decision: null
---

# Types — Resonance

## Core Domain Types
- **Note** — a stored passage. `id, text, content_hash, source?, importance,
  created_at, n_terms`. Immutable once stored; removed only by `forget`.
- **Term** — a normalized token (casefolded, Latin accents folded, stopword-free, plural-folded; see
  `text.py`). Row: `id, text, df, mass`.
- **Pair** — learned co-occurrence evidence between two terms. Row:
  `a, b, count` with `a < b` (Contracts I4). `count` is a real number: the sum
  of `1/distance` over every co-occurrence within the window.
- **Relation** — asserted knowledge: `a, b, type, weight, created_at`, keyed by
  term **text** (Contracts: "Relations are keyed by term text").
- **Edge** (`weights.Edge`, in memory only) — a weighted link from one term to a
  neighbor: `term, weight ∈ (0,1], source, count?, npmi?, confidence?,
  relation?, direction?`.
- **Activation** (`recall.Activation`, in memory only) — `act: term → float`,
  `best: term → (contribution, Step)`, `seeds`.

## Primitives & Identifiers
| Name | Type | Notes |
|---|---|---|
| note id | `str`, 1–64 chars | default: 16 hex chars from uuid4; preserved by export/import |
| term id | `int` | SQLite rowid; **not stable** across rebuild/import — never persisted outside the DB |
| content_hash | `str` | sha256 hex of `text.strip()` (Contracts I3) |
| timestamps | `str` | ISO-8601, normalized to UTC, second precision; naive input is treated as UTC |
| importance, relation weight | `float` | [0, 1] |
| total | `float` | `meta.total` = Σ mass (Contracts I1) |
| pair_rows | `int` | `meta.pair_rows`, trigger-maintained row count of `pairs` |
| tokenizer_version | `int` | `meta.tokenizer_version`; `text.TOKENIZER_VERSION` = 1 |

## Enums
- **RelationType**: `synonym` (factor 1.0), `is_a` (0.8), `part_of` (0.7),
  `related` (0.6), `antonym` (0.4). Factor multiplies the asserted weight.
- **EdgeSource**: `learned` | `asserted`.
- **Direction** (asserted edges): `out` — the queried term is `a` in `a→b`;
  `in` — it is `b`.

## Structural Schemas
```jsonc
// remember → 
{"id": "8bffa44cfc4f440d", "duplicate": false, "terms": 8, "pruned_pairs": 0 /* only if > 0 */}

// neighbors →
{"term": "dog", "neighbors": [
  {"term": "canine", "weight": 0.8, "source": "asserted", "relation": "is_a", "direction": "out"},
  {"term": "chased", "weight": 0.1402, "source": "learned", "count": 1.0, "npmi": 0.4207, "confidence": 0.3333}]}

// recall →
{"query": "canine", "seeds": ["canine"], "unknown": [],
 "terms": [{"term": "dog", "activation": 0.4, "seed": false, "why": "canine —is_a 0.80→ dog"}],
 "notes": [{"id": "…", "score": 0.2875, "created_at": "2026-09-27T00:12:00+00:00",
            "source": null, "importance": 0.5, "text": "…",
            "matched": [{"term": "dog", "why": "canine —is_a 0.80→ dog"}]}]}

// export line →
{"kind": "note", "id": "…", "text": "…", "source": null, "importance": 0.5, "created_at": "…"}
{"kind": "relation", "a": "dog", "b": "canine", "type": "is_a", "weight": 1.0, "created_at": "…"}
```
