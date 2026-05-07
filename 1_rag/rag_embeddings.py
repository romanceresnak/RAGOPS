"""
rag_embeddings.py
─────────────────
Build and persist a FAISS index from documents in S3 (or local sample_docs/).
Uses Amazon Titan Embeddings V2 via Bedrock.

Usage:
  python 1_rag/rag_embeddings.py --source local   # use data/sample_docs/
  python 1_rag/rag_embeddings.py --source s3       # use S3 bucket
"""
from __future__ import annotations

import argparse
import json
import logging
import time
from pathlib import Path

import boto3
import faiss
import numpy as np

import sys; sys.path.insert(0, str(Path(__file__).parent.parent))
from config import (
    AWS_REGION, BEDROCK_EMBED_MODEL, S3_BUCKET_NAME, S3_DOCS_PREFIX,
    SAMPLE_DOCS, FAISS_INDEX, FAISS_METADATA, PRICING,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

bedrock = boto3.client("bedrock-runtime", region_name=AWS_REGION)
s3      = boto3.client("s3",              region_name=AWS_REGION)


# ─── Embedding ────────────────────────────────────────────────────────────────

def embed_text(text: str) -> list[float]:
    """Call Titan Embeddings V2 and return a 1536-dim vector."""
    response = bedrock.invoke_model(
        modelId=BEDROCK_EMBED_MODEL,
        contentType="application/json",
        accept="application/json",
        body=json.dumps({"inputText": text[:8000]}),  # Titan V2 max input
    )
    return json.loads(response["body"].read())["embedding"]


# ─── Document loading ─────────────────────────────────────────────────────────

def load_local_docs() -> list[dict]:
    """Load all .txt files from data/sample_docs/."""
    docs = []
    for path in sorted(SAMPLE_DOCS.glob("*.txt")):
        content = path.read_text(encoding="utf-8").strip()
        docs.append({"id": path.stem, "source": str(path), "content": content})
    log.info(f"Loaded {len(docs)} local documents")
    return docs


def load_s3_docs() -> list[dict]:
    """Load all documents from S3 bucket under the documents/ prefix."""
    docs = []
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=S3_BUCKET_NAME, Prefix=S3_DOCS_PREFIX):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            if key.endswith(".keep"):
                continue
            body = s3.get_object(Bucket=S3_BUCKET_NAME, Key=key)["Body"].read().decode("utf-8")
            docs.append({"id": Path(key).stem, "source": f"s3://{S3_BUCKET_NAME}/{key}", "content": body})
    log.info(f"Loaded {len(docs)} documents from S3")
    return docs


# ─── Chunking ─────────────────────────────────────────────────────────────────

def chunk_document(doc: dict, chunk_size: int = 800, overlap: int = 80) -> list[dict]:
    """Split a document into overlapping word-based chunks."""
    words  = doc["content"].split()
    chunks = []
    start  = 0
    idx    = 0
    while start < len(words):
        chunk_words = words[start : start + chunk_size]
        chunks.append({
            "id":      f"{doc['id']}_chunk{idx}",
            "source":  doc["source"],
            "content": " ".join(chunk_words),
            "doc_id":  doc["id"],
        })
        start += chunk_size - overlap
        idx   += 1
    return chunks


# ─── Index building ───────────────────────────────────────────────────────────

def build_index(docs: list[dict], chunk_size: int = 800) -> tuple[faiss.Index, list[dict]]:
    """Embed all document chunks and build a FAISS flat index."""
    all_chunks: list[dict] = []
    for doc in docs:
        all_chunks.extend(chunk_document(doc, chunk_size=chunk_size))

    log.info(f"Embedding {len(all_chunks)} chunks with Titan V2...")
    vectors     = []
    total_tokens = 0

    for i, chunk in enumerate(all_chunks):
        vec = embed_text(chunk["content"])
        vectors.append(vec)
        # Rough token count: ~0.75 tokens per word
        total_tokens += len(chunk["content"].split()) * 0.75
        if (i + 1) % 5 == 0:
            log.info(f"  {i+1}/{len(all_chunks)} chunks embedded")
        time.sleep(0.2)  # stay within Bedrock rate limits

    embed_cost = (total_tokens / 1_000_000) * PRICING["embed_per_1m"]
    log.info(f"Total embedding tokens: ~{total_tokens:,.0f} | Cost: ${embed_cost:.4f}")

    # Build FAISS index
    dim   = len(vectors[0])
    index = faiss.IndexFlatL2(dim)
    index.add(np.array(vectors, dtype="float32"))
    log.info(f"FAISS IndexFlatL2 built: {index.ntotal} vectors, dim={dim}")
    return index, all_chunks


def save_index(index: faiss.Index, chunks: list[dict]) -> None:
    """Persist FAISS index + chunk metadata to disk."""
    FAISS_INDEX.parent.mkdir(parents=True, exist_ok=True)
    faiss.write_index(index, str(FAISS_INDEX))
    with open(FAISS_METADATA, "w") as f:
        json.dump(chunks, f, indent=2)
    log.info(f"Saved index → {FAISS_INDEX}")
    log.info(f"Saved metadata → {FAISS_METADATA}")


def load_index() -> tuple[faiss.Index, list[dict]]:
    """Load a previously saved FAISS index from disk."""
    index  = faiss.read_index(str(FAISS_INDEX))
    chunks = json.loads(FAISS_METADATA.read_text())
    log.info(f"Loaded FAISS index: {index.ntotal} vectors")
    return index, chunks


# ─── CLI entrypoint ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build FAISS embedding index")
    parser.add_argument("--source", choices=["local", "s3"], default="local")
    parser.add_argument("--chunk-size", type=int, default=800)
    args = parser.parse_args()

    docs  = load_local_docs() if args.source == "local" else load_s3_docs()
    index, chunks = build_index(docs, chunk_size=args.chunk_size)
    save_index(index, chunks)
    print(f"\n✓ Index ready: {index.ntotal} vectors from {len(docs)} documents")
