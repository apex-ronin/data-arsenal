# Archived GCP / Vertex / ADK scaffold (retired 2026-06-12, sovereign port)

These files targeted the dead Google Cloud stack — Vertex AI, Vertex Vector Search,
GCS, Cloud Logging, Cloud Run — and the Google ADK agent-starter-pack boilerplate.
GCP was torn down 2026-06-06. data-arsenal is now sovereign-local: data acquisition +
ETL feeding local **FAISS** indexes (nomic-embed-text-v1.5 via LM Studio), see
`pipeline/build_local_indexes.py` and `pipeline/query_local_indexes.py`.

Kept for reference/history only. None of this is on the live path; most is regenerable
starter-pack output and safe to delete.

| File | What it was |
|------|-------------|
| `app/agent.py` | Starter-pack toy ReAct agent (`get_weather`/`get_current_time`) on `gemini-3-flash-preview` via Vertex. Contradicted the repo's "infrastructure only, no agent client code" rule. |
| `app/fast_api_app.py` | Cloud Run FastAPI server; needed GCP ADC + Cloud Logging + GCS artifact bucket to boot. |
| `app/app_utils/telemetry.py` | OpenTelemetry → GCS/Cloud Trace upload. |
| `app/app_utils/typing.py` | `Feedback` model for the dead `/feedback` endpoint. |
| `pipeline/embedder.py` | Vertex AI `text-embedding-005` embedder (model + project gone). Replaced by local nomic-embed in `build_local_indexes.py`. |
| `pipeline/storage.py` | GCS bucket management (`gs://ronin-sovereign-core-embeddings`). |
| `pipeline/deploy_index.py` | Vertex Vector Search index create/deploy. |
| `Dockerfile` | Cloud Run container (port 8080). |
| `tests/integration/test_agent.py`, `test_server_e2e.py` | Tests for the archived agent/server. |
| `tests/eval/*` | ADK eval harness with a `gemini-3-flash-preview` judge model. |

Ground truth: `STATE.md` + `CLAUDE.md`. To rebuild a cloud path (FedRAMP / volume trigger), restore from git history rather than these snapshots.
