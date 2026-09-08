# data-arsenal (public sample)

Core infrastructure for [`primordial-galaxy`](https://github.com/apex-ronin/primordial-galaxy)
— the sovereign-local **data acquisition + ETL layer** that builds the FAISS
retrieval indexes its opportunity-scoring and antibody pipeline queries at
runtime. No cloud, no Vertex, no Gemini.

**This repo ships small, real, non-growing token samples** of the two
datasets it indexes — sourced directly from the public
[`legal-corpus`](https://github.com/apex-ronin/legal-corpus) (20 clauses)
and [`principalities-index`](https://github.com/apex-ronin/principalities-index)
(50 entities) repos — so the full acquire → embed → index → retrieve
pipeline can be built and run end to end as a working demo. The private
version indexes the full 104-clause / 78,291-entity datasets.

## Architecture

```
Acquisition (app/)                Indexing (pipeline/)              Retrieval
  census_ingest.py    ─┐            build_local_indexes.py  ─┐         query_local_indexes.py
  ecfr_ingest.py       ├─ data/ ──>   (nomic-embed via       ├─> data/indexes/  ──> top-k + metadata
  puf_to_master_jsonl  ─┘  (local)     Ollama, FAISS)        ─┘    index_manifest.json
```

- **Embedder:** `nomic-embed-text` (768-dim) served by **Ollama** at `localhost:11434` — no network beyond localhost, no GCP creds. (Was LM Studio until 2026-08-10, when it was retired from the stack; this repo's pipeline is rewired to match.)
- **Indexes:** FAISS `IndexFlatIP` (cosine) under `data/indexes/` (repo-relative by default, override with `RONIN_INDEX_DIR`), each with a sidecar `*_meta.jsonl` and a shared `index_manifest.json` recording embedder/dims — never mix embedders in one index.
- **Two indexes:** `legal_corpus` (from `data/legal_corpus/`, mirrors `apex-ronin/legal-corpus`) and `principalities` (from `data/processed/census/`, mirrors `apex-ronin/principalities-index`).

Both indexes were built and queried live against this box's real Ollama
instance as part of preparing this repo — this isn't just code that's
supposed to work, it's proven to run.

## Requirements

- Python 3 with `faiss-cpu`, `numpy`, `requests`
- **Ollama** running locally with `nomic-embed-text` pulled: `ollama pull nomic-embed-text`

## Commands

```bash
python pipeline/build_local_indexes.py                 # build both indexes from the bundled sample
python pipeline/query_local_indexes.py legal_corpus "cybersecurity assessment requirement"
python pipeline/query_local_indexes.py principalities "county government"
```

To build against the full private datasets instead of the bundled sample,
set `LEGAL_CORPUS_DIR` / point `data/processed/census/master_gov_units_2022.jsonl`
at a full private checkout — the code doesn't change.

## License

[PolyForm Shield 1.0.0](LICENSE) — free to use, may not be used to build a
competing product.
