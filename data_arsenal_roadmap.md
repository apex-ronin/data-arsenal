# DATA ARSENAL ADK — PROJECT ROADMAP

**Level 2 Tracking | Local Environment: `data-arsenal/` workspace**
**Updated: 2026-06-06**

---

## CURRENT STATUS

**Pipeline items complete. GCP torn down 2026-06-06.** ronin-sovereign-core deleted — Vertex index, endpoint, and GCS bucket are gone.
Embeddings (289.8 MB, 78,291 records) confirmed on local disk at `GCP_RECOVERY\embeddings\`. Source of truth is local.
This workspace is in cold storage — no active build work until cloud rebuild trigger fires.

---

## WHAT IS COMPLETE

| Item | Status | Details |
|---|---|---|
| 1. Embedding Generator (`pipeline/embedder.py`) | ✅ COMPLETE | 392 batches × 200 items. 78,291 records. `text-embedding-005`. Validated schema. (2026-04-09) |
| 2. Secure GCS Sync (`pipeline/storage.py`) | ✅ COMPLETE | `gs://ronin-sovereign-core-embeddings/`. Uniform bucket-level access + PAP enforced. **us-central1** (us-east5 not mandated — confirmed 2026-05-14 regulatory audit). 290MB uploaded. |
| 3. Sovereign Index Deployment (`pipeline/deploy_index.py`) | ✅ COMPLETE | Tree-AH index. VPC-peered private endpoint. 78,256 vectors indexed. DEPLOYED 2026-05-14. |

**Former endpoint (DELETED 2026-06-06 with ronin-sovereign-core):**
```
Index / Endpoint resource IDs: [redacted — GCP project + Vertex resources deleted 2026-06-06]
Deployed index ID: census_govs_2022
```
Superseded by the local FAISS pipeline (`pipeline/build_local_indexes.py`). The old Vertex
deploy script is archived at `_archive_gcp/pipeline/deploy_index.py` if a cloud path is ever rebuilt.

---

## SETTLED DECISIONS — DO NOT RELITIGATE

- **us-east5 vs us-central1:** us-east5 is a design choice, not a regulatory mandate. CMMC L2, DFARS 252.239-7010, and FedRAMP Moderate impose no specific region. Census GOVS data is PUBLIC — CUI controls not triggered. us-central1 is correct (FedRAMP High confirmed Mar 2025). us-east5 is not supported for Vertex AI Vector Search. (Confirmed 2026-05-14 regulatory audit.)
- **Embeddings in .gitignore:** `census_govs_embeddings.json` (289.8MB) is gitignored. **Canonical copy is now local only:** `C:\Users\jnel9\OneDrive\Workspaces\GCP_RECOVERY\embeddings\ronin-sovereign-core-embeddings\census-govs\embeddings\`. GCS bucket deleted 2026-06-06.
- **Repo boundary:** This repo is infrastructure only. No agent client code here. `ronin/` consumes the endpoint via VPC peering.

---

## MAINTENANCE / NEXT ACTIONS

| Task | When | Notes |
|---|---|---|
| Rebuild Vertex index from local embeddings | On cloud trigger | `deploy_index.py` is idempotent. Embeddings on disk, ready to re-deploy. |
| Delta refresh pipeline (3x daily Cloud Scheduler) | Phase 3F / before enterprise | Suspended until cloud rebuilt. |
| SAM/USASpending enrichment (2B.2–2B.4) | Post Phase 3F | Suspended. Adds registration data + award history to entity records. |

---

## SESSION LOG

| Date | Key Actions | Commit |
|---|---|---|
| 2026-04-09 | embedder.py + storage.py written and validated | — |
| 2026-04-18 | deploy_index.py written, LRO restarted | — |
| 2026-05-14 | Regulatory audit: us-east5 not mandated. Storage fixed to us-central1. Index DEPLOYED. VPC-peered endpoint live. | — |
| 2026-05-14 | Repository reinitialized after OneDrive git corruption. Embeddings added to .gitignore. | latest |
| 2026-06-03 | Roadmap synced to STATE.md ground truth. Project marked complete/maintenance. | — |
| 2026-06-10 | Local retrieval rebuild (handoff Item 1): Vertex embeddings orphaned (embedder model gone) — re-embedded locally via LM Studio nomic-embed-text-v1.5, FAISS indexes on G:\AI-Models\indexes with manifest. pipeline/build_local_indexes.py (checkpointed) + query_local_indexes.py (acceptance gates). venv rebuilt (uv). | — |
