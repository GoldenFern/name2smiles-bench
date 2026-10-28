"""Validate the built dataset and its generated assets."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from rdkit import Chem, RDLogger

ROOT = Path(__file__).resolve().parents[1]
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

    issues: list[str] = []
    ids: Counter[str] = Counter()
    cids: Counter[int] = Counter()
    inchikeys: Counter[str] = Counter()
    missing_images: Counter[str] = Counter()
    missing_mol: Counter[str] = Counter()

    for record in records:
        ids[record["id"]] += 1
        cids[record["cid"]] += 1
        inchikeys[record["inchikey"]] += 1

        mol = Chem.MolFromSmiles(record["smiles"])
        if mol is None:
            issues.append(f"{record['id']}: invalid SMILES")
            continue
        if Chem.MolToInchiKey(mol) != record["inchikey"]:
            issues.append(f"{record['id']}: InChIKey mismatch")

        for key, relative in record["images"].items():
            path = ROOT / relative
            if not path.exists() or path.stat().st_size == 0:
                missing_images[key] += 1
        for key, relative in record["mol_files"].items():
            path = ROOT / relative
            if not path.exists() or path.stat().st_size == 0:
                missing_mol[key] += 1

    duplicate_ids = [key for key, count in ids.items() if count > 1]
    duplicate_cids = [key for key, count in cids.items() if count > 1]
    duplicate_inchikeys = [key for key, count in inchikeys.items() if count > 1]

    print(f"records: {len(records)}")
    print(f"duplicate ids: {len(duplicate_ids)}")
    print(f"duplicate cids: {len(duplicate_cids)}")
    print(f"duplicate inchikeys: {len(duplicate_inchikeys)}")
    print(f"issues: {len(issues)}")
    for issue in issues[:20]:
        print(f"  {issue}")
    print(f"missing images: {dict(missing_images)}")
    print(f"missing coordinate files: {dict(missing_mol)}")


if __name__ == "__main__":
    main()
