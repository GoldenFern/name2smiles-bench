"""Send a short prompt to registered models and report connectivity.

The smoke test is intentionally small. It checks that each provider accepts
the request shape, that the key works, and that the response parser extracts
text, reasoning, and usage.

Examples:
    python scripts/smoke_llm.py --all
    python scripts/smoke_llm.py --provider deepseek
    python scripts/smoke_llm.py --models "deepseek-v4-pro,glm-5.3"
"""

from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from name2smiles.llm import (  # noqa: E402
    LLMClient,
    LLMError,
    ModelSpec,
    list_models,
    resolve_model,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--all",
        action="store_true",
        help="run every registered model",
    )
    parser.add_argument(
        "--models",
        default="",
        help="comma-separated model keys or display names; default: all",
    )
    parser.add_argument("--provider", default="", help="only this provider")
    parser.add_argument("--prompt", default="hi", help="user prompt")
    parser.add_argument("--system", default="", help="optional system prompt")
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=None,
        help="override the registered output cap",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=None,
        help="override the provider default; Kimi and Claude reject custom values",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=4,
        help="parallel requests; each thread gets its own HTTP session",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=None,
        help="read timeout in seconds; default: provider setting",
    )
    parser.add_argument(
        "--allow-failures",
        action="store_true",
        help="return exit code 0 even when some models fail",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="JSONL output path; default: data/llm_smoke_<timestamp>.jsonl",
    )
    return parser.parse_args()


def select_models(args: argparse.Namespace) -> list[ModelSpec]:
    if args.all:
        specs = list_models(args.provider or None)
    elif args.models:
        specs = [resolve_model(name) for name in args.models.split(",") if name.strip()]
    else:
        specs = list_models(args.provider or None)
    if args.provider:
        specs = [spec for spec in specs if spec.provider == args.provider]
    if not specs:
        raise SystemExit("no models selected")
    return specs


def run_one(
    client: LLMClient,
    spec: ModelSpec,
    messages: list[dict[str, str]],
    args: argparse.Namespace,
) -> dict[str, Any]:
    try:
        result = client.chat(
            spec,
            messages,
            max_tokens=args.max_tokens,
            temperature=args.temperature,
        )
        return {"ok": True, "result": result}
    except LLMError as exc:
        return {
            "ok": False,
            "error": str(exc),
            "status": exc.status,
            "attempts": exc.attempts,
        }
    except Exception as exc:  # noqa: BLE001 - the smoke test reports any failure
        return {
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}",
            "status": None,
            "attempts": None,
        }


def row_to_dict(
    row: dict[str, Any],
    spec: ModelSpec,
    args: argparse.Namespace,
    timestamp: str,
) -> dict[str, Any]:
    data: dict[str, Any] = {
        "model_key": spec.key,
        "display_name": spec.display_name,
        "provider": spec.provider,
        "model_id": spec.model_id,
        "prompt": args.prompt,
        "system": args.system or None,
        "max_tokens": (
            args.max_tokens if args.max_tokens is not None else spec.max_tokens
        ),
        "temperature": args.temperature,
        "timestamp": timestamp,
    }
    if row["ok"]:
        result = row["result"]
        data.update(
            {
                "ok": True,
                "latency_ms": result.latency_ms,
                "attempts": result.attempts,
                "text": result.text,
                "reasoning": result.reasoning,
                "finish_reason": result.finish_reason,
                "usage": result.usage.to_dict(),
                "response_model": result.response_model,
                "request_id": result.request_id,
            }
        )
    else:
        data.update(
            {
                "ok": False,
                "error": row["error"],
                "status": row["status"],
                "attempts": row["attempts"],
            }
        )
    return data


def preview(text: str, limit: int = 80) -> str:
    compact = " ".join((text or "").split())
    if not compact:
        return ""
    return compact if len(compact) <= limit else compact[:limit] + "..."


def token_text(value: int | None) -> str:
    return "-" if value is None else str(value)


def print_table(rows: list[tuple[int, ModelSpec, dict[str, Any]]]) -> None:
    print()
    print(
        f"{'model':<24} {'status':<7} {'latency':>8} "
        f"{'input':>7} {'output':>7} {'reason':>7}"
    )
    print("-" * 70)
    for _, spec, row in rows:
        if row["ok"]:
            result = row["result"]
            usage = result.usage
            print(
                f"{spec.key:<24} {'ok':<7} {result.latency_ms / 1000:>7.2f}s "
                f"{token_text(usage.input_tokens):>7} "
                f"{token_text(usage.output_tokens):>7} "
                f"{token_text(usage.reasoning_tokens):>7}"
            )
        else:
            print(f"{spec.key:<24} {'FAIL':<7} {'-':>8} {'-':>7} {'-':>7} {'-':>7}")


def main() -> None:
    args = parse_args()
    specs = select_models(args)
    messages: list[dict[str, str]] = []
    if args.system:
        messages.append({"role": "system", "content": args.system})
    messages.append({"role": "user", "content": args.prompt})

    timeout = (30.0, args.timeout) if args.timeout is not None else None
    client = LLMClient(timeout=timeout)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    workers = max(1, min(args.workers, len(specs)))

    completed: list[tuple[int, ModelSpec, dict[str, Any]]] = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(run_one, client, spec, messages, args): (index, spec)
            for index, spec in enumerate(specs, start=1)
        }
        for future in as_completed(futures):
            index, spec = futures[future]
            row = future.result()
            completed.append((index, spec, row))
            if row["ok"]:
                result = row["result"]
                text = result.text or (
                    f"[reasoning only] {result.reasoning}" if result.reasoning else ""
                )
                print(
                    f"[{index:>2}/{len(specs)}] OK   {spec.key:<24} "
                    f"{result.latency_ms / 1000:6.2f}s  "
                    f"in={token_text(result.usage.input_tokens)} "
                    f"out={token_text(result.usage.output_tokens)}  "
                    f"{preview(text)}",
                    flush=True,
                )
            else:
                print(
                    f"[{index:>2}/{len(specs)}] FAIL {spec.key:<24} "
                    f"{row['error'][:160]}",
                    flush=True,
                )

    completed.sort(key=lambda item: item[0])
    print_table(completed)

    out = args.out or ROOT / "data" / f"llm_smoke_{timestamp}.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as handle:
        for _, spec, row in completed:
            handle.write(
                json.dumps(
                    row_to_dict(row, spec, args, timestamp),
                    ensure_ascii=False,
                )
                + "\n"
            )

    failures = [spec.key for _, spec, row in completed if not row["ok"]]
    print()
    print(f"models: {len(specs)}  ok: {len(specs) - len(failures)}  failed: {len(failures)}")
    if failures:
        print(f"failed models: {', '.join(failures)}")
    print(f"wrote: {out}")

    if failures and not args.allow_failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
