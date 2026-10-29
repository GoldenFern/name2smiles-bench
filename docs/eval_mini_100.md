# Name2SMILES Mini-100 Benchmark

**English** | [简体中文](eval_mini_100.zh-CN.md)

Eight models answered the same 100 PubChem names, one call per name. All 800
calls completed after retries. Claude Haiku 5.5 produced the most exact
structures (79%). GPT-6.1 Terra was the cheapest at CNY 0.07 per 100 names and
the best value per correct answer. Accuracy fell from 78% on the easiest tier
to 28% on the hardest.

![Exact-match rate by model](figures/eval_mini_100/leaderboard.png)

## Results

One hundred records per model. `Exact` is canonical isomeric SMILES equality.
`Connectivity` ignores stereochemistry. `Valid` means RDKit parsed the answer.
`Tanimoto` is the mean Morgan fingerprint similarity over valid answers.
`Cost` is the estimated list price for 100 completed calls.

| Model | Exact | Connectivity | Valid | InChIKey | Tanimoto | CNY / 100 | CNY / 100 exact | Output tok | Latency |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Claude Haiku 5.5 | 79% | 84% | 100% | 83% | 0.95 | 0.20 | 0.25 | 2.4k | 15.8s |
| DeepSeek Flash | 74% | 80% | 100% | 85% | 0.93 | 5.04 | 6.82 | 12.6k | 71.8s |
| MiniMax M3.1 Flash | 71% | 74% | 98% | 80% | 0.91 | 2.12 | 2.99 | 5.3k | 51.4s |
| Gemini 3.8 Flash | 70% | 81% | 94% | 72% | 0.97 | 4.86 | 6.94 | 6.5k | 174.1s |
| GPT-6.1 Terra | 62% | 70% | 93% | 71% | 0.92 | 0.07 | 0.11 | 0.3k | 7.6s |
| GLM 5.3 Flash | 49% | 54% | 91% | 54% | 0.86 | 2.17 | 4.42 | 7.7k | 128.6s |
| LongCat 2.5 Preview | 46% | 52% | 88% | 53% | 0.81 | 4.80 | 10.43 | 6.0k | 61.5s |
| MiMo V2.6 Flash | 30% | 32% | 74% | 31% | 0.75 | 0.94 | 3.13 | 4.7k | 122.3s |

Tanimoto is averaged over valid answers. If invalid answers are scored zero,
MiMo falls from 0.75 to 0.55; the other models fall by up to 0.09.

### What stands out

- **Claude Haiku 5.5** leads exact match (79%) and connectivity (84%), with
  every answer parseable. It costs CNY 0.20 per 100 names and answers in 16
  seconds on average.
- **GPT-6.1 Terra** is the cheapest model at CNY 0.07 per 100 names and the
  cheapest per exact answer at CNY 0.11 per 100 exact answers. It reaches 62%
  exact.
- **DeepSeek Flash** is second on exact match (74%) but costs CNY 5.04 per 100
  names. It writes 12.6k output tokens per name, 99.7% of them reasoning. It
  costs about 70 times more than GPT-6.1 Terra for 12 more exact answers per
  100.
- **Gemini 3.8 Flash** shows the largest stereo gap: 70% exact and 81%
  connectivity. Its mean Tanimoto over valid answers is 0.97, the highest in
  the run. It is also the slowest at 174 seconds per call.
- **GLM 5.3 Flash**, **LongCat 2.5 Preview**, and **MiMo V2.6 Flash** trail at
  49%, 46%, and 30% exact. MiMo also leaves 26% of answers unparseable.

Across all 800 calls, 481 answers (60.1%) were exact, 527 (65.9%) matched after
removing stereochemistry, and 738 (92.3%) were valid SMILES. All 800 API calls
returned a response; the invalid answers are parse failures, not missing rows.

## Accuracy by tier

![Exact-match rate by difficulty tier](figures/eval_mini_100/tiers.png)

The mini set has five heuristic tiers: L1 (25 names), L2 (30), L3 (20), L4
(15), and L5 (10). Across all models, exact match is 77.5% on L1, 71.3% on L2,
46.3% on L3, 49.2% on L4, and 27.5% on L5. L3 and L4 overlap in difficulty;
L4 is slightly easier than L3 for several models. The tiers are useful for
coverage, not a strict ranking.

## Cost and tokens

![Accuracy versus cost](figures/eval_mini_100/cost_accuracy.png)

The run cost about CNY 20.20 for 800 completed calls at list prices. DeepSeek
uses off-peak prices: CNY 1.00 input, 4.00 output, and 0.02 cache read per 1M
tokens. GPT-6.1 Terra is the cheapest at CNY 0.07 per 100 names; DeepSeek Flash
is the most expensive at CNY 5.04. Per 100 exact answers, GPT-6.1 Terra costs
CNY 0.11 and Claude Haiku 5.5 costs CNY 0.25. The other models cost CNY 2.99 to
10.43 per 100 exact answers.

![Token use per name](figures/eval_mini_100/tokens.png)

Reasoning tokens explain most of the cost gap. DeepSeek writes 12.6k output
tokens per name; Gemini 6.5k; GLM 7.7k; LongCat 6.0k; MiniMax 5.3k; MiMo 4.7k;
Claude 2.4k; GPT-6.1 Terra 0.3k. Mean input ranges from 107 to 297 tokens per
call. Providers count and report reasoning tokens differently, so cross-model
token comparisons are approximate.

## Method

- **Data:** 100 records from `data/mini_100.jsonl`, selected from the
  1,500-record v0 set. The mini set covers all 53 functional groups in v0 and
  uses five difficulty tiers.
- **Prompt:** one system message asks for one valid SMILES and nothing else.
  One user message contains the compound name. One answer per record.
- **Scoring:** RDKit 2025.09.1. `exact` is canonical isomeric SMILES equality;
  `connectivity` strips stereochemistry; `valid` means RDKit parsed the answer;
  `inchikey` is full standard InChIKey equality; `Tanimoto` is Morgan
  fingerprint similarity.
- **Run:** five workers per model, 40 total. Initial read timeout 2,400 s,
  maximum output 100,000 tokens, reasoning `high`. HTTP 429 and 503 responses
  were requeued with exponential delay, up to five attempts.
- **Retries:** 171 attempts ended in failure or timeout. After the main run and
  two retry passes, 42 rows for GLM, LongCat, and MiMo still failed. Those rows
  were completed with reasoning `low`, maximum output 25,000, and a 1,200 s
  timeout. The 42 rows are GLM 11, LongCat 18, and MiMo 13. The other 758 rows
  use `high`.
- **Cost:** list prices in `config/llm_pricing.json`, with DeepSeek off-peak.
  Failed attempts that returned no usage are not priced. The total is an
  estimate, not a provider bill.
- **Caveat:** the 42 low-effort rows are the hardest cases for those three
  models. Their final scores mix two effort levels, so comparisons with the
  five high-effort models are not controlled.

## Run notes

The batch started at 23:18 CST on 28 October 2026. The first pass used a
2,400 s read timeout and `high` reasoning. A watcher retried failed rows once.
A second pass raised the timeout to 3,600 s for GLM, LongCat, and MiMo. The last
42 rows still failed, so they were rerun at `low` reasoning, 25,000 maximum
output, and 1,200 s. The final file has 800 rows and no failed calls.

## Reproduce

```powershell
python -m pytest tests/
python scripts/make_mini_report.py
```

The batch runner is:

```powershell
python scripts/eval_mini_batch.py --data data/mini_100.jsonl `
  --timeout-seconds 2400 --workers-per-model 5
```

Raw artifacts are in `data/eval_mini_100_20261028T231806/`:

- `dedup.jsonl`: 800 rows, the latest row for each model and name.
- `raw.jsonl`: 971 rows, including failed attempts and requeues.
- `logs/`: main run and retry logs.
- `summary.json`: recomputed summary used by the figures.

The `data/` directory is ignored by Git. The figures are in
`docs/figures/eval_mini_100/`. The model icons are in `assets/icons/`, with
rendered PNGs under the figure directory.

## Trademarks

Model names and logos are trademarks of their respective owners. They identify
the systems tested here and do not imply endorsement.
