"""Select a coverage-aware subset from the PubChem candidate pool.

The selection is greedy: candidates that fill under-represented descriptor
bins are preferred. It is not a random sample.

Example:
    python scripts/select_dataset.py --n 1500
"""

from __future__ import annotations

import argparse
import heapq
import json
import random
import sys
from collections import Counter
from pathlib import Path

from tqdm import tqdm

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from name2smiles.descriptors import FUNCTIONAL_GROUP_SMARTS  # noqa: E402
from name2smiles.names import name_quality  # noqa: E402

TARGETS: dict[str, int] = {}
WEIGHTS: dict[str, float] = {}


def add_targets(prefix: str, values: dict[str, int], weight: float) -> None:
    for key, target in values.items():
        bin_id = f"{prefix}:{key}"
        TARGETS[bin_id] = target
        WEIGHTS[bin_id] = weight


add_targets(
    "element",
    {
        "CHNO": 750,
        "halogen": 300,
        "S_P": 250,
        "B_Si_Se_As": 80,
        "metal": 100,
    },
    5.0,
)
add_targets(
    "size",
    {"1-10": 120, "11-20": 450, "21-30": 550, "31-50": 300, "51-100": 70, "100+": 10},
    2.0,
)
add_targets("ring", {"0": 250, "1": 450, "2": 400, "3-4": 300, "5+": 100}, 2.0)
add_targets(
    "stereo",
    {
        "none": 550,
        "centers_1_2": 600,
        "centers_3plus": 200,
        "double_only": 100,
        "centers_and_double": 50,
    },
    1.2,
)
add_targets(
    "charge",
    {"neutral": 1250, "negative": 100, "positive": 100, "zwitterion": 50},
    1.0,
)
add_targets(
    "flag",
    {
        "multi": 120,
        "spiro": 60,
        "bridgehead": 60,
        "macrocycle": 60,
        "radical": 20,
        "isotope": 40,
    },
    4.0,
)
add_targets(
    "fg",
    {name: 15 for name in FUNCTIONAL_GROUP_SMARTS},
    1.0,
)


def candidate_bins(desc: dict) -> list[str]:
    bins = [
        f"element:{desc['element_class']}",
        f"size:{desc['size_bin']}",
        f"ring:{desc['ring_bin']}",
        f"stereo:{desc['stereo_bin']}",
        f"charge:{desc['charge_bin']}",
    ]
    if desc["multi_component"]:
        bins.append("flag:multi")
    if desc["spiro_atoms"] > 0:
        bins.append("flag:spiro")
    if desc["bridgehead_atoms"] > 0:
        bins.append("flag:bridgehead")
    if desc["macrocycle"]:
        bins.append("flag:macrocycle")
    if desc["is_radical"]:
        bins.append("flag:radical")
    if desc["has_isotope"]:
        bins.append("flag:isotope")
    for group in desc["functional_groups"]:
        bin_id = f"fg:{group}"
        if bin_id in TARGETS:
            bins.append(bin_id)
    return bins


def score(bins: list[str], counts: Counter[str]) -> float:
    total = 0.0
    for bin_id in bins:
        target = TARGETS.get(bin_id)
        if not target:
            continue
        remaining = target - counts[bin_id]
        if remaining > 0:
            total += WEIGHTS.get(bin_id, 1.0) * remaining / target
    return total


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidates", type=Path, default=ROOT / "data" / "candidates.jsonl")
    parser.add_argument("--n", type=int, default=1500)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--scaffold-cap", type=int, default=5)
    parser.add_argument("--out", type=Path, default=ROOT / "data" / "selected.jsonl")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    random.seed(args.seed)

    candidates: list[dict] = []
    rejected_names = 0
    with args.candidates.open(encoding="utf-8") as handle:
        for line in handle:
            record = json.loads(line)
            desc = record["descriptors"]
            accepted, _reason = name_quality(
                record["properties"]["IUPACName"],
                num_components=desc["num_components"],
            )
            if not accepted:
                rejected_names += 1
                continue
            record["bins"] = candidate_bins(desc)
            candidates.append(record)

    print(f"candidates: {len(candidates)} (rejected names: {rejected_names})")
    if len(candidates) < args.n:
        raise SystemExit(f"not enough candidates: need {args.n}, have {len(candidates)}")

    heap: list[tuple[float, float, int]] = []
    for index, record in enumerate(candidates):
        initial = score(record["bins"], Counter())
        heapq.heappush(heap, (-initial, random.random(), index))

    selected: list[dict] = []
    selected_indices: set[int] = set()
    counts: Counter[str] = Counter()
    scaffold_counts: Counter[str] = Counter()

    progress = tqdm(total=args.n, desc="Selecting")
    while heap and len(selected) < args.n:
        negative_score, jitter, index = heapq.heappop(heap)
        if index in selected_indices:
            continue
        record = candidates[index]
        scaffold = record["descriptors"]["scaffold"] or f"cid:{record['cid']}"
        if scaffold_counts[scaffold] >= args.scaffold_cap:
            continue

        current_score = score(record["bins"], counts)
        if current_score + 1e-9 < -negative_score:
            heapq.heappush(heap, (-current_score, random.random(), index))
            continue

        selected.append(record)
        selected_indices.add(index)
        scaffold_counts[scaffold] += 1
        for bin_id in record["bins"]:
            counts[bin_id] += 1
        progress.update(1)

    if len(selected) < args.n:
        for index, record in enumerate(candidates):
            if len(selected) >= args.n:
                break
            if index in selected_indices:
                continue
            scaffold = record["descriptors"]["scaffold"] or f"cid:{record['cid']}"
            if scaffold_counts[scaffold] >= args.scaffold_cap:
                continue
            selected.append(record)
            selected_indices.add(index)
            scaffold_counts[scaffold] += 1
            for bin_id in record["bins"]:
                counts[bin_id] += 1
            progress.update(1)
    progress.close()

    selected.sort(key=lambda record: record["cid"])
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as handle:
        for number, record in enumerate(selected, start=1):
            record["dataset_id"] = f"N2S-{number:06d}"
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    print(f"selected: {len(selected)}")
    print("coverage:")
    for prefix in ("element", "size", "ring", "stereo", "charge"):
        selected_counts = {
            bin_id.split(":", 1)[1]: count
            for bin_id, count in counts.items()
            if bin_id.startswith(prefix + ":")
        }
        print(f"  {prefix}: {selected_counts}")

    missing = []
    for bin_id, target in TARGETS.items():
        if counts[bin_id] < target:
            missing.append((bin_id, counts[bin_id], target))
    print(f"underfilled bins: {len(missing)}")
    for bin_id, actual, target in missing[:40]:
        print(f"  {bin_id}: {actual}/{target}")

    print(f"wrote: {args.out}")


if __name__ == "__main__":
    main()
