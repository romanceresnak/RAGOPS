"""
config.py — centralised settings loaded from .env
All pipeline modules import from here; never read os.environ directly.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# =============================================================================
# AWS
# =============================================================================
AWS_REGION: str = os.getenv("AWS_REGION", "us-east-1")
APP_ROLE_ARN: str = os.getenv("APP_ROLE_ARN", "")

# =============================================================================
# BEDROCK
# =============================================================================
BEDROCK_MODEL_ID: str = os.getenv(
    "BEDROCK_MODEL_ID",
    "us.anthropic.claude-sonnet-4-6",
)
BEDROCK_EMBED_MODEL: str = os.getenv(
    "BEDROCK_EMBED_MODEL",
    "amazon.titan-embed-text-v2:0",
)
MAX_TOKENS: int = 1024

# =============================================================================
# S3
# =============================================================================
S3_BUCKET_NAME: str = os.getenv("S3_BUCKET_NAME", "")
S3_DOCS_PREFIX: str = "documents/"
S3_EMBEDDINGS_PREFIX: str = "embeddings/"
S3_BENCHMARK_PREFIX: str = "benchmark-results/"

# =============================================================================
# NEPTUNE
# =============================================================================
NEPTUNE_ENDPOINT: str = os.getenv("NEPTUNE_ENDPOINT", "")
NEPTUNE_PORT: int = int(os.getenv("NEPTUNE_PORT", "8182"))

# =============================================================================
# BENCHMARK
# =============================================================================
BENCHMARK_RUNS: int = int(os.getenv("BENCHMARK_RUNS", "3"))
TOP_K_RAG: int = int(os.getenv("TOP_K_RAG", "3"))
CAG_CACHE_WARMUP: bool = os.getenv("CAG_CACHE_WARMUP", "true").lower() == "true"

# =============================================================================
# TOKEN PRICING  (Claude 3.5 Sonnet on Bedrock, USD per 1 M tokens)
# https://aws.amazon.com/bedrock/pricing/
# =============================================================================
PRICING = {
    "input_per_1m":        3.00,   # standard input
    "output_per_1m":      15.00,   # generated output
    "cache_write_per_1m":  3.75,   # writing to prompt cache (+25 %)
    "cache_read_per_1m":   0.30,   # reading from prompt cache (−90 %)
    "embed_per_1m":        0.02,   # Titan Embeddings V2
}

# =============================================================================
# PATHS (local)
# =============================================================================
import pathlib

ROOT_DIR       = pathlib.Path(__file__).parent
DATA_DIR       = ROOT_DIR / "data"
SAMPLE_DOCS    = DATA_DIR / "sample_docs"
KG_DIR         = DATA_DIR / "knowledge_graph"
BENCHMARK_DIR  = ROOT_DIR / "benchmark"
VISUALIZE_DIR  = ROOT_DIR / "visualize"
FAISS_INDEX    = ROOT_DIR / "data" / "faiss_index.bin"
FAISS_METADATA = ROOT_DIR / "data" / "faiss_metadata.json"
