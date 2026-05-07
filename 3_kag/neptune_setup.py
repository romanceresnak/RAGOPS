"""
neptune_setup.py
────────────────
Initialise the Amazon Neptune knowledge graph from data/knowledge_graph/triples.json.
Uses IAM authentication (AWS Signature V4) — no database password required.

Usage:
  python 3_kag/neptune_setup.py --action load    # load triples into Neptune
  python 3_kag/neptune_setup.py --action verify  # check vertex/edge counts
  python 3_kag/neptune_setup.py --action clear   # drop all data (dev only)
"""
from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

import boto3
from gremlin_python.driver import client as gremlin_client, serializer
from gremlin_python.driver.driver_remote_connection import DriverRemoteConnection
from gremlin_python.process.anonymous_traversal import traversal
from requests_aws4auth import AWS4Auth

import sys; sys.path.insert(0, str(Path(__file__).parent.parent))
from config import AWS_REGION, NEPTUNE_ENDPOINT, NEPTUNE_PORT, KG_DIR

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)


# ─── Neptune client factory ───────────────────────────────────────────────────

def get_neptune_client() -> gremlin_client.Client:
    """Create an IAM-authenticated Gremlin client for Neptune."""
    credentials = boto3.Session().get_credentials().get_frozen_credentials()
    auth = AWS4Auth(
        credentials.access_key,
        credentials.secret_key,
        AWS_REGION,
        "neptune-db",
        session_token=credentials.token,
    )
    endpoint = f"wss://{NEPTUNE_ENDPOINT}:{NEPTUNE_PORT}/gremlin"
    log.info(f"Connecting to Neptune: {endpoint}")
    return gremlin_client.Client(
        endpoint,
        "g",
        message_serializer=serializer.GraphSONSerializersV2d0(),
        headers={"Authorization": auth},
    )


def submit(c: gremlin_client.Client, query: str, params: dict | None = None):
    """Execute a Gremlin query and return results."""
    future = c.submitAsync(query, request_options={"args": params or {}})
    return future.result().all().result()


# ─── Graph loading ────────────────────────────────────────────────────────────

def load_graph(triples_path: Path = KG_DIR / "triples.json") -> None:
    """Load vertices and edges from triples.json into Neptune."""
    data = json.loads(triples_path.read_text())
    c    = get_neptune_client()

    log.info(f"Loading {len(data['vertices'])} vertices...")
    for v in data["vertices"]:
        props = " ".join(
            f".property('{k}', '{val}')"
            for k, val in v.items()
            if k not in ("id", "label")
        )
        query = f"g.addV('{v['label']}').property(T.id, '{v['id']}'){props}"
        try:
            submit(c, query)
        except Exception as e:
            log.warning(f"  Vertex {v['id']} may already exist: {e}")

    log.info(f"Loading {len(data['edges'])} edges...")
    for e in data["edges"]:
        query = (
            f"g.V('{e['from']}').addE('{e['label']}').to(g.V('{e['to']}'))"
        )
        try:
            submit(c, query)
        except Exception as ex:
            log.warning(f"  Edge {e['from']}→{e['to']} may already exist: {ex}")

    c.close()
    log.info("Graph load complete")


def verify_graph() -> dict:
    """Return vertex and edge counts from Neptune."""
    c = get_neptune_client()
    v_count = submit(c, "g.V().count()")[0]
    e_count = submit(c, "g.E().count()")[0]
    c.close()
    log.info(f"Graph: {v_count} vertices, {e_count} edges")
    return {"vertices": v_count, "edges": e_count}


def clear_graph() -> None:
    """Drop all vertices and edges (dev/test only)."""
    c = get_neptune_client()
    log.warning("Dropping all graph data...")
    submit(c, "g.V().drop()")
    c.close()
    log.info("Graph cleared")


# ─── CLI ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--action", choices=["load", "verify", "clear"], default="load")
    args = parser.parse_args()

    if args.action == "load":
        load_graph()
        verify_graph()
    elif args.action == "verify":
        counts = verify_graph()
        print(f"Vertices: {counts['vertices']}  |  Edges: {counts['edges']}")
    elif args.action == "clear":
        confirm = input("Type 'yes' to confirm graph deletion: ")
        if confirm.lower() == "yes":
            clear_graph()
