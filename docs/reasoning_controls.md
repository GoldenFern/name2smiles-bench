# Reasoning Controls

Vendor documentation for reasoning / thinking intensity, checked on
**2026-10-28**. The table is a reference for the registry settings, not a
promise that a relay honors them. Several observations were verified with
real requests; those are marked in the notes.

## Summary

| Model | Protocol | Reasoning field(s) | Levels / values | Default | Can disable? | Counts in output cap? | Temperature / top_p |
|---|---|---|---|---|---|---|---|
| `deepseek-v4-pro` | OpenAI-compatible | `thinking: {"type": ...}` + `reasoning_effort` | on/off; `low`, `high`, `max` | on, `high` | Yes | Yes | Ignored in thinking mode |
| `deepseek-flash` | OpenAI-compatible | same | same | on, `high` | Yes | Yes | Ignored in thinking mode; `top_p` 0.95-1.0 |
| `glm-5.3` | OpenAI-compatible | `thinking: {"type":"enabled"}` + `reasoning_effort` | `low`, `high`, `max` | `max` | No | Yes | Free; defaults 1.0 / 0.95 |
| `glm-5.3-flash` | OpenAI-compatible | same | same | `max` | No | Yes | same |
| `MiniMax-M3.1-Flash` | OpenAI-compatible | `reasoning_effort` | `low`, `medium`, `high`, `xhigh`, `max` | `max` | No, always thinks | Yes | Fixed 1.0 / 0.95 |
| `LongCat-2.5-Preview` | OpenAI-compatible | `thinking: {"type": ...}` + `thinking_budget` | on/off; token budget | on, not documented | Yes | Budget caps reasoning separately | Fixed 1.0 on / 0.7 off |
| `mimo-v2.6-flash` | OpenAI-compatible | `thinking: {"type": ...}` | on/off | on | Yes | Yes, via `max_completion_tokens` | Fixed 1.0 / 0.95 in thinking mode |
| `mimo-v2.6-pro` | OpenAI-compatible | same | same | on | Yes | same | same |
| `kimi-k2.6` | OpenAI-compatible | `thinking: {"type": ...}` | on/off | on | Yes | Yes | Fixed temperature |
| `kimi-k3.1-pro` | OpenAI-compatible | `reasoning_effort` | `low`, `high`, `max` | `max` | No, always thinks | Yes | Fixed 1.0 / 0.95 |
| `qwen3.8-flash` | OpenAI-compatible | `enable_thinking` + `thinking_budget` | true/false; token budget | on | Yes | Yes | Free; defaults 1.0 / 0.95 |
| `qwen3.8-max` | OpenAI-compatible | same | same | on | Yes | Yes | same |
| `gpt-6-astra` | OpenAI-compatible via 4Router | `reasoning_effort` | `low`, `medium`, `high`, `xhigh`, `max` | `medium` | No | Yes | Sampling unsupported when effort is set |
| `gpt-6.1-sol` | same | same | same | `medium` | No | Yes | same |
| `gpt-6.1-terra` | same | same | plus `none` | `medium` | Yes, `none` | Yes | Sampling only at `none` |
| `gpt-6-luna` | same | same | plus `none` | `medium` | Yes, `none` | Yes | Sampling only at `none` |
| `claude-opus-5.5` | Anthropic Messages via 4Router | `thinking: {"type":"adaptive"}` + `output_config: {"effort": ...}` | `low`, `medium`, `high`, `xhigh`, `max` | `medium` | No, always adaptive | Yes | Only defaults; other values return 400 |
| `claude-haiku-5.5` | same | same | same | `medium` | Yes at `low`/`medium`/`high` | Yes | Only defaults |
| `gemini-4-argon` | OpenAI-compatible via 4Router; native `thinkingConfig.thinkingLevel` | `reasoning_effort` | `low`, `medium`, `high` | `medium` | No | Yes, thinking + answer share output cap | Ignored by Gemini |
| `gemini-3.8-flash` | same | same | same | `medium` | No | same | Ignored by Gemini |

## Named levels vs token budgets

Only three families use a token count:

- **LongCat**: `thinking_budget` is a token count, not a named level.
- **Qwen**: `thinking_budget` is a token count. The model card gives a
  maximum chain-of-thought length of 262,144, while the console widget quotes
  1-32,768 with a default of 4,000.
- **Claude 5.5**: `budget_tokens` has been removed in favor of
  `thinking: adaptive` plus `output_config.effort`. The old form is still
  accepted by 4Router but is deprecated.

Everything else uses named levels such as `low`, `medium`, `high`, `xhigh`,
or `max`. Do not translate a named level into a token budget in the benchmark
config; record the field and the level that was actually sent.

## What was verified with real requests

These checks used the project client and the same prompt as the pilot.

- **Claude Haiku 5.5, adaptive low**: 1,507 reasoning tokens and a correct
  answer. Adaptive high: 2,023 reasoning tokens. The older
  `enabled + budget_tokens: 1024` form produced 2,576 reasoning tokens, more
  than adaptive low, and returned no thinking text. The registry now uses the
  adaptive form.
- **Qwen 3.8 Flash, `thinking_budget: 1024`**: exactly 1,024 reasoning tokens
  and a correct answer.
- **DeepSeek Flash, low**: about 10k reasoning tokens on one name and a
  correct answer. Low is real for Flash, but it is not a small budget.
- **LongCat 2.5 Preview, `thinking_budget: 1024`**: the budget was not
  honored. The model used 16,384 tokens, hit `length`, and returned no final
  SMILES. The demo uses non-thinking mode for LongCat.
- **Gemini 3.8 Flash, low / minimal / none**: the 4Router endpoint did not
  reduce reasoning tokens on the same name; it used about 7.8k tokens in each
  case. Native Gemini `thinkingLevel` may behave differently, but the relay
  path did not.
- **MiMo V2.6 Flash**: the documented output field is
  `max_completion_tokens`; the registry now uses it for both MiMo models.
- **MiniMax M3.1 Flash**: this is a full effort-level model, not a simple
  fast model. The registry tags it as `reasoning` and `fast`.

## Practical rules

1. Set `thinking_budget` or `output_config.effort` below the total
   `max_tokens`, otherwise thinking can consume the entire output and leave
   no answer.
2. For models with named levels, record the level in the result row. For
   token budgets, record the number.
3. For 4Router models, verify one paired request per model before trusting a
   label. The relay has no public parameter documentation.
4. Gemini needs a generous output cap because thinking and the answer share
   `max_output_tokens`. A cap below 32,768 can be consumed by thinking.
5. Do not compare a model's low-effort result with another model's default
   result. The defaults differ: GLM and MiniMax default to `max`, DeepSeek
   defaults to `high`, GPT and Claude default to `medium`.

## Sources

- DeepSeek: https://api-docs.deepseek.com/guides/thinking_mode/
- Zhipu: https://docs.bigmodel.cn/cn/guide/capabilities/thinking
- MiniMax: https://platform.minimax.io/docs/guides/text-generation
- LongCat: https://longcat.chat/platform/docs/zh/api/model-params
- Xiaomi MiMo: https://mimo.mi.com/docs/zh-CN/quick-start/usage-guide/text-generation/deep-thinking
- Moonshot Kimi: https://platform.kimi.com/docs/guide/use-thinking-models
- Qwen: https://help.aliyun.com/zh/model-studio/deep-thinking
- OpenAI: https://developers.openai.com/api/docs/guides/latest-model
- Anthropic: https://platform.claude.com/docs/en/build-with-claude/effort
- Gemini: https://ai.google.dev/gemini-api/docs/thinking
- 4Router: https://4router.net/api/pricing. The relay publishes no
  parameter documentation.
