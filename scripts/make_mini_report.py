"""Build the mini-100 summary tables and result figures.

The script reads the deduplicated JSONL produced by ``eval_mini_batch.py`` and
writes a machine-readable summary, a metrics CSV, and four figures. Model icons
are taken from ``docs/figures/eval_mini_100/icons``; the SVG sources live in
``assets/icons``.

Examples:
    python scripts/make_mini_report.py
    python scripts/make_mini_report.py --data data/run.jsonl --out docs/figures
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.lines import Line2D
from matplotlib.offsetbox import AnnotationBbox, OffsetImage
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA = ROOT / "data" / "eval_mini_100_20261028T231806" / "dedup.jsonl"
DEFAULT_OUT = ROOT / "docs" / "figures" / "eval_mini_100"
DEFAULT_SUMMARY = ROOT / "data" / "eval_mini_100_20261028T231806" / "summary.json"
DEFAULT_CSV = ROOT / "data" / "eval_mini_100_20261028T231806" / "metrics.csv"

TIER_ORDER = ["L1", "L2", "L3", "L4", "L5"]
TIER_SIZES = {"L1": 25, "L2": 30, "L3": 20, "L4": 15, "L5": 10}

# Display order and matching icon file. The icon set has no MiMo mark, so the
# Xiaomi parent-brand icon is used for MiMo.
MODEL_ORDER = [
    "claude-haiku-5.5",
    "deepseek-flash",
    "minimax-m3.1-flash",
    "gemini-3.8-flash",
    "gpt-6.1-terra",
    "glm-5.3-flash",
    "longcat-2.5-preview",
    "mimo-v2.6-flash",
]
ICON_FILES = {
    "claude-haiku-5.5": "claude.png",
    "deepseek-flash": "deepseek.png",
    "minimax-m3.1-flash": "minimax.png",
    "gemini-3.8-flash": "gemini.png",
    "gpt-6.1-terra": "openai.png",
    "glm-5.3-flash": "zhipu.png",
    "longcat-2.5-preview": "longcat.png",
    "mimo-v2.6-flash": "xiaomi.png",
}

ACCENT = "#3D5AFE"
INK = "#0F172A"
MUTED = "#64748B"
GRID = "#E2E8F0"
TRACK = "#EEF2F7"
AMBER = "#F59E0B"
DARK_BLUE = "#1E3A8A"
LIGHT_BLUE = "#93C5FD"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    parser.add_argument(
        "--icons",
        type=Path,
        default=DEFAULT_OUT / "icons",
        help="directory with rendered model icons",
    )
    return parser.parse_args()


def load_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def build_frame(rows: list[dict[str, Any]]) -> pd.DataFrame:
    records: list[dict[str, Any]] = []
    for row in rows:
        usage = row.get("usage") or {}
        output_tokens = int(usage.get("output_tokens") or 0)
        reasoning_tokens = int(usage.get("reasoning_tokens") or 0)
        records.append(
            {
                "model_key": row["model_key"],
                "display_name": row["display_name"],
                "record_id": row["record_id"],
                "tier": row["tier"],
                "reasoning_level": row.get("reasoning_level"),
                "max_tokens": row.get("max_tokens"),
                "ok": bool(row.get("ok")),
                "valid": bool(row.get("valid")),
                "exact": bool(row.get("exact")),
                "connectivity": bool(row.get("connectivity")),
                "inchikey": bool(row.get("inchikey")),
                "tanimoto": float(row.get("tanimoto") or 0.0),
                "input_tokens": int(usage.get("input_tokens") or 0),
                "output_tokens": output_tokens,
                "reasoning_tokens": reasoning_tokens,
                "answer_tokens": max(0, output_tokens - reasoning_tokens),
                "latency_ms": float(row.get("latency_ms") or 0.0),
                "cost_cny": float(row.get("cost_cny") or 0.0),
            }
        )
    frame = pd.DataFrame(records)
    if set(frame["model_key"]) != set(MODEL_ORDER):
        missing = set(MODEL_ORDER) - set(frame["model_key"])
        extra = set(frame["model_key"]) - set(MODEL_ORDER)
        raise SystemExit(f"model mismatch; missing={missing}, extra={extra}")
    return frame


def summarize(frame: pd.DataFrame, source: Path | None = None) -> dict[str, Any]:
    models: dict[str, Any] = {}
    for key in MODEL_ORDER:
        part = frame[frame["model_key"] == key]
        n = len(part)
        exact_n = int(part["exact"].sum())
        valid_n = int(part["valid"].sum())
        cost = float(part["cost_cny"].sum())
        tiers: dict[str, Any] = {}
        for tier in TIER_ORDER:
            tier_part = part[part["tier"] == tier]
            tiers[tier] = {
                "n": len(tier_part),
                "exact": int(tier_part["exact"].sum()),
                "connectivity": int(tier_part["connectivity"].sum()),
                "valid": int(tier_part["valid"].sum()),
                "exact_rate": round(
                    float(tier_part["exact"].mean()) if len(tier_part) else 0.0,
                    4,
                ),
            }
        models[key] = {
            "display_name": part["display_name"].iloc[0],
            "n": n,
            "ok": int(part["ok"].sum()),
            "valid": valid_n,
            "valid_rate": round(valid_n / n, 4) if n else 0.0,
            "exact": exact_n,
            "exact_rate": round(exact_n / n, 4) if n else 0.0,
            "connectivity": int(part["connectivity"].sum()),
            "connectivity_rate": round(
                float(part["connectivity"].mean()) if n else 0.0, 4
            ),
            "inchikey": int(part["inchikey"].sum()),
            "inchikey_rate": round(float(part["inchikey"].mean()) if n else 0.0, 4),
            "tanimoto_valid": round(
                float(part.loc[part["valid"], "tanimoto"].mean()) if valid_n else 0.0,
                4,
            ),
            "tanimoto_all": round(float(part["tanimoto"].mean()) if n else 0.0, 4),
            "input_tokens_sum": int(part["input_tokens"].sum()),
            "input_tokens_mean": (
                round(float(part["input_tokens"].mean()), 2) if n else 0.0
            ),
            "output_tokens_sum": int(part["output_tokens"].sum()),
            "output_tokens_mean": (
                round(float(part["output_tokens"].mean()), 2) if n else 0.0
            ),
            "reasoning_tokens_sum": int(part["reasoning_tokens"].sum()),
            "reasoning_tokens_mean": (
                round(float(part["reasoning_tokens"].mean()), 2) if n else 0.0
            ),
            "answer_tokens_sum": int(part["answer_tokens"].sum()),
            "answer_tokens_mean": (
                round(float(part["answer_tokens"].mean()), 2) if n else 0.0
            ),
            "total_cost_cny": round(cost, 6),
            "cost_per_100_cny": round(cost * 100 / n, 6) if n else 0.0,
            "cost_per_exact_100_cny": (
                round(cost * 100 / exact_n, 4) if exact_n else None
            ),
            "mean_latency_ms": round(float(part["latency_ms"].mean()), 2) if n else 0.0,
            "mean_latency_s": (
                round(float(part["latency_ms"].mean()) / 1000, 2) if n else 0.0
            ),
            "reasoning_levels": {
                str(k): int(v)
                for k, v in part["reasoning_level"].value_counts().items()
            },
            "tiers": tiers,
        }

    tier_totals: dict[str, Any] = {}
    for tier in TIER_ORDER:
        part = frame[frame["tier"] == tier]
        tier_totals[tier] = {
            "n": len(part),
            "exact": int(part["exact"].sum()),
            "exact_rate": round(float(part["exact"].mean()), 4) if len(part) else 0.0,
            "connectivity": int(part["connectivity"].sum()),
            "valid": int(part["valid"].sum()),
        }

    n_total = len(frame)
    exact_total = int(frame["exact"].sum())
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": (
            str(source.relative_to(ROOT)).replace("\\", "/")
            if source is not None and source.is_relative_to(ROOT)
            else str(source or DEFAULT_DATA)
        ),
        "models": models,
        "tiers": tier_totals,
        "totals": {
            "calls": n_total,
            "ok": int(frame["ok"].sum()),
            "valid": int(frame["valid"].sum()),
            "exact": exact_total,
            "exact_rate": round(exact_total / n_total, 4),
            "connectivity": int(frame["connectivity"].sum()),
            "connectivity_rate": round(float(frame["connectivity"].mean()), 4),
            "valid_rate": round(float(frame["valid"].mean()), 4),
            "cost_cny": round(float(frame["cost_cny"].sum()), 6),
        },
        "settings": {
            "reasoning": "high",
            "max_tokens": 100_000,
            "workers_per_model": 5,
            "timeout_seconds": 2400,
            "retry_timeout_seconds": 3600,
            "low_effort_retry": {
                "models": [
                    "glm-5.3-flash",
                    "longcat-2.5-preview",
                    "mimo-v2.6-flash",
                ],
                "rows": 42,
                "reasoning": "low",
                "max_tokens": 25_000,
                "timeout_seconds": 1200,
            },
            "pricing_window": "off-peak for DeepSeek",
        },
        "notes": [
            "Exact means canonical isomeric SMILES equality.",
            "Connectivity ignores stereochemistry.",
            "Tanimoto is the mean Morgan fingerprint similarity over valid answers; invalid answers would score 0.",
            "Cost covers completed calls at list prices. Failed attempts without usage are not priced.",
            "42 rows for GLM, LongCat, and MiMo were completed on a low-reasoning retry after high-effort timeouts.",
        ],
    }


def build_model_frame(summary: dict[str, Any]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for key in MODEL_ORDER:
        model = summary["models"][key]
        record: dict[str, Any] = {
            "model_key": key,
            "display_name": model["display_name"],
            "exact": model["exact"],
            "exact_rate": model["exact_rate"],
            "connectivity_rate": model["connectivity_rate"],
            "valid_rate": model["valid_rate"],
            "inchikey_rate": model["inchikey_rate"],
            "tanimoto_valid": model["tanimoto_valid"],
            "cost_per_100_cny": model["cost_per_100_cny"],
            "cost_per_exact_100_cny": model["cost_per_exact_100_cny"],
            "output_tokens_mean": model["output_tokens_mean"],
            "reasoning_tokens_mean": model["reasoning_tokens_mean"],
            "answer_tokens_mean": model["answer_tokens_mean"],
            "mean_latency_s": model["mean_latency_s"],
        }
        for tier in TIER_ORDER:
            tier_row = model["tiers"][tier]
            record[f"{tier}_exact"] = tier_row["exact"]
            record[f"{tier}_n"] = tier_row["n"]
            record[f"{tier}_rate"] = tier_row["exact_rate"]
        rows.append(record)
    return pd.DataFrame(rows)


def style() -> None:
    plt.rcParams.update(
        {
            "font.family": "Segoe UI",
            "font.size": 10,
            "axes.edgecolor": GRID,
            "axes.labelcolor": MUTED,
            "xtick.color": MUTED,
            "ytick.color": MUTED,
            "text.color": INK,
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "savefig.facecolor": "white",
        }
    )


@lru_cache(maxsize=32)
def load_icon(path: Path) -> Image.Image:
    image = Image.open(path).convert("RGBA")
    alpha = np.asarray(image)[..., 3]
    ys, xs = np.where(alpha > 8)
    if len(xs):
        image = image.crop(
            (int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1)
        )
    return image


def add_icon(
    ax: plt.Axes,
    icon: Image.Image,
    xy: tuple[float, float],
    *,
    zoom: float = 0.055,
    coords: str = "data",
    pad: float = 0.32,
) -> AnnotationBbox:
    box = AnnotationBbox(
        OffsetImage(icon, zoom=zoom),
        xy,
        xycoords=coords,
        frameon=True,
        bboxprops={
            "boxstyle": f"round,pad={pad},rounding_size=0.35",
            "facecolor": "white",
            "edgecolor": GRID,
            "linewidth": 0.8,
        },
        box_alignment=(0.5, 0.5),
        zorder=6,
    )
    ax.add_artist(box)
    return box


def icon_axis(
    fig: plt.Figure,
    grid: Any,
    frame: pd.DataFrame,
    icons: dict[str, Image.Image],
) -> tuple[plt.Axes, plt.Axes]:
    ax_names = fig.add_subplot(grid[0])
    ax = fig.add_subplot(grid[1], sharey=ax_names)
    n = len(frame)
    ys = np.arange(n)
    for y, row in zip(ys, frame.itertuples()):
        add_icon(ax_names, icons[row.model_key], (0.12, float(y)))
        ax_names.text(
            0.30,
            float(y),
            row.display_name,
            ha="left",
            va="center",
            fontsize=11.5,
            fontweight="bold",
            color=INK,
        )
    ax_names.set_xlim(0, 1)
    ax_names.set_ylim(n - 0.5, -0.5)
    ax_names.axis("off")
    ax.set_ylim(n - 0.5, -0.5)
    ax.set_yticks([])
    for spine in ("top", "right", "left"):
        ax.spines[spine].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(axis="x", length=0, pad=6)
    ax.grid(axis="x", color=GRID, linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)
    return ax_names, ax


def title_block(fig: plt.Figure, title: str, subtitle: str) -> None:
    fig.text(0.025, 0.945, title, fontsize=22, fontweight="bold", color=INK)
    fig.text(0.025, 0.898, subtitle, fontsize=10.5, color=MUTED)


def fig_leaderboard(
    frame: pd.DataFrame,
    icons: dict[str, Image.Image],
    path: Path,
) -> None:
    fig = plt.figure(figsize=(13.2, 7.0))
    grid = fig.add_gridspec(
        1,
        2,
        width_ratios=[3.15, 9.0],
        left=0.018,
        right=0.985,
        top=0.80,
        bottom=0.15,
        wspace=0.02,
    )
    _, ax = icon_axis(fig, (grid[0, 0], grid[0, 1]), frame, icons)
    n = len(frame)
    ys = np.arange(n)
    ax.set_xlim(0, 108)
    ax.set_xticks([0, 25, 50, 75, 100])
    ax.set_xticklabels(["0", "25", "50", "75", "100"])
    ax.set_xlabel("Exact-match rate (%)", fontsize=9, labelpad=8)
    for y, row in zip(ys, frame.itertuples()):
        ax.plot(
            [0, 100],
            [y, y],
            color=TRACK,
            lw=13,
            solid_capstyle="round",
            zorder=1,
        )
        ax.plot(
            [0, row.exact_rate * 100],
            [y, y],
            color=ACCENT,
            lw=13,
            solid_capstyle="round",
            zorder=2,
        )
        ax.scatter(
            [row.connectivity_rate * 100],
            [y],
            s=62,
            facecolor="white",
            edgecolor=INK,
            linewidth=1.2,
            zorder=4,
        )
        rate = row.exact_rate * 100
        if rate >= 12:
            ax.text(
                rate - 2.2,
                y,
                f"{rate:.0f}%",
                va="center",
                ha="right",
                fontsize=12.5,
                fontweight="bold",
                color="white",
                zorder=5,
            )
        else:
            ax.text(
                rate + 2.2,
                y,
                f"{rate:.0f}%",
                va="center",
                ha="left",
                fontsize=12.5,
                fontweight="bold",
                color=INK,
                zorder=5,
            )
    handles = [
        Line2D(
            [0],
            [0],
            color=ACCENT,
            lw=8,
            solid_capstyle="round",
            label="Exact match",
        ),
        Line2D(
            [0],
            [0],
            marker="o",
            color="none",
            markerfacecolor="white",
            markeredgecolor=INK,
            markeredgewidth=1.2,
            markersize=7,
            linestyle="none",
            label="Connectivity (stereo ignored)",
        ),
    ]
    ax.legend(
        handles=handles,
        loc="upper left",
        bbox_to_anchor=(0.0, -0.095),
        ncol=2,
        frameon=False,
        fontsize=9,
        handlelength=1.2,
        columnspacing=1.6,
    )
    title_block(
        fig,
        "Name-to-SMILES accuracy",
        "100 PubChem names · 8 models · one answer per name · RDKit canonical-SMILES match",
    )
    fig.text(
        0.985,
        0.905,
        "n = 100 per model",
        ha="right",
        fontsize=9,
        color=MUTED,
    )
    fig.text(
        0.025,
        0.035,
        "GLM, LongCat, and MiMo include 42 rows completed on a low-reasoning retry after high-effort timeouts.",
        fontsize=7.8,
        color=MUTED,
    )
    fig.savefig(path, dpi=220, bbox_inches="tight")
    plt.close(fig)


def fig_tiers(
    frame: pd.DataFrame,
    icons: dict[str, Image.Image],
    path: Path,
) -> None:
    fig = plt.figure(figsize=(12.8, 6.8))
    grid = fig.add_gridspec(
        1,
        2,
        width_ratios=[3.1, 9.0],
        left=0.018,
        right=0.93,
        top=0.76,
        bottom=0.18,
        wspace=0.02,
    )
    ax_names = fig.add_subplot(grid[0])
    ax = fig.add_subplot(grid[1])
    n = len(frame)
    ys = np.arange(n)
    for y, row in zip(ys, frame.itertuples()):
        add_icon(ax_names, icons[row.model_key], (0.12, float(y)))
        ax_names.text(
            0.30,
            float(y),
            row.display_name,
            ha="left",
            va="center",
            fontsize=11.5,
            fontweight="bold",
            color=INK,
        )
    ax_names.set_xlim(0, 1)
    ax_names.set_ylim(n - 0.5, -0.5)
    ax_names.axis("off")

    matrix = np.array(
        [
            [getattr(row, f"{tier}_rate") * 100 for tier in TIER_ORDER]
            for row in frame.itertuples()
        ]
    )
    counts = np.array(
        [
            [getattr(row, f"{tier}_exact") for tier in TIER_ORDER]
            for row in frame.itertuples()
        ]
    )
    sizes = np.array(
        [
            [getattr(row, f"{tier}_n") for tier in TIER_ORDER]
            for row in frame.itertuples()
        ]
    )
    cmap = LinearSegmentedColormap.from_list(
        "n2s_blue",
        ["#F8FAFC", "#DBEAFE", "#93C5FD", "#3B82F6", "#1E3A8A"],
    )
    im = ax.imshow(matrix, aspect="auto", cmap=cmap, vmin=0, vmax=100)
    ax.set_xticks(np.arange(len(TIER_ORDER)))
    ax.set_xticklabels(
        [f"{tier}\n(n={TIER_SIZES[tier]})" for tier in TIER_ORDER],
        fontsize=10,
    )
    ax.xaxis.tick_top()
    ax.tick_params(axis="x", length=0, pad=8)
    ax.set_yticks([])
    ax.set_xticks(np.arange(-0.5, len(TIER_ORDER), 1), minor=True)
    ax.set_yticks(np.arange(-0.5, n, 1), minor=True)
    ax.grid(which="minor", color="white", linewidth=3)
    ax.tick_params(which="minor", length=0)
    ax.set_ylim(n - 0.5, -0.5)
    for i in range(n):
        for j in range(len(TIER_ORDER)):
            value = matrix[i, j]
            color = "white" if value >= 55 else INK
            ax.text(
                j,
                i,
                f"{value:.0f}%",
                ha="center",
                va="center",
                fontsize=10.5,
                fontweight="bold",
                color=color,
            )
            ax.text(
                j,
                i + 0.24,
                f"{counts[i, j]}/{sizes[i, j]}",
                ha="center",
                va="center",
                fontsize=7.2,
                color=color,
                alpha=0.85,
            )
    title_block(
        fig,
        "Accuracy by difficulty tier",
        "Exact-match rate per tier. Cell labels show exact/n. L1 is easiest; L5 is hardest.",
    )
    cax = fig.add_axes([0.27, 0.105, 0.66, 0.018])
    colorbar = fig.colorbar(im, cax=cax, orientation="horizontal")
    colorbar.set_label("Exact match (%)", fontsize=8, color=MUTED, labelpad=6)
    colorbar.ax.tick_params(labelsize=8, colors=MUTED, length=2)
    colorbar.outline.set_visible(False)
    fig.text(
        0.025,
        0.025,
        "Tiers are heuristic and L3/L4 overlap in difficulty. Failed calls would count as 0.",
        fontsize=7.8,
        color=MUTED,
    )
    fig.savefig(path, dpi=220, bbox_inches="tight")
    plt.close(fig)


def fig_cost(
    frame: pd.DataFrame,
    icons: dict[str, Image.Image],
    path: Path,
) -> None:
    fig, ax = plt.subplots(figsize=(11.8, 7.2))
    fig.subplots_adjust(left=0.095, right=0.975, top=0.81, bottom=0.15)
    ax.set_xscale("log")
    ax.set_xlim(0.05, 10)
    ax.set_ylim(0, 100)
    ax.set_xticks([0.1, 0.3, 1, 3, 10])
    ax.set_xticklabels(["0.1", "0.3", "1", "3", "10"])
    ax.set_yticks([0, 20, 40, 60, 80, 100])
    ax.set_yticklabels(["0%", "20%", "40%", "60%", "80%", "100%"])
    ax.grid(True, which="major", color=GRID, linewidth=0.8, zorder=0)
    ax.grid(True, which="minor", color="#F1F5F9", linewidth=0.6, zorder=0)
    ax.set_axisbelow(True)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    ax.spines["left"].set_color(GRID)
    ax.spines["bottom"].set_color(GRID)
    ax.set_xlabel("Estimated cost for 100 names (CNY, log scale)", fontsize=10)
    ax.set_ylabel("Exact-match rate", fontsize=10)

    by_key = {row.model_key: row for row in frame.itertuples()}
    pareto = ["gpt-6.1-terra", "claude-haiku-5.5"]
    ax.plot(
        [by_key[key].cost_per_100_cny for key in pareto],
        [by_key[key].exact_rate * 100 for key in pareto],
        color=AMBER,
        lw=1.6,
        ls="--",
        zorder=1,
        label="Pareto frontier",
    )

    offsets = {
        "claude-haiku-5.5": (24, 10),
        "gpt-6.1-terra": (22, -20),
        "deepseek-flash": (-24, 16),
        "gemini-3.8-flash": (24, -12),
        "minimax-m3.1-flash": (-26, 18),
        "glm-5.3-flash": (24, -10),
        "longcat-2.5-preview": (-24, -18),
        "mimo-v2.6-flash": (24, 6),
    }
    for key in MODEL_ORDER:
        row = by_key[key]
        x = row.cost_per_100_cny
        y = row.exact_rate * 100
        add_icon(ax, icons[key], (x, y), zoom=0.033, pad=0.24)
        dx, dy = offsets[key]
        ha = "left" if dx >= 0 else "right"
        ax.annotate(
            f"{row.display_name}\n{y:.0f}% exact · ¥{x:.2f}",
            xy=(x, y),
            xytext=(dx, dy),
            textcoords="offset points",
            ha=ha,
            va="center",
            fontsize=8.6,
            color="#334155",
            linespacing=1.25,
        )
    ax.axhline(60.1, color="#CBD5E1", lw=1, ls=(0, (2, 3)), zorder=0)
    ax.text(
        9.8,
        61.5,
        "mean 60%",
        ha="right",
        va="bottom",
        fontsize=8,
        color=MUTED,
    )
    ax.legend(
        loc="lower right",
        frameon=False,
        fontsize=8.5,
        handlelength=2.2,
    )
    title_block(
        fig,
        "Accuracy vs cost",
        "One dot per model. Left is cheaper; up is more accurate. The dashed line is the Pareto frontier.",
    )
    fig.text(
        0.025,
        0.025,
        "Cost is estimated list price for completed calls; failed attempts without usage are not priced. "
        "GLM, LongCat, and MiMo include 42 low-reasoning retry rows.",
        fontsize=7.6,
        color=MUTED,
    )
    fig.savefig(path, dpi=220, bbox_inches="tight")
    plt.close(fig)


def fig_tokens(
    frame: pd.DataFrame,
    icons: dict[str, Image.Image],
    path: Path,
) -> None:
    fig = plt.figure(figsize=(13.2, 7.0))
    grid = fig.add_gridspec(
        1,
        2,
        width_ratios=[3.15, 9.0],
        left=0.018,
        right=0.985,
        top=0.80,
        bottom=0.15,
        wspace=0.02,
    )
    _, ax = icon_axis(fig, (grid[0, 0], grid[0, 1]), frame, icons)
    n = len(frame)
    ys = np.arange(n)
    for y, row in zip(ys, frame.itertuples()):
        reasoning = row.reasoning_tokens_mean
        answer = row.answer_tokens_mean
        ax.barh(
            y,
            reasoning,
            height=0.36,
            color=DARK_BLUE,
            edgecolor="white",
            linewidth=1.4,
            zorder=2,
        )
        ax.barh(
            y,
            answer,
            left=reasoning,
            height=0.36,
            color=LIGHT_BLUE,
            edgecolor="white",
            linewidth=1.4,
            zorder=2,
        )
        total = reasoning + answer
        share = reasoning / total * 100 if total else 0
        ax.text(
            total + 220,
            y,
            f"{total / 1000:.1f}k",
            va="center",
            ha="left",
            fontsize=11,
            fontweight="bold",
            color=INK,
        )
        ax.text(
            total + 1450,
            y,
            f"{share:.1f}% reasoning",
            va="center",
            ha="left",
            fontsize=8,
            color=MUTED,
        )
    ax.set_xlim(0, 15000)
    ax.set_xticks([0, 5000, 10000, 15000])
    ax.set_xticklabels(["0", "5k", "10k", "15k"])
    ax.set_xlabel("Mean output tokens per name", fontsize=9, labelpad=8)
    handles = [
        Line2D([0], [0], color=DARK_BLUE, lw=8, label="Reasoning"),
        Line2D([0], [0], color=LIGHT_BLUE, lw=8, label="Answer"),
    ]
    ax.legend(
        handles=handles,
        loc="upper left",
        bbox_to_anchor=(0.0, -0.095),
        ncol=2,
        frameon=False,
        fontsize=9,
        handlelength=1.2,
        columnspacing=1.6,
    )
    title_block(
        fig,
        "Token budget per name",
        "Mean output tokens per call, split into reasoning and answer tokens.",
    )
    fig.text(
        0.985,
        0.905,
        "n = 100 per model",
        ha="right",
        fontsize=9,
        color=MUTED,
    )
    fig.text(
        0.025,
        0.035,
        "Reasoning tokens are as reported by each provider; counting and disclosure differ. "
        "Input tokens are negligible (about 100-300 per call).",
        fontsize=7.8,
        color=MUTED,
    )
    fig.savefig(path, dpi=220, bbox_inches="tight")
    plt.close(fig)


def write_metrics(frame: pd.DataFrame, summary: dict[str, Any], csv: Path) -> None:
    rows = []
    for key in MODEL_ORDER:
        model = summary["models"][key]
        rows.append(
            {
                "model_key": key,
                "display_name": model["display_name"],
                "n": model["n"],
                "exact": model["exact"],
                "exact_rate": model["exact_rate"],
                "connectivity": model["connectivity"],
                "connectivity_rate": model["connectivity_rate"],
                "valid": model["valid"],
                "valid_rate": model["valid_rate"],
                "inchikey": model["inchikey"],
                "inchikey_rate": model["inchikey_rate"],
                "tanimoto_valid": model["tanimoto_valid"],
                "tanimoto_all": model["tanimoto_all"],
                "input_tokens_mean": model["input_tokens_mean"],
                "output_tokens_mean": model["output_tokens_mean"],
                "reasoning_tokens_mean": model["reasoning_tokens_mean"],
                "answer_tokens_mean": model["answer_tokens_mean"],
                "total_cost_cny": model["total_cost_cny"],
                "cost_per_100_cny": model["cost_per_100_cny"],
                "cost_per_exact_100_cny": model["cost_per_exact_100_cny"],
                "mean_latency_s": model["mean_latency_s"],
                **{
                    f"{tier}_exact_rate": model["tiers"][tier]["exact_rate"]
                    for tier in TIER_ORDER
                },
            }
        )
    pd.DataFrame(rows).to_csv(csv, index=False, encoding="utf-8", lineterminator="\n")


def markdown_table(summary: dict[str, Any]) -> str:
    lines = [
        "| Model | Exact | Connectivity | Valid | InChIKey | Tanimoto | "
        "Cost / 100 | CNY / 100 exact | Output tok | Latency |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for key in MODEL_ORDER:
        row = summary["models"][key]
        lines.append(
            f"| {row['display_name']} | {row['exact_rate'] * 100:.0f}% | "
            f"{row['connectivity_rate'] * 100:.0f}% | "
            f"{row['valid_rate'] * 100:.0f}% | "
            f"{row['inchikey_rate'] * 100:.0f}% | "
            f"{row['tanimoto_valid']:.2f} | "
            f"{row['cost_per_100_cny']:.2f} | "
            f"{row['cost_per_exact_100_cny']:.2f} | "
            f"{row['output_tokens_mean'] / 1000:.1f}k | "
            f"{row['mean_latency_s']:.1f}s |"
        )
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    style()
    frame = build_frame(load_rows(args.data))
    frame["_order"] = frame["model_key"].map(
        {key: index for index, key in enumerate(MODEL_ORDER)}
    )
    frame = frame.sort_values(["_order", "record_id"]).reset_index(drop=True)
    summary = summarize(frame, args.data)
    model_stats = build_model_frame(summary)

    args.out.mkdir(parents=True, exist_ok=True)
    icons = {key: load_icon(args.icons / ICON_FILES[key]) for key in MODEL_ORDER}
    fig_leaderboard(model_stats, icons, args.out / "leaderboard.png")
    fig_tiers(model_stats, icons, args.out / "tiers.png")
    fig_cost(model_stats, icons, args.out / "cost_accuracy.png")
    fig_tokens(model_stats, icons, args.out / "tokens.png")

    args.summary.parent.mkdir(parents=True, exist_ok=True)
    args.summary.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    write_metrics(frame, summary, args.csv)

    print(markdown_table(summary))
    print()
    print(f"calls: {summary['totals']['calls']}")
    print(
        f"exact: {summary['totals']['exact']} ({summary['totals']['exact_rate']:.1%})"
    )
    print(f"cost: {summary['totals']['cost_cny']:.4f} CNY")
    print(f"wrote: {args.out}")
    print(f"wrote: {args.summary}")
    print(f"wrote: {args.csv}")


if __name__ == "__main__":
    main()
