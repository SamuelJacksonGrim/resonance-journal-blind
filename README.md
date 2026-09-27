# Resonance

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
