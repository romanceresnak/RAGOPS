"""
run_benchmark.py
────────────────
Run all 20 queries through RAG, CAG, and KAG.
Measures per-query: input_tokens, output_tokens, cached_tokens, cost_usd, latency_ms.
Outputs:
  benchmark/results.csv       — raw results (all runs × all methods)
  benchmark/results_avg.csv   — per-method averages
  benchmark/summary.json      — structured summary for article

Usage:
  python benchmark/run_benchmark.py                        # all methods
  python benchmark/run_benchmark.py --methods RAG CAG      # subset
  python benchmark/run_benchmark.py --queries 5            # first 5 queries only
  python benchmark/run_benchmark.py --runs 1               # single run (quick test)
"""
from __future__ import annotations

import argparse
import json
import logging
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
from tqdm import tqdm

import sys; sys.path.insert(0, str(Path(__file__).parent.parent))
from config import (
    BENCHMARK_RUNS, TOP_K_RAG, CAG_CACHE_WARMUP,
    BENCHMARK_DIR, PRICING,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)


# ─── Lazy imports (avoid import errors if a method is excluded) ───────────────

def _get_rag():
    import importlib
    rag_embeddings = importlib.import_module('1_rag.rag_embeddings')
    rag_pipeline = importlib.import_module('1_rag.rag_pipeline')
    load_index = rag_embeddings.load_index
    run_rag = rag_pipeline.run_rag
    index, chunks = load_index()
    def run(query, **_): return run_rag(query, index, chunks)
    return run

def _get_cag():
    import importlib
    cag_pipeline = importlib.import_module('2_cag.cag_pipeline')
    load_knowledge_base = cag_pipeline.load_knowledge_base
    cag_generate = cag_pipeline.cag_generate
    warmup_cache = cag_pipeline.warmup_cache
    kb = load_knowledge_base()
    if CAG_CACHE_WARMUP:
        warmup_cache(kb)
    def run(query, **_): return cag_generate(query, kb)
    return run

def _get_kag():
    import importlib
    kag_pipeline = importlib.import_module('3_kag.kag_pipeline')
    kag_generate = kag_pipeline.kag_generate
    def run(query, entity=None, **_): return kag_generate(query, entity=entity)
    return run


# ─── Cost calculation ─────────────────────────────────────────────────────────

def compute_cost(row: dict) -> float:
    """Re-compute USD cost from token fields (validation / override)."""
    return (
          (row.get("input_tokens",       0) / 1_000_000) * PRICING["input_per_1m"]
        + (row.get("output_tokens",      0) / 1_000_000) * PRICING["output_per_1m"]
        + (row.get("cached_tokens",      0) / 1_000_000) * PRICING["cache_read_per_1m"]
        + (row.get("cache_write_tokens", 0) / 1_000_000) * PRICING["cache_write_per_1m"]
    )


# ─── Main benchmark loop ──────────────────────────────────────────────────────

def run_benchmark(
    methods:    list[str] = None,
    n_queries:  int       = None,
    n_runs:     int       = None,
) -> pd.DataFrame:
    methods   = methods  or ["RAG", "CAG", "KAG"]
    n_runs    = n_runs   or BENCHMARK_RUNS
    queries   = json.loads((BENCHMARK_DIR / "queries.json").read_text())
    if n_queries:
        queries = queries[:n_queries]

    log.info(f"Benchmark: {len(methods)} methods × {len(queries)} queries × {n_runs} runs")

    # Initialise pipelines
    runners = {}
    if "RAG" in methods:
        log.info("Initialising RAG pipeline...")
        runners["RAG"] = _get_rag()
    if "CAG" in methods:
        log.info("Initialising CAG pipeline (loading knowledge base)...")
        runners["CAG"] = _get_cag()
    if "KAG" in methods:
        log.info("Initialising KAG pipeline...")
        runners["KAG"] = _get_kag()

    records = []
    total   = len(methods) * len(queries) * n_runs
    pbar    = tqdm(total=total, desc="Benchmark progress")

    for run_idx in range(n_runs):
        for q in queries:
            for method in methods:
                try:
                    result = runners[method](
                        query  = q["query"],
                        entity = q.get("entity"),
                    )
                    records.append({
                        "run":             run_idx + 1,
                        "query_id":        q["id"],
                        "category":        q.get("category", ""),
                        "complexity":      q.get("complexity", ""),
                        **{k: v for k, v in result.items() if k not in ("answer",)},
                        "cost_usd_verify": compute_cost(result),
                    })
                except Exception as e:
                    log.error(f"Error: method={method} query={q['id']} run={run_idx+1}: {e}")
                    records.append({
                        "run": run_idx + 1, "query_id": q["id"],
                        "method": method, "error": str(e),
                    })
                pbar.update(1)
                time.sleep(0.5)  # rate-limit buffer

    pbar.close()

    df = pd.DataFrame(records)
    return df


# ─── Reporting ────────────────────────────────────────────────────────────────

def save_results(df: pd.DataFrame) -> None:
    BENCHMARK_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    raw_path = BENCHMARK_DIR / f"results_{ts}.csv"
    df.to_csv(raw_path, index=False)
    # Also overwrite the canonical results.csv for visualise/
    df.to_csv(BENCHMARK_DIR / "results.csv", index=False)
    log.info(f"Saved raw results → {raw_path}")

    # Averages per method
    numeric_cols = ["input_tokens", "output_tokens", "cached_tokens",
                    "cache_write_tokens", "cost_usd", "latency_ms", "facts_count"]
    available    = [c for c in numeric_cols if c in df.columns]
    # Filter out error rows if error column exists
    df_valid = df[~df["error"].notna()] if "error" in df.columns else df
    avg_df       = df_valid.groupby("method")[available].mean().round(2)
    avg_df.to_csv(BENCHMARK_DIR / "results_avg.csv")
    log.info(f"\n{avg_df.to_string()}")

    # Summary JSON for article generation
    summary = {}
    for method, group in df.groupby("method"):
        summary[method] = {
            "avg_input_tokens":      round(group["input_tokens"].mean(),  1),
            "avg_output_tokens":     round(group["output_tokens"].mean(), 1),
            "avg_cached_tokens":     round(group.get("cached_tokens", pd.Series([0])).mean(), 1),
            "avg_cost_usd":          round(group["cost_usd"].mean(),      6),
            "avg_latency_ms":        round(group["latency_ms"].mean(),    1),
            "total_queries":         int(len(group)),
        }

    # Token savings ratios (vs RAG as baseline)
    if "RAG" in summary:
        rag_tokens = summary["RAG"]["avg_input_tokens"]
        rag_cost   = summary["RAG"]["avg_cost_usd"]
        for m in ("CAG", "KAG"):
            if m in summary:
                summary[m]["token_savings_vs_rag_pct"] = round(
                    (1 - summary[m]["avg_input_tokens"] / rag_tokens) * 100, 1
                )
                summary[m]["cost_savings_vs_rag_pct"] = round(
                    (1 - summary[m]["avg_cost_usd"] / rag_cost) * 100, 1
                )

    summary_path = BENCHMARK_DIR / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2))
    log.info(f"Saved summary → {summary_path}")
    print("\n=== BENCHMARK SUMMARY ===")
    print(json.dumps(summary, indent=2))


# ─── CLI ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="RAG vs CAG vs KAG benchmark")
    parser.add_argument("--methods",  nargs="+", choices=["RAG", "CAG", "KAG"],
                        default=["RAG", "CAG", "KAG"])
    parser.add_argument("--queries",  type=int, default=None, help="Limit to first N queries")
    parser.add_argument("--runs",     type=int, default=None, help="Override BENCHMARK_RUNS")
    args = parser.parse_args()

    df = run_benchmark(methods=args.methods, n_queries=args.queries, n_runs=args.runs)
    save_results(df)
