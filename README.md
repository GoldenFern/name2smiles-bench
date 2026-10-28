# Name2SMILES Dataset

**English** | [简体中文](README.zh-CN.md)

Most language-model benchmarks for chemistry ask whether a model can read a
SMILES string. This project tests the harder direction: given only a molecule
name, can a model write the correct structure? It builds a reproducible
benchmark from PubChem, with reference structures, descriptor metadata, 2D
depictions, and coordinate files, then runs candidate models through one
provider-agnostic client and scores their answers with RDKit. Version 0 is
built: 1,500 records selected for coverage of elements, ring systems,
stereochemistry, charge states, and functional groups.

## Features

- 1,500 unique PubChem records, one InChIKey each, 968 non-empty Murcko
  scaffolds.
- Coverage-aware sampling across element class, heavy-atom count, ring count,
  stereochemistry, charge, 53 functional groups, and structural flags.
- Six 2D depictions per record: RDKit clean PNG and SVG, RDKit without
  stereochemistry, RDKit with atom indices, RDKit low-resolution PNG, and the
  PubChem image.
- A 2D SDF, a PubChem 3D SDF when available (1,068 records), and an RDKit
  ETKDG fallback conformer (365 records).
- RDKit descriptors, element counts, ring sizes, spiro and bridgehead atoms,
  stereocenters, and Murcko scaffold for every record.
- A 100-record mini set for quick, low-cost checks, split into five
  difficulty tiers and covering every functional group in v0.
- One client for 20 models across 10 providers, handling
  OpenAI-compatible and Anthropic-compatible APIs, token accounting, and
  reasoning controls.
- A price table and cost estimator, plus a pilot evaluation script that
  parses SMILES and scores them with RDKit.
- A resumable build pipeline with rate-limited, cached PubChem requests.

## Requirements

- Python 3.11 or newer. The dataset was built with Python 3.13.
- RDKit. Version 0 used RDKit 2025.09.1.
- About 170 MB of disk space for the full set of images and coordinate files.
- API keys only for the evaluation scripts. Building the dataset needs none.

## Installation

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[test]"
Copy-Item .env.example .env
```

Scripts and tests add `src/` to the path themselves, so the editable install
is a convenience rather than a requirement. Fill the keys for the models you
plan to call in `.env`. Each key is optional; a model is skipped when its key
is missing.

## Quick start

```powershell
python scripts/sample_candidates.py --n 20000
python scripts/select_dataset.py --n 1500
python scripts/build_dataset.py
python scripts/coverage_report.py
python scripts/select_mini_dataset.py --n 100
```

`sample_candidates.py` draws random CIDs from PubChem and keeps structures
that pass the filters. `select_dataset.py` fills coverage bins greedily.
`build_dataset.py` fetches names, synonyms, images, and coordinate files, and
is resumable: rerun it to continue. `data/` is generated and not tracked, so
a fresh clone rebuilds it locally. The pipeline depends on live PubChem
content, so a rebuild today can differ in details from the version 0 counts
below.

## Usage and configuration

### Record fields

Each record in `data/benchmark_v0.jsonl` contains:

- PubChem CID, IUPAC name, synonyms, isomeric SMILES, connectivity SMILES,
  InChIKey, molecular formula, charge, and heavy-atom count.
- RDKit descriptors: element counts, ring sizes, aromatic rings, spiro and
  bridgehead atoms, stereocenters, double-bond stereochemistry, functional
  groups, fragments, and Murcko scaffold.
- Paths to six 2D depictions, a 2D SDF, and up to two 3D SDF files.
- Source URL, retrieval timestamp, and the raw PubChem response.

### Dataset version 0

- 765 CHNO, 305 halogen, 287 S/P, 82 B/Si/Se/As, and 61 metal-containing
  records.
- 250 acyclic records and 968 distinct non-empty Murcko scaffolds.
- 1,068 PubChem 3D structures and 365 RDKit fallbacks; 67 records, mostly
  large or metal-containing, have no 3D file.
- All 1,500 records have the six 2D depictions.

The full coverage table is in [`docs/coverage.md`](docs/coverage.md), and the
dataset documentation is in [`docs/datasheet.md`](docs/datasheet.md). The
names are PubChem computed IUPAC names, not guaranteed preferred IUPAC names.

### Mini test set

`data/mini_100.jsonl` holds 100 records for quick model checks. The selector
scores every record with a heuristic difficulty model, seeds the easiest and
hardest records, then fills five tier quotas while covering element, size,
ring, stereo, charge, flag, and functional-group bins.

| Tier | Label | Records | Score range |
|---|---|---:|---|
| L1 | easy | 25 | 0-<12 |
| L2 | moderate | 30 | 12-<24 |
| L3 | hard | 20 | 24-<38 |
| L4 | very hard | 15 | 38-<52 |
| L5 | extreme | 10 | >=52 |

The mini set covers all 53 functional groups, all element classes, all
heavy-atom, ring, stereo, and charge bins, and 84 unique non-empty Murcko
scaffolds plus 16 acyclic records. Records keep their original IDs and asset
paths, so the full set's images and SDF files are reused.

```powershell
python scripts/select_mini_dataset.py --n 100
python scripts/evaluate_name2smiles.py --data data/mini_100.jsonl --limit 100 --models "deepseek-flash,qwen3.8-flash" --workers 6 --reasoning low
```

The difficulty score is a planning heuristic, not a calibrated difficulty
measure. The tier ladder, score components, and coverage comparison are in
[`docs/mini_100.md`](docs/mini_100.md).

### LLM evaluation

The 20 candidate models are registered in
`src/name2smiles/llm/registry.py`. No vendor SDK is needed. The client
normalizes token usage and keeps reasoning text separate from the visible
answer. See [`docs/llm.md`](docs/llm.md) for the provider table and model IDs,
and [`docs/reasoning_controls.md`](docs/reasoning_controls.md) for the
thinking and effort parameters.

```powershell
python scripts/smoke_llm.py --all
python scripts/smoke_llm.py --provider deepseek
python scripts/smoke_llm.py --models "deepseek-v4-pro,glm-5.3"
```

The default output cap is 16,384 tokens. Temperature is omitted so each
provider uses its own default. The smoke test writes results to
`data/llm_smoke_<timestamp>.jsonl`.

The pilot runs 10 balanced records through the low-cost model set:

```powershell
python scripts/evaluate_name2smiles.py --pilot --workers 6 --reasoning low
```

The 90-call run cost 0.60 CNY with low effort. Results and observations are in
[`docs/eval_pilot.md`](docs/eval_pilot.md). The script writes one row per
model and record pair, plus a summary JSON file under `data/`.

### Cost estimation

Prices live in `config/llm_pricing.json` and are documented in
[`docs/llm_pricing.md`](docs/llm_pricing.md). The table uses CNY per 1M tokens
and records the 4Router group price as displayed, with the group multiplier
already applied.

```powershell
python scripts/estimate_costs.py --records 1500 --input-tokens 200 --output-tokens 800
python scripts/estimate_costs.py --records 1500 --input-tokens 200 --output-tokens 800 --models "deepseek-v4-pro,claude-opus-5.5"
```

The estimator is a planning tool. Replace the token assumptions with a pilot
run before committing to a large batch.

## Repository layout

```text
src/name2smiles/
  pubchem.py              # rate-limited PubChem client
  descriptors.py          # RDKit descriptors and functional groups
  difficulty.py           # heuristic difficulty score for mini sets
  names.py                # name quality rules
  render.py               # RDKit depictions and 3D embedding
  llm/                    # provider registry, chat client, pricing
scripts/
  sample_candidates.py    # random, filtered candidate pool
  select_dataset.py       # coverage-aware selection
  select_mini_dataset.py  # 100-record difficulty-graded subset
  build_dataset.py        # names, images, SDF files
  assign_common_names.py  # common and trade names
  recompute_descriptors.py
  validate_dataset.py
  coverage_report.py
  regenerate_large_images.py
  smoke_llm.py
  estimate_costs.py
  evaluate_name2smiles.py
tests/
config/llm_pricing.json   # machine-readable model prices
docs/                     # coverage, datasheet, mini set, LLM notes
data/                     # generated records and assets, not tracked
```

## Tests

```powershell
python -m pytest tests/
```

The suite covers descriptors, naming rules, difficulty scoring, the PubChem
client, the LLM client, the pricing table, and the mini-set invariants. It
runs offline and needs no API key.

## License

No license has been chosen yet. The repository is unpublished, so the code is
not licensed for reuse. PubChem computed data is free to use; the dataset
license and any third-party annotation terms will be decided before release.
