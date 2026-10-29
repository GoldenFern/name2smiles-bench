"""Run the 100-record mini set across the eight registered models.

The runner keeps five workers per model, appends every completed row to JSONL
immediately, and supports resuming from the same output file. HTTP 429 and 503
responses are put back into the model queue with an exponential delay. A
40-minute read timeout is a terminal failure.

Examples:
    python scripts/eval_mini_batch.py
    python scripts/eval_mini_batch.py --resume --output data/eval_mini_100.jsonl
"""

from __future__ import annotations

import argparse
import itertools
import json
import queue
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from name2smiles.llm import (  # noqa: E402
    LLMClient,
    PROVIDERS,
    resolve_model,
)
from eval_tier_probe import (  # noqa: E402
    DEFAULT_MODELS,
    TIER_ORDER,
    attempt_record,
    build_row,
    run_task,
    summarize,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data",
        type=Path,
        default=ROOT / "data" / "mini_100.jsonl",
    )
    parser.add_argument("--ids", default="", help="optional comma-separated IDs")
    parser.add_argument("--models", default=",".join(DEFAULT_MODELS))
    parser.add_argument(
        "--reasoning",
        default="high",
        choices=["default", "none", "low", "high", "max"],
    )
    parser.add_argument("--max-tokens", type=int, default=100_000)
    parser.add_argument("--connect-timeout-seconds", type=float, default=30.0)
    parser.add_argument("--timeout-seconds", type=float, default=2400.0)
    parser.add_argument("--workers-per-model", type=int, default=5)
    parser.add_argument("--max-attempts", type=int, default=5)
    parser.add_argument("--retry-delay", type=float, default=30.0)
    parser.add_argument("--retry-delay-max", type=float, default=600.0)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument(
        "--retry-failed",
        action="store_true",
        help="when resuming, retry rows that ended in failure",
    )
    parser.add_argument("--preflight-json", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--summary", type=Path, default=None)
    parser.add_argument(
        "--report",
        type=Path,
        default=ROOT / "docs" / "eval_mini_100.md",
    )
    return parser.parse_args()


def load_records(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle]


def select_records(records: list[dict[str, Any]], ids: str) -> list[dict[str, Any]]:
    if not ids.strip():
        return records
    wanted = [value.strip() for value in ids.split(",") if value.strip()]
    by_id = {record["id"]: record for record in records}
    missing = [record_id for record_id in wanted if record_id not in by_id]
    if missing:
        raise SystemExit(f"unknown dataset IDs: {', '.join(missing)}")
    return [by_id[record_id] for record_id in wanted]


def select_models(values: str) -> list[Any]:
    models = [
        resolve_model(value.strip()) for value in values.split(",") if value.strip()
    ]
    if not models:
        raise SystemExit("no models selected")
    return models


def read_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def latest_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    latest: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        key = (row["model_key"], row["record_id"])
        latest[key] = row
    return list(latest.values())


def load_done(rows: list[dict[str, Any]], retry_failed: bool) -> set[tuple[str, str]]:
    done: set[tuple[str, str]] = set()
    for row in rows:
        if retry_failed and not row.get("ok"):
            continue
        done.add((row["model_key"], row["record_id"]))
    return done


def preflight_caps(
    path: Path | None,
    specs: list[Any],
    max_tokens: int,
) -> dict[str, int]:
    if path is None:
        path = ROOT / "data" / "eval_tier_probe_preflight.json"
    caps = {spec.key: max_tokens for spec in specs}
    if not path.exists():
        print(f"preflight not found, using {max_tokens}: {path}")
        return caps
    payload = json.loads(path.read_text(encoding="utf-8"))
    for result in payload.get("results", []):
        if result.get("ok") and result.get("effective_max_tokens"):
            caps[result["model_key"]] = int(result["effective_max_tokens"])
    print(f"loaded preflight: {path}")
    return caps


def write_row(
    handle: Any,
    lock: threading.Lock,
    row: dict[str, Any],
) -> None:
    with lock:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        handle.flush()


def run_batch(
    client: LLMClient,
    specs: list[Any],
    records: list[dict[str, Any]],
    caps: dict[str, int],
    args: argparse.Namespace,
    run_id: str,
    output: Path,
    done: set[tuple[str, str]],
) -> int:
    pending = [
        (spec, record)
        for spec in specs
        for record in records
        if (spec.key, record["id"]) not in done
    ]
    if not pending:
        print("nothing to do")
        return 0

    queues: dict[str, queue.PriorityQueue] = {
        spec.key: queue.PriorityQueue() for spec in specs
    }
    sequence = itertools.count()
    for spec, record in pending:
        task = {
            "spec": spec,
            "record": record,
            "max_tokens": caps.get(spec.key, args.max_tokens),
            "round": 1,
            "requeues": 0,
            "history": [],
        }
        queues[spec.key].put((0.0, next(sequence), task))

    total = len(pending)
    completed = 0
    completed_lock = threading.Lock()
    done_event = threading.Event()
    print_lock = threading.Lock()
    output.parent.mkdir(parents=True, exist_ok=True)
    handle = output.open("a", encoding="utf-8", newline="\n")

    def worker(spec: Any) -> None:
        nonlocal completed
        model_queue = queues[spec.key]
        while not done_event.is_set():
            try:
                ready_at, _, task = model_queue.get(timeout=1.0)
            except queue.Empty:
                continue
            delay = ready_at - time.time()
            if delay > 0:
                time.sleep(delay)
            result = run_task(
                client,
                task,
                None if args.reasoning in {"default", "none"} else args.reasoning,
            )
            if result["retryable"] and task["requeues"] < args.max_attempts - 1:
                task["history"].append(attempt_record(task["requeues"] + 1, result))
                task["requeues"] += 1
                retry_delay = min(
                    args.retry_delay * (2 ** (task["requeues"] - 1)),
                    args.retry_delay_max,
                )
                model_queue.put((time.time() + retry_delay, next(sequence), task))
                with print_lock:
                    print(
                        f"  RETRY {spec.key:<24} {task['record']['id']} "
                        f"status={result.get('status')} "
                        f"attempt={task['requeues'] + 1} "
                        f"wait={retry_delay:.0f}s",
                        flush=True,
                    )
                continue

            row = build_row(
                run_id,
                task,
                result,
                task["requeues"] + 1,
                args.reasoning,
            )
            write_row(handle, completed_lock, row)
            with completed_lock:
                completed += 1
                current = completed
            with print_lock:
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
                    f"[{len(done) + current}/{len(done) + total}] "
                    f"{spec.key:<24} {task['record']['id']} "
                    f"{status:<8} in={usage.get('input_tokens')} "
                    f"out={usage.get('output_tokens')} "
                    f"{(row['latency_ms'] or 0) / 1000:5.1f}s",
                    flush=True,
                )
            if current >= total:
                done_event.set()

    threads = [
        threading.Thread(target=worker, args=(spec,), daemon=True)
        for spec in specs
        for _ in range(max(1, args.workers_per_model))
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    handle.close()
    return len(pending)


def summarize_batch(
    rows: list[dict[str, Any]],
    specs: list[Any],
    records: list[dict[str, Any]],
    preflight: dict[str, Any],
    args: argparse.Namespace,
    run_id: str,
    started_at: str,
) -> dict[str, Any]:
    summarize_args = SimpleNamespace(
        data=args.data,
        reasoning=args.reasoning,
        max_tokens=args.max_tokens,
        timeout_seconds=args.timeout_seconds,
        connect_timeout_seconds=args.connect_timeout_seconds,
        global_concurrency=args.workers_per_model * len(specs),
        provider_concurrency=args.workers_per_model,
        max_rounds=args.max_attempts,
        round_delay=args.retry_delay,
    )
    summary = summarize(
        rows,
        specs,
        records,
        preflight,
        summarize_args,
        run_id,
        started_at,
    )
    summary["settings"].update(
        {
            "workers_per_model": args.workers_per_model,
            "max_attempts": args.max_attempts,
            "retry_delay_seconds": args.retry_delay,
            "retry_delay_max_seconds": args.retry_delay_max,
            "pricing_window": "off-peak",
            "resume": args.resume,
            "retry_failed": args.retry_failed,
        }
    )
    summary["failures"] = [
        {
            "model_key": row["model_key"],
            "tier": row["tier"],
            "record_id": row["record_id"],
            "status": row["status"],
            "error": row["error"],
            "latency_ms": row["latency_ms"],
        }
        for row in rows
        if not row["ok"]
    ]
    return summary


def format_rate(value: float | None) -> str:
    return f"{value * 100:.1f}%" if value is not None else "-"


def print_summary(summary: dict[str, Any]) -> None:
    print("\nSummary")
    print(
        f"{'model':<24} {'ok':>6} {'valid':>7} {'exact':>7} {'conn':>7} "
        f"{'inchikey':>9} {'tanimoto':>8} {'in_tok':>8} {'out_tok':>9} "
        f"{'cost':>9}"
    )
    print("-" * 121)
    for key, row in summary["models"].items():
        print(
            f"{key:<24} {row['ok']:>3}/{row['n']:<2} "
            f"{format_rate(row['valid_rate']):>7} "
            f"{format_rate(row['exact_rate']):>7} "
            f"{format_rate(row['connectivity_rate']):>7} "
            f"{format_rate(row['inchikey_rate']):>9} "
            f"{(row['mean_tanimoto'] or 0):>8.3f} "
            f"{row['input_tokens_mean'] or 0:>8.1f} "
            f"{row['output_tokens_mean'] or 0:>9.1f} "
            f"{row['total_cost_cny']:>9.4f}"
        )
    print("-" * 121)
    total_cost = sum(row["total_cost_cny"] for row in summary["models"].values())
    print(f"total cost: {total_cost:.4f} CNY")


def write_report(path: Path, summary: dict[str, Any]) -> None:
    settings = summary["settings"]
    lines: list[str] = [
        "# Mini 100 Batch",
        "",
        f"Run: `{summary['run_id']}`",
        "",
        "The 100-record mini set, eight models, one prompt per record. "
        "Correctness rates use all records as the denominator.",
        "",
        "## Settings",
        "",
        f"- Reasoning: `{settings['reasoning']}`",
        f"- Max output tokens: `{settings['max_tokens']}`",
        f"- Timeout: `{settings['timeout_seconds']}` s "
        f"(connect `{settings['connect_timeout_seconds']}` s)",
        f"- Workers per model: `{settings['workers_per_model']}`",
        f"- Max attempts: `{settings['max_attempts']}`, retry status: "
        f"`{settings['retry_status']}`",
        f"- Retry delay: `{settings['retry_delay_seconds']}` s, cap "
        f"`{settings['retry_delay_max_seconds']}` s",
        f"- Pricing window: `{settings['pricing_window']}`",
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
        "| Model | ok | valid | exact | connectivity | inchikey | "
        "Tanimoto | Input tok (mean) | Output tok (mean) | Cost CNY | "
        "Mean latency |",
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
            f"{row['total_cost_cny']:.4f} | "
            f"{(row['mean_latency_ms'] or 0) / 1000:.1f}s |"
        )

    tier_sizes = {
        tier: summary["models"][next(iter(summary["models"]))]["tiers"][tier]["n"]
        for tier in TIER_ORDER
    }
    lines += [
        "",
        "## Correctness by tier",
        "",
        "Cells are `exact/connectivity` counts. The denominator for each "
        "tier is shown in the header. Failed calls count as 0/0.",
        "",
        "| Model | "
        + " | ".join(f"{tier} ({tier_sizes[tier]})" for tier in TIER_ORDER)
        + " |",
        "|---|" + "|".join("---:" for _ in TIER_ORDER) + "|",
    ]
    for key, row in summary["models"].items():
        cells = [
            f"{row['tiers'][tier]['exact']}/{row['tiers'][tier]['connectivity']}"
            for tier in TIER_ORDER
        ]
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
        "## Failures and timeouts",
        "",
    ]
    if summary["failures"]:
        lines += [
            "| Model | Tier | Record | Status | Latency | Error |",
            "|---|---|---|---:|---:|---|",
        ]
        for failure in summary["failures"]:
            error = (failure.get("error") or "").replace("|", "\\|")[:180]
            lines.append(
                f"| {failure['model_key']} | {failure['tier']} | "
                f"{failure['record_id']} | {failure['status']} | "
                f"{(failure.get('latency_ms') or 0) / 1000:.1f}s | "
                f"{error} |"
            )
    else:
        lines.append("No failed calls.")
    lines += [
        "",
        "## Notes",
        "",
        "- Five workers run per model. A 40-minute read timeout is a terminal "
        "failure.",
        "- HTTP 429 and 503 responses are re-queued for the same model with "
        "an exponential delay.",
        "- Each row is appended and flushed immediately. Resume with the same "
        "output file; completed rows, including failures, are skipped by "
        "default.",
        "- Full model text, reasoning, token usage, and per-attempt history "
        "are in the JSONL output.",
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8", newline="\n")


def main() -> None:
    args = parse_args()
    records = select_records(load_records(args.data), args.ids)
    specs = select_models(args.models)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output = args.output or ROOT / "data" / f"eval_mini_100_{run_id}.jsonl"
    if output.exists() and not args.resume:
        raise SystemExit(
            f"output exists: {output}; use --resume or choose another --output"
        )
    existing = read_rows(output)
    done = load_done(existing, args.retry_failed)
    if existing:
        run_id = existing[0].get("run_id", run_id)
    caps = preflight_caps(args.preflight_json, specs, args.max_tokens)
    preflight_path = args.preflight_json or (
        ROOT / "data" / "eval_tier_probe_preflight.json"
    )
    preflight = (
        json.loads(preflight_path.read_text(encoding="utf-8"))
        if preflight_path.exists()
        else {"results": []}
    )

    total = len(specs) * len(records)
    print(
        f"run: {run_id}  records: {len(records)}  models: {len(specs)}  "
        f"calls: {total}  already done: {len(done)}"
    )
    print(
        f"output: {output}  workers/model: {args.workers_per_model}  "
        f"timeout: {args.timeout_seconds}s  max_tokens: {args.max_tokens}"
    )

    client = LLMClient(
        max_attempts=1,
        timeout=(args.connect_timeout_seconds, args.timeout_seconds),
        provider_concurrency={
            provider: args.workers_per_model for provider in PROVIDERS
        },
    )
    started_at = datetime.now(timezone.utc).isoformat()
    run_batch(
        client,
        specs,
        records,
        caps,
        args,
        run_id,
        output,
        done,
    )

    rows = latest_rows(read_rows(output))
    summary = summarize_batch(
        rows,
        specs,
        records,
        preflight,
        args,
        run_id,
        started_at,
    )
    summary_path = args.summary or output.with_name(output.stem + "_summary.json")
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
