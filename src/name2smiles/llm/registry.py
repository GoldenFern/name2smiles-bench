"""Provider and model registry for the benchmark.

Endpoints and authentication styles follow the local key-manager registry.
Keys are read from the project .env at call time; no key is stored here.

The default output cap is deliberately generous. A chemistry answer needs
far less, but reasoning models spend tokens before producing visible text.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Literal

ApiStyle = Literal["openai", "anthropic"]

DEFAULT_MAX_TOKENS = 50_000


@dataclass(frozen=True)
class ProviderSpec:
    """One API endpoint family."""

    id: str
    display_name: str
    api_key_env: str
    base_url: str
    api_style: ApiStyle = "openai"
    chat_path: str = "/chat/completions"
    models_path: str = "/models"
    timeout: tuple[float, float] = (30.0, 600.0)
    max_concurrency: int = 4

    @property
    def chat_url(self) -> str:
        return self.base_url.rstrip("/") + self.chat_path

    @property
    def models_url(self) -> str:
        return self.base_url.rstrip("/") + self.models_path


@dataclass(frozen=True)
class ModelSpec:
    """One model exposed by one provider."""

    key: str
    display_name: str
    provider: str
    model_id: str
    max_tokens: int = DEFAULT_MAX_TOKENS
    max_tokens_field: str = "max_tokens"
    temperature: float | None = None
    supports_temperature: bool = True
    extra_body: dict[str, Any] = field(default_factory=dict)
    reasoning_bodies: dict[str, dict[str, Any]] = field(default_factory=dict)
    context_window: int | None = None
    max_output_tokens: int | None = None
    tags: tuple[str, ...] = ()


PROVIDERS: dict[str, ProviderSpec] = {
    "deepseek": ProviderSpec(
        id="deepseek",
        display_name="DeepSeek",
        api_key_env="DEEPSEEK_API_KEY",
        base_url="https://api.deepseek.com",
    ),
    "zhipu": ProviderSpec(
        id="zhipu",
        display_name="Zhipu AI",
        api_key_env="GLM_API_KEY",
        base_url="https://open.bigmodel.cn/api/paas/v4",
    ),
    "minimax": ProviderSpec(
        id="minimax",
        display_name="MiniMax",
        api_key_env="MINIMAX_API_KEY",
        base_url="https://api.minimaxi.com/v1",
    ),
    "longcat": ProviderSpec(
        id="longcat",
        display_name="LongCat",
        api_key_env="LONGCAT_API_KEY",
        base_url="https://api.longcat.chat/openai/v1",
    ),
    "mimo": ProviderSpec(
        id="mimo",
        display_name="Xiaomi MiMo",
        api_key_env="MIMO_API_KEY",
        base_url="https://api.xiaomimimo.com/v1",
    ),
    "kimi": ProviderSpec(
        id="kimi",
        display_name="Moonshot Kimi",
        api_key_env="KIMI_API_KEY",
        base_url="https://api.moonshot.cn/v1",
        max_concurrency=1,
    ),
    "qwen": ProviderSpec(
        id="qwen",
        display_name="Qwen",
        api_key_env="QWEN_API_KEY",
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    ),
    "4router-gpt": ProviderSpec(
        id="4router-gpt",
        display_name="4Router GPT",
        api_key_env="FOURROUTER_GPT_API_KEY",
        base_url="https://4router.net/v1",
    ),
    "4router-claude": ProviderSpec(
        id="4router-claude",
        display_name="4Router Claude",
        api_key_env="FOURROUTER_CLAUDE_API_KEY",
        base_url="https://4router.net/v1",
        api_style="anthropic",
        chat_path="/messages",
    ),
    "4router-gemini": ProviderSpec(
        id="4router-gemini",
        display_name="4Router Gemini",
        api_key_env="FOURROUTER_GEMINI_API_KEY",
        base_url="https://4router.net/v1",
    ),
}


# Provider-specific "high" reasoning bodies. Models with a token budget instead
# of named effort levels get 8192 thinking tokens, which is generous for a
# short name-to-SMILES answer.
_REASONING_HIGH: dict[str, dict[str, Any]] = {
    "deepseek-v4-pro": {
        "thinking": {"type": "enabled"},
        "reasoning_effort": "high",
    },
    "deepseek-flash": {
        "thinking": {"type": "enabled"},
        "reasoning_effort": "high",
    },
    "glm-5.3": {
        "thinking": {"type": "enabled"},
        "reasoning_effort": "high",
    },
    "glm-5.3-flash": {
        "thinking": {"type": "enabled"},
        "reasoning_effort": "high",
    },
    "minimax-m3.1-flash": {"reasoning_effort": "high"},
    "longcat-2.5-preview": {
        "thinking": {"type": "enabled"},
        "thinking_budget": 8192,
    },
    "mimo-v2.6-flash": {"thinking": {"type": "enabled"}},
    "mimo-v2.6-pro": {"thinking": {"type": "enabled"}},
    "kimi-k2.6": {"thinking": {"type": "enabled"}},
    "kimi-k3.1-pro": {"reasoning_effort": "high"},
    "qwen3.8-flash": {
        "enable_thinking": True,
        "thinking_budget": 8192,
    },
    "qwen3.8-max": {
        "enable_thinking": True,
        "thinking_budget": 8192,
    },
    "gpt-6-astra": {"reasoning_effort": "high"},
    "gpt-6.1-sol": {"reasoning_effort": "high"},
    "gpt-6.1-terra": {"reasoning_effort": "high"},
    "gpt-6-luna": {"reasoning_effort": "high"},
    "claude-opus-5.5": {
        "thinking": {"type": "adaptive"},
        "output_config": {"effort": "high"},
    },
    "claude-haiku-5.5": {
        "thinking": {"type": "adaptive"},
        "output_config": {"effort": "high"},
    },
    "gemini-4-argon": {"reasoning_effort": "high"},
    "gemini-3.8-flash": {"reasoning_effort": "high"},
}


# Low effort for a cost-controlled benchmark demo. DeepSeek keeps thinking
# enabled with low effort. LongCat and MiMo have no named low tier, so their
# demo profile uses non-thinking mode to keep the run short.
_REASONING_LOW: dict[str, dict[str, Any]] = {
    "deepseek-v4-pro": {
        "thinking": {"type": "enabled"},
        "reasoning_effort": "low",
    },
    "deepseek-flash": {
        "thinking": {"type": "enabled"},
        "reasoning_effort": "low",
    },
    "glm-5.3": {
        "thinking": {"type": "enabled"},
        "reasoning_effort": "low",
    },
    "glm-5.3-flash": {
        "thinking": {"type": "enabled"},
        "reasoning_effort": "low",
    },
    "minimax-m3.1-flash": {"reasoning_effort": "low"},
    "longcat-2.5-preview": {"thinking": {"type": "disabled"}},
    "mimo-v2.6-flash": {"thinking": {"type": "disabled"}},
    "mimo-v2.6-pro": {"thinking": {"type": "disabled"}},
    "kimi-k2.6": {"thinking": {"type": "disabled"}},
    "kimi-k3.1-pro": {"reasoning_effort": "low"},
    "qwen3.8-flash": {
        "enable_thinking": True,
        "thinking_budget": 1024,
    },
    "qwen3.8-max": {
        "enable_thinking": True,
        "thinking_budget": 1024,
    },
    "gpt-6-astra": {"reasoning_effort": "low"},
    "gpt-6.1-sol": {"reasoning_effort": "low"},
    "gpt-6.1-terra": {"reasoning_effort": "low"},
    "gpt-6-luna": {"reasoning_effort": "low"},
    "claude-opus-5.5": {
        "thinking": {"type": "adaptive"},
        "output_config": {"effort": "low"},
    },
    "claude-haiku-5.5": {
        "thinking": {"type": "adaptive"},
        "output_config": {"effort": "low"},
    },
    "gemini-4-argon": {"reasoning_effort": "low"},
    "gemini-3.8-flash": {"reasoning_effort": "low"},
}


_MODEL_SPECS: tuple[ModelSpec, ...] = (
    ModelSpec(
        key="deepseek-v4-pro",
        display_name="DeepSeek V4 Pro",
        provider="deepseek",
        model_id="deepseek-v4-pro",
        context_window=1_000_000,
        max_output_tokens=384_000,
        tags=("reasoning", "flagship"),
    ),
    ModelSpec(
        key="deepseek-flash",
        display_name="DeepSeek Flash",
        provider="deepseek",
        model_id="deepseek-flash",
        context_window=1_000_000,
        max_output_tokens=384_000,
        tags=("reasoning", "fast"),
    ),
    ModelSpec(
        key="glm-5.3",
        display_name="GLM 5.3",
        provider="zhipu",
        model_id="glm-5.3",
        context_window=1_000_000,
        max_output_tokens=128_000,
        tags=("reasoning", "flagship"),
    ),
    ModelSpec(
        key="glm-5.3-flash",
        display_name="GLM 5.3 Flash",
        provider="zhipu",
        model_id="glm-5.3-flash",
        context_window=1_000_000,
        max_output_tokens=128_000,
        tags=("reasoning", "fast"),
    ),
    ModelSpec(
        key="minimax-m3.1-flash",
        display_name="MiniMax M3.1 Flash",
        provider="minimax",
        model_id="MiniMax-M3.1-Flash",
        context_window=1_000_000,
        tags=("reasoning", "fast"),
    ),
    ModelSpec(
        key="longcat-2.5-preview",
        display_name="LongCat 2.5 Preview",
        provider="longcat",
        model_id="LongCat-2.5-Preview",
        context_window=1_000_000,
        max_output_tokens=128_000,
        tags=("reasoning", "preview"),
    ),
    ModelSpec(
        key="mimo-v2.6-flash",
        display_name="MiMo V2.6 Flash",
        provider="mimo",
        model_id="mimo-v2.6-flash",
        max_tokens_field="max_completion_tokens",
        context_window=1_000_000,
        max_output_tokens=128_000,
        tags=("reasoning", "fast"),
    ),
    ModelSpec(
        key="mimo-v2.6-pro",
        display_name="MiMo V2.6 Pro",
        provider="mimo",
        model_id="mimo-v2.6-pro",
        max_tokens_field="max_completion_tokens",
        context_window=1_000_000,
        max_output_tokens=128_000,
        tags=("reasoning", "flagship"),
    ),
    ModelSpec(
        key="kimi-k2.6",
        display_name="Kimi K2.6",
        provider="kimi",
        model_id="kimi-k2.6",
        supports_temperature=False,
        context_window=262_144,
        max_output_tokens=32_768,
        tags=("reasoning", "open-weights"),
    ),
    ModelSpec(
        key="kimi-k3.1-pro",
        display_name="Kimi K3.1 Pro",
        provider="kimi",
        model_id="kimi-k3.1-pro",
        supports_temperature=False,
        context_window=1_048_576,
        max_output_tokens=1_048_576,
        tags=("reasoning", "flagship"),
    ),
    ModelSpec(
        key="qwen3.8-flash",
        display_name="Qwen3.8 Flash",
        provider="qwen",
        model_id="qwen3.8-flash",
        context_window=1_000_000,
        max_output_tokens=131_072,
        tags=("reasoning", "fast"),
    ),
    ModelSpec(
        key="qwen3.8-max",
        display_name="Qwen3.8 Max",
        provider="qwen",
        model_id="qwen3.8-max",
        context_window=1_000_000,
        max_output_tokens=131_072,
        tags=("reasoning", "flagship"),
    ),
    ModelSpec(
        key="gpt-6-astra",
        display_name="GPT-6 Astra",
        provider="4router-gpt",
        model_id="gpt-6-astra",
        max_tokens_field="max_completion_tokens",
        tags=("flagship",),
    ),
    ModelSpec(
        key="gpt-6.1-sol",
        display_name="GPT-6.1 Sol",
        provider="4router-gpt",
        model_id="gpt-6.1-sol",
        max_tokens_field="max_completion_tokens",
        tags=("flagship",),
    ),
    ModelSpec(
        key="gpt-6.1-terra",
        display_name="GPT-6.1 Terra",
        provider="4router-gpt",
        model_id="gpt-6.1-terra",
        max_tokens_field="max_completion_tokens",
        tags=("flagship",),
    ),
    ModelSpec(
        key="gpt-6-luna",
        display_name="GPT-6 Luna",
        provider="4router-gpt",
        model_id="gpt-6-luna",
        max_tokens_field="max_completion_tokens",
        tags=("fast",),
    ),
    ModelSpec(
        key="claude-opus-5.5",
        display_name="Claude Opus 5.5",
        provider="4router-claude",
        model_id="claude-opus-5-5",
        supports_temperature=False,
        tags=("flagship",),
    ),
    ModelSpec(
        key="claude-haiku-5.5",
        display_name="Claude Haiku 5.5",
        provider="4router-claude",
        model_id="claude-haiku-5-5",
        supports_temperature=False,
        tags=("fast",),
    ),
    ModelSpec(
        key="gemini-4-argon",
        display_name="Gemini 4 Argon",
        provider="4router-gemini",
        model_id="gemini-4-argon",
        tags=("flagship",),
    ),
    ModelSpec(
        key="gemini-3.8-flash",
        display_name="Gemini 3.8 Flash",
        provider="4router-gemini",
        model_id="gemini-3.8-flash",
        tags=("fast",),
    ),
)

_MODEL_SPECS = tuple(
    replace(
        spec,
        reasoning_bodies={
            level: bodies[spec.key]
            for level, bodies in (
                ("low", _REASONING_LOW),
                ("high", _REASONING_HIGH),
            )
            if spec.key in bodies
        },
    )
    for spec in _MODEL_SPECS
)

MODELS: dict[str, ModelSpec] = {spec.key: spec for spec in _MODEL_SPECS}


def resolve_model(name: str) -> ModelSpec:
    """Resolve a model key, model ID, or display name.

    Spaces and underscores are normalized to hyphens, so "DeepSeek V4 Pro"
    and "deepseek_v4_pro" both resolve to `deepseek-v4-pro`.
    """
    text = " ".join(name.split())
    normalized = text.casefold().replace("_", "-").replace(" ", "-")
    if normalized in MODELS:
        return MODELS[normalized]
    for spec in MODELS.values():
        candidates = {
            spec.key.casefold(),
            spec.model_id.casefold(),
            spec.display_name.casefold().replace(" ", "-"),
        }
        if normalized in candidates:
            return spec
    available = ", ".join(MODELS)
    raise KeyError(f"unknown model {name!r}; available: {available}")


def list_models(provider: str | None = None) -> list[ModelSpec]:
    """Return registered models in registry order."""
    if provider is None:
        return list(MODELS.values())
    return [spec for spec in MODELS.values() if spec.provider == provider]


def validate_registry() -> None:
    """Check that the registry is internally consistent."""
    seen_keys: set[str] = set()
    seen_pairs: set[tuple[str, str]] = set()
    seen_names: set[str] = set()

    for provider_id, provider in PROVIDERS.items():
        if provider.id != provider_id:
            raise ValueError(f"provider key mismatch: {provider_id} != {provider.id}")
        if not provider.base_url.startswith("https://"):
            raise ValueError(f"{provider_id}: base_url must use https")
        if not provider.api_key_env:
            raise ValueError(f"{provider_id}: api_key_env is empty")
        if not provider.chat_path.startswith("/"):
            raise ValueError(f"{provider_id}: chat_path must start with /")
        if provider.max_concurrency <= 0:
            raise ValueError(f"{provider_id}: max_concurrency must be positive")

    for key, spec in MODELS.items():
        if key != spec.key:
            raise ValueError(f"model key mismatch: {key} != {spec.key}")
        if key in seen_keys:
            raise ValueError(f"duplicate model key: {key}")
        seen_keys.add(key)
        if spec.provider not in PROVIDERS:
            raise ValueError(f"{key}: unknown provider {spec.provider}")
        pair = (spec.provider, spec.model_id)
        if pair in seen_pairs:
            raise ValueError(f"duplicate provider/model pair: {pair}")
        seen_pairs.add(pair)
        if spec.display_name.casefold() in seen_names:
            raise ValueError(f"duplicate display name: {spec.display_name}")
        seen_names.add(spec.display_name.casefold())
        if spec.max_tokens <= 0:
            raise ValueError(f"{key}: max_tokens must be positive")
        if spec.max_tokens_field not in {"max_tokens", "max_completion_tokens"}:
            raise ValueError(f"{key}: unsupported max_tokens_field")
        if not spec.supports_temperature and spec.temperature is not None:
            raise ValueError(
                f"{key}: temperature must be None when supports_temperature is False"
            )
