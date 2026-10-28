"""Estimate the cost of a batch run from the recorded price table.

The estimate assumes every record uses the same token counts. It is a
planning tool, not a bill. Use the smoke JSONL or a pilot run to replace the
defaults with measured token counts.

Example:
    python scripts/estimate_costs.py --records 1500 --input-tokens 200 --output-tokens 800
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from name2smiles.llm import (  # noqa: E402
    MODELS,
    ModelSpec,
    Usage,
    list_models,
    load_pricing,
    resolve_model,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--records", type=int, default=1500)
    parser.add_argument("--input-tokens", type=int, default=200)
    parser.add_argument("--output-tokens", type=int, default=800)
    parser.add_argument("--cached-input-tokens", type=int, default=0)
    parser.add_argument("--cache-write-input-tokens", type=int, default=0)
    parser.add_argument(
        "--models",
        default="",
        help="comma-separated model keys or display names; default: all",
    )
    parser.add_argument(
        "--sort",
        choices=["cost", "name"],
        default="cost",
        help="cost: most expensive first; name: registry order",
    )
    return parser.parse_args()


def select_models(value: str) -> list[ModelSpec]:
    if not value:
        return list_models()
    return [resolve_model(name) for name in value.split(",") if name.strip()]


def main() -> None:
    args = parse_args()
    pricing = load_pricing()
    specs = select_models(args.models)
    usage = Usage(
        input_tokens=args.input_tokens,
        output_tokens=args.output_tokens,
        cached_input_tokens=args.cached_input_tokens,
        cache_write_input_tokens=args.cache_write_input_tokens,
    )

    rows: list[tuple[str, float | None, float | None, float | None]] = []
    missing: list[str] = []
    for spec in specs:
        try:
            estimate = pricing.estimate(spec.key, usage)
        except KeyError:
            missing.append(spec.key)
            rows.append((spec.key, None, None, None))
            continue
        rows.append(
            (
                spec.key,
                estimate.input_cost * args.records,
                estimate.output_cost * args.records,
                estimate.total_cost * args.records,
            )
        )

    if args.sort == "cost":
        rows.sort(key=lambda row: (row[3] is None, -(row[3] or 0.0), row[0]))

    print(
        f"records={args.records}  "
        f"input={args.input_tokens}  output={args.output_tokens}  "
        f"cached_input={args.cached_input_tokens}  "
        f"cache_write={args.cache_write_input_tokens}"
    )
    print()
    print(
        f"{'model':<24} {'input':>12} {'output':>12} "
        f"{'total':>12} {'per_1k':>12}"
    )
    print("-" * 78)
    for key, input_cost, output_cost, total_cost in rows:
        if total_cost is None:
            print(f"{key:<24} {'n/a':>12} {'n/a':>12} {'n/a':>12} {'n/a':>12}")
            continue
        per_1k = total_cost / args.records * 1000 if args.records else 0.0
        print(
            f"{key:<24} {input_cost:>12.4f} {output_cost:>12.4f} "
            f"{total_cost:>12.4f} {per_1k:>12.4f}"
        )

    print()
    print(f"currency: {pricing.base_currency}")
    print(f"prices as of: {pricing.as_of}")
    if missing:
        print(f"missing prices: {', '.join(missing)}")
    total = sum(row[3] for row in rows if row[3] is not None)
    included = sum(1 for row in rows if row[3] is not None)
    print(f"total across {included} models: {total:.4f} {pricing.base_currency}")
    print("This is a planning estimate, not a provider bill.")


if __name__ == "__main__":
    main()
