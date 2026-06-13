# data-arsenal

Sovereign-local **data acquisition + ETL** layer for the Apex Ronin stack. It ingests
authoritative government data, normalizes it, and builds **local FAISS retrieval indexes** —
no cloud, no Vertex, no Gemini. Tooling is shareable; **the data layer is never tracked in git**
(`data/` is gitignored — reconstruct it via the pipeline below).

> The repo was originally scaffolded from Google's `agent-starter-pack` (ADK/Vertex/Cloud Run).
> That entire stack was retired in the 2026-06-12 sovereign port and lives under `_archive_gcp/`
> for reference only. Ground truth is `STATE.md` + `CLAUDE.md`.

## Architecture

```
Acquisition (app/)                Indexing (pipeline/)              Retrieval
  census_ingest.py    ─┐            build_local_indexes.py  ─┐         query_local_indexes.py
  ecfr_ingest.py       ├─ data/ ──>   (nomic-embed via       ├─> G:\AI-Models\indexes\  ──> top-k + metadata
  puf_to_master_jsonl  ─┘  (local)     LM Studio, FAISS)     ─┘    index_manifest.json
```

- **Embedder:** `nomic-embed-text-v1.5` (768-dim) served by **LM Studio** at `localhost:1234`. No network beyond localhost, no GCP creds.
- **Indexes:** FAISS `IndexFlatIP` (cosine) on `G:\AI-Models\indexes\`, each with a sidecar `*_meta.jsonl` and a shared `index_manifest.json` recording embedder/dims/prefixes — never mix embedders in one index.
- **Two indexes:** `legal_corpus` (regulatory clauses from `primordial-galaxy/data/legal_corpus`) and `principalities` (78,291 Census of Governments entities).

## Project Structure

```
data-arsenal/
├── app/                       # Data acquisition / ETL
│   ├── census_ingest.py       # Census GOVS CSV -> structured JSON
│   ├── ecfr_ingest.py         # eCFR Title 48 (FAR) scrape
│   └── puf_to_master_jsonl.py # Census Excel -> master_gov_units_2022.jsonl
├── pipeline/                  # Sovereign retrieval pipeline
│   ├── build_local_indexes.py # Embed + build FAISS indexes
│   └── query_local_indexes.py # Query + acceptance gates
├── data/                      # gitignored — local only, never committed
├── _archive_gcp/              # Retired GCP/Vertex/ADK scaffold (reference only)
├── Makefile · pyproject.toml · CLAUDE.md
```

## Requirements

- **uv** — Python package manager: `make install`
- **LM Studio** running locally with `nomic-embed-text-v1.5` served on `localhost:1234` (for index build/query)
- The source data placed under `data/` (not tracked in git)

## Commands

| Command | Description |
| --- | --- |
| `make install` | Install dependencies with uv |
| `make build-indexes` | Build both FAISS indexes (`ONLY=legal` or `ONLY=princ` for one) |
| `make acceptance` | Run the retrieval acceptance gates (CMMC clause + CA irrigation district) |
| `make test` | Run unit tests |
| `make lint` | codespell + ruff + ty |

## Data-privacy rule

The data layer (`data/`, corpus contents, the 78K entity base) must **never** be shared on
public GitHub — it stays local. Only the acquisition/pipeline *code* is shareable. See `CLAUDE.md`.
