---
artifact: Schemas
status: complete
order: 6
fills: "conceptual ontology — Entity→State→Event→Evaluation→Decision→Action"
depends_on: [Types]
filled_by: both
last_decision: null
---

# Schemas — Resonance

## Core Transformation Chain
| Stage | In Resonance |
|---|---|
| **Entity** | Note (text), Term, Relation |
| **State** | Count ledger (pairs, mass, total), postings, relations |
| **Event** | `remember`, `forget`, `relate`, `unrelate`, `rebuild` — synchronous calls, no event bus |
| **Evaluation** | `weights.learned_weight` / `asserted_weight` / `combine`: NPMI × confidence, or relation factor × asserted weight |
| **Decision** | `recall.spread`: which edges to follow (top 16), which nodes to expand (top 32), what to keep (top 256) |
| **Action** | Return ranked terms, notes, and paths; `context` packs them into a budgeted text block |

## Cognitive Schemas
Resonance models association, not belief. It holds two kinds of knowledge:
- **Statistical** (learned): "these words appear near each other more than
  chance predicts". Revised automatically as notes arrive or leave.
- **Declared** (asserted): "an operator or AI said these words stand in this
  relation". Revised only by another assertion. Declared beats statistical for
  the same pair.

Relevance is **activation**: a query lights up its words, and activation flows
along the strongest links, halving each step.

## Information Schemas
Text → sentences → terms → (pair deltas, term frequencies) → count ledger.
Query → seed terms → activation map → note scores → ranked, explained results.
Only counts and declared relations persist; weights and activations are
computed and discarded per call.

## Transformation Schemas
- **count → weight**: `max(0, NPMI(c, mass_a, mass_b, total)) · c/(c+2)`.
- **relation → weight**: `factor(type) · weight`.
- **(learned, asserted) → edge**: asserted wins for the pair; weight 0 removes it.
- **activation → note score**: `Σ act(t)·(1+ln tf)·idf(t) / √n_terms · (0.5+importance)`.
