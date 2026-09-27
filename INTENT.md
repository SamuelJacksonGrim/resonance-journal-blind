---
artifact: Intent
status: complete
order: 0
fills: "human intent plus the inspectable class/depth decision"
depends_on: []
filled_by: both
last_decision: D-004
---

# Intent Card

> Request, verbatim: *"Build me something that weighs semantic relationships
> between words for storage that makes accessing them easy for an AI to pull
> when relevant."* Built as a one-pass autonomous build (no human present to
> answer questions), so SELECTOR Step A rule 1 applies: pick the reading with
> the fewest escalation triggers and name the other reading first in the
> handover. Guesses are marked *(guess)*.

- **Want:** A local memory store that (1) learns weighted semantic relationships
  between words from text it is given, (2) lets an AI or operator assert typed
  relationships explicitly (synonym, is_a, ...), and (3) answers "what is
  relevant to this?" by following those weighted relationships more than one
  step, returning ranked terms *and* the stored passages they came from, with
  an explanation of why each was pulled.
- **Must not:** Send text anywhere off the machine. Depend on a network model or
  API to function. Let the AI delete the operator's stored memory.
- **Roles:**
  - *Operator* (the human who owns the machine): everything, including
    `forget` (delete a note) and `unrelate`, via the CLI.
  - *AI client* (an LLM agent connected over MCP or calling the library):
    read (`recall`, `context`, `neighbors`, `stats`) and additive writes only
    (`remember`, `relate`) *(guess — see D-004)*.
- **Runs where / exposed to:** The operator's machine. One SQLite file. The MCP
  server speaks JSON-RPC over stdio to the AI client that launched it; no
  network listener.
- **Money:** none.
- **Private data / secrets:** The operator's own notes on their own machine —
  not a trigger per SELECTOR Step A. No secrets.
- **Irreversible actions:** none outside its own store. `forget` deletes the
  operator's own notes behind an explicit `--yes` guard.
- **Done when:**
  - Text can be stored; word-pair weights are derived from it and inspectable.
  - Typed relations can be asserted and override learned weights.
  - A query returns ranked related terms and ranked notes, reaching terms
    two hops away, each with a human-readable "why" path.
  - An AI can use it over MCP (stdio) and via a single `context` call that
    returns a prompt-ready block within a character budget.
  - Export → import round-trips notes and relations with links intact.
  - Every growing table has a stated bound.
- **Stack** *(chosen, not named)*: Python 3.11+ standard library only
  (`sqlite3`, `json`, `argparse`, `unittest`). Smallest thing that can
  smoke-test with zero installs. See D-002.

## Implied counterparts

| Named | Expected but unstated | Decision | Why |
|---|---|---|---|
| store text (remember) | delete a note (forget) | include | Counterpart of add; operator-only, `--yes` guard; derived weights are decremented exactly. |
| assert a relation (relate) | retract it (unrelate) | include | Counterpart of add; reversible by re-asserting. |
| assert a relation | edit it and recover the previous weight | exclude | Re-asserting overwrites; previous value is shown in the `relate` result so the caller can restore it. A history table is new growth for little gain. |
| store for later | export / import with links still working | include | JSONL of notes + relations. Relations are keyed by term text, not ids, so they survive import. Learned weights are derived and rebuilt on import. |
| weigh relationships | inspect a word's weights and their evidence (neighbors) | include | "Weighs" is only trustworthy if the weights can be seen. |
| pull when relevant | follow links more than one step | include | Category norm for linked data; spreading activation, 2 hops default. |
| pull when relevant | explain why something was pulled | include | An AI deciding whether to trust recalled memory needs the path. |
| dated records | filter recall by date | include | `since` / `until` on recall and context. |
| pull when relevant | learn from which recalls were useful (reinforcement) | exclude | Feedback loops entrench whatever was pulled first and need a decay policy — a behavior choice for the human. Named first in handover. |
| semantic weights | neural embeddings (vector model) | exclude | Needs a model download or network API; violates *Must not*. The other plausible reading of the request; the ranking seam (`weights.py`) is where it would plug in. |
| store words | multi-word phrases as single terms | exclude | Needs phrase detection; single normalized tokens only in v1. |
| usable by other people | privacy policy, licensing of ingested text | exclude | Norms outside software — the human's call; listed in handover. |

## Selector decision

```yaml
class: library
depth: standard
exposure: local-single
asked: none — no human available to answer; SELECTOR Step A rule 1 (one-shot) applied, fewest-trigger reading chosen
reasons:
  - second process: the MCP server runs as a separate process launched by the AI client and shares the SQLite file with the CLI
escalate_if:
  - any network listener (e.g. an HTTP API instead of stdio MCP)
  - storing other people's records, or syncing the DB off the machine (private data)
  - several OS users sharing one DB file (local-shared)
  - reuse of this design as a skeleton
```
