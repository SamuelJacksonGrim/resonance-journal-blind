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
import io
import json
import math
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from resonance import NotFound, Resonance, ValidationError  # noqa: E402
from resonance import mcp_server, text as T, weights as W  # noqa: E402

CORPUS = [
    "The dog chased the cat across the garden. Dogs are loyal companions to people.",
    "A wolf is a wild canine that hunts in packs. The wolf howls at night.",
    "My cat sleeps in the sun on the garden wall all afternoon.",
    "Loyal friends stand by you. Loyal companions matter.",
    "The garden needs water. Tomatoes grow in the garden beside the wall.",
    "Coffee in the morning, then a walk with the dog to the park.",
]


def ledger_ok(mem: Resonance) -> None:
    """Contracts I1 and I2, checked from the raw tables."""
    c = mem.store.conn
    for tid, mass in c.execute("SELECT id, mass FROM terms"):
        s = c.execute("SELECT COALESCE(SUM(count),0) FROM pairs WHERE a=? OR b=?", (tid, tid)).fetchone()[0]
        assert math.isclose(mass, s, abs_tol=1e-6), (tid, mass, s)
    pair_sum = c.execute("SELECT COALESCE(SUM(count),0) FROM pairs").fetchone()[0]
    assert math.isclose(mem.store.total(), 2 * pair_sum, abs_tol=1e-6)
    for tid, df in c.execute("SELECT id, df FROM terms"):
        n = c.execute("SELECT COUNT(*) FROM postings WHERE term_id=?", (tid,)).fetchone()[0]
        assert df == n and df > 0, (tid, df, n)
    assert c.execute("SELECT COUNT(*) FROM pairs WHERE count <= 0").fetchone()[0] == 0


class Base(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.path = Path(self.dir.name) / "sub" / "r.db"
        self.mem = Resonance(self.path)

    def tearDown(self):
        self.mem.close()
        self.dir.cleanup()

    def load(self):
        return [self.mem.remember(t)["id"] for t in CORPUS]


class TextTests(unittest.TestCase):
    def test_fold(self):
        self.assertEqual([T.fold(w) for w in ["dogs", "berries", "boxes", "glass", "bus", "analysis", "cat"]],
                         ["dog", "berry", "box", "glass", "bus", "analysis", "cat"])

    def test_stopwords_possessive_and_digits(self):
        self.assertEqual(T.terms("The dog's 42 bones are in THE yard"), ["dog", "bone", "yard"])

    def test_pairs_window_and_sentence_boundary(self):
        pairs, tf = T.analyze("alpha beta gamma. delta")
        self.assertEqual(pairs[("alpha", "beta")], 1.0)
        self.assertEqual(pairs[("alpha", "gamma")], 0.5)
        self.assertNotIn(("alpha", "delta"), pairs)
        self.assertNotIn(("beta", "delta"), pairs)
        self.assertEqual(tf["delta"], 1)

    def test_window_limit(self):
        words = "w0 w1 w2 w3 w4 w5 w6".replace("w", "word")
        pairs, _ = T.analyze(words)
        self.assertIn(("word0", "word5"), pairs)
        self.assertNotIn(("word0", "word6"), pairs)


class AccentTests(Base):
    def test_fold_accents_latin(self):
        for raw, want in [("Zürich", "zurich"), ("café", "cafe"), ("naïve", "naive"),
                          ("Straße", "strasse"), ("Ørsted", "orsted"), ("ﬁle", "file"),
                          ("ÉTÉ", "ete")]:
            self.assertEqual(T.fold_accents(raw), want, raw)

    def test_non_latin_marks_kept(self):
        for word in ["हिन्दी", "ภาษาไทย", "Москва", "東京"]:
            self.assertEqual(T.fold_accents(word), word.casefold(), word)

    def test_recall_matches_either_spelling(self):
        self.mem.remember("Café owners in Zürich serve strong coffee.")
        for q in ("zurich", "ZÜRICH", "Zurich", "zürich"):
            terms = [t["term"] for t in self.mem.recall(q)["terms"]]
            self.assertIn("zurich", terms, q)
        self.assertEqual(self.mem.relate("café", "coffee", "related")["a"], "cafe")

    def test_upgrade_rekeys_relations(self):
        self.mem.remember("Café owners in Zürich serve strong coffee.")
        c = self.mem.store.conn
        with self.mem.store.tx():  # simulate a v1 store: accented keys, old version
            c.execute("INSERT INTO relations(a,b,type,weight,created_at) VALUES"
                      "('zürich','city','is_a',0.9,'2026-01-01T00:00:00Z'),"
                      "('café','cafe','synonym',1.0,'2026-01-01T00:00:00Z')")
            self.mem.store.set_meta("tokenizer_version", "1")
        self.mem.close()
        import contextlib
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            self.mem = Resonance(self.path)
        rels = {(r["a"], r["b"]) for r in self.mem.store.iter_relations()}
        self.assertIn(("zurich", "city"), rels)
        self.assertNotIn(("zürich", "city"), rels)
        self.assertFalse(any(a == b for a, b in rels))
        self.assertIn("1 relation(s) re-keyed, 1 collapsed", err.getvalue())
        pulled = {t["term"] for t in self.mem.recall("city")["terms"]}
        self.assertIn("zurich", pulled)
        ledger_ok(self.mem)


class WeightTests(unittest.TestCase):
    def test_npmi_bounds(self):
        self.assertEqual(W.npmi(0, 1, 1, 10), 0.0)
        self.assertLessEqual(W.npmi(5, 5, 5, 10), 1.0)
        self.assertGreaterEqual(W.npmi(1, 100, 100, 1000), -1.0)

    def test_confidence_damps_single_sightings(self):
        rare, _, _ = W.learned_weight(1, 1, 1, 100)       # hapax pair, NPMI = 1
        common, _, _ = W.learned_weight(10, 12, 12, 100)  # well attested
        self.assertLess(rare, common)

    def test_asserted_overrides_and_zero_suppresses(self):
        learned = {"x": W.Edge("x", 0.5, "learned")}
        self.assertEqual(W.combine(learned, {}), [learned["x"]])
        self.assertEqual(W.combine(learned, {"x": W.Edge("x", 0.0, "asserted", relation="related")}), [])


class StoreTests(Base):
    def test_file_permissions(self):
        self.assertEqual(stat.S_IMODE(os.stat(self.path).st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(os.stat(self.path.parent).st_mode), 0o700)

    def test_ledger_after_ingest_and_forget(self):
        ids = self.load()
        ledger_ok(self.mem)
        before = self.mem.stats()
        self.mem.forget(ids[0])
        ledger_ok(self.mem)
        self.assertEqual(self.mem.stats()["notes"], before["notes"] - 1)
        for i in ids[1:]:
            self.mem.forget(i)
        ledger_ok(self.mem)
        s = self.mem.stats()
        self.assertEqual((s["notes"], s["terms"], s["pairs"], s["total_mass"]), (0, 0, 0, 0.0))

    def test_duplicate_does_not_double_count(self):
        self.mem.remember(CORPUS[0])
        before = self.mem.stats()
        r = self.mem.remember("  " + CORPUS[0] + "\n")
        self.assertTrue(r["duplicate"])
        self.assertEqual(self.mem.stats(), before)

    def test_remember_many_is_one_transaction(self):
        r = self.mem.remember_many(CORPUS + [CORPUS[0]])
        self.assertEqual((r["notes"], r["duplicates"]), (len(CORPUS), 1))
        ledger_ok(self.mem)
        before = self.mem.stats()
        with self.assertRaises(ValidationError):
            self.mem.remember_many(["fresh words entirely", ""])  # rejected before any write
        self.assertEqual(self.mem.stats(), before)

    def test_prune_bound_keeps_ledger(self):
        self.mem.close()
        self.mem = Resonance(self.path, max_pairs=40)
        self.load()
        self.assertLessEqual(self.mem.stats()["pairs"], 40)
        ledger_ok(self.mem)
        # Forget after pruning must not drive anything negative.
        for row in list(self.mem.store.iter_notes()):
            self.mem.forget(row["id"])
            ledger_ok(self.mem)

    def test_rebuild_matches_fresh_ingest(self):
        self.load()
        c = self.mem.store.conn
        snap = lambda: sorted((*sorted((r[0], r[1])), r[2]) for r in c.execute(  # noqa: E731
            "SELECT ta.text, tb.text, round(p.count, 6) FROM pairs p "
            "JOIN terms ta ON ta.id=p.a JOIN terms tb ON tb.id=p.b"))
        before = snap()
        self.mem.rebuild()
        self.assertEqual(snap(), before)
        ledger_ok(self.mem)

    def test_tokenizer_version_change_rebuilds(self):
        self.load()
        with self.mem.store.tx():
            self.mem.store.set_meta("tokenizer_version", "0")
            self.mem.store.conn.execute("DELETE FROM pairs")  # simulate stale derived data
        self.mem.close()
        import contextlib
        with contextlib.redirect_stderr(io.StringIO()):
            self.mem = Resonance(self.path)
        self.assertGreater(self.mem.stats()["pairs"], 0)
        ledger_ok(self.mem)

    def test_rollback_on_failure(self):
        self.load()
        before = self.mem.stats()
        orig = self.mem.store.add_contribution

        def boom(*a, **k):
            orig(*a, **k)
            raise RuntimeError("injected")
        self.mem.store.add_contribution = boom
        with self.assertRaises(RuntimeError):
            self.mem.remember("entirely new words about volcanoes and lava")
        self.mem.store.add_contribution = orig
        self.assertEqual(self.mem.stats(), before)
        ledger_ok(self.mem)


class ApiTests(Base):
    def test_validation(self):
        bad = [
            lambda: self.mem.remember(""),
            lambda: self.mem.remember("x" * 100_001),
            lambda: self.mem.remember("ok text", importance=2),
            lambda: self.mem.remember("ok text", created_at="yesterday"),
            lambda: self.mem.relate("dog", "big cat"),
            lambda: self.mem.relate("the", "dog"),
            lambda: self.mem.relate("dog", "dogs"),
            lambda: self.mem.relate("dog", "cat", "friend_of"),
            lambda: self.mem.relate("dog", "cat", weight=1.5),
            lambda: self.mem.recall(""),
            lambda: self.mem.recall("dog", hops=9),
            lambda: self.mem.recall("dog", limit=0),
            lambda: self.mem.context("dog", budget_chars=10),
        ]
        for f in bad:
            with self.assertRaises(ValidationError):
                f()
        with self.assertRaises(NotFound):
            self.mem.forget("nope")

    def test_error_messages_never_contain_note_text(self):
        secret = "zanzibar-" + "q" * 100_000
        with self.assertRaises(ValidationError) as cm:
            self.mem.remember(secret)
        self.assertNotIn("zanzibar", str(cm.exception))

    def test_neighbors_evidence(self):
        self.load()
        r = self.mem.neighbors("garden")
        self.assertTrue(r["neighbors"])
        ws = [e["weight"] for e in r["neighbors"]]
        self.assertEqual(ws, sorted(ws, reverse=True))
        self.assertTrue(all(0 < w <= 1 for w in ws))
        self.assertIn("npmi", r["neighbors"][0])

    def test_relate_returns_previous_and_suppresses(self):
        self.load()
        self.assertIn("cat", [e["term"] for e in self.mem.neighbors("garden")["neighbors"]])
        first = self.mem.relate("garden", "cat", "related", 0.9)
        self.assertNotIn("previous", first)
        second = self.mem.relate("garden", "cat", "related", 0)
        self.assertEqual(second["previous"], {"type": "related", "weight": 0.9})
        self.assertNotIn("cat", [e["term"] for e in self.mem.neighbors("garden")["neighbors"]])
        self.mem.unrelate("garden", "cat")
        self.assertIn("cat", [e["term"] for e in self.mem.neighbors("garden")["neighbors"]])

    def test_recall_two_hops_with_path(self):
        self.load()
        self.mem.relate("dog", "canine", "is_a", 1.0)
        r = self.mem.recall("canine", limit=10, hops=2)
        terms = {t["term"]: t for t in r["terms"]}
        self.assertIn("loyal", terms)  # canine → dog → loyal: two hops
        self.assertEqual(terms["loyal"]["why"].split()[0], "canine")
        self.assertIn("is_a", terms["loyal"]["why"])
        texts = [n["text"] for n in r["notes"]]
        self.assertIn(CORPUS[0], texts)  # reached only through the asserted link
        self.assertTrue(all(n["matched"] for n in r["notes"]))

        r0 = self.mem.recall("canine", hops=0)
        self.assertEqual([t["term"] for t in r0["terms"]], ["canine"])

    def test_recall_unknown_query_is_empty_not_error(self):
        self.load()
        r = self.mem.recall("quasar nebula")
        self.assertEqual((r["seeds"], r["notes"]), ([], []))
        self.assertEqual(r["unknown"], ["quasar", "nebula"])

    def test_importance_and_date_filter(self):
        a = self.mem.remember("rust borrow checker lifetimes", importance=0.0,
                              created_at="2024-01-01")["id"]
        b = self.mem.remember("rust borrow checker ownership", importance=1.0,
                              created_at="2026-01-01")["id"]
        r = self.mem.recall("borrow checker")
        self.assertEqual([n["id"] for n in r["notes"]][:2], [b, a])
        r = self.mem.recall("borrow checker", until="2025-01-01")
        self.assertEqual([n["id"] for n in r["notes"]], [a])
        r = self.mem.recall("borrow checker", since="2025-06-01")
        self.assertEqual([n["id"] for n in r["notes"]], [b])

    def test_context_budget(self):
        self.load()
        for budget in (200, 300, 1000, 4000):
            out = self.mem.context("garden dog", budget_chars=budget)
            self.assertLessEqual(len(out), budget)
            self.assertTrue(out.startswith("[resonance]"))
        self.assertIn(CORPUS[4], self.mem.context("garden", budget_chars=4000))

    def test_export_import_roundtrip(self):
        self.load()
        self.mem.relate("dog", "canine", "is_a", 0.9)
        buf = io.StringIO()
        self.assertEqual(self.mem.export(buf), {"notes": len(CORPUS), "relations": 1})
        other = Resonance(Path(self.dir.name) / "other.db")
        try:
            r = other.import_(io.StringIO(buf.getvalue()))
            self.assertEqual((r["notes"], r["relations"], r["errors"]), (len(CORPUS), 1, []))
            self.assertEqual(other.stats()["pairs"], self.mem.stats()["pairs"])
            self.assertAlmostEqual(other.stats()["total_mass"], self.mem.stats()["total_mass"], places=3)
            self.assertEqual(other.recall("canine")["notes"][0]["id"],
                             self.mem.recall("canine")["notes"][0]["id"])
            again = other.import_(io.StringIO(buf.getvalue()))
            self.assertEqual(again["duplicates"], len(CORPUS))
            bad = other.import_(io.StringIO('{"kind":"note","text":""}\nnot json\n'))
            self.assertEqual(len(bad["errors"]), 2)
            ledger_ok(other)
        finally:
            other.close()


class McpTests(Base):
    def rpc(self, method, params=None, mid=1):
        msg = {"jsonrpc": "2.0", "id": mid, "method": method}
        if params is not None:
            msg["params"] = params
        return mcp_server.handle(self.mem, msg)

    def test_handshake_and_tools(self):
        r = self.rpc("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                    "clientInfo": {"name": "t", "version": "0"}})
        self.assertEqual(r["result"]["serverInfo"]["name"], "resonance")
        self.assertIsNone(mcp_server.handle(self.mem, {"jsonrpc": "2.0",
                                                       "method": "notifications/initialized"}))
        names = {t["name"] for t in self.rpc("tools/list")["result"]["tools"]}
        self.assertEqual(names, {"context", "recall", "neighbors", "remember", "relate", "stats"})
        self.assertNotIn("forget", names)
        self.assertNotIn("unrelate", names)

    def test_tool_calls(self):
        call = lambda name, args: self.rpc("tools/call", {"name": name, "arguments": args})["result"]  # noqa
        r = call("remember", {"text": CORPUS[0], "importance": 0.8})
        self.assertFalse(r.get("isError"))
        call("remember", {"text": CORPUS[1]})
        call("relate", {"a": "dog", "b": "canine", "type": "is_a"})
        ctx = call("context", {"query": "canine", "budget_chars": 500})["content"][0]["text"]
        self.assertIn("dog chased", ctx)
        rec = json.loads(call("recall", {"query": "wolf"})["content"][0]["text"])
        self.assertTrue(rec["notes"])
        err = call("forget", {"id": "x"})
        self.assertTrue(err["isError"])
        err = call("remember", {"text": "hi", "created_at": "2020-01-01"})
        self.assertTrue(err["isError"])
        err = call("recall", {"query": "dog", "hops": 99})
        self.assertTrue(err["isError"])

    def test_protocol_errors(self):
        self.assertEqual(self.rpc("nope")["error"]["code"], -32601)
        self.assertEqual(mcp_server.handle(self.mem, {"id": 1})["error"]["code"], -32600)
        out = io.StringIO()
        mcp_server.serve(self.mem, io.StringIO("not json\n\n"), out)
        self.assertEqual(json.loads(out.getvalue())["error"]["code"], -32700)


class SmokeTests(unittest.TestCase):
    """Main path through the real processes: CLI writes, MCP server reads."""

    def test_cli_and_mcp_subprocess(self):
        with tempfile.TemporaryDirectory() as d:
            db = str(Path(d) / "s.db")
            run = lambda *a, **k: subprocess.run(  # noqa: E731
                [sys.executable, "-m", "resonance", "--db", db, *a], cwd=ROOT,
                capture_output=True, text=True, **k)
            self.assertEqual(run("remember", CORPUS[0]).returncode, 0)
            f = Path(d) / "notes.txt"
            f.write_text("\n\n".join(CORPUS[1:]), encoding="utf-8")
            out = run("--json", "ingest", "--split", str(f))
            self.assertEqual(json.loads(out.stdout), {"notes": len(CORPUS) - 1, "duplicates": 0})
            self.assertEqual(run("relate", "dog", "is_a", "canine").returncode, 0)
            out = run("recall", "canine")
            self.assertEqual(out.returncode, 0, out.stderr)
            self.assertIn("is_a", out.stdout)
            self.assertEqual(run("forget", "whatever").returncode, 2)  # no --yes

            msgs = [
                {"jsonrpc": "2.0", "id": 1, "method": "initialize",
                 "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                            "clientInfo": {"name": "smoke", "version": "0"}}},
                {"jsonrpc": "2.0", "method": "notifications/initialized"},
                {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                 "params": {"name": "context", "arguments": {"query": "canine loyal"}}},
            ]
            p = subprocess.run([sys.executable, "-m", "resonance.mcp_server", "--db", db], cwd=ROOT,
                               input="".join(json.dumps(m) + "\n" for m in msgs),
                               capture_output=True, text=True, timeout=30)
            replies = [json.loads(l) for l in p.stdout.splitlines()]
            self.assertEqual([r["id"] for r in replies], [1, 2])
            self.assertIn("dog chased", replies[1]["result"]["content"][0]["text"])


if __name__ == "__main__":
    unittest.main()
