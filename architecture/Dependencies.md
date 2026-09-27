---
artifact: Dependencies
status: complete
order: 9
fills: "allowed/forbidden dependency directions, hierarchy, import rules"
depends_on: [Modules, Interfaces]
filled_by: both
last_decision: D-002
---

# Dependencies — Resonance

## Module Hierarchy
```
adapters:   cli.py        mcp_server.py
               \            /
facade:          memory.py
               /     |      \
core:     recall.py  |    text.py
            /   \    |
       weights.py  store.py
```
External: Python standard library only (D-002). No third-party packages.

## Allowed Directions
- `cli`, `mcp_server` → `memory`, `weights` (for the `RELATION_TYPES` enum only)
- `memory` → `recall`, `store`, `text`, `weights`
- `recall` → `weights`, `store` (read methods only)

## Forbidden Directions
- **Adapters → `store`**: would bypass input validation (S2) and the MCP
  write restriction (D-004).
- **Anything → `sqlite3` except `store`**: keeps S1 auditable in one file.
- **`weights`, `text` → any project module**: they are pure; importing I/O
  would make weights depend on state they do not own.
- **`recall` → `Store` write methods** (`tx`, `add_*`, `remove_*`, `upsert_*`,
  `prune_*`): recall is read-only (Contracts guardrail).

## Import Rules
- No cycles. Imports only point down the hierarchy above.
- New third-party dependencies require a DecisionLog entry (they change the
  "zero install" smoke test).
