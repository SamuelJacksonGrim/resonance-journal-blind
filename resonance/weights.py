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
"""Edge weights: the single authority on how strong a relationship is.

Pure functions. Recall consumes these; nothing else computes a weight.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

# Confidence damping: weight *= c / (c + CONFIDENCE_K). With K=2 a pair seen
# once at distance 1 keeps 1/3 of its NPMI, a pair with count 10 keeps 5/6.
# Provenance: additive smoothing constant chosen so a single co-occurrence can
# never outrank a pair attested ~3+ times at similar NPMI.
CONFIDENCE_K = 2.0

# How much an asserted relation of each type counts toward relevance. A
# synonym is as good as the word itself; an antonym is on-topic but opposite.
RELATION_FACTORS = {
    "synonym": 1.0,
    "is_a": 0.8,
    "part_of": 0.7,
    "related": 0.6,
    "antonym": 0.4,
}
RELATION_TYPES = tuple(RELATION_FACTORS)


@dataclass(frozen=True)
class Edge:
    term: str
    weight: float
    source: str                  # "learned" | "asserted"
    count: float = 0.0
    npmi: float = 0.0
    confidence: float = 0.0
    relation: str | None = None  # asserted type
    direction: str | None = None  # "out" (term is b of a→b), "in", or None

    def as_dict(self) -> dict:
        d = {"term": self.term, "weight": round(self.weight, 4), "source": self.source}
        if self.source == "learned":
            d.update(count=round(self.count, 3), npmi=round(self.npmi, 4),
                     confidence=round(self.confidence, 4))
        else:
            d.update(relation=self.relation, direction=self.direction)
        return d


def npmi(count: float, mass_a: float, mass_b: float, total: float) -> float:
    """Normalized PMI in [-1, 1] over the symmetric co-occurrence matrix.

    p(a,b) = count/total, p(a) = mass_a/total, where total = Σ mass.
    """
    if count <= 0 or mass_a <= 0 or mass_b <= 0 or total <= 0:
        return 0.0
    p_ab = count / total
    if p_ab >= 1.0:
        return 1.0
    pmi = math.log(count * total / (mass_a * mass_b))
    return max(-1.0, min(1.0, pmi / -math.log(p_ab)))


def confidence(count: float) -> float:
    return count / (count + CONFIDENCE_K) if count > 0 else 0.0


def learned_weight(count: float, mass_a: float, mass_b: float, total: float) -> tuple[float, float, float]:
    """→ (weight in [0,1], npmi, confidence). Negative association weighs 0."""
    n = npmi(count, mass_a, mass_b, total)
    c = confidence(count)
    return max(0.0, n) * c, n, c


def asserted_weight(relation: str, weight: float) -> float:
    return RELATION_FACTORS[relation] * weight


def combine(learned: dict[str, Edge], asserted: dict[str, Edge]) -> list[Edge]:
    """Asserted overrides learned for the same neighbor (explicit beats
    statistics, including weight 0 = suppress). Returns positive edges sorted
    by weight desc, then term for determinism."""
    merged = dict(learned)
    merged.update(asserted)
    return sorted((e for e in merged.values() if e.weight > 0),
                  key=lambda e: (-e.weight, e.term))
