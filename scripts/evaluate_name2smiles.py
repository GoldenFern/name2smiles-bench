"""Run a small name-to-SMILES pilot and score predictions with RDKit.

The pilot uses a fixed set of 10 records and a fixed set of low-cost models.
It writes one JSONL row per model/record pair and a summary JSON file.

Example:
    python scripts/evaluate_name2smiles.py --pilot --workers 6
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from rdkit import Chem, DataStructs, RDLogger
from rdkit.Chem import AllChem

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from name2smiles.llm import (  # noqa: E402
    LLMClient,
    LLMError,
    ModelSpec,
    estimate_cost,
    resolve_model,
)

RDLogger.DisableLog("rdApp.*")

SYSTEM_PROMPT = """You are a chemistry expert. Convert the given molecule name to one valid SMILES string.
Return only the SMILES. Do not explain, do not use Markdown, and do not use code fences.
If the name describes a salt or a multi-component system, include every component separated by a dot."""

PILOT_MODELS: tuple[str, ...] = (
    "deepseek-flash",
    "glm-5.3-flash",
    "minimax-m3.1-flash",
    "mimo-v2.6-flash",
    "qwen3.8-flash",
    "gemini-3.8-flash",
    "claude-haiku-5.5",
    "gpt-6.1-terra",
    "longcat-2.5-preview",
)

PILOT_IDS: tuple[str, ...] = (
    "N2S-000652",
    "N2S-000637",
    "N2S-000824",
    "N2S-000514",
    "N2S-000696",
    "N2S-000225",
    "N2S-000624",
    "N2S-001385",
    "N2S-000835",
    "N2S-000311",
)

_PREFIX_RE = re.compile(
    r"^(?:canonical\s+|isomeric\s+)?smiles\s*[:=]\s*", re.IGNORECASE
)
_FENCE_RE = re.compile(r"```(?:smiles)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)
_STOPWORDS = {
    "answer",
    "are",
    "and",
    "is",
    "it",
    "no",
    "none",
    "not",
    "null",
    "smiles",
    "that",
    "the",
    "this",
    "to",
    "unknown",
    "yes",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data",
        type=Path,
        default=ROOT / "data" / "benchmark_v0.jsonl",
    )
    parser.add_argument(
        "--pilot",
        action="store_true",
        help="use the fixed pilot models and 10-record set",
    )
    parser.add_argument(
        "--models",
        default="",
        help="comma-separated model keys; overrides --pilot models",
    )
    parser.add_argument(
        "--ids",
        default="",
        help="comma-separated dataset IDs; overrides --pilot records",
    )
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="randomly sample records when --ids is not set",
    )
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument(
        "--reasoning",
        default="low",
        choices=["default", "none", "low", "high", "max"],
        help="reasoning level; default/none sends no reasoning body",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=None,
        help="output cap; default: model registry value",
    )
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--summary", type=Path, default=None)
    return parser.parse_args()


def load_records(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle]


def select_models(args: argparse.Namespace) -> list[ModelSpec]:
    if args.models:
        return [resolve_model(name) for name in args.models.split(",") if name.strip()]
    if args.pilot:
        return [resolve_model(name) for name in PILOT_MODELS]
    raise SystemExit("specify --models or --pilot")


def select_records(
    records: list[dict[str, Any]], args: argparse.Namespace
) -> list[dict[str, Any]]:
    if args.ids:
        wanted = [value.strip() for value in args.ids.split(",") if value.strip()]
    elif args.pilot:
        wanted = list(PILOT_IDS)
    else:
        wanted = []

    if wanted:
        by_id = {record["id"]: record for record in records}
        missing = [record_id for record_id in wanted if record_id not in by_id]
        if missing:
            raise SystemExit(f"unknown dataset IDs: {', '.join(missing)}")
        return [by_id[record_id] for record_id in wanted]

    if args.limit <= 0:
        raise SystemExit("--limit must be positive")
    pool = records[args.offset :]
    if args.seed is not None:
        if len(pool) < args.limit:
            raise SystemExit("not enough records for the requested sample")
        return random.Random(args.seed).sample(pool, args.limit)
    selected = pool[: args.limit]
    if len(selected) < args.limit:
        raise SystemExit("not enough records for the requested limit")
    return selected


def run_one(
    client: LLMClient,
    spec: ModelSpec,
    record: dict[str, Any],
    max_tokens: int | None,
    reasoning: str | None,
) -> dict[str, Any]:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"Name: {record['name']}\nSMILES:",
        },
    ]
    try:
        result = client.chat(
            spec,
            messages,
            max_tokens=max_tokens,
            reasoning=reasoning,
        )
    except LLMError as exc:
        return {
            "ok": False,
            "error": str(exc),
            "status": exc.status,
            "attempts": exc.attempts,
        }
    except Exception as exc:  # noqa: BLE001 - the pilot reports any failure
        return {
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}",
            "status": None,
            "attempts": None,
        }

    predicted = extract_smiles(result.text)
    scores = score_prediction(predicted, record)
    try:
        cost = estimate_cost(spec.key, result.usage).total_cost
    except KeyError:
        cost = None
    return {
        "ok": True,
        "result": result,
        "predicted_smiles": predicted,
        "scores": scores,
        "cost_cny": cost,
    }


def extract_smiles(text: str) -> str | None:
    """Extract the first RDKit-parseable SMILES-like token from a reply."""
    if not text:
        return None
    candidates: list[str] = []
    for block in _FENCE_RE.findall(text):
        candidates.extend(_line_candidates(block))
    candidates.extend(_line_candidates(text))
    for match in re.finditer(
        r"(?:canonical\s+|isomeric\s+)?smiles\s*[:=]\s*([^\s`]+)",
        text,
        flags=re.IGNORECASE,
    ):
        candidates.append(match.group(1))

    seen: set[str] = set()
    fallback: str | None = None
    for candidate in candidates:
        for variant in _variants(candidate):
            if variant in seen:
                continue
            seen.add(variant)
            if not _looks_like_smiles(variant):
                continue
            if Chem.MolFromSmiles(variant) is not None:
                return variant
            if fallback is None:
                fallback = variant
    return fallback


def _line_candidates(text: str) -> list[str]:
    result: list[str] = []
    for line in text.splitlines():
        value = line.strip().strip("`*_ ")
        value = _PREFIX_RE.sub("", value).strip().strip("`*_ ")
        if value:
            result.append(value)
    return result


def _variants(candidate: str) -> list[str]:
    base = candidate.strip().strip("`*_ ")
    values = [base]
    trimmed = base.rstrip(".,;:")
    if trimmed != base:
        values.append(trimmed)
    no_spaces = trimmed.replace(" ", "")
    if no_spaces != trimmed:
        values.append(no_spaces)
    first = trimmed.split()[0] if trimmed.split() else ""
    first = first.strip(".,;:")
    if first and first != trimmed:
        values.append(first)
    return values


def _looks_like_smiles(value: str) -> bool:
    if not (2 <= len(value) <= 1000):
        return False
    if value.casefold() in _STOPWORDS:
        return False
    if not re.search(r"[A-Za-z]", value):
        return False
    if not re.search(r"[BCNOPSFIbcnopsfi\[\]\(\)=#@+\-0-9]", value):
        return False
    if " " in value and not re.fullmatch(
        r"[A-Za-z0-9\[\]\(\)=#@+\-.,;:/*\\%]+", value
    ):
        return False
    return True


def score_prediction(
    predicted: str | None, record: dict[str, Any]
) -> dict[str, Any]:
    scores: dict[str, Any] = {
        "valid": False,
        "exact": False,
        "connectivity": False,
        "inchikey": False,
        "inchikey_skeleton": False,
        "tanimoto": 0.0,
    }
    if not predicted:
        return scores
    pred_mol = Chem.MolFromSmiles(predicted)
    if pred_mol is None:
        return scores
    ref_mol = Chem.MolFromSmiles(record["canonical_smiles"])
    if ref_mol is None:
        return scores

    scores["valid"] = True
    pred_isomeric = Chem.MolToSmiles(pred_mol, isomericSmiles=True)
    pred_connectivity = Chem.MolToSmiles(pred_mol, isomericSmiles=False)
    scores["exact"] = pred_isomeric == record["canonical_smiles"]
    scores["connectivity"] = pred_connectivity == record["connectivity_smiles"]

    try:
        pred_key = Chem.MolToInchiKey(pred_mol)
        ref_key = record["inchikey"]
        scores["inchikey"] = pred_key == ref_key
        scores["inchikey_skeleton"] = pred_key[:14] == ref_key[:14]
    except Exception:  # noqa: BLE001 - InChI can fail on unusual structures
        pass

    try:
        ref_fp = AllChem.GetMorganFingerprintAsBitVect(ref_mol, 2, nBits=2048)
        pred_fp = AllChem.GetMorganFingerprintAsBitVect(pred_mol, 2, nBits=2048)
        scores["tanimoto"] = round(
            DataStructs.TanimotoSimilarity(ref_fp, pred_fp), 4
        )
    except Exception:  # noqa: BLE001 - fingerprints can fail on unusual structures
        pass
    return scores


def format_percent(value: float) -> str:
    return f"{value * 100:.1f}%"


def summarize(
    rows: list[dict[str, Any]],
    specs: list[ModelSpec],
    records: list[dict[str, Any]],
) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for spec in specs:
        model_rows = [row for row in rows if row["model_key"] == spec.key]
        n = len(model_rows)
        if n == 0:
            continue
        ok_rows = [row for row in model_rows if row["ok"]]
        valid = sum(row["scores"]["valid"] for row in ok_rows)
        exact = sum(row["scores"]["exact"] for row in ok_rows)
        connectivity = sum(row["scores"]["connectivity"] for row in ok_rows)
        inchikey = sum(row["scores"]["inchikey"] for row in ok_rows)
        skeleton = sum(row["scores"]["inchikey_skeleton"] for row in ok_rows)
        tanimoto_values = [
            row["scores"]["tanimoto"] for row in ok_rows if row["scores"]["valid"]
        ]
        costs = [row["cost_cny"] for row in ok_rows if row["cost_cny"] is not None]
        latencies = [row["result"].latency_ms for row in ok_rows]
        summary[spec.key] = {
            "model_id": spec.model_id,
            "provider": spec.provider,
            "n": n,
            "ok": len(ok_rows),
            "errors": n - len(ok_rows),
            "valid": valid,
            "exact": exact,
            "connectivity": connectivity,
            "inchikey": inchikey,
            "inchikey_skeleton": skeleton,
            "valid_rate": valid / n,
            "exact_rate": exact / n,
            "connectivity_rate": connectivity / n,
            "inchikey_rate": inchikey / n,
            "inchikey_skeleton_rate": skeleton / n,
            "mean_tanimoto": (
                round(sum(tanimoto_values) / len(tanimoto_values), 4)
                if tanimoto_values
                else 0.0
            ),
            "total_cost_cny": round(sum(costs), 6),
            "mean_latency_ms": (
                round(sum(latencies) / len(latencies), 1) if latencies else None
            ),
        }
    return {
        "records": [record["id"] for record in records],
        "models": summary,
    }


def print_summary(summary: dict[str, Any]) -> None:
    print()
    print(
        f"{'model':<22} {'ok':>5} {'valid':>7} {'exact':>7} "
        f"{'conn':>7} {'inchikey':>8} {'tanimoto':>8} {'cost':>8}"
    )
    print("-" * 88)
    total_cost = 0.0
    for key, row in summary["models"].items():
        total_cost += row["total_cost_cny"]
        print(
            f"{key:<22} {row['ok']:>2}/{row['n']:<2} "
            f"{format_percent(row['valid_rate']):>7} "
            f"{format_percent(row['exact_rate']):>7} "
            f"{format_percent(row['connectivity_rate']):>7} "
            f"{format_percent(row['inchikey_rate']):>8} "
            f"{row['mean_tanimoto']:>8.3f} "
            f"{row['total_cost_cny']:>8.4f}"
        )
    print("-" * 88)
    print(f"total cost: {total_cost:.4f} CNY")


def main() -> None:
    args = parse_args()
    records = select_records(load_records(args.data), args)
    specs = select_models(args)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output = args.output or ROOT / "data" / f"eval_pilot_{timestamp}.jsonl"
    summary_path = args.summary or output.with_name(
        output.stem + "_summary.json"
    )
    output.parent.mkdir(parents=True, exist_ok=True)

    client = LLMClient()
    tasks = [
        (index, spec, record)
        for index, (spec, record) in enumerate(
            ((spec, record) for spec in specs for record in records),
            start=1,
        )
    ]
    total = len(tasks)
    print(
        f"models: {len(specs)}  records: {len(records)}  calls: {total}  "
        f"workers: {max(1, min(args.workers, total))}  reasoning: {args.reasoning}"
    )

    rows: list[dict[str, Any]] = []
    partial_path = output.with_name(output.stem + ".partial.jsonl")
    partial_path.write_text("", encoding="utf-8", newline="\n")
    with ThreadPoolExecutor(max_workers=max(1, min(args.workers, total))) as executor:
        futures = {
            executor.submit(
                run_one,
                client,
                spec,
                record,
                args.max_tokens,
                None if args.reasoning in {"default", "none"} else args.reasoning,
            ): (index, spec, record)
            for index, spec, record in tasks
        }
        for future in as_completed(futures):
            index, spec, record = futures[future]
            row = future.result()
            row.update(
                {
                    "run_id": timestamp,
                    "model_key": spec.key,
                    "model_id": spec.model_id,
                    "provider": spec.provider,
                    "record_id": record["id"],
                    "name": record["name"],
                    "reference_smiles": record["canonical_smiles"],
                    "reference_inchikey": record["inchikey"],
                    "reasoning_level": args.reasoning,
                }
            )
            rows.append(row)
            with partial_path.open("a", encoding="utf-8", newline="\n") as partial:
                partial.write(json.dumps(row_to_dict(row), ensure_ascii=False) + "\n")
            if row["ok"]:
                result = row["result"]
                predicted = row["predicted_smiles"] or "(no parse)"
                status = "EXACT" if row["scores"]["exact"] else (
                    "CONN" if row["scores"]["connectivity"] else (
                        "VALID" if row["scores"]["valid"] else "INVALID"
                    )
                )
                print(
                    f"[{index:>3}/{total}] {spec.key:<22} {record['id']} "
                    f"{status:<7} {result.latency_ms / 1000:5.1f}s  "
                    f"fin={result.finish_reason or '-'} "
                    f"out={result.usage.output_tokens or 0}  "
                    f"{predicted[:60]}",
                    flush=True,
                )
            else:
                print(
                    f"[{index:>3}/{total}] {spec.key:<22} {record['id']} "
                    f"FAIL    {row['error'][:100]}",
                    flush=True,
                )

    rows.sort(key=lambda row: (row["model_key"], row["record_id"]))
    with output.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row_to_dict(row), ensure_ascii=False) + "\n")

    summary = summarize(rows, specs, records)
    summary["run_id"] = timestamp
    summary["data"] = str(args.data)
    summary["output"] = str(output)
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    partial_path.unlink(missing_ok=True)
    print_summary(summary)
    print(f"wrote: {output}")
    print(f"wrote: {summary_path}")


def row_to_dict(row: dict[str, Any]) -> dict[str, Any]:
    data: dict[str, Any] = {
        "run_id": row["run_id"],
        "model_key": row["model_key"],
        "model_id": row["model_id"],
        "provider": row["provider"],
        "record_id": row["record_id"],
        "name": row["name"],
        "reference_smiles": row["reference_smiles"],
        "reference_inchikey": row["reference_inchikey"],
        "reasoning_level": row["reasoning_level"],
        "ok": row["ok"],
    }
    if row["ok"]:
        result = row["result"]
        data.update(
            {
                "predicted_smiles": row["predicted_smiles"],
                "raw_text": result.text,
                "reasoning": result.reasoning,
                "finish_reason": result.finish_reason,
                "latency_ms": result.latency_ms,
                "attempts": result.attempts,
                "usage": result.usage.to_dict(),
                "cost_cny": row["cost_cny"],
                **row["scores"],
            }
        )
    else:
        data.update(
            {
                "error": row["error"],
                "status": row["status"],
                "attempts": row["attempts"],
            }
        )
    return data


if __name__ == "__main__":
    main()
