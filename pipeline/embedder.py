"""
Vertex AI Vector Search — Embedding Generator
Phase 3D: Census GOVS JSONL Ingestion Pipeline

Model:      text-embedding-005 (RETRIEVAL_DOCUMENT task type)
Batch size: 200 items (rate-limit safe)
Output:     data/processed/embeddings/census_govs_embeddings.jsonl
Format:     {"id": "...", "embedding": [...]} per line (Vector Search compliant)

CMMC Level 2 | Region: us-east5
"""

import argparse
import json
import logging
import os
import time
from pathlib import Path

import vertexai
from vertexai.language_models import TextEmbeddingInput, TextEmbeddingModel

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration (override via environment variables)
# ---------------------------------------------------------------------------
PROJECT_ID: str = os.environ.get("GCP_PROJECT_ID", "")
LOCATION: str = os.environ.get("GCP_LOCATION", "us-east5")
MODEL_ID: str = "text-embedding-005"
BATCH_SIZE: int = 200                      # per roadmap constraint
INTER_BATCH_DELAY_SECS: float = 1.0       # courtesy pacing between batches

INPUT_JSONL = Path("data/processed/census/master_gov_units_2022.jsonl")
OUTPUT_DIR = Path("data/processed/embeddings")
OUTPUT_FILE = OUTPUT_DIR / "census_govs_embeddings.jsonl"

# text-embedding-005 output dimensionality
EMBEDDING_DIMS: int = 768


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------

def load_records(path: Path) -> list[dict]:
    records = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    logger.info("Loaded %d records from %s", len(records), path)
    return records


def embed_batch(
    model: TextEmbeddingModel,
    batch: list[dict],
) -> list[dict]:
    """Call Vertex AI to embed one batch; return Vector Search-formatted dicts."""
    inputs = [
        TextEmbeddingInput(
            text=record["content"],
            task_type="RETRIEVAL_DOCUMENT",
        )
        for record in batch
    ]
    response = model.get_embeddings(inputs)
    return [
        {"id": record["id"], "embedding": emb.values}
        for record, emb in zip(batch, response)
    ]


def run(dry_run: bool = False) -> Path:
    """
    Full embedding pipeline.

    Args:
        dry_run: If True, skip API calls and emit zero-vectors for local
                 schema validation without incurring Vertex AI costs.

    Returns:
        Path to the output JSONL file.
    """
    if not dry_run:
        if not PROJECT_ID:
            raise EnvironmentError("GCP_PROJECT_ID environment variable is required.")
        vertexai.init(project=PROJECT_ID, location=LOCATION)
        model = TextEmbeddingModel.from_pretrained(MODEL_ID)
        logger.info("Initialized Vertex AI: project=%s location=%s model=%s", PROJECT_ID, LOCATION, MODEL_ID)
    else:
        model = None
        logger.info("[DRY RUN] Skipping Vertex AI init — emitting zero-vectors (%d dims)", EMBEDDING_DIMS)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    records = load_records(INPUT_JSONL)

    total_batches = (len(records) + BATCH_SIZE - 1) // BATCH_SIZE
    logger.info(
        "Processing %d records in %d batches of %d",
        len(records), total_batches, BATCH_SIZE,
    )

    all_embeddings: list[dict] = []

    for batch_num, start in enumerate(range(0, len(records), BATCH_SIZE), start=1):
        batch = records[start : start + BATCH_SIZE]
        logger.info(
            "Batch %d/%d — embedding %d records...",
            batch_num, total_batches, len(batch),
        )

        if dry_run:
            embedded = [
                {"id": r["id"], "embedding": [0.0] * EMBEDDING_DIMS}
                for r in batch
            ]
        else:
            embedded = embed_batch(model, batch)

        all_embeddings.extend(embedded)

        # Pacing delay between batches (skip after the final batch)
        if batch_num < total_batches and not dry_run:
            time.sleep(INTER_BATCH_DELAY_SECS)

    # Write single consolidated JSONL (Vector Search ingests the entire file)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        for record in all_embeddings:
            f.write(json.dumps(record) + "\n")

    logger.info(
        "Wrote %d embedding records → %s",
        len(all_embeddings), OUTPUT_FILE,
    )
    return OUTPUT_FILE


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate Vertex AI embeddings for the Census GOVS JSONL corpus."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Skip API calls; emit zero-vectors for local schema validation.",
    )
    args = parser.parse_args()

    output_path = run(dry_run=args.dry_run)
    print(f"\nEmbeddings written to: {output_path}")
