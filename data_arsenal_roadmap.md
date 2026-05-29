# DATA ARSENAL ADK — PROJECT ROADMAP

**Level 2 Tracking | Local Environment: `data-arsenal/` workspace**

---

## CLAUDE CODE DIRECTIVES - CURRENT SESSION
**Task Assigned:** Phase 3D - Vertex AI Vector Search Ingestion Pipeline
**Priority:** Highest (Per Gemini Global Arbitrator)

### Current Priority: CMMC Level 2 Sovereign Infrastructure
**Goal:** Build the GCP deployment scripts to embed and ingest the 78K Census GOVS JSONL into a strictly private, VPC-bound Vertex AI Vector Search index.

### Execution Sequence (Continuous Autonomy Authorized)
Execute the following sequentially. DO NOT mix client code (agent tools) into this repository. This repo is strictly infrastructure.

- [x] **1. Embedding Generator:** Create `pipeline/embedder.py` leveraging Vertex AI's `text-embedding-005` model.
    - **Constraints:** Read the Census GOVS JSONL. Crucially, drop batch size to exactly **200 items per batch** to avoid API rate limits. Output `.jsonl` files formatted as `{"id": "...", "embedding": [...]}` compliant with Vector Search.
    - **Completed:** 2026-04-09 | 392 batches × 200 | dry-run validated 78,291 records → correct schema
- [x] **2. Secure GCS Sync:** Create `pipeline/storage.py` to push embeddings to GCS.
    - **Constraints:** Target region MUST be `us-east5`. The bucket must be instantiated with **Uniform Bucket-Level Access** enabled and **Public Access Prevention (Enforced)**. Absolutely no public bleed, to maintain CMMC Level 2 CUI compliance.
    - **Completed:** 2026-04-09 | Uniform access + PAP enforced | compliance patch logic included
- [x] **3. Sovereign Index Deployment:** Create `pipeline/deploy_index.py`.
    - **Constraints:** 
        - Use `create_tree_ah_index()` due to the 78K corpus size. Target `us-central1` (Vector Search not supported in us-east5; compliance unlock is Assured Workloads + Org Policy, not region selection).
        - **Data Handoff:** You must build an async polling loop to check `index.resource_name` for a DEPLOYED status which will take 30-60 minutes.
        - **VPC Enforcement:** Do not deploy a default public endpoint. The `aiplatform.MatchingEngineIndexEndpoint.create()` call must specify a private `network` kwarg (VPC-peered endpoint) to prevent public internet CUI leakage.
        - Only after the long DEPLOYED wait, call `deploy_index()`.
    - **Completed:** 2026-04-09 | Script written | **DEPLOYED 2026-05-14** | 78,256 vectors indexed | VPC-peered endpoint live
    - **Index:** `projects/776676408891/locations/us-central1/indexes/1040747129317883904`
    - **Endpoint:** `projects/776676408891/locations/us-central1/indexEndpoints/6319845501898326016`
    - **Deployed index ID:** `census_govs_2022`

*Note for Claude: You have continuous autonomy within this `data-arsenal/` boundary. Because Step 3 has a 30-60 minute wait loop, coordinate with the terminal environment carefully so you don't time out. When done, output the private `endpoint_id` so we can wire the `ronin/` client.*

---

## EXECUTION RUNBOOK (CLI REFERENCE)
Once the scripts are built, execute the pipeline sequentially in your terminal using the following parameters:

```bash
# Step 1 (~20 min API time)
export GCP_PROJECT_ID=ronin-sovereign-core
uv run python pipeline/embedder.py

# Step 2
export GCS_EMBEDDINGS_BUCKET=ronin-sovereign-core-embeddings
uv run python pipeline/storage.py
# → prints CONTENTS_DELTA_URI

# Step 3 (30-60 min LRO — run in a persistent terminal)
export VPC_NETWORK=projects/{project_number}/global/networks/{network_name}
export CONTENTS_DELTA_URI=gs://...
uv run python pipeline/deploy_index.py
# → prints endpoint_resource_name to wire into ronin/
```
