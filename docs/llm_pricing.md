# LLM Pricing

Recorded on **2026-10-28**. All prices are **CNY per 1M tokens** and are used
for planning, not billing. Recheck the source pages before a large run.

The machine-readable table is `config/llm_pricing.json`. The estimator is
`scripts/estimate_costs.py`.

## Domestic models

Official mainland China list prices. DeepSeek uses the peak tier; GLM-5.3-Flash
uses the standard tier; MiMo uses realtime inference.

| Model | Vendor | Input | Output | Cache read | Cache write | Source type |
|---|---|---:|---:|---:|---:|---:|
| `deepseek-v4-pro` | DeepSeek | 9.00 | 27.00 | 0.30 | not published | official |
| `deepseek-flash` | DeepSeek | 2.00 | 8.00 | 0.04 | not published | official |
| `glm-5.3` | Zhipu AI | 8.00 | 28.00 | 2.00 | not published | official |
| `glm-5.3-flash` | Zhipu AI | 0.80 | 2.80 | 0.23 | not published | official |
| `minimax-m3.1-flash` | MiniMax | 1.00 | 4.00 | 0.10 | not published | official |
| `longcat-2.5-preview` | LongCat | 2.00 | 8.00 | 0.04 | not published | official |
| `mimo-v2.6-flash` | Xiaomi MiMo | 1.00 | 2.00 | 0.02 | 0.00 | official |
| `mimo-v2.6-pro` | Xiaomi MiMo | 3.00 | 6.00 | 0.025 | 0.00 | official |
| `kimi-k2.6` | Moonshot Kimi | 6.50 | 27.00 | 1.10 | not published | official |
| `kimi-k3.1-pro` | Moonshot Kimi | 13.00 | 68.00 | 1.30 | 13.00 | official |
| `qwen3.8-flash` | Alibaba Qwen | 0.80 | 2.70 | 0.10 | 1.25 | official |
| `qwen3.8-max` | Alibaba Qwen | 12.00 | 36.00 | 1.50 | 15.00 | official |

## 4Router models

The 4Router console shows an effective price for each group. The displayed
prices already include the group multiplier. Do not apply it again.

Assumption: the card price is the final price after the group multiplier. If
a billing statement shows the multiplier applied separately, multiply the
card price by the group factor.

| Model | Group | Input | Output | Cache read | Cache write |
|---|---|---:|---:|---:|---:|
| `gpt-6-astra` | GptHyper x0.5 | 5.00 | 25.00 | 0.50 | 6.25 |
| `gpt-6.1-sol` | GptHyper x0.5 | 1.00 | 5.00 | 0.05 | 1.25 |
| `gpt-6.1-terra` | GptHyper x0.5 | 0.50 | 2.50 | 0.025 | 0.625 |
| `gpt-6-luna` | GptHyper x0.5 | 0.05 | 0.25 | 0.005 | 0.0625 |
| `claude-opus-5.5` | ClaudeExtern x1.65 | 6.60 | 33.00 | 0.33 | 8.25 |
| `claude-haiku-5.5` | ClaudeExtern x1.65 | 0.165 | 0.825 | 0.0165 | 0.2062 |
| `gemini-4-argon` | GeminiApi x2 | 4.00 | 20.00 | 0.20 | not published |
| `gemini-3.8-flash` | GeminiApi x2 | 1.50 | 7.50 | 0.15 | not published |

## Planning example

1,500 records, 200 input tokens and 800 output tokens per record, no cache.
The full table comes from `python scripts/estimate_costs.py`.

| Model | Total CNY | CNY per 1K records |
|---|---:|---:|
| `kimi-k3.1-pro` | 85.50 | 57.00 |
| `qwen3.8-max` | 46.80 | 31.20 |
| `claude-opus-5.5` | 41.58 | 27.72 |
| `glm-5.3` | 36.00 | 24.00 |
| `deepseek-v4-pro` | 35.10 | 23.40 |
| `kimi-k2.6` | 34.35 | 22.90 |
| `gpt-6-astra` | 31.50 | 21.00 |
| `gemini-4-argon` | 25.20 | 16.80 |
| `deepseek-flash` | 10.20 | 6.80 |
| `longcat-2.5-preview` | 10.20 | 6.80 |
| `gemini-3.8-flash` | 9.45 | 6.30 |
| `mimo-v2.6-pro` | 8.10 | 5.40 |
| `gpt-6.1-sol` | 6.30 | 4.20 |
| `minimax-m3.1-flash` | 5.10 | 3.40 |
| `glm-5.3-flash` | 3.60 | 2.40 |
| `qwen3.8-flash` | 3.48 | 2.32 |
| `gpt-6.1-terra` | 3.15 | 2.10 |
| `mimo-v2.6-flash` | 2.70 | 1.80 |
| `claude-haiku-5.5` | 1.04 | 0.69 |
| `gpt-6-luna` | 0.32 | 0.21 |

Total across all 20 models: about **399.66 CNY** for one 1,500-record pass.

The real cost depends on the prompt, the amount of reasoning, cache hits, and
provider discounts. Use a pilot run to replace these token assumptions.

## Cost formula

For OpenAI-compatible providers, `input_tokens` includes cached tokens. The
estimator charges the uncached part at the input rate and the cached part at
the cache-read rate.

For Anthropic, `input_tokens` excludes cache tokens. The estimator charges
normal input, cache read, and cache write separately.

If a cache-write price is not published, the estimator charges cache-write
tokens at the input rate. This is conservative.

```text
cost = uncached_input / 1M * input_price
     + cache_read / 1M * cache_read_price
     + cache_write / 1M * cache_write_price
     + output / 1M * output_price
```

## Caveats

- **DeepSeek:** prices above are peak. Off-peak is half price. Peak is Beijing
  time Monday to Friday, 09:00-12:00 and 14:00-18:00, excluding public
  holidays.
- **GLM-5.3-Flash:** standard price above. A limited-time 50% discount gives
  0.40 / 1.40 / 0.115. Cache storage is free for now.
- **LongCat-2.5-Preview:** all published prices are limited-time launch
  discounts. The regular list price is not published.
- **MiMo:** realtime prices above. Batch inference is 50% off. Cache write is
  free for now.
- **Kimi K2.6:** the K2 series stops accepting new users on 2026-10-31 and is
  scheduled for retirement by end-2026.
- **Kimi K3.1 Pro:** cache write is 13.00 for 5 minutes and 26.00 for 1 hour.
  `temperature=1.0` is fixed. A minimum 10 CNY recharge is required.
- **Qwen:** prices are for China Beijing. `qwen3.8-max` implicit cache hit is
  1.50, explicit cache hit is 1.00, explicit cache write is 15.00. Batch File
  price is 6.00 input and 18.00 output.
- **4Router:** relay prices can change without notice. The console price
  already includes the group multiplier.

## Sources

- DeepSeek: https://api-docs.deepseek.com/zh-cn/quick_start/pricing
- Zhipu: https://docs.bigmodel.cn/cn/guide/start/pricing
- MiniMax: https://platform.minimaxi.com/docs/pricing/overview
- LongCat: https://longcat.chat/platform/docs/zh/pricing/longcat-2.5
- Xiaomi MiMo: https://mimo.mi.com/docs/zh-CN/price/pay-as-you-go
- Moonshot Kimi: https://platform.kimi.com/docs/pricing/chat
- Kimi K3.1 Pro pricing: https://www.kimi.com/resources/kimi-k3-1-pro-pricing
- Qwen3.8-Flash: https://help.aliyun.com/zh/model-studio/qwen3-8-flash
- Qwen3.8-Max: https://help.aliyun.com/zh/model-studio/qwen3-8-max
- 4Router: https://4router.net (console screenshots, 2026-10-28)
