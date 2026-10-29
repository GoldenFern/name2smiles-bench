"""Heuristic difficulty scoring for name-to-SMILES records.

The score combines name-format complexity with structural complexity. It is a
deterministic planning aid for building smaller test sets. It is not
calibrated against model failure rates.

The score is a weighted sum. Each component is capped before weighting, so one
extreme feature cannot dominate the total. The final score is clamped to 100.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Any

TIER_KEYS: tuple[str, ...] = ("L1", "L2", "L3", "L4", "L5")
TIER_LABELS: dict[str, str] = {
    "L1": "easy",
    "L2": "moderate",
    "L3": "hard",
    "L4": "very_hard",
    "L5": "extreme",
}
# A score below the first bound is L1, below the second is L2, and so on.
TIER_UPPER_BOUNDS: tuple[float, ...] = (12.0, 24.0, 38.0, 52.0)

ELEMENT_CLASS_WEIGHTS: dict[str, float] = {
    "radioactive": 12.0,
    "metal": 10.0,
    "B_Si_Se_As": 8.0,
    "S_P": 3.0,
    "halogen": 1.0,
    "CHNO": 0.0,
}

UNCOMMON_FUNCTIONAL_GROUPS: frozenset[str] = frozenset(
    {
        "acid_halide",
        "allene",
        "anhydride",
        "azide",
        "boronate_ester",
        "boronic_acid",
        "disulfide",
        "hydrazone",
        "isocyanate",
        "isothiocyanate",
        "n_oxide",
        "nitroso",
        "oxime",
        "siloxane",
    }
)

COMPONENT_MAX: dict[str, float] = {
    "name_length": 10.0,
    "name_locants": 10.0,
    "name_nesting": 8.0,
    "name_stereo": 10.0,
    "heavy_atoms": 12.0,
    "rings": 8.0,
    "stereo_centers": 8.0,
    "double_bond_stereo": 4.0,
    "fragments": 6.0,
    "charge": 6.0,
    "element_class": 12.0,
    "salt": 2.0,
    "uncommon_group": 4.0,
    "macrocycle": 6.0,
    "spiro": 4.0,
    "bridgehead": 4.0,
    "isotope": 10.0,
    "radical": 10.0,
}

_STEREO_RE = re.compile(r"(?:^|[\[(,])(?:\d+[a-z]?'?)?([RSEZ])(?=[,\])\-]|$)")


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def name_stereo_descriptors(name: str) -> int:
    """Count R/S/E/Z stereodescriptors in an IUPAC-style name."""
    return len(_STEREO_RE.findall(name))


def name_nesting_depth(name: str) -> int:
    """Return the deepest bracket or parenthesis nesting in a name."""
    depth = 0
    deepest = 0
    for char in name:
        if char in "([":
            depth += 1
            deepest = max(deepest, depth)
        elif char in ")]":
            depth -= 1
    return deepest


def name_locant_count(name: str) -> int:
    """Count numeric locant groups, including ring sizes and isotope labels."""
    return len(re.findall(r"\d+", name))


def tier_for_score(score: float) -> str:
    """Return the tier key for a difficulty score."""
    for key, upper in zip(TIER_KEYS, TIER_UPPER_BOUNDS):
        if score < upper:
            return key
    return TIER_KEYS[-1]


def tier_range(key: str) -> str:
    """Return a human-readable score range for a tier key."""
    index = TIER_KEYS.index(key)
    lower = 0.0 if index == 0 else TIER_UPPER_BOUNDS[index - 1]
    if index == len(TIER_UPPER_BOUNDS):
        return f">={lower:g}"
    return f"{lower:g}-<{TIER_UPPER_BOUNDS[index]:g}"


@dataclass(frozen=True)
class Difficulty:
    """Difficulty score, tier, and per-component contributions."""

    score: float
    tier: str
    label: str
    components: dict[str, float]

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation."""
        return {
            "score": self.score,
            "tier": self.tier,
            "label": self.label,
            "components": self.components,
        }


def score_record(record: dict[str, Any]) -> Difficulty:
    """Score one dataset record.

    Expected fields match the records in ``data/benchmark_v0.jsonl``. Missing
    optional flags are treated as false.

    Args:
        record: Dataset record with name, descriptor, and flag fields.

    Returns:
        Difficulty with a rounded score in ``[0, 100]`` and component values.
    """
    name = str(record["name"])
    heavy_atoms = int(record["heavy_atoms"])
    ring_count = int(record["rings"]["count"])
    stereo = record["stereo"]
    centers = int(stereo["centers"])
    double_bonds = int(stereo["double_bonds"])
    fragments = len(record["fragments"])
    charge = abs(int(record["charge"]))
    element_class = str(record["element_class"])
    groups = set(record["functional_groups"])
    uncommon_groups = len(groups & UNCOMMON_FUNCTIONAL_GROUPS)
    rings = record["rings"]

    components = {
        "name_length": round(10.0 * _clamp01((len(name) - 20) / 140), 2),
        "name_locants": round(10.0 * _clamp01((name_locant_count(name) - 2) / 18), 2),
        "name_nesting": round(8.0 * _clamp01((name_nesting_depth(name) - 1) / 5), 2),
        "name_stereo": round(10.0 * _clamp01(name_stereo_descriptors(name) / 4), 2),
        "heavy_atoms": round(12.0 * _clamp01((heavy_atoms - 5) / 45), 2),
        "rings": round(8.0 * _clamp01(ring_count / 4), 2),
        "stereo_centers": round(8.0 * _clamp01(centers / 3), 2),
        "double_bond_stereo": round(4.0 * _clamp01(double_bonds / 2), 2),
        "fragments": round(6.0 * _clamp01((fragments - 1) / 3), 2),
        "charge": round(
            (4.0 if charge else 0.0) + (2.0 if record.get("is_zwitterion") else 0.0),
            2,
        ),
        "element_class": ELEMENT_CLASS_WEIGHTS.get(element_class, 0.0),
        "salt": 2.0 if record.get("is_salt") else 0.0,
        "uncommon_group": round(2.0 * min(2, uncommon_groups), 2),
        "macrocycle": 6.0 if rings.get("macrocycle") else 0.0,
        "spiro": 4.0 if int(rings.get("spiro_atoms", 0)) > 0 else 0.0,
        "bridgehead": (4.0 if int(rings.get("bridgehead_atoms", 0)) > 0 else 0.0),
        "isotope": 10.0 if record.get("has_isotope") else 0.0,
        "radical": 10.0 if record.get("is_radical") else 0.0,
    }
    # Keep rounding stable across Python versions with different sum algorithms.
    score = round(min(100.0, math.fsum(components.values())), 1)
    tier = tier_for_score(score)
    return Difficulty(
        score=score,
        tier=tier,
        label=TIER_LABELS[tier],
        components=components,
    )
