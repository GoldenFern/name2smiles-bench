"""Select a small, difficulty-graded subset of the benchmark dataset.

The selection has two layers:

1. Every record gets a heuristic difficulty score.
2. A greedy pass fills per-tier quotas while preferring records that cover
   under-represented element, size, ring, stereo, charge, flag, and
   functional-group bins.

Example:
    python scripts/select_mini_dataset.py --n 100
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import statistics
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from name2smiles.descriptors import charge_bin, ring_bin, size_bin  # noqa: E402
from name2smiles.difficulty import (  # noqa: E402
    COMPONENT_MAX,
    TIER_KEYS,
    TIER_LABELS,
    score_record,
    tier_range,
)

TIER_RATIOS: dict[str, float] = {
    "L1": 0.25,
    "L2": 0.30,
    "L3": 0.20,
    "L4": 0.15,
    "L5": 0.10,
}

ELEMENT_TARGETS: dict[str, int] = {
    "CHNO": 48,
    "halogen": 20,
    "S_P": 20,
    "B_Si_Se_As": 7,
    "metal": 5,
}
SIZE_TARGETS: dict[str, int] = {
    "1-10": 8,
    "11-20": 30,
    "21-30": 37,
    "31-50": 20,
    "51-100": 4,
    "100+": 1,
}
RING_TARGETS: dict[str, int] = {
    "0": 16,
    "1": 30,
    "2": 27,
    "3-4": 20,
    "5+": 7,
}
STEREO_TARGETS: dict[str, int] = {
    "none": 37,
    "centers_1_2": 40,
    "centers_3plus": 13,
    "double_only": 7,
    "centers_and_double": 3,
}
CHARGE_TARGETS: dict[str, int] = {
    "neutral": 82,
    "negative": 7,
    "positive": 7,
    "zwitterion": 4,
}
FLAG_TARGETS: dict[str, int] = {
    "multi": 10,
    "salt": 10,
    "spiro": 5,
    "bridgehead": 5,
    "macrocycle": 5,
    "radical": 1,
    "isotope": 3,
}

FLAG_LABELS: dict[str, str] = {
    "multi": "Multi-component",
    "salt": "Salt",
    "metal": "Metal-containing",
    "zwitterion": "Zwitterion",
    "radical": "Radical",
    "isotope": "Isotope-labeled",
    "macrocycle": "Macrocycle",
    "spiro": "Spiro",
    "bridgehead": "Bridgehead",
}


def scale_partition(values: dict[str, int], n: int) -> dict[str, int]:
    """Scale partition targets so they sum to ``n`` (largest remainder)."""
    total = sum(values.values())
    raw = {key: value * n / total for key, value in values.items()}
    scaled = {key: int(value) for key, value in raw.items()}
    remainder = n - sum(scaled.values())
    order = sorted(
        raw,
        key=lambda key: (raw[key] - scaled[key], -list(raw).index(key)),
        reverse=True,
    )
    for key in order[:remainder]:
        scaled[key] += 1
    return scaled


def allocate_quotas(n: int) -> dict[str, int]:
    """Allocate tier quotas by ratio, with the largest remainder method."""
    total = sum(TIER_RATIOS.values())
    raw = {key: n * value / total for key, value in TIER_RATIOS.items()}
    quotas = {key: int(value) for key, value in raw.items()}
    remainder = n - sum(quotas.values())
    order = sorted(
        raw,
        key=lambda key: (raw[key] - quotas[key], -TIER_KEYS.index(key)),
        reverse=True,
    )
    for key in order[:remainder]:
        quotas[key] += 1
    return quotas


def build_targets(
    records: list[dict[str, Any]], n: int
) -> tuple[dict[str, int], dict[str, float], Counter[str]]:
    """Build coverage targets and weights for a mini set of ``n`` records."""
    targets: dict[str, int] = {}
    weights: dict[str, float] = {}

    def add(prefix: str, values: dict[str, int], weight: float) -> None:
        for key, target in values.items():
            bin_id = f"{prefix}:{key}"
            targets[bin_id] = target
            weights[bin_id] = weight

    add("element", scale_partition(ELEMENT_TARGETS, n), 5.0)
    add("size", scale_partition(SIZE_TARGETS, n), 2.0)
    add("ring", scale_partition(RING_TARGETS, n), 2.0)
    add("stereo", scale_partition(STEREO_TARGETS, n), 1.5)
    add("charge", scale_partition(CHARGE_TARGETS, n), 1.0)

    for flag, target in FLAG_TARGETS.items():
        targets[f"flag:{flag}"] = max(1, round(target * n / 100))
        weights[f"flag:{flag}"] = 4.0

    pool_counts: Counter[str] = Counter(
        group for record in records for group in record["functional_groups"]
    )
    for group, count in pool_counts.items():
        target = 2 if count >= 100 else 1
        targets[f"fg:{group}"] = max(1, round(target * n / 100))
        weights[f"fg:{group}"] = 1.0
    return targets, weights, pool_counts


def record_bins(record: dict[str, Any]) -> list[str]:
    """Return the coverage bins a record fills."""
    bins = [
        f"element:{record['element_class']}",
        f"size:{size_bin(int(record['heavy_atoms']))}",
        f"ring:{ring_bin(int(record['rings']['count']))}",
        f"stereo:{record['stereo']['bin']}",
        f"charge:{charge_bin(int(record['charge']), bool(record['is_zwitterion']))}",
    ]
    if record.get("is_multi_component"):
        bins.append("flag:multi")
    if record.get("is_salt"):
        bins.append("flag:salt")
    if record.get("is_radical"):
        bins.append("flag:radical")
    if record.get("has_isotope"):
        bins.append("flag:isotope")
    rings = record["rings"]
    if rings.get("macrocycle"):
        bins.append("flag:macrocycle")
    if int(rings.get("spiro_atoms", 0)) > 0:
        bins.append("flag:spiro")
    if int(rings.get("bridgehead_atoms", 0)) > 0:
        bins.append("flag:bridgehead")
    bins.extend(f"fg:{group}" for group in record["functional_groups"])
    return bins


def coverage_score(
    bins: list[str],
    counts: Counter[str],
    targets: dict[str, int],
    weights: dict[str, float],
) -> float:
    """Score how much a candidate fills under-represented bins."""
    total = 0.0
    for bin_id in bins:
        target = targets.get(bin_id)
        if not target:
            continue
        remaining = target - counts[bin_id]
        if remaining > 0:
            total += weights.get(bin_id, 1.0) * remaining / target
    return total


def prepare_candidates(
    records: list[dict[str, Any]], seed: int
) -> list[dict[str, Any]]:
    """Attach difficulty, coverage bins, and a deterministic tie-breaker."""
    rng = random.Random(seed)
    candidates: list[dict[str, Any]] = []
    for record in records:
        difficulty = score_record(record)
        candidate = dict(record)
        candidate["difficulty"] = difficulty.to_dict()
        candidate["_bins"] = record_bins(record)
        candidate["_jitter"] = rng.random()
        candidates.append(candidate)
    return candidates


def select_candidates(
    candidates: list[dict[str, Any]],
    quotas: dict[str, int],
    targets: dict[str, int],
    weights: dict[str, float],
    scaffold_cap: int,
    acyclic_cap: int,
    anchor_each: int,
) -> list[dict[str, Any]]:
    """Greedily select records under tier quotas and scaffold caps.

    The easiest and hardest ``anchor_each`` records are seeded first so the
    mini set spans the full difficulty range. The remaining slots use coverage.
    """
    by_tier = {
        tier: [
            candidate
            for candidate in candidates
            if candidate["difficulty"]["tier"] == tier
        ]
        for tier in TIER_KEYS
    }
    for tier, pool in by_tier.items():
        if len(pool) < quotas[tier]:
            raise SystemExit(
                f"tier {tier} has {len(pool)} candidates, needs {quotas[tier]}"
            )

    selected: list[dict[str, Any]] = []
    selected_ids: set[str] = set()
    counts: Counter[str] = Counter()
    scaffold_counts: Counter[str] = Counter()
    remaining = dict(quotas)

    def add(candidate: dict[str, Any]) -> None:
        tier = candidate["difficulty"]["tier"]
        selected.append(candidate)
        selected_ids.add(candidate["id"])
        remaining[tier] -= 1
        scaffold = candidate["scaffold"] or ""
        scaffold_counts[scaffold] += 1
        for bin_id in candidate["_bins"]:
            counts[bin_id] += 1

    ordered = sorted(
        candidates,
        key=lambda candidate: (
            candidate["difficulty"]["score"],
            candidate["cid"],
        ),
    )
    anchors = ordered[:anchor_each] + ordered[-anchor_each:] if anchor_each > 0 else []
    for candidate in anchors:
        tier = candidate["difficulty"]["tier"]
        scaffold = candidate["scaffold"] or ""
        cap = acyclic_cap if not scaffold else scaffold_cap
        if (
            candidate["id"] in selected_ids
            or remaining[tier] <= 0
            or scaffold_counts[scaffold] >= cap
        ):
            continue
        add(candidate)

    while len(selected) < sum(quotas.values()):
        tier = max(
            (key for key in TIER_KEYS if remaining[key] > 0),
            key=lambda key: (
                remaining[key] / quotas[key],
                -TIER_KEYS.index(key),
            ),
        )
        best: dict[str, Any] | None = None
        best_key: tuple[float, float] | None = None
        for candidate in by_tier[tier]:
            if candidate["id"] in selected_ids:
                continue
            scaffold = candidate["scaffold"] or ""
            cap = acyclic_cap if not scaffold else scaffold_cap
            if scaffold_counts[scaffold] >= cap:
                continue
            score = coverage_score(candidate["_bins"], counts, targets, weights)
            key = (score, candidate["_jitter"])
            if best_key is None or key > best_key:
                best = candidate
                best_key = key
        if best is None:
            raise SystemExit(
                f"no eligible candidate left for tier {tier}; "
                f"relax --scaffold-cap or --acyclic-cap"
            )
        add(best)

    selected.sort(
        key=lambda candidate: (
            TIER_KEYS.index(candidate["difficulty"]["tier"]),
            candidate["difficulty"]["score"],
            candidate["cid"],
        )
    )
    return selected


def output_record(candidate: dict[str, Any], number: int) -> dict[str, Any]:
    """Return a clean output record with a mini-set ID."""
    data = {key: value for key, value in candidate.items() if not key.startswith("_")}
    return {"mini_id": f"M2S-{number:06d}", **data}


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def write_csv(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "mini_id",
        "id",
        "inchikey",
        "tier",
        "tier_label",
        "difficulty_score",
        "name",
        "formula",
        "heavy_atoms",
        "rings",
        "stereo_bin",
        "element_class",
        "charge",
        "is_multi_component",
        "is_salt",
        "is_metal",
        "is_zwitterion",
        "has_isotope",
        "scaffold",
        "canonical_smiles",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for record in records:
            writer.writerow(
                {
                    "mini_id": record["mini_id"],
                    "id": record["id"],
                    "inchikey": record["inchikey"],
                    "tier": record["difficulty"]["tier"],
                    "tier_label": record["difficulty"]["label"],
                    "difficulty_score": record["difficulty"]["score"],
                    "name": record["name"],
                    "formula": record["formula"],
                    "heavy_atoms": record["heavy_atoms"],
                    "rings": record["rings"]["count"],
                    "stereo_bin": record["stereo"]["bin"],
                    "element_class": record["element_class"],
                    "charge": record["charge"],
                    "is_multi_component": record["is_multi_component"],
                    "is_salt": record["is_salt"],
                    "is_metal": record["is_metal"],
                    "is_zwitterion": record["is_zwitterion"],
                    "has_isotope": record["has_isotope"],
                    "scaffold": record["scaffold"],
                    "canonical_smiles": record["canonical_smiles"],
                }
            )


def _count(
    records: list[dict[str, Any]], key: Callable[[dict[str, Any]], str]
) -> Counter[str]:
    return Counter(key(record) for record in records)


_FLAG_FIELDS: dict[str, str] = {
    "multi": "is_multi_component",
    "salt": "is_salt",
    "metal": "is_metal",
    "zwitterion": "is_zwitterion",
    "radical": "is_radical",
    "isotope": "has_isotope",
}


def _flag_value(record: dict[str, Any], flag: str) -> bool:
    if flag in _FLAG_FIELDS:
        return bool(record[_FLAG_FIELDS[flag]])
    rings = record["rings"]
    if flag == "macrocycle":
        return bool(rings["macrocycle"])
    if flag == "spiro":
        return int(rings["spiro_atoms"]) > 0
    if flag == "bridgehead":
        return int(rings["bridgehead_atoms"]) > 0
    raise ValueError(f"unknown flag: {flag}")


def _format_count(count: int, total: int) -> str:
    return f"{count} ({count / total * 100:.1f}%)"


def _escape(value: str) -> str:
    return value.replace("|", "\\|")


def write_report(
    path: Path,
    full: list[dict[str, Any]],
    mini: list[dict[str, Any]],
    quotas: dict[str, int],
    targets: dict[str, int],
    pool_groups: Counter[str],
) -> None:
    """Write a Markdown report with the difficulty ladder and coverage."""
    full_count = len(full)
    mini_count = len(mini)
    lines: list[str] = [
        "# Mini Test Set",
        "",
        f"Records: **{mini_count}** selected from **{full_count}** "
        "benchmark records.",
        "",
        "The set is a difficulty-graded subset. Difficulty is a heuristic "
        "weighted score built from name complexity and structure complexity. "
        "It is meant for quick model comparison, not for absolute claims "
        "about model capability. The extremes of the score range are seeded "
        "first; the remaining slots are filled by coverage.",
        "",
        "## Difficulty ladder",
        "",
        "| Tier | Label | Score range | Quota | Offset | Selected | Score min | "
        "Score median | Score max | Heavy atoms median | Name length median |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    offset = 0
    for tier in TIER_KEYS:
        subset = [r for r in mini if r["difficulty"]["tier"] == tier]
        scores = [r["difficulty"]["score"] for r in subset]
        heavy = [r["heavy_atoms"] for r in subset]
        names = [len(r["name"]) for r in subset]
        lines.append(
            f"| {tier} | {TIER_LABELS[tier]} | {tier_range(tier)} | "
            f"{quotas[tier]} | {offset} | "
            f"{len(subset)} | {min(scores):g} | {statistics.median(scores):g} | "
            f"{max(scores):g} | {statistics.median(heavy):g} | "
            f"{statistics.median(names):g} |"
        )
        offset += quotas[tier]

    full_scores = [score_record(record).score for record in full]
    mini_scores = [record["difficulty"]["score"] for record in mini]
    lines += [
        "",
        f"Mean difficulty: **{statistics.mean(mini_scores):.1f}** in the mini "
        f"set vs **{statistics.mean(full_scores):.1f}** in the full set. "
        f"Median: **{statistics.median(mini_scores):.1f}** vs "
        f"**{statistics.median(full_scores):.1f}**. Score range: "
        f"**{min(mini_scores):g}-{max(mini_scores):g}** in the mini set vs "
        f"**{min(full_scores):g}-{max(full_scores):g}** in the full set.",
        "",
        "## Score composition",
        "",
        "| Component | Component cap | Mean contribution in mini set |",
        "|---|---:|---:|",
    ]
    components = list(mini[0]["difficulty"]["components"])
    for component in components:
        values = [record["difficulty"]["components"][component] for record in mini]
        lines.append(
            f"| {component} | {COMPONENT_MAX[component]:g} | "
            f"{statistics.mean(values):.2f} |"
        )
    lines += [
        "",
        "Component caps sum to more than 100 because the final score is "
        "clamped at 100.",
        "",
    ]

    lines += [
        "",
        "## Coverage",
        "",
        "Percentages use the full set and the mini set as their denominators.",
        "",
    ]

    specs: list[tuple[str, Callable[[dict[str, Any]], str], list[str]]] = [
        (
            "Element class",
            lambda r: r["element_class"],
            list(ELEMENT_TARGETS),
        ),
        (
            "Heavy-atom bin",
            lambda r: size_bin(int(r["heavy_atoms"])),
            list(SIZE_TARGETS),
        ),
        (
            "Ring count",
            lambda r: ring_bin(int(r["rings"]["count"])),
            list(RING_TARGETS),
        ),
        (
            "Stereo bin",
            lambda r: r["stereo"]["bin"],
            list(STEREO_TARGETS),
        ),
        (
            "Charge bin",
            lambda r: charge_bin(int(r["charge"]), bool(r["is_zwitterion"])),
            list(CHARGE_TARGETS),
        ),
    ]
    for title, key, order in specs:
        full_counter = _count(full, key)
        mini_counter = _count(mini, key)
        lines += [
            f"### {title}",
            "",
            "| Bin | Full set | Mini set |",
            "|---|---:|---:|",
        ]
        for bin_name in order:
            lines.append(
                f"| {bin_name} | "
                f"{_format_count(full_counter[bin_name], full_count)} | "
                f"{_format_count(mini_counter[bin_name], mini_count)} |"
            )
        lines.append("")

    flag_keys = [
        "multi",
        "salt",
        "metal",
        "zwitterion",
        "radical",
        "isotope",
        "macrocycle",
        "spiro",
        "bridgehead",
    ]
    lines += [
        "### Structural flags",
        "",
        "| Flag | Full set | Mini set |",
        "|---|---:|---:|",
    ]
    for flag in flag_keys:
        full_n = sum(1 for record in full if _flag_value(record, flag))
        mini_n = sum(1 for record in mini if _flag_value(record, flag))
        label = FLAG_LABELS.get(flag, flag)
        lines.append(
            f"| {label} | {_format_count(full_n, full_count)} | "
            f"{_format_count(mini_n, mini_count)} |"
        )

    lines += [
        "",
        "### Functional groups",
        "",
        "The floor is a minimum coverage target; counts can exceed it.",
        "",
        "| Group | Full set | Mini set | Floor |",
        "|---|---:|---:|---:|",
    ]
    covered = 0
    for group, count in pool_groups.most_common():
        mini_n = sum(1 for record in mini if group in record["functional_groups"])
        if mini_n:
            covered += 1
        lines.append(
            f"| {group} | {_format_count(count, full_count)} | "
            f"{mini_n} | {targets.get(f'fg:{group}', 0)} |"
        )
    missing = [
        group
        for group in pool_groups
        if not any(group in record["functional_groups"] for record in mini)
    ]
    lines += [
        "",
        f"Functional-group coverage: **{covered}/{len(pool_groups)}** groups.",
        "",
    ]
    if missing:
        lines += [
            "Not represented in the mini set: " + ", ".join(sorted(missing)) + ".",
            "",
        ]

    scaffolds = [record["scaffold"] for record in mini if record["scaffold"]]
    acyclic = sum(1 for record in mini if not record["scaffold"])
    lines += [
        "## Scaffold diversity",
        "",
        f"- Unique non-empty Murcko scaffolds: **{len(set(scaffolds))}** "
        f"across {len(scaffolds)} records.",
        f"- Acyclic records (empty scaffold): **{acyclic}**.",
        "",
        "## Selected records",
        "",
        "Names longer than 90 characters are truncated here. Full names and "
        "SMILES are in the JSONL and CSV files.",
        "",
        "| Mini ID | Tier | Score | Dataset ID | Name | Formula | Heavy atoms | "
        "Rings | Element class |",
        "|---|---|---:|---|---|---|---:|---:|---|",
    ]
    for record in mini:
        difficulty = record["difficulty"]
        name = record["name"]
        if len(name) > 90:
            name = name[:87] + "..."
        lines.append(
            f"| {record['mini_id']} | {difficulty['tier']} | "
            f"{difficulty['score']:g} | {record['id']} | "
            f"{_escape(name)} | {record['formula']} | "
            f"{record['heavy_atoms']} | {record['rings']['count']} | "
            f"{record['element_class']} |"
        )
    lines += [
        "",
        "## Usage",
        "",
        "```powershell",
        "python scripts/evaluate_name2smiles.py "
        f"--data data/mini_{mini_count}.jsonl --limit {mini_count} "
        '--models "deepseek-flash,qwen3.8-flash"',
        "```",
        "",
        "The file is sorted by tier, so `--offset` and `--limit` can select a "
        "single tier. Use the offset column in the ladder table.",
        "",
        "The records keep the original dataset IDs, image paths, and coordinate "
        "paths. The mini file is a view over the full set, not a copy of the "
        "generated assets.",
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8", newline="\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data",
        type=Path,
        default=ROOT / "data" / "benchmark_v0.jsonl",
    )
    parser.add_argument("--n", type=int, default=100)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--scaffold-cap",
        type=int,
        default=1,
        help="maximum records per non-empty Murcko scaffold",
    )
    parser.add_argument(
        "--acyclic-cap",
        type=int,
        default=20,
        help="maximum records with an empty scaffold",
    )
    parser.add_argument(
        "--anchor-each",
        type=int,
        default=2,
        help="seed this many easiest and hardest records before coverage",
    )
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--csv", type=Path, default=None)
    parser.add_argument("--report", type=Path, default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.n < len(TIER_KEYS):
        raise SystemExit(f"--n must be at least {len(TIER_KEYS)}")
    out_path = args.out or ROOT / "data" / f"mini_{args.n}.jsonl"
    csv_path = args.csv or ROOT / "data" / f"mini_{args.n}.csv"
    report_path = args.report or ROOT / "docs" / f"mini_{args.n}.md"

    with args.data.open(encoding="utf-8") as handle:
        records = [json.loads(line) for line in handle]

    candidates = prepare_candidates(records, args.seed)
    quotas = allocate_quotas(args.n)
    targets, weights, pool_groups = build_targets(records, args.n)
    selected = select_candidates(
        candidates,
        quotas,
        targets,
        weights,
        args.scaffold_cap,
        args.acyclic_cap,
        args.anchor_each,
    )
    mini = [
        output_record(candidate, number)
        for number, candidate in enumerate(selected, start=1)
    ]

    write_jsonl(out_path, mini)
    write_csv(csv_path, mini)
    write_report(report_path, records, mini, quotas, targets, pool_groups)

    counts = Counter(bin_id for candidate in selected for bin_id in candidate["_bins"])
    tier_counts = Counter(candidate["difficulty"]["tier"] for candidate in selected)
    print(f"source records: {len(records)}")
    print(f"selected: {len(mini)}")
    print(f"tiers: {dict(sorted(tier_counts.items()))}")
    print(f"quotas: {quotas}")

    underfilled = [
        (bin_id, counts[bin_id], target)
        for bin_id, target in targets.items()
        if counts[bin_id] < target
    ]
    underfilled.sort(key=lambda item: (item[1] / item[2], item[0]))
    print(f"underfilled bins: {len(underfilled)}")
    for bin_id, actual, target in underfilled[:30]:
        print(f"  {bin_id}: {actual}/{target}")

    print(f"wrote: {out_path}")
    print(f"wrote: {csv_path}")
    print(f"wrote: {report_path}")


if __name__ == "__main__":
    main()
