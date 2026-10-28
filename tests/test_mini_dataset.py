from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from name2smiles.descriptors import charge_bin, ring_bin, size_bin
from name2smiles.difficulty import (
    COMPONENT_MAX,
    TIER_KEYS,
    TIER_LABELS,
    score_record,
    tier_for_score,
)

ROOT = Path(__file__).resolve().parents[1]
MINI = ROOT / "data" / "mini_100.jsonl"
BENCHMARK = ROOT / "data" / "benchmark_v0.jsonl"

EXPECTED_TIERS = {"L1": 25, "L2": 30, "L3": 20, "L4": 15, "L5": 10}


def load(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle]


def test_mini_dataset_shape():
    records = load(MINI)
    assert len(records) == 100
    assert len({record["id"] for record in records}) == 100
    assert len({record["mini_id"] for record in records}) == 100
    assert len({record["inchikey"] for record in records}) == 100

    counts = Counter(record["difficulty"]["tier"] for record in records)
    assert counts == EXPECTED_TIERS

    tiers = [record["difficulty"]["tier"] for record in records]
    assert tiers == sorted(tiers, key=TIER_KEYS.index)

    scores = [record["difficulty"]["score"] for record in records]
    assert scores == sorted(scores)
    assert min(scores) < 2.0
    assert max(scores) > 70.0


def test_mini_dataset_difficulty_fields():
    for record in load(MINI):
        difficulty = record["difficulty"]
        recomputed = score_record(record)
        assert difficulty["tier"] == tier_for_score(difficulty["score"])
        assert difficulty["label"] == TIER_LABELS[difficulty["tier"]]
        assert 0.0 <= difficulty["score"] <= 100.0
        assert set(difficulty["components"]) == set(COMPONENT_MAX)
        assert difficulty["score"] == recomputed.score
        assert difficulty["components"] == recomputed.components


def test_mini_dataset_ids_exist_in_full_set():
    mini_ids = {record["id"] for record in load(MINI)}
    full_ids = {record["id"] for record in load(BENCHMARK)}
    assert mini_ids <= full_ids


def test_mini_dataset_coverage():
    records = load(MINI)

    assert {record["element_class"] for record in records} == {
        "CHNO",
        "halogen",
        "S_P",
        "B_Si_Se_As",
        "metal",
    }
    assert {size_bin(record["heavy_atoms"]) for record in records} == {
        "1-10",
        "11-20",
        "21-30",
        "31-50",
        "51-100",
        "100+",
    }
    assert {ring_bin(record["rings"]["count"]) for record in records} == {
        "0",
        "1",
        "2",
        "3-4",
        "5+",
    }
    assert {record["stereo"]["bin"] for record in records} == {
        "none",
        "centers_1_2",
        "centers_3plus",
        "double_only",
        "centers_and_double",
    }
    assert {
        charge_bin(record["charge"], record["is_zwitterion"]) for record in records
    } == {"neutral", "negative", "positive", "zwitterion"}

    assert any(record["is_multi_component"] for record in records)
    assert any(record["is_salt"] for record in records)
    assert any(record["is_metal"] for record in records)
    assert any(record["is_zwitterion"] for record in records)
    assert any(record["is_radical"] for record in records)
    assert any(record["has_isotope"] for record in records)
    assert any(record["rings"]["macrocycle"] for record in records)
    assert any(record["rings"]["spiro_atoms"] for record in records)
    assert any(record["rings"]["bridgehead_atoms"] for record in records)

    groups = {group for record in records for group in record["functional_groups"]}
    assert len(groups) >= 50

    scaffolds = {record["scaffold"] for record in records if record["scaffold"]}
    assert len(scaffolds) >= 80
