"""
generate_charts.py
──────────────────
Generate all charts and tables for the RAG vs CAG vs KAG article.
Reads benchmark/results.csv (or benchmark/summary.json).

Outputs (saved to visualize/):
  01_input_tokens_comparison.png
  02_cost_per_query.png
  03_cached_tokens_cag.png
  04_latency_comparison.png
  05_cost_breakdown_stacked.png
  06_token_savings_heatmap.png
  07_cumulative_cost_1000_queries.png
  08_cost_by_category.png
  article_table.md           — Markdown comparison table for the article

Usage:
  python visualize/generate_charts.py
  python visualize/generate_charts.py --summary   # use summary.json (no raw CSV needed)
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd

import sys; sys.path.insert(0, str(Path(__file__).parent.parent))
from config import BENCHMARK_DIR, VISUALIZE_DIR, PRICING

VISUALIZE_DIR.mkdir(parents=True, exist_ok=True)

# ── Colour palette ────────────────────────────────────────────────────────────
COLORS = {
    "RAG": "#FF9900",   # AWS orange
    "CAG": "#146EB4",   # AWS blue
    "KAG": "#1A9C3E",   # AWS green
}
METHODS = ["RAG", "CAG", "KAG"]
plt.rcParams.update({
    "font.family":  "DejaVu Sans",
    "font.size":    11,
    "axes.spines.top":   False,
    "axes.spines.right": False,
})


# ─── Data loading ─────────────────────────────────────────────────────────────

def load_data() -> tuple[pd.DataFrame, dict]:
    csv_path     = BENCHMARK_DIR / "results.csv"
    summary_path = BENCHMARK_DIR / "summary.json"

    if csv_path.exists():
        df  = pd.read_csv(csv_path)
        avg = df.groupby("method").mean(numeric_only=True)  # Don't round here - preserve precision
    else:
        # Fallback: generate synthetic data for demonstration
        print("WARNING: results.csv not found — using synthetic demo data")
        df  = _synthetic_data()
        avg = df.groupby("method").mean(numeric_only=True)

    summary = json.loads(summary_path.read_text()) if summary_path.exists() else {}
    return df, avg, summary


def _synthetic_data() -> pd.DataFrame:
    """Generate realistic synthetic benchmark data for chart testing."""
    import random; random.seed(42)
    records = []
    for run in range(3):
        for qid in range(1, 21):
            # RAG: ~2200 input tokens, no cache
            records.append({
                "method": "RAG", "run": run+1, "query_id": f"q{qid:02d}",
                "input_tokens":  random.randint(1800, 2600),
                "output_tokens": random.randint(150,  450),
                "cached_tokens": 0,
                "cache_write_tokens": 0,
                "cost_usd":      random.uniform(0.008, 0.016),
                "latency_ms":    random.uniform(1800, 3500),
                "category":      random.choice(["cost","overview","implementation","security"]),
            })
            # CAG: small input + large cache read
            cw = 9800 if run == 0 else 0
            cr = 0    if run == 0 else 9800
            records.append({
                "method": "CAG", "run": run+1, "query_id": f"q{qid:02d}",
                "input_tokens":  random.randint(80, 160),
                "output_tokens": random.randint(150, 450),
                "cached_tokens": cr,
                "cache_write_tokens": cw,
                "cost_usd":      random.uniform(0.003, 0.008) if run > 0 else random.uniform(0.008, 0.014),
                "latency_ms":    random.uniform(1200, 2400),
                "category":      random.choice(["cost","overview","implementation","security"]),
            })
            # KAG: low input tokens, no cache
            records.append({
                "method": "KAG", "run": run+1, "query_id": f"q{qid:02d}",
                "input_tokens":  random.randint(250, 550),
                "output_tokens": random.randint(150, 450),
                "cached_tokens": 0,
                "cache_write_tokens": 0,
                "cost_usd":      random.uniform(0.003, 0.009),
                "latency_ms":    random.uniform(800,  2000),
                "category":      random.choice(["cost","overview","implementation","security"]),
            })
    return pd.DataFrame(records)


# ─── Individual chart functions ───────────────────────────────────────────────

def chart_01_input_tokens(avg: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(8, 5))
    vals = [avg.loc[m, "input_tokens"] if m in avg.index else 0 for m in METHODS]
    bars = ax.bar(METHODS, vals, color=[COLORS[m] for m in METHODS], width=0.5, edgecolor="white", linewidth=1.2)
    for bar, val in zip(bars, vals):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 30,
                f"{val:,.0f}", ha="center", va="bottom", fontweight="bold")
    ax.set_title("Average Input Tokens per Query", fontsize=13, fontweight="bold", pad=12)
    ax.set_ylabel("Tokens")
    ax.set_ylim(0, max(vals) * 1.25)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x:,.0f}"))
    _add_savings_annotation(ax, vals, "input tokens")
    fig.tight_layout()
    fig.savefig(VISUALIZE_DIR / "01_input_tokens_comparison.png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("✓ 01_input_tokens_comparison.png")


def chart_02_cost_per_query(avg: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(8, 5))
    vals = [avg.loc[m, "cost_usd"] * 1000 if m in avg.index else 0 for m in METHODS]  # convert to milli-USD
    bars = ax.bar(METHODS, vals, color=[COLORS[m] for m in METHODS], width=0.5, edgecolor="white")
    for bar, val in zip(bars, vals):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.05,
                f"${val:.2f}m", ha="center", va="bottom", fontweight="bold")
    ax.set_title("Average Cost per Query (milli-USD)", fontsize=13, fontweight="bold", pad=12)
    ax.set_ylabel("Cost (mUSD = USD × 10⁻³)")
    ax.set_ylim(0, max(vals) * 1.3)
    _add_savings_annotation(ax, vals, "cost")
    fig.tight_layout()
    fig.savefig(VISUALIZE_DIR / "02_cost_per_query.png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("✓ 02_cost_per_query.png")


def chart_03_cached_tokens(avg: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(8, 5))
    vals = [avg.loc[m, "cached_tokens"] if m in avg.index and "cached_tokens" in avg.columns else 0 for m in METHODS]
    bars = ax.bar(METHODS, vals, color=[COLORS[m] for m in METHODS], width=0.5, edgecolor="white")
    for bar, val in zip(bars, vals):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 30,
                f"{val:,.0f}", ha="center", va="bottom", fontweight="bold")
    ax.set_title("Average Cached Tokens per Query\n(CAG Cache Hit Rate)", fontsize=13, fontweight="bold", pad=12)
    ax.set_ylabel("Cache Read Tokens")
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x:,.0f}"))
    ax.annotate("↑ Higher = more tokens served\nfrom cache at −90% cost",
                xy=(1, vals[1] if vals[1] > 0 else 1),
                xytext=(1.3, max(vals) * 0.7),
                arrowprops=dict(arrowstyle="->", color=COLORS["CAG"]),
                color=COLORS["CAG"], fontweight="bold")
    fig.tight_layout()
    fig.savefig(VISUALIZE_DIR / "03_cached_tokens_cag.png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("✓ 03_cached_tokens_cag.png")


def chart_04_latency(avg: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(8, 5))
    vals = [avg.loc[m, "latency_ms"] if m in avg.index else 0 for m in METHODS]
    bars = ax.bar(METHODS, vals, color=[COLORS[m] for m in METHODS], width=0.5, edgecolor="white")
    for bar, val in zip(bars, vals):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 20,
                f"{val:,.0f} ms", ha="center", va="bottom", fontweight="bold")
    ax.set_title("Average End-to-End Latency (ms)", fontsize=13, fontweight="bold", pad=12)
    ax.set_ylabel("Latency (ms)")
    ax.set_ylim(0, max(vals) * 1.3)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x:,.0f}"))
    fig.tight_layout()
    fig.savefig(VISUALIZE_DIR / "04_latency_comparison.png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("✓ 04_latency_comparison.png")


def chart_05_cost_breakdown(avg: pd.DataFrame) -> None:
    """Stacked bar: input / output / cache costs."""
    fig, ax = plt.subplots(figsize=(9, 5))
    x = np.arange(len(METHODS))
    width = 0.5

    def _get(m, col):
        return avg.loc[m, col] if m in avg.index and col in avg.columns else 0

    input_cost  = [(_get(m, "input_tokens")       / 1e6) * PRICING["input_per_1m"]       * 1000 for m in METHODS]
    output_cost = [(_get(m, "output_tokens")       / 1e6) * PRICING["output_per_1m"]      * 1000 for m in METHODS]
    cache_cost  = [(_get(m, "cached_tokens")       / 1e6) * PRICING["cache_read_per_1m"]  * 1000 for m in METHODS]
    cwrite_cost = [(_get(m, "cache_write_tokens")  / 1e6) * PRICING["cache_write_per_1m"] * 1000 for m in METHODS]

    p1 = ax.bar(x, input_cost,  width, label="Input tokens",       color="#FF9900", alpha=0.9)
    p2 = ax.bar(x, output_cost, width, bottom=input_cost,           label="Output tokens", color="#146EB4", alpha=0.9)
    p3 = ax.bar(x, cache_cost,  width, bottom=[a+b for a,b in zip(input_cost, output_cost)],
                label="Cache read",  color="#1A9C3E", alpha=0.9)
    p4 = ax.bar(x, cwrite_cost, width,
                bottom=[a+b+c for a,b,c in zip(input_cost, output_cost, cache_cost)],
                label="Cache write", color="#D13212", alpha=0.7)

    ax.set_xticks(x); ax.set_xticklabels(METHODS)
    ax.set_title("Cost Breakdown per Query (milli-USD)", fontsize=13, fontweight="bold", pad=12)
    ax.set_ylabel("Cost (mUSD)")
    ax.legend(loc="upper right", fontsize=9)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"${v:.1f}m"))
    fig.tight_layout()
    fig.savefig(VISUALIZE_DIR / "05_cost_breakdown_stacked.png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("✓ 05_cost_breakdown_stacked.png")


def chart_06_cumulative_cost(avg: pd.DataFrame) -> None:
    """Cumulative cost for 1,000 queries — shows long-term savings."""
    query_counts = np.arange(0, 1001, 50)
    fig, ax = plt.subplots(figsize=(10, 5))
    for method in METHODS:
        cost_per_q = avg.loc[method, "cost_usd"] if method in avg.index else 0
        ax.plot(query_counts, query_counts * cost_per_q,
                label=method, color=COLORS[method], linewidth=2.5)
    ax.set_title("Cumulative Cost — 1,000 Queries\n(Excluding CAG Cache Warmup Cost)",
                 fontsize=13, fontweight="bold", pad=12)
    ax.set_xlabel("Number of Queries")
    ax.set_ylabel("Cumulative Cost (USD)")
    ax.legend()
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"${v:.2f}"))
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{v:,.0f}"))
    fig.tight_layout()
    fig.savefig(VISUALIZE_DIR / "07_cumulative_cost_1000_queries.png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("✓ 07_cumulative_cost_1000_queries.png")


def chart_07_cost_by_category(df: pd.DataFrame) -> None:
    """Average cost by query category and method."""
    if "category" not in df.columns:
        return
    pivot = df.groupby(["category", "method"])["cost_usd"].mean().unstack("method") * 1000
    if pivot.empty:
        return
    fig, ax = plt.subplots(figsize=(11, 5))
    x     = np.arange(len(pivot))
    width = 0.25
    for i, method in enumerate(METHODS):
        if method in pivot.columns:
            ax.bar(x + i * width, pivot[method], width, label=method, color=COLORS[method], alpha=0.9)
    ax.set_xticks(x + width); ax.set_xticklabels(pivot.index, rotation=20, ha="right")
    ax.set_title("Cost per Query by Category (milli-USD)", fontsize=13, fontweight="bold", pad=12)
    ax.set_ylabel("Cost (mUSD)")
    ax.legend()
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"${v:.2f}m"))
    fig.tight_layout()
    fig.savefig(VISUALIZE_DIR / "08_cost_by_category.png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("✓ 08_cost_by_category.png")


# ─── Article Markdown table ───────────────────────────────────────────────────

def generate_markdown_table(avg: pd.DataFrame, summary: dict) -> None:
    lines = [
        "## RAG vs CAG vs KAG — Benchmark Results\n",
        "| Metric | RAG | CAG | KAG | CAG vs RAG | KAG vs RAG |",
        "|--------|-----|-----|-----|------------|------------|",
    ]
    metrics = {
        "Avg Input Tokens":    ("input_tokens",  "{:.0f}"),
        "Avg Output Tokens":   ("output_tokens", "{:.0f}"),
        "Avg Cached Tokens":   ("cached_tokens", "{:.0f}"),
        "Avg Cost (mUSD)":     ("cost_usd",      lambda v: f"${v*1000:.2f}m"),
        "Avg Latency (ms)":    ("latency_ms",    "{:.0f} ms"),
    }
    for label, (col, fmt) in metrics.items():
        row = [label]
        vals = {}
        for m in METHODS:
            v = avg.loc[m, col] if m in avg.index and col in avg.columns else 0
            vals[m] = v
            row.append(fmt.format(v) if isinstance(fmt, str) else fmt(v))
        # savings
        for compare in ("CAG", "KAG"):
            if vals["RAG"] and vals.get(compare) is not None:
                saving = (1 - vals[compare] / vals["RAG"]) * 100
                row.append(f"**−{saving:.1f}%**" if saving > 0 else f"+{-saving:.1f}%")
            else:
                row.append("—")
        lines.append("| " + " | ".join(str(c) for c in row) + " |")

    out = "\n".join(lines)
    path = VISUALIZE_DIR / "article_table.md"
    path.write_text(out)
    print(f"✓ article_table.md\n\n{out}\n")


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _add_savings_annotation(ax, vals: list, metric: str) -> None:
    if vals[0] > 0:
        for i, (method, val) in enumerate(zip(METHODS[1:], vals[1:]), 1):
            saving = (1 - val / vals[0]) * 100
            if saving > 0:
                ax.text(i, val * 0.5, f"−{saving:.0f}%\nvs RAG",
                        ha="center", va="center", color="white",
                        fontsize=9, fontweight="bold")


# ─── Entrypoint ───────────────────────────────────────────────────────────────

def main() -> None:
    df, avg, summary = load_data()
    print(f"\nGenerating charts from {len(df)} records across {df['method'].nunique()} methods\n")
    chart_01_input_tokens(avg)
    chart_02_cost_per_query(avg)
    chart_03_cached_tokens(avg)
    chart_04_latency(avg)
    chart_05_cost_breakdown(avg)
    chart_06_cumulative_cost(avg)
    chart_07_cost_by_category(df)
    generate_markdown_table(avg, summary)
    print(f"\nAll charts saved to: {VISUALIZE_DIR}")


if __name__ == "__main__":
    main()
