"""Run a five-molecule, eight-model tier probe with round-based retries.

The probe uses one record from each difficulty tier, sends the same prompt to
every model, and records full outputs, token usage, and RDKit correctness.
Concurrency-limit errors (HTTP 429 and 503) are returned to the scheduler and
re-queued for the next round.

Examples:
    python scripts/eval_tier_probe.py --preflight-only
    python scripts/eval_tier_probe.py --skip-preflight --preflight-json data/eval_tier_probe_preflight.json
    python scripts/eval_tier_probe.py
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from name2smiles.llm import (  # noqa: E402
    LLMClient,
    LLMError,
    ModelSpec,
    PROVIDERS,
    estimate_cost,
    resolve_model,
)
from evaluate_name2smiles import (  # noqa: E402
    SYSTEM_PROMPT,
    extract_smiles,
    score_prediction,
)

DEFAULT_MODELS: tuple[str, ...] = (
    "deepseek-flash",
    "minimax-m3.1-flash",
    "glm-5.3-flash",
    "claude-haiku-5.5",
    "gpt-6.1-terra",
    "gemini-3.8-flash",
    "mimo-v2.6-flash",
    "longcat-2.5-preview",
)
DEFAULT_IDS: tuple[str, ...] = (
    "N2S-000519",
    "N2S-001035",
    "N2S-000177",
    "N2S-001425",
    "N2S-001135",
)
TIER_ORDER: tuple[str, ...] = ("L1", "L2", "L3", "L4", "L5")
RETRY_STATUS = {429, 503}
PREFLIGHT_PROMPT = "Reply with the single word: ok"
EMPTY_SCORES: dict[str, Any] = {
    "valid": False,
    "exact": False,
    "connectivity": False,
    "inchikey": False,
    "inchikey_skeleton": False,
    "tanimoto": 0.0,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data",
        type=Path,
        default=ROOT / "data" / "mini_100.jsonl",
    )
    parser.add_argument("--ids", default=",".join(DEFAULT_IDS))
    parser.add_argument("--models", default=",".join(DEFAULT_MODELS))
    parser.add_argument(
        "--reasoning",
        default="high",
        choices=["default", "none", "low", "high", "max"],
    )
    parser.add_argument("--max-tokens", type=int, default=100_000)
    parser.add_argument("--connect-timeout-seconds", type=float, default=30.0)
    parser.add_argument("--timeout-seconds", type=float, default=1800.0)
    parser.add_argument("--global-concurrency", type=int, default=40)
    parser.add_argument("--provider-concurrency", type=int, default=5)
    parser.add_argument("--max-rounds", type=int, default=5)
    parser.add_argument("--round-delay", type=float, default=15.0)
    parser.add_argument(
        "--preflight-timeout-seconds",
        type=float,
        default=300.0,
    )
    parser.add_argument(
        "--fallback-max-tokens",
        type=int,
        default=32_000,
        help="cap to try when a provider rejects the requested max_tokens",
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--preflight-only", action="store_true")
    group.add_argument("--skip-preflight", action="store_true")
    parser.add_argument("--preflight-json", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--summary", type=Path, default=None)
    parser.add_argument(
        "--report",
        type=Path,
        default=ROOT / "docs" / "eval_tier_probe.md",
    )
    return parser.parse_args()


def load_records(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle]


def select_records(records: list[dict[str, Any]], ids: str) -> list[dict[str, Any]]:
    wanted = [value.strip() for value in ids.split(",") if value.strip()]
    by_id = {record["id"]: record for record in records}
    missing = [record_id for record_id in wanted if record_id not in by_id]
    if missing:
        raise SystemExit(f"unknown dataset IDs: {', '.join(missing)}")
    return [by_id[record_id] for record_id in wanted]


def select_models(values: str) -> list[ModelSpec]:
    models = [
        resolve_model(value.strip()) for value in values.split(",") if value.strip()
    ]
    if not models:
        raise SystemExit("no models selected")
    return models


def preflight_cap(spec: ModelSpec, args: argparse.Namespace) -> int:
    if spec.max_output_tokens and spec.max_output_tokens < args.max_tokens:
        return spec.max_output_tokens
    return args.fallback_max_tokens


def is_token_limit_error(error: LLMError) -> bool:
    text = f"{error} {error.body or ''}".casefold()
    return any(
        marker in text
        for marker in (
            "max_tokens",
            "max_completion_tokens",
            "too large",
            "exceed",
            "maximum",
        )
    )


def preflight_one(
    client: LLMClient,
    spec: ModelSpec,
    args: argparse.Namespace,
) -> dict[str, Any]:
    attempts: list[dict[str, Any]] = []
    caps = [args.max_tokens]
    fallback = preflight_cap(spec, args)
    if 0 < fallback < args.max_tokens:
        caps.append(fallback)

    for index, cap in enumerate(caps):
        for attempt in range(1, 4):
            started = time.perf_counter()
            try:
                result = client.chat(
                    spec,
                    PREFLIGHT_PROMPT,
                    max_tokens=cap,
                    reasoning=None,
                )
            except LLMError as exc:
                latency = round((time.perf_counter() - started) * 1000, 1)
                attempts.append(
                    {
                        "cap": cap,
                        "attempt": attempt,
                        "ok": False,
                        "status": exc.status,
                        "error": str(exc),
                        "latency_ms": latency,
                    }
                )
                if exc.status in RETRY_STATUS and attempt < 3:
                    time.sleep(10.0 * attempt)
                    continue
                if (
                    index == 0
                    and exc.status == 400
                    and is_token_limit_error(exc)
                    and len(caps) > 1
                ):
                    break
                return {
                    "model_key": spec.key,
                    "model_id": spec.model_id,
                    "provider": spec.provider,
                    "display_name": spec.display_name,
                    "ok": False,
                    "status": exc.status,
                    "error": str(exc),
                    "body": exc.body,
                    "latency_ms": latency,
                    "effective_max_tokens": args.max_tokens,
                    "fallback_used": False,
                    "attempts": attempts,
                }
            except Exception as exc:  # noqa: BLE001 - preflight reports any failure
                latency = round((time.perf_counter() - started) * 1000, 1)
                attempts.append(
                    {
                        "cap": cap,
                        "attempt": attempt,
                        "ok": False,
                        "status": None,
                        "error": f"{type(exc).__name__}: {exc}",
                        "latency_ms": latency,
                    }
                )
                return {
                    "model_key": spec.key,
                    "model_id": spec.model_id,
                    "provider": spec.provider,
                    "display_name": spec.display_name,
                    "ok": False,
                    "status": None,
                    "error": f"{type(exc).__name__}: {exc}",
                    "body": None,
                    "latency_ms": latency,
                    "effective_max_tokens": args.max_tokens,
                    "fallback_used": False,
                    "attempts": attempts,
                }

            latency = result.latency_ms
            attempts.append(
                {
                    "cap": cap,
                    "attempt": attempt,
                    "ok": True,
                    "status": 200,
                    "error": None,
                    "latency_ms": latency,
                }
            )
            return {
                "model_key": spec.key,
                "model_id": spec.model_id,
                "provider": spec.provider,
                "display_name": spec.display_name,
                "ok": True,
                "status": 200,
                "error": None,
                "body": None,
                "latency_ms": latency,
                "effective_max_tokens": cap,
                "fallback_used": index > 0,
                "text": result.text,
                "usage": result.usage.to_dict(),
                "finish_reason": result.finish_reason,
                "attempts": attempts,
            }
    return {
        "model_key": spec.key,
        "model_id": spec.model_id,
        "provider": spec.provider,
        "display_name": spec.display_name,
        "ok": False,
        "status": None,
        "error": "preflight exhausted",
        "body": None,
        "latency_ms": attempts[-1]["latency_ms"] if attempts else None,
        "effective_max_tokens": args.max_tokens,
        "fallback_used": False,
        "attempts": attempts,
    }


def run_preflight(
    specs: list[ModelSpec],
    args: argparse.Namespace,
    run_id: str,
) -> dict[str, Any]:
    providers = {spec.provider for spec in specs}
    client = LLMClient(
        max_attempts=1,
        timeout=(args.connect_timeout_seconds, args.preflight_timeout_seconds),
        provider_concurrency={provider: 1 for provider in providers},
    )
    started_at = datetime.now(timezone.utc).isoformat()
    results: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=max(1, len(specs))) as executor:
        futures = {
            executor.submit(preflight_one, client, spec, args): spec for spec in specs
        }
        for future in as_completed(futures):
            spec = futures[future]
            try:
                result = future.result()
            except Exception as exc:  # noqa: BLE001 - keep the preflight alive
                result = {
                    "model_key": spec.key,
                    "model_id": spec.model_id,
                    "provider": spec.provider,
                    "display_name": spec.display_name,
                    "ok": False,
                    "status": None,
                    "error": f"{type(exc).__name__}: {exc}",
                    "body": None,
                    "latency_ms": None,
                    "effective_max_tokens": args.max_tokens,
                    "fallback_used": False,
                    "attempts": [],
                }
            results.append(result)

    order = {spec.key: index for index, spec in enumerate(specs)}
    results.sort(key=lambda item: order[item["model_key"]])
    payload = {
        "run_id": run_id,
        "started_at": started_at,
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "settings": {
            "max_tokens": args.max_tokens,
            "fallback_max_tokens": args.fallback_max_tokens,
            "preflight_timeout_seconds": args.preflight_timeout_seconds,
            "reasoning": None,
        },
        "results": results,
    }
    path = ROOT / "data" / "eval_tier_probe_preflight.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    print("\nPreflight")
    print(
        f"{'model':<24} {'100k':>5} {'effective':>10} {'ok':>3} "
        f"{'latency':>9}  note"
    )
    print("-" * 86)
    for result in results:
        note = ""
        if result.get("fallback_used"):
            note = "fallback cap used"
        elif not result["ok"]:
            note = (result.get("error") or "")[:48]
        print(
            f"{result['model_key']:<24} {'yes':>5} "
            f"{result['effective_max_tokens']:>10} "
            f"{'yes' if result['ok'] else 'no':>3} "
            f"{(result.get('latency_ms') or 0) / 1000:>8.1f}s  {note}"
        )
    print(f"wrote: {path}")
    return payload


def load_preflight(
    path: Path | None,
    specs: list[ModelSpec],
    args: argparse.Namespace,
) -> dict[str, Any]:
    if path is None:
        path = ROOT / "data" / "eval_tier_probe_preflight.json"
    if not path.exists():
        results = [
            {
                "model_key": spec.key,
                "model_id": spec.model_id,
                "provider": spec.provider,
                "display_name": spec.display_name,
                "ok": None,
                "status": None,
                "error": "preflight not run",
                "effective_max_tokens": args.max_tokens,
                "fallback_used": False,
                "attempts": [],
            }
            for spec in specs
        ]
        return {"results": results, "settings": {"preflight_skipped": True}}
    payload = json.loads(path.read_text(encoding="utf-8"))
    print(f"loaded preflight: {path}")
    return payload


def run_task(
    client: LLMClient,
    task: dict[str, Any],
    reasoning: str | None,
) -> dict[str, Any]:
    spec: ModelSpec = task["spec"]
    record = task["record"]
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Name: {record['name']}\nSMILES:"},
    ]
    started = time.perf_counter()
    try:
        result = client.chat(
            spec,
            messages,
            max_tokens=task["max_tokens"],
            reasoning=reasoning,
        )
    except LLMError as exc:
        latency = round((time.perf_counter() - started) * 1000, 1)
        return {
            "ok": False,
            "status": exc.status,
            "error": str(exc),
            "body": exc.body,
            "attempts": exc.attempts,
            "latency_ms": latency,
            "retryable": exc.status in RETRY_STATUS,
            "result": None,
            "predicted_smiles": None,
            "scores": dict(EMPTY_SCORES),
            "cost_cny": None,
        }
    except Exception as exc:  # noqa: BLE001 - the probe reports any failure
        latency = round((time.perf_counter() - started) * 1000, 1)
        return {
            "ok": False,
            "status": None,
            "error": f"{type(exc).__name__}: {exc}",
            "body": None,
            "attempts": None,
            "latency_ms": latency,
            "retryable": False,
            "result": None,
            "predicted_smiles": None,
            "scores": dict(EMPTY_SCORES),
            "cost_cny": None,
        }

    try:
        predicted = extract_smiles(result.text)
        scores = score_prediction(predicted, record)
    except Exception as exc:  # noqa: BLE001 - keep the successful call
        predicted = None
        scores = dict(EMPTY_SCORES)
        scores["parse_error"] = f"{type(exc).__name__}: {exc}"

    try:
        cost = estimate_cost(spec.key, result.usage).total_cost
    except KeyError:
        cost = None
    return {
        "ok": True,
        "status": 200,
        "error": None,
        "body": None,
        "attempts": result.attempts,
        "latency_ms": result.latency_ms,
        "retryable": False,
        "result": result,
        "predicted_smiles": predicted,
        "scores": scores,
        "cost_cny": cost,
    }


def attempt_record(
    round_no: int,
    result: dict[str, Any],
) -> dict[str, Any]:
    usage = {}
    if result.get("result") is not None:
        usage = result["result"].usage.to_dict()
    return {
        "round": round_no,
        "ok": result["ok"],
        "status": result.get("status"),
        "error": result.get("error"),
        "latency_ms": result.get("latency_ms"),
        "usage": usage,
    }


def build_row(
    run_id: str,
    task: dict[str, Any],
    result: dict[str, Any],
    round_no: int,
    reasoning_level: str,
) -> dict[str, Any]:
    spec: ModelSpec = task["spec"]
    record = task["record"]
    difficulty = record["difficulty"]
    usage = result["result"].usage.to_dict() if result.get("result") else {}
    scores = result.get("scores") or dict(EMPTY_SCORES)
    history = list(task["history"])
    history.append(attempt_record(round_no, result))
    return {
        "run_id": run_id,
        "round": round_no,
        "requeues": task["requeues"],
        "attempts_history": history,
        "model_key": spec.key,
        "model_id": spec.model_id,
        "provider": spec.provider,
        "display_name": spec.display_name,
        "record_id": record["id"],
        "mini_id": record["mini_id"],
        "tier": difficulty["tier"],
        "difficulty_score": difficulty["score"],
        "name": record["name"],
        "reference_smiles": record["canonical_smiles"],
        "reference_inchikey": record["inchikey"],
        "reasoning_level": reasoning_level,
        "max_tokens": task["max_tokens"],
        "ok": result["ok"],
        "status": result.get("status"),
        "error": result.get("error"),
        "body": result.get("body"),
        "attempts": result.get("attempts"),
        "latency_ms": result.get("latency_ms"),
        "finish_reason": (
            result["result"].finish_reason if result.get("result") else None
        ),
        "response_model": (
            result["result"].response_model if result.get("result") else None
        ),
        "request_id": (result["result"].request_id if result.get("result") else None),
        "usage": usage,
        "cost_cny": result.get("cost_cny"),
        "predicted_smiles": result.get("predicted_smiles"),
        "raw_text": result["result"].text if result.get("result") else None,
        "reasoning": (result["result"].reasoning if result.get("result") else None),
        "valid": bool(scores.get("valid", False)),
        "exact": bool(scores.get("exact", False)),
        "connectivity": bool(scores.get("connectivity", False)),
        "inchikey": bool(scores.get("inchikey", False)),
        "inchikey_skeleton": bool(scores.get("inchikey_skeleton", False)),
        "tanimoto": float(scores.get("tanimoto", 0.0)),
        "parse_error": scores.get("parse_error"),
    }


def build_tasks(
    specs: list[ModelSpec],
    records: list[dict[str, Any]],
    preflight: dict[str, Any],
    args: argparse.Namespace,
) -> list[dict[str, Any]]:
    by_model = {result["model_key"]: result for result in preflight.get("results", [])}
    tasks: list[dict[str, Any]] = []
    for spec in specs:
        info = by_model.get(spec.key, {})
        if info.get("ok") is True:
            cap = int(info["effective_max_tokens"])
        else:
            cap = args.max_tokens
        for record in records:
            tasks.append(
                {
                    "spec": spec,
                    "record": record,
                    "max_tokens": cap,
                    "round": 1,
                    "requeues": 0,
                    "history": [],
                }
            )
    return tasks


def run_rounds(
    client: LLMClient,
    tasks: list[dict[str, Any]],
    specs: list[ModelSpec],
    records: list[dict[str, Any]],
    args: argparse.Namespace,
    run_id: str,
) -> list[dict[str, Any]]:
    pending = deque(tasks)
    rows: list[dict[str, Any]] = []
    round_no = 0
    while pending and round_no < args.max_rounds:
        round_no += 1
        batch = [
            pending.popleft() for _ in range(min(args.global_concurrency, len(pending)))
        ]
        print(f"\nRound {round_no}: {len(batch)} task(s), " f"{len(pending)} waiting")
        retry_tasks: list[dict[str, Any]] = []
        with ThreadPoolExecutor(max_workers=max(1, len(batch))) as executor:
            futures = {
                executor.submit(
                    run_task,
                    client,
                    task,
                    None if args.reasoning in {"default", "none"} else args.reasoning,
                ): task
                for task in batch
            }
            for future in as_completed(futures):
                task = futures[future]
                try:
                    result = future.result()
                except Exception as exc:  # noqa: BLE001 - keep the round alive
                    result = {
                        "ok": False,
                        "status": None,
                        "error": f"{type(exc).__name__}: {exc}",
                        "body": None,
                        "attempts": None,
                        "latency_ms": None,
                        "retryable": False,
                        "result": None,
                        "predicted_smiles": None,
                        "scores": dict(EMPTY_SCORES),
                        "cost_cny": None,
                    }
                if result["retryable"] and round_no < args.max_rounds:
                    task["history"].append(attempt_record(round_no, result))
                    task["requeues"] += 1
                    task["round"] = round_no + 1
                    retry_tasks.append(task)
                    print(
                        f"  REQUEUE {task['spec'].key:<24} "
                        f"{task['record']['id']} status={result.get('status')}",
                        flush=True,
                    )
                    continue
                row = build_row(
                    run_id,
                    task,
                    result,
                    round_no,
                    args.reasoning,
                )
                rows.append(row)
                status = (
                    "EXACT"
                    if row["exact"]
                    else (
                        "CONN"
                        if row["connectivity"]
                        else (
                            "VALID"
                            if row["valid"]
                            else "INVALID" if row["ok"] else f"FAIL:{row['status']}"
                        )
                    )
                )
                usage = row["usage"]
                print(
                    f"  {task['spec'].key:<24} {task['record']['id']} "
                    f"{status:<8} in={usage.get('input_tokens')} "
                    f"out={usage.get('output_tokens')} "
                    f"{row['latency_ms'] / 1000 if row['latency_ms'] else 0:5.1f}s",
                    flush=True,
                )
        pending = deque(retry_tasks) + pending
        if retry_tasks and pending:
            delay = min(args.round_delay * (2 ** (round_no - 1)), 120.0)
            print(f"waiting {delay:.0f}s before round {round_no + 1}", flush=True)
            time.sleep(delay)

    while pending:
        task = pending.popleft()
        result = {
            "ok": False,
            "status": None,
            "error": f"max rounds exceeded ({args.max_rounds})",
            "body": None,
            "attempts": None,
            "latency_ms": None,
            "retryable": False,
            "result": None,
            "predicted_smiles": None,
            "scores": dict(EMPTY_SCORES),
            "cost_cny": None,
        }
        rows.append(
            build_row(
                run_id,
                task,
                result,
                args.max_rounds,
                args.reasoning,
            )
        )

    model_order = {spec.key: index for index, spec in enumerate(specs)}
    record_order = {record["id"]: index for index, record in enumerate(records)}
    rows.sort(
        key=lambda row: (
            model_order[row["model_key"]],
            record_order[row["record_id"]],
        )
    )
    return rows


def mean(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 2) if values else None


def summarize(
    rows: list[dict[str, Any]],
    specs: list[ModelSpec],
    records: list[dict[str, Any]],
    preflight: dict[str, Any],
    args: argparse.Namespace,
    run_id: str,
    started_at: str,
) -> dict[str, Any]:
    model_summaries: dict[str, Any] = {}
    for spec in specs:
        model_rows = [row for row in rows if row["model_key"] == spec.key]
        n = len(model_rows)
        ok_rows = [row for row in model_rows if row["ok"]]
        valid_rows = [row for row in ok_rows if row["valid"]]
        input_values = [
            row["usage"]["input_tokens"]
            for row in ok_rows
            if row["usage"].get("input_tokens") is not None
        ]
        output_values = [
            row["usage"]["output_tokens"]
            for row in ok_rows
            if row["usage"].get("output_tokens") is not None
        ]
        reasoning_values = [
            row["usage"]["reasoning_tokens"]
            for row in ok_rows
            if row["usage"].get("reasoning_tokens") is not None
        ]
        costs = [row["cost_cny"] for row in ok_rows if row["cost_cny"] is not None]
        latencies = [
            row["latency_ms"] for row in model_rows if row["latency_ms"] is not None
        ]
        tier_summaries: dict[str, Any] = {}
        for tier in TIER_ORDER:
            tier_rows = [row for row in model_rows if row["tier"] == tier]
            tier_valid = [row for row in tier_rows if row["valid"]]
            tier_summaries[tier] = {
                "n": len(tier_rows),
                "ok": sum(row["ok"] for row in tier_rows),
                "valid": sum(row["valid"] for row in tier_rows),
                "exact": sum(row["exact"] for row in tier_rows),
                "connectivity": sum(row["connectivity"] for row in tier_rows),
                "inchikey": sum(row["inchikey"] for row in tier_rows),
                "mean_tanimoto": mean([row["tanimoto"] for row in tier_valid]),
                "input_tokens": sum(
                    row["usage"].get("input_tokens") or 0
                    for row in tier_rows
                    if row["usage"]
                ),
                "output_tokens": sum(
                    row["usage"].get("output_tokens") or 0
                    for row in tier_rows
                    if row["usage"]
                ),
            }
        model_summaries[spec.key] = {
            "model_id": spec.model_id,
            "provider": spec.provider,
            "display_name": spec.display_name,
            "n": n,
            "ok": len(ok_rows),
            "errors": n - len(ok_rows),
            "requeues": sum(row["requeues"] for row in model_rows),
            "valid": sum(row["valid"] for row in model_rows),
            "exact": sum(row["exact"] for row in model_rows),
            "connectivity": sum(row["connectivity"] for row in model_rows),
            "inchikey": sum(row["inchikey"] for row in model_rows),
            "inchikey_skeleton": sum(row["inchikey_skeleton"] for row in model_rows),
            "valid_rate": (
                round(sum(row["valid"] for row in model_rows) / n, 4) if n else 0.0
            ),
            "exact_rate": (
                round(sum(row["exact"] for row in model_rows) / n, 4) if n else 0.0
            ),
            "connectivity_rate": (
                round(sum(row["connectivity"] for row in model_rows) / n, 4)
                if n
                else 0.0
            ),
            "inchikey_rate": (
                round(sum(row["inchikey"] for row in model_rows) / n, 4) if n else 0.0
            ),
            "mean_tanimoto": mean([row["tanimoto"] for row in valid_rows]),
            "input_tokens_sum": sum(input_values),
            "input_tokens_mean": mean([float(value) for value in input_values]),
            "output_tokens_sum": sum(output_values),
            "output_tokens_mean": mean([float(value) for value in output_values]),
            "reasoning_tokens_sum": sum(reasoning_values),
            "total_cost_cny": round(sum(costs), 6) if costs else 0.0,
            "mean_latency_ms": mean([float(value) for value in latencies]),
            "tiers": tier_summaries,
        }

    return {
        "run_id": run_id,
        "started_at": started_at,
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "data": str(args.data),
        "record_ids": [record["id"] for record in records],
        "settings": {
            "reasoning": args.reasoning,
            "max_tokens": args.max_tokens,
            "timeout_seconds": args.timeout_seconds,
            "connect_timeout_seconds": args.connect_timeout_seconds,
            "global_concurrency": args.global_concurrency,
            "provider_concurrency": args.provider_concurrency,
            "max_rounds": args.max_rounds,
            "round_delay_seconds": args.round_delay,
            "retry_status": sorted(RETRY_STATUS),
        },
        "preflight": preflight,
        "models": model_summaries,
    }


def format_rate(value: float | None) -> str:
    return f"{value * 100:.1f}%" if value is not None else "-"


def print_summary(summary: dict[str, Any]) -> None:
    print("\nSummary")
    print(
        f"{'model':<24} {'ok':>5} {'valid':>7} {'exact':>7} {'conn':>7} "
        f"{'inchikey':>9} {'tanimoto':>8} {'in_tok':>8} {'out_tok':>8} "
        f"{'cost':>8}"
    )
    print("-" * 116)
    for key, row in summary["models"].items():
        print(
            f"{key:<24} {row['ok']:>2}/{row['n']:<2} "
            f"{format_rate(row['valid_rate']):>7} "
            f"{format_rate(row['exact_rate']):>7} "
            f"{format_rate(row['connectivity_rate']):>7} "
            f"{format_rate(row['inchikey_rate']):>9} "
            f"{(row['mean_tanimoto'] or 0):>8.3f} "
            f"{row['input_tokens_mean'] or 0:>8.1f} "
            f"{row['output_tokens_mean'] or 0:>8.1f} "
            f"{row['total_cost_cny']:>8.4f}"
        )
    print("-" * 116)
    total_cost = sum(row["total_cost_cny"] for row in summary["models"].values())
    print(f"total cost: {total_cost:.4f} CNY")


def write_report(path: Path, summary: dict[str, Any]) -> None:
    settings = summary["settings"]
    lines: list[str] = [
        "# Tier Probe",
        "",
        f"Run: `{summary['run_id']}`",
        "",
        "Five molecules, one from each difficulty tier, eight models. "
        "The prompt and system message match `evaluate_name2smiles.py`.",
        "",
        "## Settings",
        "",
        f"- Reasoning: `{settings['reasoning']}`",
        f"- Max output tokens: `{settings['max_tokens']}`",
        f"- Timeout: `{settings['timeout_seconds']}` s "
        f"(connect `{settings['connect_timeout_seconds']}` s)",
        f"- Global concurrency: `{settings['global_concurrency']}`",
        f"- Per-provider concurrency: `{settings['provider_concurrency']}`",
        f"- Max rounds: `{settings['max_rounds']}`, retry status: "
        f"`{settings['retry_status']}`",
        "",
        "## Preflight",
        "",
        "| Model | 100k accepted | Effective cap | Fallback | Latency | Note |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for result in summary["preflight"].get("results", []):
        note = ""
        if result.get("fallback_used"):
            note = "fallback cap used"
        elif result.get("ok") is False:
            note = (result.get("error") or "")[:120].replace("|", "\\|")
        lines.append(
            f"| {result['model_key']} | "
            f"{'yes' if result.get('ok') else 'no' if result.get('ok') is False else '-'} | "
            f"{result.get('effective_max_tokens', '-')} | "
            f"{'yes' if result.get('fallback_used') else 'no'} | "
            f"{(result.get('latency_ms') or 0) / 1000:.1f}s | {note} |"
        )

    lines += [
        "",
        "## Per-model results",
        "",
        "Correctness rates use all five records as the denominator. "
        "`valid` means RDKit parsed the answer. `exact` is the canonical "
        "isomeric SMILES. `connectivity` ignores stereochemistry. `inchikey` "
        "is the full InChIKey match.",
        "",
        "| Model | ok | valid | exact | connectivity | inchikey | "
        "Tanimoto | Input tok (mean) | Output tok (mean) | Cost CNY | Requeues |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for key, row in summary["models"].items():
        lines.append(
            f"| {key} | {row['ok']}/{row['n']} | "
            f"{format_rate(row['valid_rate'])} | "
            f"{format_rate(row['exact_rate'])} | "
            f"{format_rate(row['connectivity_rate'])} | "
            f"{format_rate(row['inchikey_rate'])} | "
            f"{(row['mean_tanimoto'] or 0):.3f} | "
            f"{row['input_tokens_mean'] or 0:.1f} | "
            f"{row['output_tokens_mean'] or 0:.1f} | "
            f"{row['total_cost_cny']:.4f} | {row['requeues']} |"
        )

    lines += [
        "",
        "## Correctness by tier",
        "",
        "Cells are `exact/connectivity` counts out of one record per tier. "
        "A failed call also counts as 0/0; see `ok` in the per-model table.",
        "",
        "| Model | L1 | L2 | L3 | L4 | L5 |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for key, row in summary["models"].items():
        cells = []
        for tier in TIER_ORDER:
            tier_row = row["tiers"][tier]
            cells.append(f"{tier_row['exact']}/{tier_row['connectivity']}")
        lines.append(f"| {key} | " + " | ".join(cells) + " |")

    lines += [
        "",
        "## Token usage",
        "",
        "| Model | Input sum | Input mean | Output sum | Output mean | "
        "Reasoning sum | Total cost CNY |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for key, row in summary["models"].items():
        lines.append(
            f"| {key} | {row['input_tokens_sum']} | "
            f"{row['input_tokens_mean'] or 0:.1f} | "
            f"{row['output_tokens_sum']} | "
            f"{row['output_tokens_mean'] or 0:.1f} | "
            f"{row['reasoning_tokens_sum']} | "
            f"{row['total_cost_cny']:.4f} |"
        )

    lines += [
        "",
        "## Notes",
        "",
        "- HTTP 429 and 503 responses are re-queued for the next round.",
        "- A request that exceeds the 30-minute timeout is recorded as a "
        "terminal failure.",
        "- Full model text and reasoning are in the JSONL output.",
        "- The JSONL also contains per-attempt history, token usage, and "
        "RDKit scores.",
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8", newline="\n")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def main() -> None:
    args = parse_args()
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    records = select_records(load_records(args.data), args.ids)
    specs = select_models(args.models)
    print(
        f"run: {run_id}  records: {len(records)}  models: {len(specs)}  "
        f"calls: {len(records) * len(specs)}"
    )

    if args.preflight_only:
        run_preflight(specs, args, run_id)
        return

    started_at = datetime.now(timezone.utc).isoformat()
    if args.skip_preflight:
        preflight = load_preflight(args.preflight_json, specs, args)
    else:
        preflight = run_preflight(specs, args, run_id)

    tasks = build_tasks(specs, records, preflight, args)
    client = LLMClient(
        max_attempts=1,
        timeout=(args.connect_timeout_seconds, args.timeout_seconds),
        provider_concurrency={
            provider: args.provider_concurrency for provider in PROVIDERS
        },
    )
    rows = run_rounds(client, tasks, specs, records, args, run_id)
    output = args.output or ROOT / "data" / f"eval_tier_probe_{run_id}.jsonl"
    summary_path = args.summary or output.with_name(output.stem + "_summary.json")
    write_jsonl(output, rows)
    summary = summarize(
        rows,
        specs,
        records,
        preflight,
        args,
        run_id,
        started_at,
    )
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    write_report(args.report, summary)
    print_summary(summary)
    print(f"wrote: {output}")
    print(f"wrote: {summary_path}")
    print(f"wrote: {args.report}")


if __name__ == "__main__":
    main()
