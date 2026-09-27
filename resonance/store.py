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
"""SQLite persistence. The only module that speaks SQL.

Owns the count ledger (Contracts I1): pair counts, per-term mass, and the
total always move together inside one transaction.
"""

from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterable, Iterator

DEFAULT_MAX_PAIRS = 1_000_000
PRUNE_TARGET = 0.9          # prune down to 90% of the cap, so it does not fire every write
NEIGHBOR_CANDIDATES = 512   # learned candidates scanned per neighbor lookup (Contracts G4)
EPS = 1e-9

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS notes (
    id TEXT PRIMARY KEY,
    text TEXT NOT NULL,
    content_hash TEXT NOT NULL UNIQUE,
    source TEXT,
    importance REAL NOT NULL,
    created_at TEXT NOT NULL,
    n_terms INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS notes_created ON notes(created_at);
CREATE TABLE IF NOT EXISTS terms (
    id INTEGER PRIMARY KEY,
    text TEXT NOT NULL UNIQUE,
    df INTEGER NOT NULL DEFAULT 0,
    mass REAL NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS pairs (
    a INTEGER NOT NULL,
    b INTEGER NOT NULL,
    count REAL NOT NULL,
    PRIMARY KEY (a, b),
    CHECK (a < b)
) WITHOUT ROWID;
CREATE INDEX IF NOT EXISTS pairs_b ON pairs(b, count);
CREATE INDEX IF NOT EXISTS pairs_a ON pairs(a, count);
CREATE TABLE IF NOT EXISTS postings (
    term_id INTEGER NOT NULL,
    note_id TEXT NOT NULL,
    tf INTEGER NOT NULL,
    PRIMARY KEY (term_id, note_id)
) WITHOUT ROWID;
CREATE INDEX IF NOT EXISTS postings_note ON postings(note_id);
CREATE TABLE IF NOT EXISTS relations (
    a TEXT NOT NULL,
    b TEXT NOT NULL,
    type TEXT NOT NULL,
    weight REAL NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (a, b)
);
CREATE INDEX IF NOT EXISTS relations_b ON relations(b);
-- Exact pair-row counter for the I5 bound; COUNT(*) is O(pairs) per write.
INSERT OR IGNORE INTO meta(key, value) VALUES('pair_rows', (SELECT COUNT(*) FROM pairs));
CREATE TRIGGER IF NOT EXISTS pairs_ins AFTER INSERT ON pairs BEGIN
    UPDATE meta SET value = CAST(value AS INTEGER) + 1 WHERE key = 'pair_rows';
END;
CREATE TRIGGER IF NOT EXISTS pairs_del AFTER DELETE ON pairs BEGIN
    UPDATE meta SET value = CAST(value AS INTEGER) - 1 WHERE key = 'pair_rows';
END;
"""


def _placeholders(n: int) -> str:
    # The only dynamic SQL: a run of '?' sized from a list length (Contracts S1).
    return ",".join("?" * n)


def _secure_path(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if not path.exists():
        fd = os.open(path, os.O_CREAT | os.O_WRONLY, 0o600)
        os.close(fd)


def _secure_sidecars(path: Path) -> None:
    for suffix in ("", "-wal", "-shm"):
        p = Path(str(path) + suffix)
        if p.exists():
            os.chmod(p, 0o600)


class Store:
    def __init__(self, path: str | os.PathLike, max_pairs: int = DEFAULT_MAX_PAIRS):
        self.path = Path(path).expanduser()
        self.max_pairs = max_pairs
        if str(path) != ":memory:":
            _secure_path(self.path)
        self.conn = sqlite3.connect(str(path), timeout=5.0, isolation_level=None)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=NORMAL")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.conn.executescript(SCHEMA)
        if str(path) != ":memory:":
            _secure_sidecars(self.path)

    def close(self) -> None:
        self.conn.close()

    @contextmanager
    def tx(self) -> Iterator[sqlite3.Connection]:
        """One write transaction (Contracts G6). IMMEDIATE takes the write lock up
        front so two processes cannot interleave read-then-write."""
        self.conn.execute("BEGIN IMMEDIATE")
        try:
            yield self.conn
        except BaseException:
            self.conn.execute("ROLLBACK")
            raise
        self.conn.execute("COMMIT")

    # --- meta -------------------------------------------------------------

    def get_meta(self, key: str, default: str | None = None) -> str | None:
        row = self.conn.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        return row["value"] if row else default

    def set_meta(self, key: str, value: str) -> None:
        self.conn.execute(
            "INSERT INTO meta(key, value) VALUES(?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value))

    def total(self) -> float:
        return float(self.get_meta("total", "0"))

    def _add_total(self, delta: float) -> None:
        self.set_meta("total", repr(max(0.0, self.total() + delta)))

    # --- notes ------------------------------------------------------------

    def note_by_hash(self, content_hash: str) -> str | None:
        row = self.conn.execute("SELECT id FROM notes WHERE content_hash=?",
                                (content_hash,)).fetchone()
        return row["id"] if row else None

    def get_note(self, note_id: str) -> sqlite3.Row | None:
        return self.conn.execute("SELECT * FROM notes WHERE id=?", (note_id,)).fetchone()

    def get_notes(self, ids: list[str]) -> dict[str, sqlite3.Row]:
        out = {}
        for i in range(0, len(ids), 500):
            chunk = ids[i:i + 500]
            for r in self.conn.execute(
                    f"SELECT * FROM notes WHERE id IN ({_placeholders(len(chunk))})", chunk):
                out[r["id"]] = r
        return out

    def iter_notes(self) -> Iterator[sqlite3.Row]:
        yield from self.conn.execute("SELECT * FROM notes ORDER BY created_at, id")

    def note_count(self) -> int:
        return self.conn.execute("SELECT COUNT(*) FROM notes").fetchone()[0]

    def insert_note(self, note_id: str, text: str, content_hash: str, source: str | None,
                    importance: float, created_at: str, n_terms: int) -> None:
        self.conn.execute(
            "INSERT INTO notes(id, text, content_hash, source, importance, created_at, n_terms) "
            "VALUES(?, ?, ?, ?, ?, ?, ?)",
            (note_id, text, content_hash, source, importance, created_at, n_terms))

    def delete_note_row(self, note_id: str) -> None:
        self.conn.execute("DELETE FROM notes WHERE id=?", (note_id,))

    # --- terms & counts ---------------------------------------------------

    def _term_id(self, text: str, create: bool) -> int | None:
        row = self.conn.execute("SELECT id FROM terms WHERE text=?", (text,)).fetchone()
        if row:
            return row["id"]
        if not create:
            return None
        return self.conn.execute("INSERT INTO terms(text) VALUES(?)", (text,)).lastrowid

    def term_ids(self, texts: Iterable[str]) -> dict[str, int]:
        texts = list(dict.fromkeys(texts))
        out = {}
        for i in range(0, len(texts), 500):
            chunk = texts[i:i + 500]
            for r in self.conn.execute(
                    f"SELECT id, text FROM terms WHERE text IN ({_placeholders(len(chunk))})", chunk):
                out[r["text"]] = r["id"]
        return out

    def term_stats(self, texts: Iterable[str]) -> dict[str, sqlite3.Row]:
        texts = list(dict.fromkeys(texts))
        out = {}
        for i in range(0, len(texts), 500):
            chunk = texts[i:i + 500]
            for r in self.conn.execute(
                    f"SELECT id, text, df, mass FROM terms WHERE text IN ({_placeholders(len(chunk))})",
                    chunk):
                out[r["text"]] = r
        return out

    def add_contribution(self, note_id: str, pairs: dict[tuple[str, str], float],
                         tf: dict[str, int]) -> None:
        """Add one note's postings and pair counts. Caller holds the transaction."""
        ids = {t: self._term_id(t, create=True) for t in tf}
        for t, n in tf.items():
            self.conn.execute("UPDATE terms SET df = df + 1 WHERE id=?", (ids[t],))
            self.conn.execute("INSERT INTO postings(term_id, note_id, tf) VALUES(?, ?, ?)",
                              (ids[t], note_id, n))
        mass: dict[int, float] = {}
        rows = []
        for (ta, tb), delta in pairs.items():
            a, b = sorted((ids[ta], ids[tb]))
            rows.append((a, b, delta))
            mass[a] = mass.get(a, 0.0) + delta
            mass[b] = mass.get(b, 0.0) + delta
        self.conn.executemany(
            "INSERT INTO pairs(a, b, count) VALUES(?, ?, ?) "
            "ON CONFLICT(a, b) DO UPDATE SET count = count + excluded.count", rows)
        self.conn.executemany("UPDATE terms SET mass = mass + ? WHERE id = ?",
                              [(v, k) for k, v in mass.items()])
        self._add_total(sum(mass.values()))

    def remove_contribution(self, note_id: str, pairs: dict[tuple[str, str], float]) -> None:
        """Subtract one note's pair counts and postings. Subtracts min(existing, Δ)
        so a pair already pruned cannot drive masses negative (Contracts I1)."""
        ids = self.term_ids({t for k in pairs for t in k})
        removed_total = 0.0
        for (ta, tb), delta in pairs.items():
            if ta not in ids or tb not in ids:
                continue
            a, b = sorted((ids[ta], ids[tb]))
            row = self.conn.execute("SELECT count FROM pairs WHERE a=? AND b=?", (a, b)).fetchone()
            if not row:
                continue
            removed = min(row["count"], delta)
            if row["count"] - removed <= EPS:
                self.conn.execute("DELETE FROM pairs WHERE a=? AND b=?", (a, b))
            else:
                self.conn.execute("UPDATE pairs SET count = count - ? WHERE a=? AND b=?",
                                  (removed, a, b))
            self.conn.execute("UPDATE terms SET mass = MAX(0, mass - ?) WHERE id IN (?, ?)",
                              (removed, a, b))
            removed_total += removed
        self._add_total(-2 * removed_total)
        self.conn.execute(
            "UPDATE terms SET df = df - 1 WHERE id IN (SELECT term_id FROM postings WHERE note_id=?)",
            (note_id,))
        self.conn.execute("DELETE FROM postings WHERE note_id=?", (note_id,))
        self.conn.execute("DELETE FROM terms WHERE df <= 0")

    def pair_count(self) -> int:
        return int(self.get_meta("pair_rows", "0"))

    def prune_if_needed(self) -> int:
        """Enforce the pair-table bound (Contracts I5). Caller holds the tx.
        Returns the number of pairs deleted."""
        n = self.pair_count()
        if n <= self.max_pairs:
            return 0
        drop = n - int(self.max_pairs * PRUNE_TARGET)
        self.conn.execute(
            "DELETE FROM pairs WHERE (a, b) IN "
            "(SELECT a, b FROM pairs ORDER BY count ASC, a ASC, b ASC LIMIT ?)", (drop,))
        self.recompute_mass()
        return drop

    def recompute_mass(self) -> None:
        """Rebuild mass and total from the pair table (Contracts I1)."""
        self.conn.execute("UPDATE terms SET mass = 0")
        self.conn.execute(
            "UPDATE terms SET mass = mass + s.c FROM "
            "(SELECT a AS id, SUM(count) AS c FROM pairs GROUP BY a) AS s WHERE terms.id = s.id")
        self.conn.execute(
            "UPDATE terms SET mass = mass + s.c FROM "
            "(SELECT b AS id, SUM(count) AS c FROM pairs GROUP BY b) AS s WHERE terms.id = s.id")
        total = self.conn.execute("SELECT COALESCE(SUM(mass), 0) FROM terms").fetchone()[0]
        self.set_meta("total", repr(float(total)))

    def clear_derived(self) -> None:
        self.conn.execute("DELETE FROM pairs")
        self.conn.execute("DELETE FROM postings")
        self.conn.execute("DELETE FROM terms")
        self.set_meta("total", "0.0")

    # --- reads for weights / recall -----------------------------------------

    def learned_candidates(self, term: str) -> list[tuple[str, float, float, float]]:
        """→ [(neighbor, count, mass_self, mass_neighbor)], top NEIGHBOR_CANDIDATES by count."""
        row = self.conn.execute("SELECT id, mass FROM terms WHERE text=?", (term,)).fetchone()
        if not row:
            return []
        tid, mass_self = row["id"], row["mass"]
        rows = self.conn.execute(
            "SELECT t.text, x.count, t.mass FROM ("
            "  SELECT b AS other, count FROM pairs WHERE a = ?"
            "  UNION ALL SELECT a AS other, count FROM pairs WHERE b = ?"
            ") AS x JOIN terms t ON t.id = x.other "
            "ORDER BY x.count DESC, t.text ASC LIMIT ?",
            (tid, tid, NEIGHBOR_CANDIDATES)).fetchall()
        return [(r["text"], r["count"], mass_self, r["mass"]) for r in rows]

    def relations_touching(self, term: str) -> list[sqlite3.Row]:
        return self.conn.execute(
            "SELECT a, b, type, weight, created_at FROM relations WHERE a=? OR b=?",
            (term, term)).fetchall()

    def has_relation_term(self, term: str) -> bool:
        return self.conn.execute(
            "SELECT 1 FROM relations WHERE a=? OR b=? LIMIT 1", (term, term)).fetchone() is not None

    def postings_for(self, term_ids: list[int]) -> list[sqlite3.Row]:
        out = []
        for i in range(0, len(term_ids), 500):
            chunk = term_ids[i:i + 500]
            out.extend(self.conn.execute(
                f"SELECT term_id, note_id, tf FROM postings WHERE term_id IN ({_placeholders(len(chunk))})",
                chunk).fetchall())
        return out

    # --- relations ------------------------------------------------------------

    def upsert_relation(self, a: str, b: str, rtype: str, weight: float,
                        created_at: str) -> sqlite3.Row | None:
        prev = self.conn.execute("SELECT type, weight FROM relations WHERE a=? AND b=?",
                                 (a, b)).fetchone()
        self.conn.execute(
            "INSERT INTO relations(a, b, type, weight, created_at) VALUES(?, ?, ?, ?, ?) "
            "ON CONFLICT(a, b) DO UPDATE SET type=excluded.type, weight=excluded.weight, "
            "created_at=excluded.created_at", (a, b, rtype, weight, created_at))
        return prev

    def get_relation(self, a: str, b: str) -> sqlite3.Row | None:
        return self.conn.execute("SELECT * FROM relations WHERE a=? AND b=?", (a, b)).fetchone()

    def delete_relation(self, a: str, b: str) -> bool:
        return self.conn.execute("DELETE FROM relations WHERE a=? AND b=?", (a, b)).rowcount > 0

    def iter_relations(self) -> Iterator[sqlite3.Row]:
        yield from self.conn.execute("SELECT * FROM relations ORDER BY a, b")

    def stats(self) -> dict:
        q = lambda sql: self.conn.execute(sql).fetchone()[0]  # noqa: E731
        return {
            "notes": q("SELECT COUNT(*) FROM notes"),
            "terms": q("SELECT COUNT(*) FROM terms"),
            "pairs": q("SELECT COUNT(*) FROM pairs"),
            "max_pairs": self.max_pairs,
            "relations": q("SELECT COUNT(*) FROM relations"),
            "total_mass": round(self.total(), 3),
        }
