"""Resonance: the public library API and the input-validation boundary."""

from __future__ import annotations

import hashlib
import json
import math
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import IO, Iterable

from . import recall as R
from . import text as T
from .store import DEFAULT_MAX_PAIRS, Store
from .weights import RELATION_TYPES

MAX_NOTE_CHARS = 100_000
MAX_QUERY_CHARS = 2_000
MAX_SOURCE_CHARS = 200
MAX_LIMIT = 50
MIN_BUDGET, MAX_BUDGET = 200, 100_000


class ValidationError(ValueError):
    """Input rejected at the boundary. Messages never contain note text."""


class NotFound(LookupError):
    pass


def default_db_path() -> Path:
    return Path(os.environ.get("RESONANCE_DB") or Path.home() / ".resonance" / "resonance.db")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _iso(value: str, name: str) -> str:
    try:
        dt = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        raise ValidationError(f"{name} must be an ISO-8601 date or datetime") from None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds")


def _unit(value, name: str) -> float:
    try:
        v = float(value)
    except (TypeError, ValueError):
        raise ValidationError(f"{name} must be a number in [0, 1]") from None
    if not (0.0 <= v <= 1.0) or math.isnan(v):
        raise ValidationError(f"{name} must be in [0, 1]")
    return v


def _int_in(value, name: str, lo: int, hi: int) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or int(value) != value:
        raise ValidationError(f"{name} must be an integer in [{lo}, {hi}]")
    v = int(value)
    if not lo <= v <= hi:
        raise ValidationError(f"{name} must be in [{lo}, {hi}]")
    return v


def _term(raw, name: str) -> str:
    if not isinstance(raw, str) or not raw.strip() or len(raw) > 200:
        raise ValidationError(f"{name} must be a non-empty word")
    t = T.single_term(raw)
    if t is None:
        raise ValidationError(f"{name} must normalize to exactly one non-stopword term")
    return t


def _content_hash(text: str) -> str:
    return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()


class Resonance:
    def __init__(self, path: str | os.PathLike | None = None, max_pairs: int = DEFAULT_MAX_PAIRS):
        self.store = Store(path if path is not None else default_db_path(), max_pairs=max_pairs)
        self._check_tokenizer()

    def close(self) -> None:
        self.store.close()

    def __enter__(self) -> "Resonance":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def _check_tokenizer(self) -> None:
        version = self.store.get_meta("tokenizer_version")
        if version == str(T.TOKENIZER_VERSION):
            return
        if version is not None and self.store.note_count():
            print(f"resonance: tokenizer v{version} → v{T.TOKENIZER_VERSION}, rebuilding derived tables",
                  file=sys.stderr)
            r = self.rebuild()
            if r["relations_rekeyed"] or r["relations_collapsed"]:
                print(f"resonance: {r['relations_rekeyed']} relation(s) re-keyed, "
                      f"{r['relations_collapsed']} collapsed", file=sys.stderr)
        else:
            with self.store.tx():
                self.store.set_meta("tokenizer_version", str(T.TOKENIZER_VERSION))

    # --- writes -------------------------------------------------------------

    def _validate_note(self, text, source, importance, created_at, note_id) -> tuple:
        if not isinstance(text, str) or not text.strip():
            raise ValidationError("text must be non-empty")
        if len(text) > MAX_NOTE_CHARS:
            raise ValidationError(f"text exceeds {MAX_NOTE_CHARS} characters")
        if source is not None and (not isinstance(source, str) or len(source) > MAX_SOURCE_CHARS):
            raise ValidationError(f"source must be a string of at most {MAX_SOURCE_CHARS} characters")
        importance = _unit(importance, "importance")
        created = _iso(created_at, "created_at") if created_at else _now()
        if note_id is not None and (not isinstance(note_id, str) or not 1 <= len(note_id) <= 64):
            raise ValidationError("id must be a string of 1-64 characters")
        return text, source, importance, created, note_id

    def _ingest(self, text, source, importance, created, note_id) -> dict:
        """One note's writes. Caller holds the transaction."""
        h = _content_hash(text)
        existing = self.store.note_by_hash(h)
        if existing:
            return {"id": existing, "duplicate": True}
        nid = note_id or uuid.uuid4().hex[:16]
        if self.store.get_note(nid):
            raise ValidationError("id already in use by a different note")
        pairs, tf = T.analyze(text)
        self.store.insert_note(nid, text, h, source, importance, created, len(tf))
        self.store.add_contribution(nid, pairs, tf)
        return {"id": nid, "duplicate": False, "terms": len(tf)}

    def remember(self, text: str, source: str | None = None, importance: float = 0.5,
                 created_at: str | None = None, note_id: str | None = None) -> dict:
        args = self._validate_note(text, source, importance, created_at, note_id)
        with self.store.tx():
            out = self._ingest(*args)
            pruned = self.store.prune_if_needed()
        if pruned:
            out["pruned_pairs"] = pruned
        return out

    def remember_many(self, texts: Iterable[str], source: str | None = None,
                      importance: float = 0.5) -> dict:
        """Bulk ingest in ONE transaction: all notes are stored or none are.
        Much faster than repeated remember() because commit (fsync) dominates."""
        batch = [self._validate_note(t, source, importance, None, None) for t in texts]
        counts = {"notes": 0, "duplicates": 0}
        with self.store.tx():
            for args in batch:
                r = self._ingest(*args)
                counts["duplicates" if r["duplicate"] else "notes"] += 1
            pruned = self.store.prune_if_needed()
        if pruned:
            counts["pruned_pairs"] = pruned
        return counts

    def forget(self, note_id: str) -> dict:
        with self.store.tx():
            row = self.store.get_note(note_id)
            if not row:
                raise NotFound(f"no note with id {note_id!r}")
            pairs, _ = T.analyze(row["text"])
            self.store.remove_contribution(note_id, pairs)
            self.store.delete_note_row(note_id)
        return {"id": note_id, "forgotten": True}

    def relate(self, a: str, b: str, type: str = "related", weight: float = 1.0) -> dict:
        ta, tb = _term(a, "a"), _term(b, "b")
        if ta == tb:
            raise ValidationError("a and b normalize to the same term")
        if type not in RELATION_TYPES:
            raise ValidationError(f"type must be one of {', '.join(RELATION_TYPES)}")
        w = _unit(weight, "weight")
        with self.store.tx():
            prev = self.store.upsert_relation(ta, tb, type, w, _now())
        out = {"a": ta, "b": tb, "type": type, "weight": w}
        if prev:
            out["previous"] = {"type": prev["type"], "weight": prev["weight"]}
        return out

    def unrelate(self, a: str, b: str) -> dict:
        ta, tb = _term(a, "a"), _term(b, "b")
        with self.store.tx():
            removed = self.store.delete_relation(ta, tb)
        if not removed:
            raise NotFound(f"no relation {ta!r} → {tb!r}")
        return {"a": ta, "b": tb, "removed": True}

    def rebuild(self) -> dict:
        """Recompute every derived table from the notes (Flows F7)."""
        with self.store.tx():
            self.store.clear_derived()
            rekeyed, collapsed = self._rekey_relations()
            n = 0
            for row in list(self.store.iter_notes()):
                pairs, tf = T.analyze(row["text"])
                self.store.add_contribution(row["id"], pairs, tf)
                n += 1
            pruned = self.store.prune_if_needed()
            self.store.set_meta("tokenizer_version", str(T.TOKENIZER_VERSION))
        return {"notes": n, "pruned_pairs": pruned,
                "relations_rekeyed": rekeyed, "relations_collapsed": collapsed}

    def _rekey_relations(self) -> tuple[int, int]:
        """Bring asserted relations in line with the current tokenizer (D-010).

        Relations are operator data keyed by term text. A tokenizer change
        (e.g. accent folding) would otherwise orphan them. Only the fold is
        reapplied, not the whole pipeline, so stored terms are not re-folded.
        On a key clash the newer assertion wins. A relation whose ends become
        the same term is dropped and counted.
        """
        rekeyed = collapsed = 0
        for row in list(self.store.iter_relations()):
            na, nb = T.fold_accents(row["a"]), T.fold_accents(row["b"])
            if (na, nb) == (row["a"], row["b"]):
                continue
            self.store.delete_relation(row["a"], row["b"])
            if na == nb:
                collapsed += 1
                continue
            existing = self.store.get_relation(na, nb)
            if existing is None or existing["created_at"] <= row["created_at"]:
                self.store.upsert_relation(na, nb, row["type"], row["weight"], row["created_at"])
            rekeyed += 1
        return rekeyed, collapsed

    # --- reads --------------------------------------------------------------

    def neighbors(self, term: str, limit: int = 20) -> dict:
        t = _term(term, "term")
        limit = _int_in(limit, "limit", 1, 200)
        return {"term": t, "neighbors": [e.as_dict() for e in R.neighbors(self.store, t, limit)]}

    def recall(self, query: str, limit: int = 5, hops: int = 2,
               since: str | None = None, until: str | None = None) -> dict:
        if not isinstance(query, str) or not query.strip():
            raise ValidationError("query must be non-empty")
        if len(query) > MAX_QUERY_CHARS:
            raise ValidationError(f"query exceeds {MAX_QUERY_CHARS} characters")
        limit = _int_in(limit, "limit", 1, MAX_LIMIT)
        hops = _int_in(hops, "hops", 0, R.MAX_HOPS)
        since = _iso(since, "since") if since else None
        until = _iso(until, "until") if until else None

        qterms = list(dict.fromkeys(T.terms(query)))
        known = self.store.term_ids(qterms)
        seeds = [t for t in qterms if t in known or self.store.has_relation_term(t)]
        result = {"query": query, "seeds": seeds,
                  "unknown": [t for t in qterms if t not in seeds], "terms": [], "notes": []}
        if not seeds:
            return result

        A = R.spread(self.store, seeds, hops)
        result["terms"] = R.top_terms(A)
        raw = R.score_notes(self.store, A)
        rows = self.store.get_notes(list(raw))
        ranked = []
        for nid, (score, matched) in raw.items():
            row = rows[nid]
            if (since and row["created_at"] < since) or (until and row["created_at"] > until):
                continue
            final = score / math.sqrt(max(1, row["n_terms"])) * (0.5 + row["importance"])
            ranked.append((final, nid, matched))
        ranked.sort(key=lambda x: (-x[0], x[1]))
        for final, nid, matched in ranked[:limit]:
            row = rows[nid]
            top = sorted(matched, key=lambda t: (-matched[t], t))[:8]
            result["notes"].append({
                "id": nid, "score": round(final, 5), "created_at": row["created_at"],
                "source": row["source"], "importance": row["importance"], "text": row["text"],
                "matched": [{"term": t, "why": A.explain(t)} for t in top],
            })
        return result

    def context(self, query: str, budget_chars: int = 4000, limit: int = 8, hops: int = 2,
                since: str | None = None, until: str | None = None) -> str:
        """A prompt-ready block of relevant memory, ≤ budget_chars (Flows F5)."""
        budget = _int_in(budget_chars, "budget_chars", MIN_BUDGET, MAX_BUDGET)
        r = self.recall(query, limit=limit, hops=hops, since=since, until=until)
        if not r["notes"]:
            return "[resonance] no relevant memory"[:budget]
        related = ", ".join(t["term"] for t in r["terms"][:12])
        out = f"[resonance] related: {related}\n"[:budget]
        for n in r["notes"]:
            head = f"\n[{n['id']} · {n['created_at'][:10]} · {n['score']:.3f}] "
            body = " ".join(n["text"].split())
            block = head + body + "\n"
            room = budget - len(out)
            if len(block) <= room:
                out += block
            elif room - len(head) >= 200:
                out += head + body[:room - len(head) - 2] + "…\n"
                break
            else:
                break
        return out

    def stats(self) -> dict:
        return self.store.stats()

    # --- export / import (Flows F9) -----------------------------------------

    def export(self, fh: IO[str]) -> dict:
        n_notes = n_rel = 0
        for row in self.store.iter_notes():
            fh.write(json.dumps({"kind": "note", "id": row["id"], "text": row["text"],
                                 "source": row["source"], "importance": row["importance"],
                                 "created_at": row["created_at"]}, ensure_ascii=False) + "\n")
            n_notes += 1
        for row in self.store.iter_relations():
            fh.write(json.dumps({"kind": "relation", "a": row["a"], "b": row["b"], "type": row["type"],
                                 "weight": row["weight"], "created_at": row["created_at"]},
                                ensure_ascii=False) + "\n")
            n_rel += 1
        return {"notes": n_notes, "relations": n_rel}

    def import_(self, lines: Iterable[str]) -> dict:
        counts = {"notes": 0, "duplicates": 0, "relations": 0, "errors": []}
        for lineno, line in enumerate(lines, 1):
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
                if not isinstance(rec, dict):
                    raise ValidationError("line is not a JSON object")
                kind = rec.get("kind")
                if kind == "note":
                    r = self.remember(rec.get("text"), source=rec.get("source"),
                                      importance=rec.get("importance", 0.5),
                                      created_at=rec.get("created_at"), note_id=rec.get("id"))
                    counts["duplicates" if r["duplicate"] else "notes"] += 1
                elif kind == "relation":
                    self.relate(rec.get("a"), rec.get("b"), rec.get("type", "related"),
                                rec.get("weight", 1.0))
                    counts["relations"] += 1
                else:
                    raise ValidationError("kind must be 'note' or 'relation'")
            except (ValidationError, json.JSONDecodeError) as e:
                counts["errors"].append(f"line {lineno}: {e}")
        return counts
