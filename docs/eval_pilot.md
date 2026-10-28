# Name-to-SMILES Pilot

A 10-record smoke run to validate the evaluation pipeline and get a first
signal from the low-cost models. This is not a benchmark result. The record
set is deliberately small and balanced, not random.

- Date: 2026-10-28.
- Records: 10.
- Models: 9.
- Calls: 90, all completed without transport errors.
- Total cost: **0.6019 CNY** from actual API usage.
- Reasoning profile: low effort by default. DeepSeek keeps thinking enabled
  with low effort. Qwen uses a 1,024-token thinking budget. LongCat and MiMo
  have no named low tier, so this demo uses their non-thinking mode. Gemini
  low was requested, but the endpoint still used roughly 8k reasoning tokens
  per call.
- Claude note: this run used the older `thinking: enabled + budget_tokens`
  form for Claude Haiku. The registry now uses the documented Claude 5.5
  adaptive form, `thinking: adaptive` plus `output_config.effort`. Rerun
  Claude before comparing its numbers with a new run.

## Results

Rates are over all 10 records. `Exact` is the isomeric canonical SMILES match.
`Conn` is the non-isomeric canonical match. `InChIKey` is the full key match.
`Tanimoto` is the mean Morgan fingerprint similarity. `Cost` is the actual
usage cost for the 10 calls.

| Model | Effort | Valid | Exact | Conn | InChIKey | Tanimoto | Mean latency | Cost CNY |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| `claude-haiku-5.5` | low, 1k budget | 100% | **80%** | **80%** | **80%** | 0.895 | 5.6s | 0.0065 |
| `deepseek-flash` | low, thinking on | 100% | 70% | 70% | 80% | 0.835 | 22.3s | 0.2203 |
| `minimax-m3.1-flash` | low | 100% | 60% | 60% | 70% | 0.833 | 12.6s | 0.0703 |
| `gemini-3.8-flash` | low, endpoint ignores | 100% | 60% | 70% | 60% | 0.895 | 110.2s | 0.2615 |
| `gpt-6.1-terra` | low | 100% | 60% | 60% | 70% | 0.795 | 4.6s | 0.0041 |
| `glm-5.3-flash` | low | 80% | 40% | 50% | 40% | 0.825 | 5.4s | 0.0076 |
| `qwen3.8-flash` | low, 1k budget | 100% | 30% | 40% | 30% | 0.748 | 14.7s | 0.0267 |
| `longcat-2.5-preview` | non-thinking | 100% | 20% | 40% | 20% | 0.674 | 2.4s | 0.0037 |
| `mimo-v2.6-flash` | non-thinking | 90% | 10% | 10% | 10% | 0.393 | 2.4s | 0.0012 |

## What the run showed

- Claude Haiku 5.5 gave the best exact rate, 80%, at very low cost.
- DeepSeek Flash reached 70% exact and 80% InChIKey, but it was the most
  expensive model in this run because low effort still used about 10k
  reasoning tokens on some records.
- Gemini 3.8 Flash reached 60% exact with the best mean Tanimoto, but it was
  slow and expensive. The 4Router OpenAI-compatible endpoint did not honor
  the requested low effort on this model.
- GPT-6.1 Terra and MiniMax M3.1 Flash reached 60% exact. GPT-6.1 Terra was
  roughly 17 times cheaper than MiniMax for this run.
- GLM 5.3 Flash produced two invalid SMILES. Qwen3.8 Flash was fully valid
  but only 30% exact, so its errors were structural rather than parse errors.
- LongCat and MiMo were cheap and fast in non-thinking mode, but their
  structural accuracy was low.
- Record N2S-000637 was exact for 0 of 9 models. The name is
  `1-methyl-3-(6-methylcyclohexa-2,4-dien-1-yl)benzene`, and the models
  returned closely related but non-identical ring structures.
- The sodium salt N2S-000225 was exact for only 2 of 9 models. Several
  predictions were valid salts with a different charge or counterion
  placement.

## Record set

| ID | Name | Category |
|---|---|---|
| `N2S-000652` | 2-[tert-butyl(2-hydroxyethoxy)amino]oxyethanol | CHNO acyclic |
| `N2S-000637` | 1-methyl-3-(6-methylcyclohexa-2,4-dien-1-yl)benzene | aromatic |
| `N2S-000824` | N-(2-chloro-4,4-dimethylpentyl)cyclobutanecarboxamide | halogen |
| `N2S-000514` | 15-(2-methyl-1,3-thiazol-4-yl)pentadeca-10,14-dienamide | S/P |
| `N2S-000696` | methyl 2-[(4,5-dioxo-1,3,2-dioxaborolan-2-yl)oxy]-3,3,3-trifluoropropanoate | B/F |
| `N2S-000225` | sodium 2-(2,2-dimethylpropanoyl)indene-1,3-dione | metal salt |
| `N2S-000624` | 5-fluoro-1,2,3,3a,4,5,6,6a-octahydrocyclopenta[c]pyrrole;hydrochloride | halogen salt |
| `N2S-001385` | trans-(1S,3S)-3-methoxy-N-propan-2-ylcyclopentan-1-amine | stereo |
| `N2S-000835` | (Z)-3-[benzyl(methyl)amino]-2-cyano-N-cyclododecylprop-2-enamide | macrocycle |
| `N2S-000311` | N-(2,4-dioxo-1,3-diazaspiro[4.5]decan-3-yl)-2-(4-methylpyridin-1-ium-1-yl)acetamide | spiro, aromatic |

## Prompt and scoring

System prompt:

```text
You are a chemistry expert. Convert the given molecule name to one valid SMILES string.
Return only the SMILES. Do not explain, do not use Markdown, and do not use code fences.
If the name describes a salt or a multi-component system, include every component separated by a dot.
```

Scoring uses RDKit 2025.09.1:

- `valid`: RDKit can parse and sanitize the predicted SMILES.
- `exact`: isomeric canonical SMILES equals the reference.
- `connectivity`: non-isomeric canonical SMILES equals the reference.
- `inchikey`: full InChIKey equals the reference.
- `tanimoto`: Morgan fingerprint similarity with radius 2 and 2048 bits.

## Files

- Raw rows: `data/eval_pilot_20261028T115130Z.jsonl`.
- Summary: `data/eval_pilot_20261028T115130Z_summary.json`.
- Runner: `scripts/evaluate_name2smiles.py`.

```powershell
python scripts/evaluate_name2smiles.py --pilot --workers 6 --reasoning low
```

The next step is a larger pilot with the same prompt and effort profile.
Ten records are enough to validate the pipeline, not enough to rank models.
