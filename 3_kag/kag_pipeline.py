"""
kag_pipeline.py
───────────────
Knowledge-Augmented Generation (KAG) pipeline.

Flow:
  1. Extract entity name from the query (simple keyword match or NER).
  2. Query Neptune for the subgraph around that entity (depth 2).
  3. Serialise graph paths to natural-language facts.
  4. Inject facts as context into Bedrock prompt (much smaller than RAG context).

KAG produces the fewest input tokens of all three methods because only
structured, relevant facts are passed — not raw document chunks.
"""
from __future__ import annotations

import json
import logging
import re
import time
from pathlib import Path

import boto3
from gremlin_python.driver import client as gremlin_client, serializer
from requests_aws4auth import AWS4Auth

import sys; sys.path.insert(0, str(Path(__file__).parent.parent))
from config import (
    AWS_REGION, BEDROCK_MODEL_ID, MAX_TOKENS,
    NEPTUNE_ENDPOINT, NEPTUNE_PORT, PRICING,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

bedrock = boto3.client("bedrock-runtime", region_name=AWS_REGION)

# Known entity names in the graph (for simple keyword extraction)
KNOWN_ENTITIES = [
    "Bedrock", "Neptune", "S3", "Lambda", "IAM", "CloudWatch",
    "Claude-3.5-Sonnet", "Claude-3-Haiku", "TitanEmbedV2",
    "PromptCaching", "StreamingResponse", "IAMDatabaseAuth",
    "RAG", "CAG", "KAG", "FAISS", "Terraform", "NeptuneServerless",
    "VectorSearch", "GraphTraversal", "KnowledgeGraph", "EmbeddingVector",
]


# ─── Neptune client ───────────────────────────────────────────────────────────

def _get_client() -> gremlin_client.Client:
    creds = boto3.Session().get_credentials().get_frozen_credentials()
    auth  = AWS4Auth(creds.access_key, creds.secret_key, AWS_REGION, "neptune-db",
                     session_token=creds.token)
    return gremlin_client.Client(
        f"wss://{NEPTUNE_ENDPOINT}:{NEPTUNE_PORT}/gremlin",
        "g",
        message_serializer=serializer.GraphSONSerializersV2d0(),
        headers={"Authorization": auth},
    )


# ─── Entity extraction ────────────────────────────────────────────────────────

def extract_entity(query: str) -> str | None:
    """
    Simple keyword-based entity extractor.
    Returns the first known entity found in the query (case-insensitive).
    Falls back to None if no known entity is found.
    """
    query_lower = query.lower()
    for entity in KNOWN_ENTITIES:
        if entity.lower() in query_lower:
            return entity
    # Fallback: try to extract a capitalised word
    match = re.search(r'\b[A-Z][a-zA-Z0-9\-\.]+\b', query)
    return match.group(0) if match else None


# ─── Graph retrieval ──────────────────────────────────────────────────────────

def query_graph(entity_name: str, depth: int = 2, max_paths: int = 40) -> list[str]:
    """
    Traverse Neptune up to `depth` hops from the entity vertex.
    Returns a list of human-readable fact strings.
    """
    c = _get_client()
    try:
        # Find vertex by name property
        results = c.submit(
            f"g.V().has('name', '{entity_name}')"
            f".repeat(bothE().otherV().simplePath()).times({depth})"
            f".path().limit({max_paths})"
        ).all().result()
    except Exception as e:
        log.warning(f"Graph query failed for entity '{entity_name}': {e}")
        c.close()
        return []
    c.close()

    facts = []
    for path in results:
        # path.objects is a list alternating [vertex, edge, vertex, edge, vertex ...]
        objects = getattr(path, "objects", path) if hasattr(path, "objects") else path
        parts   = []
        for obj in objects:
            if isinstance(obj, dict):
                # Vertex or edge represented as dict
                name  = obj.get("properties", {}).get("name", [{}])
                label = obj.get("label", "")
                if isinstance(name, list) and name:
                    parts.append(str(name[0].get("value", label)))
                else:
                    parts.append(label)
        if len(parts) >= 2:
            facts.append(" → ".join(parts))

    log.info(f"KAG retrieved {len(facts)} facts for entity '{entity_name}'")
    return facts


def serialise_facts(facts: list[str]) -> str:
    """Convert a list of graph facts into a compact context string."""
    if not facts:
        return "(No graph facts found for this entity)"
    numbered = "\n".join(f"{i+1}. {fact}" for i, fact in enumerate(facts))
    return f"Knowledge Graph Facts:\n{numbered}"


# ─── KAG generation ──────────────────────────────────────────────────────────

def kag_generate(
    query: str,
    entity: str | None = None,
    model_id: str = BEDROCK_MODEL_ID,
) -> dict:
    """
    Full KAG pipeline: extract entity → graph query → Bedrock generation.
    """
    if entity is None:
        entity = extract_entity(query)
        log.info(f"Extracted entity: {entity}")

    facts   = query_graph(entity, depth=2) if entity else []
    context = serialise_facts(facts)

    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": MAX_TOKENS,
        "system": (
            "You are a precise AWS knowledge assistant. "
            "Answer using ONLY the structured graph facts provided. "
            "Each fact is a relationship path: Entity → relationship → Entity. "
            "If the facts do not contain the answer, clearly state that."
        ),
        "messages": [
            {"role": "user", "content": f"{context}\n\nQuestion: {query}"}
        ],
    }

    t0       = time.perf_counter()
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

    input_tokens  = usage["input_tokens"]
    output_tokens = usage["output_tokens"]
    cost = (
          (input_tokens  / 1_000_000) * PRICING["input_per_1m"]
        + (output_tokens / 1_000_000) * PRICING["output_per_1m"]
    )

    log.info(
        f"KAG | entity={entity} | facts={len(facts)} | "
        f"input={input_tokens} | output={output_tokens} | "
        f"cost=${cost:.6f} | {latency_ms:.0f}ms"
    )

    return {
        "method":        "KAG",
        "query":         query,
        "answer":        answer,
        "entity":        entity,
        "facts_count":   len(facts),
        "input_tokens":  input_tokens,
        "output_tokens": output_tokens,
        "cached_tokens": 0,
        "cost_usd":      cost,
        "latency_ms":    latency_ms,
        "model_id":      model_id,
    }


# ─── CLI demo ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    query = "What does Amazon Bedrock integrate with?"
    print(f"Query: {query}\n")
    result = kag_generate(query)
    print(f"Entity detected: {result['entity']}")
    print(f"Facts retrieved: {result['facts_count']}")
    print(f"Answer:\n{result['answer']}\n")
    print(f"Input tokens:  {result['input_tokens']}")
    print(f"Output tokens: {result['output_tokens']}")
    print(f"Cost:          ${result['cost_usd']:.6f}")
    print(f"Latency:       {result['latency_ms']:.0f} ms")
