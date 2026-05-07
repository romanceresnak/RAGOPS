"""
cag_pipeline.py
───────────────
Cache-Augmented Generation (CAG) pipeline.

The entire knowledge base is loaded into the system prompt and marked with
cache_control = {"type": "ephemeral"}.  Bedrock caches the prefix server-side:
  • First call  → cache WRITE  (+25 % on write tokens)
  • Subsequent  → cache READ   (−90 % on input tokens, TTL resets to 5 min)

This module tracks cache_creation_input_tokens and cache_read_input_tokens
separately so the benchmark can compute accurate CAG savings vs RAG.
"""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path

import boto3

import sys; sys.path.insert(0, str(Path(__file__).parent.parent))
from config import (
    AWS_REGION, BEDROCK_MODEL_ID, MAX_TOKENS,
    SAMPLE_DOCS, PRICING,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

bedrock = boto3.client("bedrock-runtime", region_name=AWS_REGION)


# ─── Knowledge base loader ────────────────────────────────────────────────────

def load_knowledge_base(source_dir: Path = SAMPLE_DOCS) -> str:
    """Concatenate all .txt documents into one knowledge base string."""
    parts = []
    for path in sorted(source_dir.glob("*.txt")):
        parts.append(f"=== {path.stem} ===\n{path.read_text(encoding='utf-8').strip()}")
    kb = "\n\n".join(parts)
    # Rough token estimate (1 token ≈ 0.75 words)
    word_count  = len(kb.split())
    token_est   = int(word_count / 0.75)
    log.info(f"Knowledge base: {len(parts)} docs, ~{word_count:,} words, ~{token_est:,} tokens")
    return kb


# ─── CAG generation ───────────────────────────────────────────────────────────

def cag_generate(
    query: str,
    knowledge_base: str,
    model_id: str = BEDROCK_MODEL_ID,
    is_warmup: bool = False,
) -> dict:
    """
    Single CAG call: knowledge base in system prompt with cache_control.

    Args:
        query:          User question.
        knowledge_base: Full knowledge base text (cached after first call).
        model_id:       Bedrock model ID.
        is_warmup:      If True, marks this as a warmup call (cache write).

    Returns:
        Dict with token counts, cost, latency, cache metrics.
    """
    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": MAX_TOKENS,
        "system": [
            {
                "type": "text",
                "text": (
                    "You are a knowledgeable AWS cloud architect. "
                    "Answer using ONLY the knowledge base below. "
                    "If the information is not present, say so.\n\n"
                    f"KNOWLEDGE BASE:\n{knowledge_base}"
                ),
                # ↓ This single line enables prompt caching for the system prompt
                "cache_control": {"type": "ephemeral"},
            }
        ],
        "messages": [
            {"role": "user", "content": query}
        ],
    }

    t0 = time.perf_counter()
    response = bedrock.invoke_model(
        modelId=model_id,
        contentType="application/json",
        accept="application/json",
        body=json.dumps(body),
    )
    latency_ms = (time.perf_counter() - t0) * 1000

    result = json.loads(response["body"].read())
    usage  = result["usage"]
    answer = result["content"][0]["text"]

    input_tokens        = usage.get("input_tokens", 0)
    output_tokens       = usage.get("output_tokens", 0)
    cache_write_tokens  = usage.get("cache_creation_input_tokens", 0)
    cache_read_tokens   = usage.get("cache_read_input_tokens", 0)

    # Cost calculation — cache reads are 90 % cheaper
    cost = (
          (input_tokens       / 1_000_000) * PRICING["input_per_1m"]
        + (output_tokens      / 1_000_000) * PRICING["output_per_1m"]
        + (cache_write_tokens / 1_000_000) * PRICING["cache_write_per_1m"]
        + (cache_read_tokens  / 1_000_000) * PRICING["cache_read_per_1m"]
    )

    cache_status = "WRITE" if cache_write_tokens > 0 else ("HIT" if cache_read_tokens > 0 else "MISS")
    log.info(
        f"CAG [{cache_status}] | input={input_tokens} | "
        f"cache_write={cache_write_tokens} | cache_read={cache_read_tokens} | "
        f"output={output_tokens} | cost=${cost:.6f} | {latency_ms:.0f}ms"
    )

    return {
        "method":              "CAG",
        "query":               query,
        "answer":              answer,
        "input_tokens":        input_tokens,
        "output_tokens":       output_tokens,
        "cached_tokens":       cache_read_tokens,
        "cache_write_tokens":  cache_write_tokens,
        "cache_status":        cache_status,
        "cost_usd":            cost,
        "latency_ms":          latency_ms,
        "model_id":            model_id,
        "is_warmup":           is_warmup,
    }


# ─── Warmup helper ────────────────────────────────────────────────────────────

def warmup_cache(knowledge_base: str, model_id: str = BEDROCK_MODEL_ID) -> dict:
    """
    Send a dummy query to prime the cache before the benchmark starts.
    The cache_write cost is amortised across all subsequent queries.
    """
    log.info("Warming up CAG cache...")
    result = cag_generate("Acknowledge you have received the knowledge base.", knowledge_base, model_id, is_warmup=True)
    log.info(f"Cache warmed — {result['cache_write_tokens']} tokens written to cache")
    return result


# ─── CLI demo ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    kb = load_knowledge_base()

    print("=== Call 1 (cache WRITE) ===")
    r1 = cag_generate("What is the cost difference between RAG and CAG?", kb)
    print(f"Cache write tokens: {r1['cache_write_tokens']}")
    print(f"Cost: ${r1['cost_usd']:.6f}\n")

    print("=== Call 2 (cache HIT — same prefix) ===")
    r2 = cag_generate("How does prompt caching work on Bedrock?", kb)
    print(f"Cache read tokens:  {r2['cached_tokens']}")
    print(f"Cost: ${r2['cost_usd']:.6f}")
    savings = (r1["cache_write_tokens"] - r2["cached_tokens"]) / max(r1["cache_write_tokens"], 1)
    print(f"\nToken cost on cache hit: {r2['cached_tokens']} × $0.30/1M vs {r1['input_tokens']} × $3.00/1M")
