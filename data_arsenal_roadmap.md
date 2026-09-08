# DATA ARSENAL ADK — PROJECT ROADMAP

**Level 2 Tracking | Local Environment: `data-arsenal/` workspace**
**Updated: 2026-06-12**

---

## CURRENT STATUS

**SOVEREIGN PORT COMPLETE 2026-06-12.** Legacy audit (Sonnet, read-only) FAILED on 22 findings (2 top/8 high — `LEGACY_AUDIT_FINDINGS_2026-06-12.md`): live Vertex/Gemini code in `app/agent.py` + pipeline was broken since the 2026-06-06 GCP teardown, and ~56MB of tracked entity data (78,291-record census base + ecfr_title_48) violated the data-private rule. `GEMINI.md` was also stale ADK boilerplate.

Full port executed same day (`a5a8888`): all GCP/Vertex code — `app/agent.py`, `fast_api_app`, `app_utils`, `pipeline/{embedder,storage,deploy_index}`, `Dockerfile`, agent eval tests — archived to `_archive_gcp/`. **New live spine is FAISS-only local:** `app/{census,ecfr,puf}_ingest` + `pipeline/{build,query}_local_indexes`; `uv.lock` regenerated GCP-tree-gone. `build_local_indexes.py`'s legal-corpus path was caught pointing at the OneDrive primordial-galaxy copy (would break once that copy was deleted) and repointed to `G:\repos\primordial-galaxy`.

Git history rewritten (`filter-repo` → `accad88`) stripping `data/` from all 5 commits — local history verified data-free, prewrite backup at `G:\repos\data-arsenal-backup-prewrite.bundle`. Port verification **PASS-CLEAN** (6/6 groups, all 22 findings verified, no broken imports — `PORT_VERIFICATION_2026-06-12.md`). 3 remaining lows closed (`f80e41b`: stale Vertex strings, roadmap task, test boilerplate). Both GitHub remotes (apex-ronin + jsnnlsn) force-pushed data-free (`788c687`) — 78K-entity census base + ecfr corpus gone from history on both.

**This is now the active local-primary spine — no longer cold storage.** Embeddings (78,291 records, 289.8MB) live on disk + FAISS index at `G:\AI-Models\indexes`.

---

## WHAT IS COMPLETE (PRE-PORT — archived to `_archive_gcp/` 2026-06-12)

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

## LIVE SPINE (2026-06-12 — current architecture)

| Module | Role |
|---|---|
| `app/census_ingest.py` | Census GOVS local ingest |
| `app/ecfr_ingest.py` | eCFR Title 48 local ingest |
| `app/puf_ingest.py` | PUF local ingest |
| `pipeline/build_local_indexes.py` | Builds FAISS indexes (nomic-embed via LM Studio), checkpointed/resumable. Legal-corpus source now `G:\repos\primordial-galaxy` |
| `pipeline/query_local_indexes.py` | Acceptance-gated local queries |
| `G:\AI-Models\indexes` | FAISS index store (78,291 census vectors) |
| `_archive_gcp/` | All pre-port GCP/Vertex code (agent, fast_api_app, app_utils, embedder/storage/deploy_index, Dockerfile, eval tests) |

---

## SETTLED DECISIONS — DO NOT RELITIGATE

- **us-east5 vs us-central1:** us-east5 is a design choice, not a regulatory mandate. CMMC L2, DFARS 252.239-7010, and FedRAMP Moderate impose no specific region. Census GOVS data is PUBLIC — CUI controls not triggered. us-central1 is correct (FedRAMP High confirmed Mar 2025). us-east5 is not supported for Vertex AI Vector Search. (Confirmed 2026-05-14 regulatory audit.)
- **Embeddings in .gitignore:** `census_govs_embeddings.json` (289.8MB) is gitignored. **Canonical copy is now local only:** `C:\Users\jnel9\OneDrive\Workspaces\GCP_RECOVERY\embeddings\ronin-sovereign-core-embeddings\census-govs\embeddings\`. GCS bucket deleted 2026-06-06.
- **Repo boundary:** This repo is infrastructure only. No agent client code here. `ronin/` consumes the local FAISS indexes (`G:\AI-Models\indexes`) directly — no VPC peering, no live endpoint (Vertex endpoint deleted 2026-06-06).

---

## MAINTENANCE / NEXT ACTIONS

| Task | When | Notes |
|---|---|---|
| (Archived) Cloud Vertex index rebuild | Only if a cloud trigger ever fires | Superseded by the local FAISS pipeline. The old Vertex `deploy_index.py` is in `_archive_gcp/` if ever needed. |
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
| 2026-06-12 | Legacy audit FAIL (22 findings: `LEGACY_AUDIT_FINDINGS_2026-06-12.md`). Sovereign port: GCP/Vertex code archived to `_archive_gcp/`, live spine now FAISS-only local. Git history rewritten — `data/` stripped from all 5 commits. Port verification PASS-CLEAN (6/6 groups: `PORT_VERIFICATION_2026-06-12.md`). 3 remaining lows closed. Both GitHub remotes force-pushed data-free. | a5a8888, accad88, f80e41b, 788c687 |
