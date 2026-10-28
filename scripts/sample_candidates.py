"""Sample random PubChem CIDs and compute RDKit descriptors.

This script builds a candidate pool. It does not select the final dataset.

Example:
    python scripts/sample_candidates.py --n 20000
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from collections import Counter
from pathlib import Path

from rdkit import RDLogger
from tqdm import tqdm

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from name2smiles.descriptors import describe_molecule  # noqa: E402
from name2smiles.pubchem import fetch_properties  # noqa: E402

RDLogger.DisableLog("rdApp.*")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=20_000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--max-cid", type=int, default=180_000_000)
    parser.add_argument("--batch-size", type=int, default=200)
    parser.add_argument("--out", type=Path, default=ROOT / "data" / "candidates.jsonl")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    random.seed(args.seed)
    cids = random.sample(range(1, args.max_cid), args.n)
    args.out.parent.mkdir(parents=True, exist_ok=True)

    fetched: list[dict] = []
    for start in tqdm(range(0, len(cids), args.batch_size), desc="PubChem batches"):
        batch = cids[start : start + args.batch_size]
        fetched.extend(fetch_properties(batch, batch_size=args.batch_size))

    kept = 0
    dropped = Counter()
    element_counts = Counter()
    size_counts = Counter()
    ring_counts = Counter()
    class_counts = Counter()
    stereo_counts = Counter()
    charge_counts = Counter()
    fg_counts = Counter()

    with args.out.open("w", encoding="utf-8") as handle:
        for record in tqdm(fetched, desc="Descriptors"):
            cid = record.get("CID")
            smiles = record.get("SMILES")
            name = record.get("IUPACName")

            if not cid or not smiles:
                dropped["missing_smiles"] += 1
                continue
            if not name or not (3 <= len(name) <= 200):
                dropped["missing_or_bad_iupac_name"] += 1
                continue
            if len(smiles) > 1000:
                dropped["smiles_too_long"] += 1
                continue

            desc = describe_molecule(smiles)
            if desc is None:
                dropped["rdkit_parse_failed"] += 1
                continue
            if desc["is_radioactive"]:
                dropped["radioactive"] += 1
                continue
            if desc["is_polymer"]:
                dropped["polymer"] += 1
                continue
            if desc["heavy_atoms"] > 120:
                dropped["too_large"] += 1
                continue
            if desc["num_components"] > 4:
                dropped["too_many_components"] += 1
                continue

            payload = {
                "cid": cid,
                "properties": {
                    "MolecularFormula": record.get("MolecularFormula"),
                    "SMILES": record.get("SMILES"),
                    "ConnectivitySMILES": record.get("ConnectivitySMILES"),
                    "InChIKey": record.get("InChIKey"),
                    "IUPACName": name,
                    "Charge": record.get("Charge"),
                    "HeavyAtomCount": record.get("HeavyAtomCount"),
                },
                "descriptors": desc,
            }
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
            kept += 1

            for element in desc["elements"]:
                element_counts[element] += 1
            size_counts[desc["size_bin"]] += 1
            ring_counts[desc["ring_bin"]] += 1
            class_counts[desc["element_class"]] += 1
            stereo_counts[desc["stereo_bin"]] += 1
            charge_counts[desc["charge_bin"]] += 1
            for group in desc["functional_groups"]:
                fg_counts[group] += 1

    print(f"fetched: {len(fetched)}")
    print(f"kept: {kept}")
    print(f"dropped: {dict(dropped)}")
    print(f"elements: {element_counts.most_common(30)}")
    print(f"size bins: {dict(size_counts)}")
    print(f"ring bins: {dict(ring_counts)}")
    print(f"element classes: {dict(class_counts)}")
    print(f"stereo bins: {dict(stereo_counts)}")
    print(f"charge bins: {dict(charge_counts)}")
    print(f"functional groups: {dict(fg_counts.most_common(30))}")
    print(f"wrote: {args.out}")


if __name__ == "__main__":
    main()
