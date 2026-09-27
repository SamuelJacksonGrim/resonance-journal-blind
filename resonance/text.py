"""Text normalization: the single authority on what counts as a term.

Pure functions, no I/O. Ingest and forget must see identical output for the
same text, so any behavior change here must bump TOKENIZER_VERSION (the store
rebuilds derived tables when the version changes).
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter

# v2: accent folding for Latin script (zürich == zurich) and casefold (ß → ss).
TOKENIZER_VERSION = 2

# Co-occurrence window: pairs up to WINDOW tokens apart, weighted 1/distance.
# Provenance: word2vec and GloVe use windows of 5-10; GloVe introduced 1/d
# weighting. 5 keeps associations topical rather than document-wide.
WINDOW = 5
MIN_TOKEN_LEN = 2

_SENTENCE_SPLIT = re.compile(r"[.!?;:\n]+")
_TOKEN = re.compile(r"[^\W_]+(?:'[^\W_]+)?", re.UNICODE)

STOPWORDS = frozenset("""
a about above after again against all am an and any are aren't as at be because
been before being below between both but by can can't cannot could couldn't did
didn't do does doesn't doing don't down during each few for from further had
hadn't has hasn't have haven't having he he'd he'll he's her here here's hers
herself him himself his how how's i i'd i'll i'm i've if in into is isn't it
it's its itself let's me more most mustn't my myself no nor not of off on once
only or other ought our ours ourselves out over own same shan't she she'd she'll
she's should shouldn't so some such than that that's the their theirs them
themselves then there there's these they they'd they'll they're they've this
those through to too under until up very was wasn't we we'd we'll we're we've
were weren't what what's when when's where where's which while who who's whom
why why's will with won't would wouldn't you you'd you'll you're you've your
yours yourself yourselves also just like get got really one two us may might
must shall much many every either neither yet still even
""".split())

# Words ending in -s that are not plurals, or whose naive fold is wrong.
_NO_FOLD_SUFFIXES = ("ss", "us", "is", "ous", "ics", "ies")


def fold(token: str) -> str:
    """Conservative English plural folding: dogs→dog, berries→berry, boxes→box.

    Deliberately under-folds (bus, glass, analysis, physics stay put): a missed
    fold splits one word into two terms, a wrong fold merges unrelated words.
    """
    n = len(token)
    if n > 4 and token.endswith("ies"):
        return token[:-3] + "y"
    if n > 4 and token.endswith(("ches", "shes", "xes", "sses", "zes")):
        return token[:-2]
    if n > 3 and token.endswith("s") and not token.endswith(_NO_FOLD_SUFFIXES):
        return token[:-1]
    return token


# Latin letters that carry no combining mark to strip (NFKD leaves them whole).
_LATIN_EXTRA = str.maketrans({"ø": "o", "æ": "ae", "œ": "oe", "ł": "l", "đ": "d",
                              "ð": "d", "þ": "th", "ı": "i"})


def _is_latin(ch: str) -> bool:
    o = ord(ch)
    return o < 0x0250 or 0x1E00 <= o <= 0x1EFF


def fold_accents(text: str) -> str:
    """Casefold, then drop combining marks that sit on Latin letters.

    Marks on other scripts are kept: in Devanagari, Thai, or Hebrew they are
    part of the word, not decoration. NFKD also unpacks ligatures and
    full-width forms (ﬁ → fi, ｚ → z).
    """
    out: list[str] = []
    prev_latin = False
    for ch in unicodedata.normalize("NFKD", text.casefold()):
        if unicodedata.combining(ch):
            if not prev_latin:
                out.append(ch)
            continue
        prev_latin = _is_latin(ch)
        out.append(ch)
    return unicodedata.normalize("NFC", "".join(out)).translate(_LATIN_EXTRA)


def normalize_token(raw: str) -> str | None:
    """One raw token → a term, or None if it is not a term."""
    t = fold_accents(raw).replace("’", "'")
    if t.endswith("'s"):
        t = t[:-2]
    if len(t) < MIN_TOKEN_LEN or t in STOPWORDS or t.isdigit():
        return None
    return fold(t)


def sentences(text: str) -> list[list[str]]:
    """Text → list of sentences, each a list of terms (stopwords removed)."""
    out = []
    for chunk in _SENTENCE_SPLIT.split(text):
        terms = [t for t in (normalize_token(m) for m in _TOKEN.findall(chunk)) if t]
        if terms:
            out.append(terms)
    return out


def terms(text: str) -> list[str]:
    """All terms in order, across sentences."""
    return [t for s in sentences(text) for t in s]


def single_term(text: str) -> str | None:
    """The one term `text` normalizes to, or None if it is zero or several."""
    ts = terms(text)
    return ts[0] if len(ts) == 1 else None


def analyze(text: str, window: int = WINDOW) -> tuple[dict[tuple[str, str], float], Counter]:
    """Text → (pair deltas keyed (min, max) by term text, term frequencies).

    Pairs never cross sentence boundaries. Self-pairs are skipped.
    """
    pairs: dict[tuple[str, str], float] = {}
    tf: Counter = Counter()
    for sent in sentences(text):
        tf.update(sent)
        for i, a in enumerate(sent):
            for d in range(1, window + 1):
                j = i + d
                if j >= len(sent):
                    break
                b = sent[j]
                if a == b:
                    continue
                key = (a, b) if a < b else (b, a)
                pairs[key] = pairs.get(key, 0.0) + 1.0 / d
    return pairs, tf
