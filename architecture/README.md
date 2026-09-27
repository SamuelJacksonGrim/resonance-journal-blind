---
artifact: README
status: complete
order: 10
fills: "front door — what/why/problem/components for the instantiated system"
depends_on: [Architecture, Flows, Contracts]
filled_by: both
last_decision: D-009
---

# Resonance — design front door

## What is this?
A local memory for AI agents. It stores passages of text, weighs how strongly
words are related (learned from the text, plus relations you or the AI
assert), and answers "what do I know that's relevant to this?" by following
the strongest word links a couple of steps out, with the path shown.

## Why does it exist?
An AI's context window is small and forgets between sessions. Keyword search
misses notes that use different words for the same idea; vector databases need
an embedding model and hide *why* something matched. Resonance sits between:
zero-install, fully local, and every result is explainable.

## What problem does it solve?
"The note I need says *canine*, but I asked about *dogs*." Once `dog is_a
canine` is asserted — or once the two words keep appearing near the same
words — recall reaches across that gap and says how it got there.

## Major components
From [`Modules.md`](Modules.md): `text` (what a word is), `weights` (how strong
a link is), `store` (SQLite, the count ledger), `recall` (spreading
activation), `memory` (the `Resonance` API and input validation), `cli` and
`mcp_server` (operator and AI adapters). See [`Architecture.md`](Architecture.md)
and [`diagrams/architecture_graph.md`](diagrams/architecture_graph.md).

Usage is in the project [README](../README.md). The Intent Card is
[`../INTENT.md`](../INTENT.md).

## Slices
All slices in the Intent Card are built: remember/ingest, forget, relate/
unrelate, neighbors, recall, context, export/import, rebuild, MCP server.

## Artifact status
| Artifact | Status |
|----------|--------|
| Architecture | complete |
| Flows | complete |
| Contracts | complete |
| Types | complete |
| Schemas | complete |
| Interfaces | complete |
| Modules | complete |
| Dependencies | complete |
| DecisionLog | complete |
| README | complete |
