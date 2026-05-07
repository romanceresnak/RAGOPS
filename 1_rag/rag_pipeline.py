"""
rag_pipeline.py
───────────────
RAG inference pipeline: embed query → FAISS retrieval → Bedrock generation.
Returns a structured result dict including precise token counts and USD cost.
"""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path

import boto3
import faiss
import numpy as np

import sys; sys.path.insert(0, str(Path(__file__).parent.parent))
from config import (
    AWS_REGION, BEDROCK_MODEL_ID, BEDROCK_EMBED_MODEL,
    MAX_TOKENS, TOP_K_RAG, PRICING,
    FAISS_INDEX, FAISS_METADATA,
)
from .rag_embeddings import embed_text, load_index   # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

bedrock = boto3.client("bedrock-runtime", region_name=AWS_REGION)


# ─── Retrieval ────────────────────────────────────────────────────────────────

def retrieve(
    query: str,
    index: faiss.Index,
    chunks: list[dict],
    top_k: int = TOP_K_RAG,
) -> list[str]:
    """Embed query and return top-k most relevant chunks."""
    q_vec = np.array([embed_text(query)], dtype="float32")
    distances, indices = index.search(q_vec, top_k)
    results = []
    for i, idx in enumerate(indices[0]):
        if idx < len(chunks):
            results.append(chunks[idx]["content"])
            log.debug(f"  Retrieved chunk {idx} (distance={distances[0][i]:.3f})")
    return results


# ─── Generation ──────────────────────────────────────────────────────────────

def rag_generate(
    query: str,
    context_chunks: list[str],
    model_id: str = BEDROCK_MODEL_ID,
) -> dict:
    """
    Inject retrieved context into the prompt and call Bedrock.
    Returns token counts, latency, and estimated cost.
    """
    context = "\n\n---\n\n".join(context_chunks)

    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": MAX_TOKENS,
        "system": (
            "You are a knowledgeable AWS cloud architect. "
            "Answer the user's question using ONLY the provided context. "
            "If the context does not contain sufficient information, say so."
        ),
        "messages": [
            {
                "role": "user",
                "content": f"Context:\n{context}\n\nQuestion: {query}",
            }
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

    result  = json.loads(response["body"].read())
    usage   = result["usage"]
    answer  = result["content"][0]["text"]

    input_tokens  = usage["input_tokens"]
    output_tokens = usage["output_tokens"]
    cost = (
        (input_tokens  / 1_000_000) * PRICING["input_per_1m"]
        + (output_tokens / 1_000_000) * PRICING["output_per_1m"]
    )

    return {
        "method":         "RAG",
        "query":          query,
        "answer":         answer,
        "input_tokens":   input_tokens,
        "output_tokens":  output_tokens,
        "cached_tokens":  0,
        "context_chunks": len(context_chunks),
        "context_tokens": input_tokens,  # approximate — includes system + context + query
        "cost_usd":       cost,
        "latency_ms":     latency_ms,
        "model_id":       model_id,
    }


# ─── Full RAG pipeline ────────────────────────────────────────────────────────

def run_rag(query: str, index: faiss.Index = None, chunks: list[dict] = None) -> dict:
    """
    End-to-end RAG: load index if not provided, retrieve, generate.
    """
    if index is None or chunks is None:
        index, chunks = load_index()

    retrieved = retrieve(query, index, chunks)
    return rag_generate(query, retrieved)


# ─── CLI demo ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    query = "What is the difference between RAG and CAG for token cost optimisation?"
    print(f"Query: {query}\n")

    result = run_rag(query)
    print(f"Answer: {result['answer']}\n")
    print(f"Input tokens:  {result['input_tokens']}")
    print(f"Output tokens: {result['output_tokens']}")
    print(f"Cost:          ${result['cost_usd']:.6f}")
    print(f"Latency:       {result['latency_ms']:.0f} ms")
