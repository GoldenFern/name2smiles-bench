"""Model price table and cost estimation.

Prices are stored in the bundled ``llm_pricing.json`` with a base currency and a
unit of per one million tokens. The 4Router prices are the displayed console
prices and already include the group multiplier.

The estimator treats ``Usage.input_tokens`` according to the model's
``input_includes_cache`` flag. OpenAI-compatible providers usually report
cached tokens as a subset of ``prompt_tokens``; Anthropic reports cache read
and cache write tokens separately.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from .registry import resolve_model
from .types import Usage

DEFAULT_PRICING_PATH = Path(__file__).with_name("llm_pricing.json")


@dataclass(frozen=True)
class ModelPrice:
    """List price for one model, per one million tokens."""

    model_key: str
    vendor: str
    provider: str
    model_id: str
    currency: str
    input_per_1m: float
    output_per_1m: float
    cache_read_per_1m: float | None = None
    cache_write_per_1m: float | None = None
    input_includes_cache: bool = True
    source: str = ""
    source_url: str = ""
    source_type: str = ""
    retrieved_at: str = ""
    notes: str = ""


@dataclass(frozen=True)
class CostEstimate:
    """Estimated cost for one call or a batch of calls."""

    model_key: str
    currency: str
    uncached_input_tokens: int
    cached_input_tokens: int
    cache_write_input_tokens: int
    output_tokens: int
    input_cost: float
    cache_read_cost: float
    cache_write_cost: float
    output_cost: float
    total_cost: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class PricingTable:
    """A parsed price table."""

    def __init__(
        self,
        models: dict[str, ModelPrice],
        *,
        as_of: str,
        base_currency: str,
        unit: str,
    ) -> None:
        self._models = models
        self.as_of = as_of
        self.base_currency = base_currency
        self.unit = unit

    @property
    def models(self) -> dict[str, ModelPrice]:
        return self._models

    @classmethod
    def load(cls, path: str | Path = DEFAULT_PRICING_PATH) -> PricingTable:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        base_currency = str(data["base_currency"])
        unit = str(data["unit"])
        if unit != "per_1m_tokens":
            raise ValueError(f"unsupported pricing unit: {unit}")
        models: dict[str, ModelPrice] = {}
        for key, raw in data["models"].items():
            spec = resolve_model(key)
            if str(raw["provider"]) != spec.provider:
                raise ValueError(
                    f"{key}: provider {raw['provider']} does not match registry"
                )
            if str(raw["model_id"]) != spec.model_id:
                raise ValueError(
                    f"{key}: model ID {raw['model_id']} does not match registry"
                )
            currency = str(raw.get("currency", base_currency))
            if currency != base_currency:
                raise ValueError(
                    f"{key}: currency {currency} does not match {base_currency}"
                )
            models[key] = ModelPrice(
                model_key=key,
                vendor=str(raw["vendor"]),
                provider=str(raw["provider"]),
                model_id=str(raw["model_id"]),
                currency=currency,
                input_per_1m=float(raw["input"]),
                output_per_1m=float(raw["output"]),
                cache_read_per_1m=_float_or_none(raw.get("cache_read")),
                cache_write_per_1m=_float_or_none(raw.get("cache_write")),
                input_includes_cache=bool(raw.get("input_includes_cache", True)),
                source=str(raw.get("source", "")),
                source_url=str(raw.get("source_url", "")),
                source_type=str(raw.get("source_type", "")),
                retrieved_at=str(raw.get("retrieved_at", data.get("as_of", ""))),
                notes=str(raw.get("notes", "")),
            )
        return cls(
            models,
            as_of=str(data["as_of"]),
            base_currency=base_currency,
            unit=unit,
        )

    def price(self, model_key: str) -> ModelPrice:
        """Return the price for a registry key, model ID, or display name."""
        spec = resolve_model(model_key)
        price = self._models.get(spec.key)
        if price is None:
            raise KeyError(f"no price registered for {spec.key}")
        return price

    def estimate(self, model_key: str, usage: Usage) -> CostEstimate:
        """Estimate the cost of one call from normalized token usage."""
        price = self.price(model_key)
        input_tokens = usage.input_tokens or 0
        cached_tokens = usage.cached_input_tokens or 0
        cache_write_tokens = usage.cache_write_input_tokens or 0
        output_tokens = usage.output_tokens or 0

        if price.input_includes_cache:
            uncached_tokens = max(input_tokens - cached_tokens, 0)
        else:
            uncached_tokens = input_tokens

        input_cost = _cost(uncached_tokens, price.input_per_1m)
        cache_read_cost = _cost(
            cached_tokens,
            price.cache_read_per_1m
            if price.cache_read_per_1m is not None
            else price.input_per_1m,
        )
        cache_write_cost = _cost(
            cache_write_tokens,
            price.cache_write_per_1m
            if price.cache_write_per_1m is not None
            else price.input_per_1m,
        )
        output_cost = _cost(output_tokens, price.output_per_1m)
        total_cost = input_cost + cache_read_cost + cache_write_cost + output_cost

        return CostEstimate(
            model_key=price.model_key,
            currency=price.currency,
            uncached_input_tokens=uncached_tokens,
            cached_input_tokens=cached_tokens,
            cache_write_input_tokens=cache_write_tokens,
            output_tokens=output_tokens,
            input_cost=round(input_cost, 6),
            cache_read_cost=round(cache_read_cost, 6),
            cache_write_cost=round(cache_write_cost, 6),
            output_cost=round(output_cost, 6),
            total_cost=round(total_cost, 6),
        )


@lru_cache(maxsize=4)
def load_pricing(path: str | Path = DEFAULT_PRICING_PATH) -> PricingTable:
    """Load and cache a price table."""
    return PricingTable.load(path)


def estimate_cost(
    model_key: str,
    usage: Usage,
    *,
    pricing: PricingTable | None = None,
) -> CostEstimate:
    """Estimate one call without creating a pricing table manually."""
    table = pricing if pricing is not None else load_pricing()
    return table.estimate(model_key, usage)


def _cost(tokens: int, price_per_1m: float) -> float:
    return tokens / 1_000_000 * price_per_1m


def _float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)
