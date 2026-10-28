"""Recompute RDKit descriptors in an existing dataset JSONL.

Useful after changing the functional-group SMARTS library or descriptor code.
Structures, names, images, and coordinate files are left unchanged.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from rdkit import RDLogger
from tqdm import tqdm

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from name2smiles.descriptors import describe_molecule  # noqa: E402

RDLogger.DisableLog("rdApp.*")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, default=ROOT / "data" / "benchmark_v0.jsonl")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    records: list[dict] = []
    with args.data.open(encoding="utf-8") as handle:
        for line in handle:
            records.append(json.loads(line))

    changed = 0
    for record in tqdm(records, desc="Recomputing"):
        desc = describe_molecule(record["smiles"])
        if desc is None:
            continue
        record["formula"] = desc["formula"]
        record["molecular_weight"] = desc["molecular_weight"]
        record["charge"] = desc["charge"]
        record["heavy_atoms"] = desc["heavy_atoms"]
        record["elements"] = desc["elements"]
        record["element_class"] = desc["element_class"]
        record["functional_groups"] = desc["functional_groups"]
        record["rings"] = {
            "count": desc["ring_count"],
            "sizes": desc["ring_sizes"],
            "aromatic": desc["aromatic_rings"],
            "aliphatic": desc["aliphatic_rings"],
            "saturated": desc["saturated_rings"],
            "max_size": desc["max_ring_size"],
            "spiro_atoms": desc["spiro_atoms"],
            "bridgehead_atoms": desc["bridgehead_atoms"],
            "macrocycle": desc["macrocycle"],
        }
        record["stereo"] = {
            "centers": desc["stereo_centers"],
            "defined_centers": desc["defined_stereo_centers"],
            "undefined_centers": desc["undefined_stereo_centers"],
            "double_bonds": desc["double_bond_stereo"],
            "bin": desc["stereo_bin"],
        }
        record["is_radical"] = desc["is_radical"]
        record["is_zwitterion"] = desc["zwitterion"]
        record["is_multi_component"] = desc["multi_component"]
        record["is_salt"] = desc["is_salt"]
        record["is_metal"] = desc["is_metal"]
        record["has_isotope"] = desc["has_isotope"]
        record["isotopes"] = desc["isotopes"]
        record["fragments"] = desc["component_smiles"]
        record["fragment_heavy_atoms"] = desc["component_heavy_atoms"]
        record["scaffold"] = desc["scaffold"]
        changed += 1

    temp = args.data.with_suffix(".jsonl.tmp")
    with temp.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    temp.replace(args.data)
    print(f"recomputed: {changed}")
    print(f"wrote: {args.data}")


if __name__ == "__main__":
    main()
