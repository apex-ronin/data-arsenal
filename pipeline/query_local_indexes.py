r"""
Query the local FAISS indexes — retrieval round-trip + acceptance check.

No network beyond localhost, no GCP creds. Embeds the query via Ollama
(nomic-embed-text with the required 'search_query: ' prefix), searches
the local index (INDEX_DIR, repo-relative by default), prints top-k with
metadata from the JSONL sidecar. Was LM Studio until 2026-08-10.

Usage:
  python pipeline/query_local_indexes.py legal_corpus "CMMC self-assessment requirement"
  python pipeline/query_local_indexes.py principalities "irrigation district California"
  python pipeline/query_local_indexes.py --acceptance     # run the handoff acceptance gates
                                                            # (assumes the full private dataset;
                                                            # point RONIN_INDEX_DIR at a full build)
"""

import argparse
import json
import os
import sys
from pathlib import Path

import faiss
import numpy as np
import requests

REPO_ROOT = Path(__file__).resolve().parents[1]
INDEX_DIR = Path(os.getenv("RONIN_INDEX_DIR", str(REPO_ROOT / "data" / "indexes")))
EMBED_URL = "http://localhost:11434/api/embed"


def load_manifest(name: str) -> dict:
    manifest = json.loads((INDEX_DIR / "index_manifest.json").read_text(encoding="utf-8"))
    return manifest[name]


def search(name: str, query: str, k: int = 5) -> list[dict]:
    m = load_manifest(name)
    resp = requests.post(EMBED_URL, json={
        "model": m["embedder"],
        "input": [m["query_prefix"] + query],
        "options": {"num_gpu": 0},
    }, timeout=120)
    resp.raise_for_status()
    vec = np.array(resp.json()["embeddings"], dtype=np.float32)
    faiss.normalize_L2(vec)

    index = faiss.read_index(str(INDEX_DIR / m["index_file"]))
    scores, ids = index.search(vec, k)

    meta = (INDEX_DIR / m["metadata_sidecar"]).read_text(encoding="utf-8").splitlines()
    results = []
    for score, i in zip(scores[0], ids[0]):
        if i < 0:
            continue
        rec = json.loads(meta[i])
        rec["_score"] = float(score)
        results.append(rec)
    return results


def acceptance() -> int:
    """Handoff Item 1 gates: CMMC query → 252.204-7021; CA irrigation query → plausible entities."""
    ok = True

    hits = search("legal_corpus", "CMMC self-assessment requirement", k=5)
    ids = [h["id"] for h in hits]
    print("\n[legal_corpus] 'CMMC self-assessment requirement' ->", ids)
    if any("252.204-7021" in i for i in ids):
        print("  PASS — 252.204-7021 in top 5")
    else:
        print("  FAIL — 252.204-7021 not in top 5")
        ok = False

    hits = search("principalities", "irrigation district California", k=5)
    print("\n[principalities] 'irrigation district California' ->")
    plausible = 0
    for h in hits:
        st = h.get("metadata", {}).get("state_code", "?")
        gt = h.get("metadata", {}).get("government_type", "?")
        print(f"  {h['name']}  [{st}, {gt}]  score={h['_score']:.3f}")
        if st == "CA" and "irrigation" in (h["name"] + gt).lower():
            plausible += 1
    if plausible >= 1:
        print(f"  PASS — {plausible} CA irrigation hits in top 5")
    else:
        print("  FAIL — no CA irrigation entities in top 5")
        ok = False

    print("\nACCEPTANCE:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def main() -> None:
    parser = argparse.ArgumentParser(description="Query local FAISS indexes.")
    parser.add_argument("index", nargs="?", choices=["legal_corpus", "principalities"])
    parser.add_argument("query", nargs="?")
    parser.add_argument("-k", type=int, default=5)
    parser.add_argument("--acceptance", action="store_true")
    args = parser.parse_args()

    if args.acceptance:
        sys.exit(acceptance())
    if not (args.index and args.query):
        parser.error("index and query required (or use --acceptance)")
    for h in search(args.index, args.query, args.k):
        title = h.get("title") or h.get("name", "")
        print(f"{h['_score']:.3f}  {h['id']}  {title}")


if __name__ == "__main__":
    main()
