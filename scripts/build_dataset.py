"""Build the final JSONL dataset and all image/coordinate assets.

The script is resumable. Records already present in the output JSONL are
skipped, and existing files are left in place.

Example:
    python scripts/build_dataset.py --limit 30
    python scripts/build_dataset.py
"""

from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from rdkit import Chem, RDLogger
from tqdm import tqdm

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from name2smiles.pubchem import fetch_png, fetch_sdf, fetch_synonyms  # noqa: E402
from name2smiles.render import (  # noqa: E402
    LOWRES_SIZE,
    PNG_SIZE,
    draw_png,
    draw_svg,
    embed_3d,
    mol_to_2d_sdf,
)

RDLogger.DisableLog("rdApp.*")


def clean_synonyms(values: list[str], *, limit: int = 50) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        text = " ".join(str(value).split())
        if not (2 <= len(text) <= 120):
            continue
        key = text.casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(text)
        if len(result) >= limit:
            break
    return result


def load_done(path: Path) -> set[str]:
    done: set[str] = set()
    if not path.exists():
        return done
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if "id" in record:
                done.add(record["id"])
    return done


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--selected", type=Path, default=ROOT / "data" / "selected.jsonl")
    parser.add_argument("--out", type=Path, default=ROOT / "data" / "benchmark_v0.jsonl")
    parser.add_argument("--images", type=Path, default=ROOT / "data" / "images")
    parser.add_argument("--mol", type=Path, default=ROOT / "data" / "mol")
    parser.add_argument("--raw", type=Path, default=ROOT / "data" / "raw" / "pubchem")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--skip-pubchem-image", action="store_true")
    parser.add_argument("--skip-3d", action="store_true")
    parser.add_argument("--skip-synonyms", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    for path in (args.images, args.mol, args.raw):
        path.mkdir(parents=True, exist_ok=True)

    selected: list[dict] = []
    with args.selected.open(encoding="utf-8") as handle:
        for line in handle:
            selected.append(json.loads(line))
    if args.limit:
        selected = selected[: args.limit]

    done = load_done(args.out)
    errors: list[str] = []
    mode = "a" if args.out.exists() else "w"
    executor = ThreadPoolExecutor(max_workers=3)

    with args.out.open(mode, encoding="utf-8") as output:
        for record in tqdm(selected, desc="Building"):
            dataset_id = record["dataset_id"]
            if dataset_id in done:
                continue

            cid = int(record["cid"])
            properties = record["properties"]
            desc = record["descriptors"]
            smiles = properties["SMILES"]
            name = properties["IUPACName"]
            mol = Chem.MolFromSmiles(smiles)
            if mol is None:
                errors.append(f"{dataset_id}\t{cid}\tRDKit parse failed")
                continue

            image_dir = args.images / dataset_id
            mol_dir = args.mol / dataset_id
            image_dir.mkdir(parents=True, exist_ok=True)
            mol_dir.mkdir(parents=True, exist_ok=True)

            images: dict[str, str] = {}
            mol_files: dict[str, str] = {}
            if desc["heavy_atoms"] > 100:
                clean_size = (1024, 1024)
            elif desc["heavy_atoms"] > 60:
                clean_size = (768, 768)
            else:
                clean_size = PNG_SIZE

            try:
                draw_png(mol, image_dir / "rdkit_clean_2d.png", size=clean_size)
                images["rdkit_clean_png"] = str(
                    (image_dir / "rdkit_clean_2d.png").relative_to(ROOT)
                )
                draw_svg(mol, image_dir / "rdkit_clean_2d.svg", size=clean_size)
                images["rdkit_clean_svg"] = str(
                    (image_dir / "rdkit_clean_2d.svg").relative_to(ROOT)
                )
                draw_png(
                    mol,
                    image_dir / "rdkit_no_stereo_2d.png",
                    size=clean_size,
                    no_stereo=True,
                )
                images["rdkit_no_stereo_png"] = str(
                    (image_dir / "rdkit_no_stereo_2d.png").relative_to(ROOT)
                )
                draw_png(
                    mol,
                    image_dir / "rdkit_atom_index_2d.png",
                    size=clean_size,
                    add_indices=True,
                )
                images["rdkit_atom_index_png"] = str(
                    (image_dir / "rdkit_atom_index_2d.png").relative_to(ROOT)
                )
                draw_png(
                    mol,
                    image_dir / "rdkit_lowres_2d.png",
                    size=LOWRES_SIZE,
                )
                images["rdkit_lowres_png"] = str(
                    (image_dir / "rdkit_lowres_2d.png").relative_to(ROOT)
                )
            except Exception as exc:
                errors.append(f"{dataset_id}\t{cid}\tRDKit image failed: {exc}")

            try:
                (mol_dir / "rdkit_2d.sdf").write_text(
                    mol_to_2d_sdf(mol), encoding="utf-8"
                )
                mol_files["rdkit_2d_sdf"] = str(
                    (mol_dir / "rdkit_2d.sdf").relative_to(ROOT)
                )
            except Exception as exc:
                errors.append(f"{dataset_id}\t{cid}\t2D SDF failed: {exc}")

            futures = {}
            if not args.skip_synonyms:
                futures["synonyms"] = executor.submit(fetch_synonyms, cid)
            if not args.skip_pubchem_image:
                futures["png"] = executor.submit(fetch_png, cid, size=500)
            if not args.skip_3d:
                futures["sdf"] = executor.submit(fetch_sdf, cid, record_type="3d")

            synonyms: list[str] = []
            if "synonyms" in futures:
                try:
                    synonyms = clean_synonyms(futures["synonyms"].result())
                except Exception as exc:
                    errors.append(f"{dataset_id}\t{cid}\tsynonyms failed: {exc}")

            if "png" in futures:
                try:
                    png = futures["png"].result()
                    if png:
                        (image_dir / "pubchem_2d.png").write_bytes(png)
                        images["pubchem_2d_png"] = str(
                            (image_dir / "pubchem_2d.png").relative_to(ROOT)
                        )
                except Exception as exc:
                    errors.append(f"{dataset_id}\t{cid}\tPubChem image failed: {exc}")

            if "sdf" in futures:
                try:
                    sdf = futures["sdf"].result()
                    if sdf:
                        (mol_dir / "pubchem_3d.sdf").write_text(sdf, encoding="utf-8")
                        mol_files["pubchem_3d_sdf"] = str(
                            (mol_dir / "pubchem_3d.sdf").relative_to(ROOT)
                        )
                    elif desc["heavy_atoms"] <= 80:
                        fallback = embed_3d(smiles)
                        if fallback:
                            (mol_dir / "rdkit_etkdg_3d.sdf").write_text(
                                fallback, encoding="utf-8"
                            )
                            mol_files["rdkit_etkdg_3d_sdf"] = str(
                                (mol_dir / "rdkit_etkdg_3d.sdf").relative_to(ROOT)
                            )
                except Exception as exc:
                    errors.append(f"{dataset_id}\t{cid}\t3D failed: {exc}")

            retrieved_at = datetime.now(timezone.utc).isoformat()
            raw_payload = {
                "cid": cid,
                "properties": properties,
                "synonyms": synonyms,
                "retrieved_at": retrieved_at,
            }
            (args.raw / f"{cid}.json").write_text(
                json.dumps(raw_payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            payload = {
                "id": dataset_id,
                "cid": cid,
                "name": name,
                "name_type": "iupac",
                "iupac_name": name,
                "synonyms": synonyms,
                "smiles": smiles,
                "canonical_smiles": desc["canonical_smiles"],
                "connectivity_smiles": desc["connectivity_smiles"],
                "inchikey": desc["inchi_key"],
                "formula": desc["formula"],
                "molecular_weight": desc["molecular_weight"],
                "charge": desc["charge"],
                "heavy_atoms": desc["heavy_atoms"],
                "elements": desc["elements"],
                "element_class": desc["element_class"],
                "rings": {
                    "count": desc["ring_count"],
                    "sizes": desc["ring_sizes"],
                    "aromatic": desc["aromatic_rings"],
                    "aliphatic": desc["aliphatic_rings"],
                    "saturated": desc["saturated_rings"],
                    "max_size": desc["max_ring_size"],
                    "spiro_atoms": desc["spiro_atoms"],
                    "bridgehead_atoms": desc["bridgehead_atoms"],
                    "macrocycle": desc["macrocycle"],
                },
                "stereo": {
                    "centers": desc["stereo_centers"],
                    "defined_centers": desc["defined_stereo_centers"],
                    "undefined_centers": desc["undefined_stereo_centers"],
                    "double_bonds": desc["double_bond_stereo"],
                    "bin": desc["stereo_bin"],
                },
                "functional_groups": desc["functional_groups"],
                "fragments": desc["component_smiles"],
                "fragment_heavy_atoms": desc["component_heavy_atoms"],
                "is_multi_component": desc["multi_component"],
                "is_salt": desc["is_salt"],
                "is_metal": desc["is_metal"],
                "is_radical": desc["is_radical"],
                "is_zwitterion": desc["zwitterion"],
                "has_isotope": desc["has_isotope"],
                "isotopes": desc["isotopes"],
                "scaffold": desc["scaffold"],
                "images": images,
                "mol_files": mol_files,
                "source": "PubChem",
                "source_url": f"https://pubchem.ncbi.nlm.nih.gov/compound/{cid}",
                "license": "PubChem computed data",
                "retrieved_at": retrieved_at,
            }
            output.write(json.dumps(payload, ensure_ascii=False) + "\n")
            output.flush()

    executor.shutdown(wait=True)

    if errors:
        error_path = ROOT / "data" / "build_errors.log"
        error_path.write_text("\n".join(errors) + "\n", encoding="utf-8")
        print(f"errors: {len(errors)} (see {error_path})")
    else:
        print("errors: 0")
    print(f"wrote: {args.out}")


if __name__ == "__main__":
    main()
