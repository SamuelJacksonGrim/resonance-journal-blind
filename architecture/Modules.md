---
artifact: Modules
status: complete
order: 8
fills: "module list, ownership, responsibilities, boundaries"
depends_on: [Interfaces]
filled_by: both
last_decision: null
---

# Modules — Resonance

| Module | Responsibility | Owns (boundary) | Implements interface |
|--------|----------------|-----------------|----------------------|
| `resonance/text.py` | Normalize text into terms and windowed pair deltas | stopword list, plural folding, `WINDOW=5`, `TOKENIZER_VERSION` | Text analysis |
| `resonance/weights.py` | Decide edge strength | `CONFIDENCE_K=2`, `RELATION_FACTORS` | Edge weighting |
| `resonance/store.py` | Persist; keep the count ledger exact; enforce the pair bound | the SQLite file and every SQL statement; `DEFAULT_MAX_PAIRS`, `NEIGHBOR_CANDIDATES` | Store |
| `resonance/recall.py` | Spreading activation, note scoring, explanation paths | `DECAY=0.5`, `FRONTIER_CAP=32`, `FANOUT=16`, `ACTIVE_CAP=256`, `MAX_HOPS=4` | (internal to facade) |
| `resonance/memory.py` | Validate input; orchestrate; export/import; context packing | input limits (`MAX_NOTE_CHARS`, …) | Resonance library API |
| `resonance/cli.py` | Operator command line | argument parsing, `--yes` guard, exit codes | CLI |
| `resonance/mcp_server.py` | AI client adapter over stdio | tool list and argument allow-list | MCP tools |
| `tests/test_resonance.py` | Prove contracts: ledger, bounds, round-trip, MCP, smoke through real processes | — | — |
