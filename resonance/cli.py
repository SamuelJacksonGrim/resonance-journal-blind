# Resonance (resonance-journal-blind)
# Copyright (C) 2026 Samuel Jackson Grim
# SPDX-License-Identifier: AGPL-3.0-only OR LicenseRef-Commercial
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, version 3 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
# A commercial license is also available: see LICENSING.md.
"""Operator CLI: every verb, including the destructive ones behind --yes."""

from __future__ import annotations

import argparse
import json
import sys

from .memory import NotFound, Resonance, ValidationError, default_db_path
from .weights import RELATION_TYPES


def _print(obj, as_json: bool) -> None:
    if as_json or not isinstance(obj, (dict, str)):
        print(json.dumps(obj, indent=2, ensure_ascii=False))
    elif isinstance(obj, str):
        print(obj, end="" if obj.endswith("\n") else "\n")
    else:
        for k, v in obj.items():
            print(f"{k}: {v}")


def _print_recall(r: dict) -> None:
    if not r["seeds"]:
        print("no known terms in query" + (f" (unknown: {', '.join(r['unknown'])})" if r["unknown"] else ""))
        return
    print("related terms:")
    for t in r["terms"]:
        print(f"  {t['activation']:.4f}  {t['term']:<20} {t['why']}")
    print("\nnotes:")
    for n in r["notes"]:
        snippet = " ".join(n["text"].split())
        snippet = snippet if len(snippet) <= 160 else snippet[:157] + "..."
        print(f"  [{n['id']}] {n['score']:.4f}  {n['created_at'][:10]}  {snippet}")
        for m in n["matched"][:4]:
            print(f"      via {m['why']}")


def _print_neighbors(r: dict) -> None:
    print(f"neighbors of '{r['term']}':")
    for e in r["neighbors"]:
        if e["source"] == "learned":
            ev = f"learned  count={e['count']} npmi={e['npmi']} conf={e['confidence']}"
        else:
            ev = f"asserted {e['relation']} ({e['direction']})"
        print(f"  {e['weight']:.4f}  {e['term']:<20} {ev}")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="resonance", description="Weighted semantic memory for AI recall.")
    p.add_argument("--db", default=None, help=f"database path (default: $RESONANCE_DB or {default_db_path()})")
    p.add_argument("--json", action="store_true", help="machine-readable output")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("remember", help="store a note (text argument, or stdin with '-')")
    s.add_argument("text")
    s.add_argument("--source")
    s.add_argument("--importance", type=float, default=0.5)
    s.add_argument("--date", dest="created_at")

    s = sub.add_parser("ingest", help="store each file (or each paragraph with --split) as notes")
    s.add_argument("files", nargs="+")
    s.add_argument("--split", action="store_true", help="one note per blank-line-separated paragraph")
    s.add_argument("--importance", type=float, default=0.5)

    s = sub.add_parser("recall", help="ranked terms and notes relevant to a query")
    s.add_argument("query")
    s.add_argument("--limit", type=int, default=5)
    s.add_argument("--hops", type=int, default=2)
    s.add_argument("--since")
    s.add_argument("--until")

    s = sub.add_parser("context", help="prompt-ready memory block for a query")
    s.add_argument("query")
    s.add_argument("--budget", type=int, default=4000)
    s.add_argument("--limit", type=int, default=8)
    s.add_argument("--since")
    s.add_argument("--until")

    s = sub.add_parser("neighbors", help="weighted relationships of one word, with evidence")
    s.add_argument("term")
    s.add_argument("--limit", type=int, default=20)

    s = sub.add_parser("relate", help="assert a typed relationship (overrides learned weight)")
    s.add_argument("a")
    s.add_argument("type", choices=RELATION_TYPES)
    s.add_argument("b")
    s.add_argument("--weight", type=float, default=1.0)

    s = sub.add_parser("unrelate", help="remove an asserted relationship")
    s.add_argument("a")
    s.add_argument("b")

    s = sub.add_parser("forget", help="delete a note (irreversible without an export)")
    s.add_argument("id")
    s.add_argument("--yes", action="store_true", help="confirm deletion")

    s = sub.add_parser("export", help="write notes + relations as JSONL")
    s.add_argument("file", help="output path, or '-' for stdout")

    s = sub.add_parser("import", help="read JSONL produced by export")
    s.add_argument("file", help="input path, or '-' for stdin")

    sub.add_parser("rebuild", help="recompute learned counts from notes")
    sub.add_parser("stats", help="table sizes and bounds")
    return p


def _paragraphs(text: str) -> list[str]:
    return [p.strip() for p in text.split("\n\n") if p.strip()]


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        with Resonance(args.db) as mem:
            c = args.cmd
            if c == "remember":
                text = sys.stdin.read() if args.text == "-" else args.text
                _print(mem.remember(text, source=args.source, importance=args.importance,
                                    created_at=args.created_at), args.json)
            elif c == "ingest":
                done = {"notes": 0, "duplicates": 0}
                for f in args.files:
                    with open(f, encoding="utf-8") as fh:
                        body = fh.read()
                    r = mem.remember_many(_paragraphs(body) if args.split else [body],
                                          source=f, importance=args.importance)
                    for k in done:
                        done[k] += r[k]
                _print(done, args.json)
            elif c == "recall":
                r = mem.recall(args.query, limit=args.limit, hops=args.hops,
                               since=args.since, until=args.until)
                _print(r, True) if args.json else _print_recall(r)
            elif c == "context":
                out = mem.context(args.query, budget_chars=args.budget, limit=args.limit,
                                  since=args.since, until=args.until)
                _print({"context": out} if args.json else out, args.json)
            elif c == "neighbors":
                r = mem.neighbors(args.term, args.limit)
                _print(r, True) if args.json else _print_neighbors(r)
            elif c == "relate":
                _print(mem.relate(args.a, args.b, args.type, args.weight), args.json)
            elif c == "unrelate":
                _print(mem.unrelate(args.a, args.b), args.json)
            elif c == "forget":
                if not args.yes:
                    print("refusing to delete without --yes (export first if you may want it back)",
                          file=sys.stderr)
                    return 2
                _print(mem.forget(args.id), args.json)
            elif c == "export":
                if args.file == "-":
                    r = mem.export(sys.stdout)
                else:
                    with open(args.file, "w", encoding="utf-8") as fh:
                        r = mem.export(fh)
                print(json.dumps(r), file=sys.stderr)
            elif c == "import":
                if args.file == "-":
                    r = mem.import_(sys.stdin)
                else:
                    with open(args.file, encoding="utf-8") as fh:
                        r = mem.import_(fh)
                _print(r, args.json)
                return 1 if r["errors"] else 0
            elif c == "rebuild":
                _print(mem.rebuild(), args.json)
            elif c == "stats":
                _print(mem.stats(), args.json)
    except ValidationError as e:
        print(f"invalid input: {e}", file=sys.stderr)
        return 2
    except NotFound as e:
        print(str(e), file=sys.stderr)
        return 1
    except OSError as e:
        print(f"file error: {e.strerror}: {e.filename}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
