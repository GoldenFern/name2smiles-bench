# Tier Probe

Run: `20261028T142931Z`

Five molecules, one from each difficulty tier, eight models. The prompt and system message match `evaluate_name2smiles.py`.

## Settings

- Reasoning: `high`
- Max output tokens: `100000`
- Timeout: `1800.0` s (connect `30.0` s)
- Global concurrency: `40`
- Per-provider concurrency: `5`
- Max rounds: `5`, retry status: `[429, 503]`

## Preflight

| Model | 100k accepted | Effective cap | Fallback | Latency | Note |
|---|---:|---:|---:|---:|---|
| deepseek-flash | yes | 100000 | no | 0.7s |  |
| minimax-m3.1-flash | yes | 100000 | no | 1.3s |  |
| glm-5.3-flash | yes | 100000 | no | 2.3s |  |
| claude-haiku-5.5 | yes | 100000 | no | 4.0s |  |
| gpt-6.1-terra | yes | 100000 | no | 4.4s |  |
| gemini-3.8-flash | yes | 100000 | no | 4.2s |  |
| mimo-v2.6-flash | yes | 100000 | no | 1.2s |  |
| longcat-2.5-preview | yes | 100000 | no | 1.5s |  |

## Per-model results

Correctness rates use all five records as the denominator. `valid` means RDKit parsed the answer. `exact` is the canonical isomeric SMILES. `connectivity` ignores stereochemistry. `inchikey` is the full InChIKey match.

| Model | ok | valid | exact | connectivity | inchikey | Tanimoto | Input tok (mean) | Output tok (mean) | Cost CNY | Requeues |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| deepseek-flash | 5/5 | 100.0% | 100.0% | 100.0% | 100.0% | 1.000 | 145.8 | 13097.6 | 0.5254 | 0 |
| minimax-m3.1-flash | 5/5 | 80.0% | 20.0% | 20.0% | 20.0% | 0.830 | 311.2 | 4150.2 | 0.0841 | 0 |
| glm-5.3-flash | 4/5 | 80.0% | 80.0% | 80.0% | 80.0% | 1.000 | 120.8 | 8422.2 | 0.0947 | 0 |
| claude-haiku-5.5 | 5/5 | 100.0% | 100.0% | 100.0% | 100.0% | 1.000 | 175.2 | 1876.2 | 0.0079 | 0 |
| gpt-6.1-terra | 5/5 | 80.0% | 60.0% | 60.0% | 60.0% | 0.900 | 130.0 | 237.8 | 0.0033 | 0 |
| gemini-3.8-flash | 5/5 | 100.0% | 100.0% | 100.0% | 100.0% | 1.000 | 122.0 | 6427.4 | 0.2419 | 0 |
| mimo-v2.6-flash | 3/5 | 60.0% | 60.0% | 60.0% | 60.0% | 1.000 | 108.3 | 574.7 | 0.0038 | 0 |
| longcat-2.5-preview | 3/5 | 60.0% | 0.0% | 0.0% | 0.0% | 0.680 | 117.3 | 6316.0 | 0.1523 | 0 |

## Correctness by tier

Cells are `exact/connectivity` counts out of one record per tier. A failed call also counts as 0/0; see `ok` in the per-model table.

| Model | L1 | L2 | L3 | L4 | L5 |
|---|---:|---:|---:|---:|---:|
| deepseek-flash | 1/1 | 1/1 | 1/1 | 1/1 | 1/1 |
| minimax-m3.1-flash | 0/0 | 1/1 | 0/0 | 0/0 | 0/0 |
| glm-5.3-flash | 1/1 | 1/1 | 1/1 | 1/1 | 0/0 |
| claude-haiku-5.5 | 1/1 | 1/1 | 1/1 | 1/1 | 1/1 |
| gpt-6.1-terra | 1/1 | 1/1 | 0/0 | 1/1 | 0/0 |
| gemini-3.8-flash | 1/1 | 1/1 | 1/1 | 1/1 | 1/1 |
| mimo-v2.6-flash | 1/1 | 1/1 | 1/1 | 0/0 | 0/0 |
| longcat-2.5-preview | 0/0 | 0/0 | 0/0 | 0/0 | 0/0 |

## Token usage

| Model | Input sum | Input mean | Output sum | Output mean | Reasoning sum | Total cost CNY |
|---|---:|---:|---:|---:|---:|---:|
| deepseek-flash | 729 | 145.8 | 65488 | 13097.6 | 65317 | 0.5254 |
| minimax-m3.1-flash | 1556 | 311.2 | 20751 | 4150.2 | 20570 | 0.0841 |
| glm-5.3-flash | 483 | 120.8 | 33689 | 8422.2 | 33556 | 0.0947 |
| claude-haiku-5.5 | 876 | 175.2 | 9381 | 1876.2 | 9116 | 0.0079 |
| gpt-6.1-terra | 650 | 130.0 | 1189 | 237.8 | 967 | 0.0033 |
| gemini-3.8-flash | 610 | 122.0 | 32137 | 6427.4 | 31936 | 0.2419 |
| mimo-v2.6-flash | 325 | 108.3 | 1724 | 574.7 | 1652 | 0.0038 |
| longcat-2.5-preview | 352 | 117.3 | 18948 | 6316.0 | 18858 | 0.1523 |

## Notes

- HTTP 429 and 503 responses are re-queued for the next round.
- A request that exceeds the 30-minute timeout is recorded as a terminal failure.
- Full model text and reasoning are in the JSONL output.
- The JSONL also contains per-attempt history, token usage, and RDKit scores.
