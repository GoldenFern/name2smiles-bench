"""Redraw large molecules at a higher resolution."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from rdkit import Chem, RDLogger
from tqdm import tqdm

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from name2smiles.render import draw_png, draw_svg  # noqa: E402

RDLogger.DisableLog("rdApp.*")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, default=ROOT / "data" / "benchmark_v0.jsonl")
    parser.add_argument("--images", type=Path, default=ROOT / "data" / "images")
    parser.add_argument("--threshold", type=int, default=60)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    records = [json.loads(line) for line in args.data.open(encoding="utf-8")]
    targets = [record for record in records if record["heavy_atoms"] > args.threshold]
    print(f"targets: {len(targets)}")

    for record in tqdm(targets, desc="Redrawing"):
        mol = Chem.MolFromSmiles(record["smiles"])
        if mol is None:
            continue
        if record["heavy_atoms"] > 100:
            size = (1024, 1024)
        else:
            size = (768, 768)
        image_dir = args.images / record["id"]
        draw_png(mol, image_dir / "rdkit_clean_2d.png", size=size)
        draw_svg(mol, image_dir / "rdkit_clean_2d.svg", size=size)
        draw_png(mol, image_dir / "rdkit_no_stereo_2d.png", size=size, no_stereo=True)
        draw_png(mol, image_dir / "rdkit_atom_index_2d.png", size=size, add_indices=True)
    print("done")


if __name__ == "__main__":
    main()
