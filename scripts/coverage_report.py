"""Generate a coverage report for the built dataset."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def markdown_table(title: str, counts: dict[str, int], total: int | None = None) -> list[str]:
    lines = [f"## {title}", "", "| Category | Count |", "|---|---:|"]
    for key, value in counts.items():
        lines.append(f"| {key} | {value} |")
    if total is not None:
        lines.append(f"| **Total records** | **{total}** |")
    lines.append("")
    return lines


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, default=ROOT / "data" / "benchmark_v0.jsonl")
    parser.add_argument("--out", type=Path, default=ROOT / "docs" / "coverage.md")
    parser.add_argument("--csv", type=Path, default=ROOT / "docs" / "coverage.csv")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    records: list[dict] = []
    with args.data.open(encoding="utf-8") as handle:
        for line in handle:
            records.append(json.loads(line))

    total = len(records)
    element_records: Counter[str] = Counter()
    element_atoms: Counter[str] = Counter()
    element_classes: Counter[str] = Counter()
    sizes: Counter[str] = Counter()
    rings: Counter[str] = Counter()
    stereo: Counter[str] = Counter()
    charges: Counter[str] = Counter()
    functional_groups: Counter[str] = Counter()
    scaffolds: Counter[str] = Counter()
    image_counts: Counter[str] = Counter()
    mol_counts: Counter[str] = Counter()
    flags: Counter[str] = Counter()

    for record in records:
        for element, count in record["elements"].items():
            element_records[element] += 1
            element_atoms[element] += count
        element_classes[record["element_class"]] += 1
        sizes[_size_bin(record["heavy_atoms"])] += 1
        rings[str(record["rings"]["count"])] += 1
        stereo[record["stereo"]["bin"]] += 1
        charges[_charge_bin(record)] += 1
        for group in record["functional_groups"]:
            functional_groups[group] += 1
        scaffolds[record["scaffold"] or "(empty)"] += 1
        for key in record["images"]:
            image_counts[key] += 1
        for key in record["mol_files"]:
            mol_counts[key] += 1
        if record["is_multi_component"]:
            flags["multi_component"] += 1
        if record["is_salt"]:
            flags["salt"] += 1
        if record["is_metal"]:
            flags["metal"] += 1
        if record["is_radical"]:
            flags["radical"] += 1
        if record["is_zwitterion"]:
            flags["zwitterion"] += 1
        if record["has_isotope"]:
            flags["isotope"] += 1
        if record["rings"]["macrocycle"]:
            flags["macrocycle"] += 1
        if record["rings"]["spiro_atoms"] > 0:
            flags["spiro"] += 1
        if record["rings"]["bridgehead_atoms"] > 0:
            flags["bridgehead"] += 1

    lines = [
        "# Dataset Coverage",
        "",
        f"Records: **{total}**",
        f"Unique InChIKeys: **{len({r['inchikey'] for r in records})}**",
        f"Unique Murcko scaffolds: **{len({r['scaffold'] for r in records if r['scaffold']})}**",
        "",
    ]
    lines += markdown_table("Element classes", dict(element_classes.most_common()), total)
    lines += markdown_table("Elements by record count", dict(element_records.most_common()))
    lines += markdown_table("Elements by atom count", dict(element_atoms.most_common()))
    lines += markdown_table("Heavy-atom bins", dict(sizes.most_common()))
    lines += markdown_table("Ring counts", dict(rings.most_common()))
    lines += markdown_table("Stereo bins", dict(stereo.most_common()))
    lines += markdown_table("Charge bins", dict(charges.most_common()))
    lines += markdown_table("Flags", dict(flags.most_common()))
    lines += markdown_table("Functional groups", dict(functional_groups.most_common()))
    lines += markdown_table("Images", dict(image_counts.most_common()))
    lines += markdown_table("Coordinate files", dict(mol_counts.most_common()))
    lines += markdown_table("Top 30 Murcko scaffolds", dict(scaffolds.most_common(30)))

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("\n".join(lines), encoding="utf-8")

    rows = []
    for record in records:
        rows.append(
            {
                "id": record["id"],
                "cid": record["cid"],
                "name": record["name"],
                "inchikey": record["inchikey"],
                "formula": record["formula"],
                "heavy_atoms": record["heavy_atoms"],
                "element_class": record["element_class"],
                "rings": record["rings"]["count"],
                "stereo_bin": record["stereo"]["bin"],
                "charge": record["charge"],
                "functional_groups": ";".join(record["functional_groups"]),
                "is_metal": record["is_metal"],
                "is_radical": record["is_radical"],
                "is_zwitterion": record["is_zwitterion"],
                "has_isotope": record["has_isotope"],
                "is_multi_component": record["is_multi_component"],
                "scaffold": record["scaffold"],
            }
        )
    pd.DataFrame(rows).to_csv(args.csv, index=False, encoding="utf-8")
    print(f"wrote {args.out} and {args.csv}")
    print(f"records: {total}")
    print(f"element classes: {dict(element_classes)}")
    print(f"size bins: {dict(sizes)}")
    print(f"ring bins: {dict(rings)}")
    print(f"stereo bins: {dict(stereo)}")


def _size_bin(heavy_atoms: int) -> str:
    if heavy_atoms <= 10:
        return "1-10"
    if heavy_atoms <= 20:
        return "11-20"
    if heavy_atoms <= 30:
        return "21-30"
    if heavy_atoms <= 50:
        return "31-50"
    if heavy_atoms <= 100:
        return "51-100"
    return "100+"


def _charge_bin(record: dict) -> str:
    if record["is_zwitterion"]:
        return "zwitterion"
    if record["charge"] < 0:
        return "negative"
    if record["charge"] > 0:
        return "positive"
    return "neutral"


if __name__ == "__main__":
    main()
