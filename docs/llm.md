# LLM Provider Layer

`src/name2smiles/llm/` is a small provider-agnostic client for the 20
candidate models. It reads keys from the project `.env`, supports
OpenAI-compatible and Anthropic-compatible APIs, and returns one normalized
result object. No vendor SDK is required.

Provider endpoints and auth styles follow the local key-manager registry.
The benchmark does not read the key-manager database at runtime.

## Providers

| Provider ID | Base URL | Key environment variable | API style |
|---|---|---|---|
| `deepseek` | `https://api.deepseek.com` | `DEEPSEEK_API_KEY` | OpenAI |
| `zhipu` | `https://open.bigmodel.cn/api/paas/v4` | `GLM_API_KEY` | OpenAI |
| `minimax` | `https://api.minimaxi.com/v1` | `MINIMAX_API_KEY` | OpenAI |
| `longcat` | `https://api.longcat.chat/openai/v1` | `LONGCAT_API_KEY` | OpenAI |
| `mimo` | `https://api.xiaomimimo.com/v1` | `MIMO_API_KEY` | OpenAI |
| `kimi` | `https://api.moonshot.cn/v1` | `KIMI_API_KEY` | OpenAI |
| `qwen` | `https://dashscope.aliyuncs.com/compatible-mode/v1` | `QWEN_API_KEY` | OpenAI |
| `4router-gpt` | `https://4router.net/v1` | `FOURROUTER_GPT_API_KEY` | OpenAI |
| `4router-claude` | `https://4router.net/v1` | `FOURROUTER_CLAUDE_API_KEY` | Anthropic |
| `4router-gemini` | `https://4router.net/v1` | `FOURROUTER_GEMINI_API_KEY` | OpenAI |

Kimi is limited to one in-flight request per client because its account
reports organization concurrency 1. Other providers default to four
in-flight requests. The limit is per `LLMClient` instance.

## Models

| Registry key | Model ID | Provider | Token field | Max output | Tags |
|---|---|---|---|---|---|
| `deepseek-v4-pro` | `deepseek-v4-pro` | deepseek | `max_tokens` | 50000 | reasoning, flagship |
| `deepseek-flash` | `deepseek-flash` | deepseek | `max_tokens` | 50000 | reasoning, fast |
| `glm-5.3` | `glm-5.3` | zhipu | `max_tokens` | 50000 | reasoning, flagship |
| `glm-5.3-flash` | `glm-5.3-flash` | zhipu | `max_tokens` | 50000 | reasoning, fast |
| `minimax-m3.1-flash` | `MiniMax-M3.1-Flash` | minimax | `max_tokens` | 50000 | fast |
| `longcat-2.5-preview` | `LongCat-2.5-Preview` | longcat | `max_tokens` | 50000 | reasoning, preview |
| `mimo-v2.6-flash` | `mimo-v2.6-flash` | mimo | `max_tokens` | 50000 | reasoning, fast |
| `mimo-v2.6-pro` | `mimo-v2.6-pro` | mimo | `max_tokens` | 50000 | reasoning, flagship |
| `kimi-k2.6` | `kimi-k2.6` | kimi | `max_tokens` | 50000 | reasoning, open-weights |
| `kimi-k3.1-pro` | `kimi-k3.1-pro` | kimi | `max_tokens` | 50000 | reasoning, flagship |
| `qwen3.8-flash` | `qwen3.8-flash` | qwen | `max_tokens` | 50000 | reasoning, fast |
| `qwen3.8-max` | `qwen3.8-max` | qwen | `max_tokens` | 50000 | reasoning, flagship |
| `gpt-6-astra` | `gpt-6-astra` | 4router-gpt | `max_completion_tokens` | 50000 | flagship |
| `gpt-6.1-sol` | `gpt-6.1-sol` | 4router-gpt | `max_completion_tokens` | 50000 | flagship |
| `gpt-6.1-terra` | `gpt-6.1-terra` | 4router-gpt | `max_completion_tokens` | 50000 | flagship |
| `gpt-6-luna` | `gpt-6-luna` | 4router-gpt | `max_completion_tokens` | 50000 | fast |
| `claude-opus-5.5` | `claude-opus-5-5` | 4router-claude | `max_tokens` | 50000 | flagship |
| `claude-haiku-5.5` | `claude-haiku-5-5` | 4router-claude | `max_tokens` | 50000 | fast |
| `gemini-4-argon` | `gemini-4-argon` | 4router-gemini | `max_tokens` | 50000 | flagship |
| `gemini-3.8-flash` | `gemini-3.8-flash` | 4router-gemini | `max_tokens` | 50000 | fast |

The output cap is 50,000 tokens for every model. It is a request cap, not the
model's hard limit. The cap is intentionally generous because reasoning
models spend tokens before writing the visible answer.

Kimi K2.6, Kimi K3.1 Pro, Claude Opus 5.5, and Claude Haiku 5.5 use the
provider's default temperature and reject custom values. The client raises a
clear error if a custom temperature is requested for them. All other models
accept an explicit temperature.

## Usage

```python
from name2smiles.llm import LLMClient

client = LLMClient()
result = client.chat("deepseek-v4-pro", "hi")
print(result.text)
print(result.usage.to_dict())
print(result.reasoning)
```

Messages can be a prompt string or a list of dicts:

```python
result = client.chat(
    "claude-opus-5.5",
    [
        {"role": "system", "content": "Answer with one SMILES string."},
        {"role": "user", "content": "aspirin"},
    ],
)
```

For Anthropic, system messages are moved to the top-level `system` field.
For OpenAI-compatible providers they stay in the message list.

## Smoke test

```powershell
python scripts/smoke_llm.py --all
python scripts/smoke_llm.py --provider deepseek
python scripts/smoke_llm.py --models "deepseek-v4-pro,glm-5.3"
```

The script sends `hi`, prints latency and token usage, and writes one JSONL
record per model to `data/llm_smoke_<timestamp>.jsonl`. It exits non-zero if
any model fails. Use `--allow-failures` when a provider is temporarily
unavailable.

Useful options:

- `--prompt`: change the user prompt.
- `--system`: add a system prompt.
- `--max-tokens`: override the 50,000 cap.
- `--temperature`: override the provider default. Kimi and Claude models
  reject custom values and report an error.
- `--workers`: parallel requests, default 4.
- `--timeout`: read timeout in seconds.

## Pricing

`src/name2smiles/llm/llm_pricing.json` records CNY list prices per 1M tokens for all 20
models. `src/name2smiles/llm/pricing.py` turns normalized `Usage` into a cost
estimate, including cache read and cache write. The human-readable table and
caveats are in [`llm_pricing.md`](llm_pricing.md).

```powershell
python scripts/estimate_costs.py --records 1500 --input-tokens 200 --output-tokens 800
```

## Reasoning levels

`LLMClient.chat(..., reasoning="low")` merges a provider-specific body from
the model registry. Supported levels are `low` and `high` for the registered
models; `none` means "do not add a reasoning body".

- DeepSeek and GLM: `thinking` enabled plus `reasoning_effort`.
- MiniMax: `reasoning_effort`.
- MiMo: `thinking` enabled or disabled. There is no named effort level.
- LongCat: `thinking` plus a `thinking_budget`.
- Qwen: `enable_thinking` plus a `thinking_budget`.
- Claude: `thinking: adaptive` plus `output_config.effort`.
- GPT and Gemini on 4Router: `reasoning_effort`.

`scripts/evaluate_name2smiles.py` defaults to `--reasoning low`. The 4Router
Gemini endpoint does not always honor the requested level, so measure actual
usage instead of relying on the label. See
[`reasoning_controls.md`](reasoning_controls.md) for the per-model fields,
defaults, and verified behavior.

## Defaults and behavior

- `max_tokens`: 50,000.
- `temperature`: omitted, so each provider uses its own default.
- `stream`: false.
- Retries: up to four attempts on 408, 409, 425, 429, and 5xx responses.
- Timeout: 30 seconds to connect, 600 seconds to read.
- Concurrency: four in-flight requests per provider, except Kimi (one).
- HTTP errors are not retried and include the status and a truncated body.
- API keys never appear in logs, results, or errors. Only the environment
  variable name is reported.

## Provider quirks

- GPT models on 4Router use `max_completion_tokens`. The other
  OpenAI-compatible providers use `max_tokens`.
- Claude models use the Anthropic Messages API with `x-api-key` and
  `anthropic-version: 2023-06-01`.
- DeepSeek, GLM, Kimi, LongCat, MiMo, and Qwen return chain-of-thought in
  `reasoning_content`. The client stores it separately from `content`.
- Claude returns thinking blocks. The client stores them in `reasoning`.
- MiniMax M3.1 Flash and some Gemini models return only `content`.
- The client accepts an empty visible answer when the model returns only
  reasoning, and records the finish reason.
- Kimi rejects concurrent requests at the organization level. The client
  serializes them; the smoke test still runs other providers in parallel.
- Kimi and Claude models reject custom temperature values. The client checks
  this before sending the request instead of waiting for a provider error.

## Adding a model

1. Add a `ProviderSpec` if the base URL or auth style is new.
2. Add a `ModelSpec` to `_MODEL_SPECS` in `registry.py`.
3. Set `max_tokens_field` to `max_completion_tokens` only when the API
   requires it.
4. Set `supports_temperature=False` when the model rejects custom values.
5. Add low and high reasoning bodies to `_REASONING_LOW` and
   `_REASONING_HIGH` when the model supports effort controls.
6. Add the price entry to `src/name2smiles/llm/llm_pricing.json`.
7. Run the smoke test for that model.

The registry is checked by `validate_registry()` and by the test suite.
