# Project Agent Notes

## Purpose

Build a reproducible name-to-SMILES benchmark dataset from PubChem, with
RDKit-rendered and PubChem-rendered 2D depictions, 3D SDF records, and
descriptor-level coverage reports. Evaluate candidate LLMs through a
provider-agnostic client under `src/name2smiles/llm/`.

## Commands

```powershell
python -m pytest tests/
python scripts/sample_candidates.py --n 20000
python scripts/select_dataset.py --n 1500
python scripts/select_mini_dataset.py --n 100
python scripts/build_dataset.py
python scripts/recompute_descriptors.py
python scripts/validate_dataset.py
python scripts/coverage_report.py
python scripts/regenerate_large_images.py
python scripts/smoke_llm.py --all
python scripts/estimate_costs.py --records 1500 --input-tokens 200 --output-tokens 800
python scripts/evaluate_name2smiles.py --pilot --workers 6 --reasoning low
python scripts/eval_tier_probe.py --preflight-only
python scripts/eval_mini_batch.py --data data/mini_100.jsonl --timeout-seconds 2400
python scripts/make_mini_report.py
```

## Conventions

- Python 3.13, RDKit 2025.09.1.
- UTF-8 without BOM, LF line endings.
- Source code in `src/name2smiles/`.
- One-off and repeatable scripts in `scripts/`.
- Generated data in `data/`; reports in `docs/`.
- PubChem requests must go through `name2smiles.pubchem` so rate limiting,
  retries, and caching stay in one place.
- LLM requests must go through `name2smiles.llm` so provider endpoints,
  auth headers, token fields, and retries stay in one place.
- Model prices live in `config/llm_pricing.json`. Keep
  `docs/llm_pricing.md` and the pricing tests in sync when prices change.
- Do not commit `data/`. It holds generated records, images, and SDF files.
- `data/mini_100.jsonl`, `data/mini_100.csv`, and `docs/mini_100.md` are
  generated together by `scripts/select_mini_dataset.py`. Rerun the selector
  after changing the difficulty score or coverage targets.
- `scripts/eval_mini_batch.py` appends one JSONL row per completed call.
  Resume a long run with `--resume` and the same `--output` file.
- Do not hardcode secrets. LLM keys live in `.env`; only the environment
  variable names appear in code and logs.
