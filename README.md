# Resonance

[![License: AGPL-3.0-only](https://img.shields.io/badge/license-AGPL--3.0--only-blue)](LICENSE)
[![dual-license](https://img.shields.io/badge/dual--license-AGPL--3.0--only%20or%20commercial-blueviolet)](LICENSING.md)
[![Python](https://img.shields.io/badge/python-%3E%3D3.11-3776AB?logo=python&logoColor=white)](pyproject.toml)
[![dependencies](https://img.shields.io/badge/dependencies-none-brightgreen)](pyproject.toml)
[![MCP server](https://img.shields.io/badge/MCP-server-111111)](https://modelcontextprotocol.io/)
[![built with](https://img.shields.io/badge/built%20with-Architecture--Blueprints--Frameworks-orange)](https://github.com/SamuelJacksonGrim/Architecture-Blueprints-Frameworks)

## License

This project is dual-licensed under **AGPL-3.0-only** OR a commercial license.

- [LICENSE](LICENSE): GNU AGPL-3.0-only (the free track)
- [LICENSING.md](LICENSING.md): how the two tracks work
- [COMMERCIAL-LICENSE.md](COMMERCIAL-LICENSE.md): the commercial agreement
- [NOTICE](NOTICE): copyright, SPDX identifier, and provenance
- [legal/AUTHORSHIP.md](legal/AUTHORSHIP.md): how this work was made

Weighted semantic memory an AI can pull from when relevant.

Resonance stores notes, learns how strongly words are related from the text
around them, lets you (or an AI) assert relationships like `car synonym
automobile`, and answers queries by following the strongest links a couple of
steps out. Every result says *why* it was pulled. Everything stays in one
local SQLite file. Python 3.11+, no dependencies.

## Install

```sh
pip install -e .          # gives you `resonance` and `resonance-mcp`
# or run without installing:
python -m resonance --help
```

The database defaults to `~/.resonance/resonance.db` (created `0600`).
Override with `--db PATH` or `RESONANCE_DB=PATH`.

## Use it

```sh
resonance remember "The dog chased the cat across the garden."
resonance remember "A wolf is a wild canine that hunts in packs."
resonance ingest --split journal.txt           # one note per paragraph, one transaction
resonance relate dog is_a canine               # synonym | antonym | is_a | part_of | related
resonance neighbors dog                        # weighted links, with evidence
resonance recall "canine" --hops 2             # ranked terms + notes + paths
resonance context "canine" --budget 2000       # prompt-ready block, ≤ 2000 chars
resonance relate garden cat --weight 0         # weight 0 suppresses a spurious learned link
resonance export backup.jsonl                  # notes + relations
resonance import backup.jsonl
resonance forget <note-id> --yes               # operator only; export first if unsure
resonance stats
```

Add `--json` before the verb for machine-readable output.

Example `recall` output:

```
related terms:
  1.1762  canine               canine
  0.4000  dog                  canine —is_a 0.80→ dog
  0.0280  chased               canine —is_a 0.80→ dog —learned 0.14→ chased
notes:
  [8bffa44cfc4f440d] 0.2875  2026-09-27  The dog chased the cat across the garden. …
      via canine —is_a 0.80→ dog
```

## Connect an AI (MCP)

Resonance ships an MCP server that speaks over stdio. Example client config:

```json
{
  "mcpServers": {
    "resonance": {
      "command": "resonance-mcp",
      "args": ["--db", "/home/you/.resonance/resonance.db"]
    }
  }
}
```

For Claude Code: `claude mcp add resonance -- resonance-mcp`.

Tools offered: `context` (best first call), `recall`, `neighbors`, `remember`,
`relate`, `stats`. The AI can add memory and assert relations; it cannot
delete anything. Deleting is `resonance forget --yes` from your shell.

## Use it as a library

```python
from resonance import Resonance

with Resonance("memory.db") as mem:
    mem.remember("Espresso is brewed by forcing hot water through fine coffee.")
    mem.relate("espresso", "coffee", "is_a")
    print(mem.context("coffee brewing", budget_chars=1500))
```

## How the weights work

- **Learned:** words within 5 tokens of each other in the same sentence
  accumulate `1/distance`. At query time the strength is normalized PMI (how
  much more often they co-occur than chance), damped by `count/(count+2)` so a
  single sighting can't outrank a well-attested pair. Range 0–1.
- **Asserted:** `type factor × weight` (synonym 1.0, is_a 0.8, part_of 0.7,
  related 0.6, antonym 0.4). An asserted relation replaces the learned weight
  for that pair.
- **Recall:** query words start with activation proportional to their rarity;
  activation flows along the 16 strongest links of each node, halving each
  hop. Notes are ranked by the activation of the words they contain.

Limits: the learned-pair table is capped at 1 000 000 rows (`max_pairs`); the
weakest pairs are pruned past that. Notes are never deleted automatically.
English stopwords and plural folding; other languages work, less precisely.

## Test

```sh
python -m unittest discover -s tests -v
```

Design docs: [`architecture/`](architecture/README.md) · Intent: [`INTENT.md`](INTENT.md).
Built with the [Architecture-Blueprints-Frameworks](https://github.com/SamuelJacksonGrim/Architecture-Blueprints-Frameworks) method.

## The two license tracks

**Dual-licensed.** You pick one. If the AGPL works for you, you owe nothing.

1. **[AGPL-3.0](LICENSE)** is free. You can use, run, modify, fork, and
   redistribute this software at no charge. The copyleft catch is AGPL §13: if
   you *modify* it and let other people interact with it over a network (SaaS,
   an API, a hosted service), you must make the complete corresponding source of
   your modified version available to those users under the AGPL-3.0.
2. **A [paid commercial license](LICENSING.md)** covers closed-source,
   proprietary, or hosted use without the AGPL's source-disclosure obligations.
   Contact Samuel Jackson Grim, `samgrim97@gmail.com`, subject
   `Commercial license — Resonance (resonance-journal-blind)`.

This README is not a contract. The binding terms are [`LICENSE`](LICENSE) and a
signed commercial agreement, if you buy one. Contributing:
[`CONTRIBUTING.md`](CONTRIBUTING.md).
