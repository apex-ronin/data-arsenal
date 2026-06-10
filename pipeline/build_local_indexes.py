r"""
Local FAISS index builder — sovereign retrieval layer (post-GCP-teardown).

Replaces the deleted Vertex AI Vector Search stack. Embeds via LM Studio's
OpenAI-compatible /v1/embeddings endpoint (nomic-embed-text-v1.5, 768 dims,
local CPU — no network, no GCP creds).

Builds two indexes on G:\ (NOT OneDrive — OneDrive corrupted 2 git repos 2026-05-29):
  G:\AI-Models\indexes\legal_corpus.faiss     + legal_corpus_meta.jsonl
  G:\AI-Models\indexes\principalities.faiss   + principalities_meta.jsonl
Each with an index_manifest.json recording embedder name/version/dims —
never mix embedders in one index.

Sources:
  legal corpus    — primordial-galaxy/data/legal_corpus/*.json (104 clauses, 8 files)
  principalities  — data/processed/census/master_gov_units_2022.jsonl (78,291 records)

Checkpointed: embeddings are written in .npy parts; rerun resumes from the
last complete part. Safe to kill and restart.

Usage:
  python pipeline/build_local_indexes.py                 # build both
  python pipeline/build_local_indexes.py --only legal    # legal corpus only
  python pipeline/build_local_indexes.py --only princ    # principalities only
"""

import argparse
import datetime
import json
import logging
import time
from pathlib import Path

import faiss
import numpy as np
import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# --- Embedder config (record in manifest; never mix embedders in one index) ---
EMBED_URL = "http://localhost:1234/v1/embeddings"
EMBED_MODEL = "text-embedding-nomic-embed-text-v1.5"
EMBED_DIMS = 768
# nomic-embed v1.5 task prefixes — documents and queries MUST use these
DOC_PREFIX = "search_document: "
QUERY_PREFIX = "search_query: "
BATCH_SIZE = 64          # strings per /v1/embeddings request
PART_SIZE = 1024         # records per checkpoint part (multiple of BATCH_SIZE)
MAX_RETRIES = 5

REPO_ROOT = Path(__file__).resolve().parents[1]
LEGAL_CORPUS_DIR = Path(
    r"C:\Users\jnel9\OneDrive\Workspaces\AI-Agents\Active\primordial-galaxy\data\legal_corpus"
)
ENTITY_JSONL = REPO_ROOT / "data" / "processed" / "census" / "master_gov_units_2022.jsonl"

INDEX_DIR = Path(r"G:\AI-Models\indexes")
CHECKPOINT_DIR = INDEX_DIR / ".checkpoints"


def embed_batch(texts: list[str]) -> np.ndarray:
    """Embed one batch of already-prefixed strings; retries on transient failure."""
    payload = {"model": EMBED_MODEL, "input": texts}
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.post(EMBED_URL, json=payload, timeout=300)
            resp.raise_for_status()
            data = resp.json()["data"]
            # API preserves input order; verify by index field anyway
            data.sort(key=lambda d: d["index"])
            return np.array([d["embedding"] for d in data], dtype=np.float32)
        except Exception as e:
            if attempt == MAX_RETRIES:
                raise
            wait = 2**attempt
            logger.warning("Embed batch failed (attempt %d/%d): %s — retrying in %ds",
                           attempt, MAX_RETRIES, e, wait)
            time.sleep(wait)


def load_legal_corpus() -> list[dict]:
    """All clauses from the 8 corpus JSONs. Embed text = title + keywords + clause text."""
    records = []
    for path in sorted(LEGAL_CORPUS_DIR.glob("*.json")):
        with open(path, encoding="utf-8") as f:
            clauses = json.load(f)
        for c in clauses:
            records.append({
                "id": c["id"],
                "source_file": path.name,
                "title": c.get("title", ""),
                "clause_text": c.get("clause_text", ""),
                "embed_text": f"{c['id']} {c.get('title', '')}. "
                              f"Keywords: {c.get('vector', '')}. {c.get('clause_text', '')}",
            })
    logger.info("Legal corpus: %d clauses from %d files", len(records),
                len(list(LEGAL_CORPUS_DIR.glob('*.json'))))
    return records


def load_entities() -> list[dict]:
    """78,291 Census GOVS entity records. Embed text = the 'content' field (same as Vertex run)."""
    records = []
    with open(ENTITY_JSONL, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            records.append({
                "id": r["id"],
                "name": r.get("name", ""),
                "metadata": r.get("metadata", {}),
                "contact_skeleton": r.get("contact_skeleton", {}),
                "embed_text": r["content"],
            })
    logger.info("Principalities: %d entity records", len(records))
    return records


def embed_corpus(name: str, records: list[dict]) -> np.ndarray:
    """Embed all records with per-part checkpointing; resumes from complete parts."""
    ckpt = CHECKPOINT_DIR / name
    ckpt.mkdir(parents=True, exist_ok=True)

    n_parts = (len(records) + PART_SIZE - 1) // PART_SIZE
    parts = []
    t0 = time.time()
    for p in range(n_parts):
        part_file = ckpt / f"part_{p:05d}.npy"
        lo, hi = p * PART_SIZE, min((p + 1) * PART_SIZE, len(records))
        if part_file.exists():
            arr = np.load(part_file)
            if arr.shape == (hi - lo, EMBED_DIMS):
                parts.append(arr)
                continue  # complete part — skip
            part_file.unlink()  # partial/corrupt — redo
        chunks = []
        for b in range(lo, hi, BATCH_SIZE):
            texts = [DOC_PREFIX + r["embed_text"] for r in records[b:min(b + BATCH_SIZE, hi)]]
            chunks.append(embed_batch(texts))
        arr = np.vstack(chunks)
        np.save(part_file, arr)
        parts.append(arr)
        done = hi
        rate = done / max(time.time() - t0, 1e-9)
        logger.info("[%s] part %d/%d — %d/%d records (%.0f rec/s, ~%.0f min left)",
                    name, p + 1, n_parts, done, len(records), rate,
                    (len(records) - done) / max(rate, 1e-9) / 60)
    return np.vstack(parts)


def build_index(name: str, records: list[dict], vectors: np.ndarray,
                source_desc: str) -> None:
    """Normalize → IndexFlatIP (cosine) → write index + metadata sidecar + manifest."""
    assert vectors.shape == (len(records), EMBED_DIMS), vectors.shape
    faiss.normalize_L2(vectors)
    index = faiss.IndexFlatIP(EMBED_DIMS)
    index.add(vectors)

    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    faiss.write_index(index, str(INDEX_DIR / f"{name}.faiss"))

    with open(INDEX_DIR / f"{name}_meta.jsonl", "w", encoding="utf-8") as f:
        for r in records:
            meta = {k: v for k, v in r.items() if k != "embed_text"}
            f.write(json.dumps(meta, ensure_ascii=False) + "\n")

    manifest_path = INDEX_DIR / "index_manifest.json"
    manifest = {}
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest[name] = {
        "embedder": EMBED_MODEL,
        "embedder_serving": "LM Studio /v1/embeddings (localhost:1234)",
        "dimensions": EMBED_DIMS,
        "metric": "cosine (L2-normalized IndexFlatIP)",
        "doc_prefix": DOC_PREFIX,
        "query_prefix": QUERY_PREFIX,
        "record_count": len(records),
        "source": source_desc,
        "index_file": f"{name}.faiss",
        "metadata_sidecar": f"{name}_meta.jsonl",
        "built_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    logger.info("[%s] index written: %d vectors → %s", name, index.ntotal,
                INDEX_DIR / f"{name}.faiss")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build local FAISS indexes via LM Studio embedder.")
    parser.add_argument("--only", choices=["legal", "princ"], help="Build a single index.")
    args = parser.parse_args()

    if args.only in (None, "legal"):
        records = load_legal_corpus()
        vectors = embed_corpus("legal_corpus", records)
        build_index("legal_corpus", records, vectors,
                    "primordial-galaxy/data/legal_corpus/*.json")

    if args.only in (None, "princ"):
        records = load_entities()
        vectors = embed_corpus("principalities", records)
        build_index("principalities", records, vectors,
                    "data-arsenal/data/processed/census/master_gov_units_2022.jsonl "
                    "(2022 Census of Governments)")


if __name__ == "__main__":
    main()
