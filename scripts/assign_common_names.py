"""Prefer a clean common synonym over the PubChem IUPAC name.

This is a post-processing step. It does not change structures or images.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

_BAD_PREFIXES = (
    "SCHEMBL",
    "CHEBI:",
    "DTXSID",
    "NSC",
    "AKOS",
    "MLS",
    "BDB",
    "ZINC",
    "NCGC",
    "SMR",
    "STK",
    "CPD",
    "CID",
    "CAS",
    "EINECS",
    "UNII",
    "KEGG",
    "HMDB",
    "PDB",
    "DB",
    "NCI",
    "NIAID",
    "EPA",
    "TSCA",
    "WHO",
    "USP",
    "BAN",
    "JAN",
)


def pick_common_name(synonyms: list[str], iupac_name: str) -> str | None:
    candidates: list[tuple[int, str]] = []
    for value in synonyms:
        text = " ".join(value.split())
        if not (3 <= len(text) <= 45):
            continue
        if not text.isascii():
            continue
        if text.casefold() == iupac_name.casefold():
            continue
        if any(character in text for character in ";[]=#%*(),"):
            continue
        if any(character.isdigit() for character in text):
            continue
        if text.isupper():
            continue
        if not re.search(r"[a-z]", text):
            continue
        if any(text.startswith(prefix) for prefix in _BAD_PREFIXES):
            continue
        if text.count(" ") > 5:
            continue
        if re.fullmatch(r"[A-Z]{2,}[0-9]+", text):
            continue
        # Prefer short, word-like names.
        score = len(text)
        if text[0].islower():
            score += 5
        candidates.append((score, text))
    if not candidates:
        return None
    candidates.sort(key=lambda item: (item[0], item[1].casefold()))
    return candidates[0][1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, default=ROOT / "data" / "benchmark_v0.jsonl")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    records: list[dict] = []
    with args.data.open(encoding="utf-8") as handle:
        for line in handle:
            records.append(json.loads(line))

    used: set[str] = set()
    changed = 0
    examples: list[tuple[str, str]] = []
    for record in records:
        chosen = pick_common_name(record.get("synonyms", []), record["iupac_name"])
        if chosen and chosen.casefold() not in used:
            if record["name"] != chosen:
                changed += 1
                if len(examples) < 20:
                    examples.append((record["name"], chosen))
            record["name"] = chosen
            record["name_type"] = "common"
            record["name_source"] = "PubChem synonym"
            used.add(chosen.casefold())
        else:
            record["name"] = record["iupac_name"]
            record["name_type"] = "iupac"
            record["name_source"] = "PubChem IUPACName"

    print(f"records: {len(records)}")
    print(f"common-name records: {sum(r['name_type'] == 'common' for r in records)}")
    print(f"iupac-name records: {sum(r['name_type'] == 'iupac' for r in records)}")
    print(f"changed: {changed}")
    for old, new in examples:
        print(f"  {old[:70]} -> {new}")

    if args.dry_run:
        return

    temp = args.data.with_suffix(".jsonl.tmp")
    with temp.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    temp.replace(args.data)
    print(f"wrote: {args.data}")


if __name__ == "__main__":
    main()
