# LEGACY AUDIT FINDINGS — data-arsenal
**Audit date:** 2026-06-12  
**Auditor:** Claude Sonnet 4.6 (read-only; no files edited)  
**Scope:** All files tracked by `git ls-files` (34 total). `.venv/` and cache dirs excluded.

---

## EXECUTIVE SUMMARY

| Severity | Count |
|----------|-------|
| TOP      | 2     |
| HIGH     | 8     |
| MEDIUM   | 5     |
| LOW      | 4     |
| INFO     | 3     |
| **TOTAL**| **22**|

**Single most important finding:** Five data files totalling ~59 MB are tracked in git — including a 78,291-record government-unit JSONL (`master_gov_units_2022.jsonl`), the Census source Excel, a PDF, and an eCFR Title 48 scrape. The `.gitignore` does NOT exclude the `data/` directory; only the large embeddings file was gitignored. These files are committed to both the `apex-ronin` (origin) and `jsnnlsn-prog` (jsnnlsn remote) GitHub repositories.

**Real data / secret / PII tracked in git:** **YES** — five data files (see F-01, F-02). No API keys or credential files were found tracked in git. The data itself is public-domain government data (Census of Governments, eCFR, FAR/DFARS corpus), so there is no personal PII exposure, but the data-privacy rule ("data layer never shared publicly") is violated.

**GEMINI.md status:** Active, tracked, and severely stale — it is the Google ADK agent-starter-pack's boilerplate coding guide, referencing `gemini-3-flash-preview`, `gemini-3.1-pro-preview`, Google Cloud ADK deployment, Terraform, `make setup-dev-env` (a target that does not exist in the Makefile), and Phase 5/6 GCP deploy workflows. The entire document describes the dead GCP/Gemini paradigm, not the sovereign-local stack.

**Public-flip verdict: FAIL**  
The repo is NOT safe to flip public in its current state. The primary blocker is the committed data files. The secondary blockers are the active GCP/Vertex/Gemini code in `app/agent.py`, `pipeline/embedder.py`, `pipeline/storage.py`, `pipeline/deploy_index.py`, and live telemetry/logging wired to GCS/Cloud Logging. See findings F-01 through F-04 for specifics.

**Positive note on `.gitignore` design intent:** The large embeddings file (`data/processed/embeddings/census_govs_embeddings.jsonl`, 289.8 MB) IS correctly gitignored — that design decision was sound. The gap is that the rest of `data/` was never gitignored, allowing the five files below to be committed.

---

## FINDINGS (severity-ranked)

---

### F-01 · TOP · Publication Safety — Data directory tracked in git (no gitignore coverage)

**File:line:** `.gitignore` (no `data/` entry); tracked files:
- `data/processed/census/master_gov_units_2022.jsonl` (38.6 MB — 78,291 records)
- `data/raw/ecfr_title_48.json` (8.8 MB — full Title 48 eCFR structure scrape)
- `data/raw/legal_corpus.jsonl` (95 KB — curated regulatory clause corpus)
- `data/raw/temp_census/Govt_Units_2022_Final.xlsx` (11.4 MB — source Census Excel)
- `data/raw/temp_census/Government_Units_List_Documentation_2022.pdf` (207 KB — Census docs)

**What it says / why it's wrong:** The data-privacy rule states the data layer must NEVER be shareable on public GitHub — tooling/pipeline code can be public, the data never is. Five files totalling ~59 MB are currently committed and tracked. The `.gitignore` only excludes `data/processed/embeddings/census_govs_embeddings.jsonl` (the large embeddings file); the rest of `data/` has no gitignore coverage. Both remotes (`apex-ronin/data-arsenal` and `jsnnlsn-prog/data-arsenal`) have these files if they have been pushed.

**Data sensitivity assessment:** The Census of Governments data and eCFR are public-domain government data — no personal PII is present (government entity names, FIPS codes, population counts, government website URLs). The legal corpus contains no personal data. However, the data-privacy rule is architectural/sovereign, not just PII-based — the data layer must stay off public GitHub regardless of public-domain status.

**Suggested correction:**
1. Add `data/` to `.gitignore` (with the specific embeddings file exception already in place, rewrite as `data/` then `!data/processed/embeddings/` or handle via a nested `.gitignore`).
2. Remove the committed data files from git history: `git rm --cached data/processed/census/master_gov_units_2022.jsonl data/raw/ecfr_title_48.json data/raw/legal_corpus.jsonl data/raw/temp_census/` then commit.
3. If either remote is already public or has had the data pushed, consider a history rewrite (`git filter-repo`) and contact GitHub support.
4. Document local data paths in a `data/README.md` (gitignored) so the pipeline can be reconstructed without tracking the data.

**Severity: TOP**

---

### F-02 · TOP · Publication Safety — `data/raw/legal_corpus.jsonl` is the curated regulatory corpus (data layer, not tooling)

**File:line:** `data/raw/legal_corpus.jsonl` (tracked in git, 95 KB)

**What it says / why it's wrong:** This file is the hand-curated regulatory clause corpus — the product of significant IP effort (DFARS/FAR clause extracts, notes, renumbering annotations, EO entries). It is part of the data layer that must stay private. Additionally, it contains two entries with `id = "OMB M-26-04"` (see F-15 for the regulatory accuracy issue within it). This finding is separate from F-01 because the legal corpus is curated IP, not just a public-domain raw download.

**Suggested correction:** Remove from git tracking along with the rest of `data/`. Store canonically at `G:\AI-Models\` or the OneDrive workspace alongside other sovereign data.

**Severity: TOP** (publication safety + curated IP)

---

### F-03 · HIGH · Dead Infra — `app/agent.py` is live Gemini/Vertex code routed through GCP

**File:line:** `app/agent.py:21-31`, `app/agent.py:66-74`

**What it says:**
```python
from google.adk.models import Gemini
from google.genai import types
import google.auth
_, project_id = google.auth.default()
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "True"
...
model=Gemini(model="gemini-3-flash-preview", ...)
```

**Why it's wrong:** This is the primary application entry point. It (a) requires `google.auth.default()` — needs GCP credentials/ADC; (b) sets `GOOGLE_GENAI_USE_VERTEXAI = "True"` which routes all inference through Vertex AI — a dead/torn-down GCP project; (c) uses `gemini-3-flash-preview` — a GCP-hosted Gemini model, not the sovereign-local cascade (LM Studio qwen3 → Venice → Anthropic API). This code will fail at runtime because GCP was torn down 2026-06-06.

**Suggested correction:** Replace with the sovereign-local cascade. At minimum, the agent needs to target the LM Studio OpenAI-compatible endpoint (localhost:1234) or the Anthropic API (claude-sonnet-4-6). The `GOOGLE_GENAI_USE_VERTEXAI` env var must be removed or set to `"False"`. If the Google ADK framework is still desired, configure it against a non-Vertex backend.

**Severity: HIGH**

---

### F-04 · HIGH · Dead Infra — `pipeline/embedder.py` is live Vertex AI code with active `vertexai` import

**File:line:** `pipeline/embedder.py:1-11`, `pipeline/embedder.py:22-23`, `pipeline/embedder.py:94-95`

**What it says:**
```python
# Vertex AI Vector Search — Embedding Generator
import vertexai
from vertexai.language_models import TextEmbeddingInput, TextEmbeddingModel
...
vertexai.init(project=PROJECT_ID, location=LOCATION)
model = TextEmbeddingModel.from_pretrained(MODEL_ID)
```
Uses `text-embedding-005` (a GCP-only model), targets `us-east5` by default.

**Why it's wrong:** Vertex AI is dead infra (GCP torn down 2026-06-06). The `text-embedding-005` model no longer exists in any project. The roadmap itself acknowledges "Vertex embeddings orphaned (embedder model gone)" and records that the local rebuild (build_local_indexes.py with nomic-embed-text-v1.5) is now the canonical path. This file is not archived — it's in the active `pipeline/` directory with no deprecation notice.

**Suggested correction:** Archive to `pipeline/archive/embedder_vertex.py` or add a prominent `# DEPRECATED — GCP torn down 2026-06-06. Use build_local_indexes.py instead.` header. Remove `vertexai` from `pyproject.toml` if present (it's a transitive dep of `google-cloud-aiplatform` which is still declared — see F-07).

**Severity: HIGH**

---

### F-05 · HIGH · Dead Infra — `pipeline/storage.py` and `pipeline/deploy_index.py` are live GCP code

**File:line:** `pipeline/storage.py` (entire file); `pipeline/deploy_index.py` (entire file)

**What it says:** `storage.py` imports `google.cloud.storage`, creates/manages GCS buckets, and uploads to `gs://ronin-sovereign-core-embeddings/`. `deploy_index.py` imports `google.cloud.aiplatform` and `google.cloud.aiplatform_v1`, creates Vertex AI Vector Search indexes, and deploys to private VPC endpoints.

**Why it's wrong:** GCP project `ronin-sovereign-core` was deleted 2026-06-06. The GCS bucket, Vertex index, and endpoint are all gone. These files contain hardcoded GCP project number `776676408891` in docstrings/help text. Running either script would fail immediately against the dead project. Neither file carries a deprecation notice. The deploy_index.py `--resume-from-index` help text even provides the former index resource name as an example.

**Suggested correction:** Archive both to `pipeline/archive/`. The index IDs/project IDs in docstrings should not be committed to git in active code — remove or redact them. Add `# ARCHIVED — GCP torn down 2026-06-06.` header at minimum before archiving.

**Severity: HIGH**

---

### F-06 · HIGH · Dead Infra — `pipeline/__init__.py` declares dead region and dead paradigm

**File:line:** `pipeline/__init__.py:1-2`

**What it says:** `# Phase 3D — Vertex AI Vector Search Ingestion Pipeline / # CMMC Level 2 | Region: us-east5`

**Why it's wrong:** The pipeline is no longer Vertex AI Vector Search. It's now FAISS/local. `us-east5` was the original incorrect region (corrected to `us-central1` per 2026-05-14 audit, then GCP was torn down entirely). This module docstring/header misleadingly describes the dead paradigm to any agent or developer reading the package.

**Suggested correction:** Update to: `# Sovereign retrieval pipeline — FAISS/local (nomic-embed-text-v1.5 via LM Studio). GCP/Vertex stack archived 2026-06-06.`

**Severity: HIGH**

---

### F-07 · HIGH · Dead Infra — `pyproject.toml` declares `google-cloud-aiplatform[evaluation]` as a core dependency

**File:line:** `pyproject.toml:14`

**What it says:** `"google-cloud-aiplatform[evaluation]>=1.130.0"` is a non-optional, non-dev core dependency.

**Why it's wrong:** `google-cloud-aiplatform` is the Vertex AI SDK — it's dead infrastructure. It is not used by any currently-live code path (the sovereign pipeline uses `faiss` and `requests` to LM Studio). Keeping it as a core dep (a) pulls in ~100+ MB of transitive GCP dependencies on every `uv sync`, (b) misleads agents and collaborators into thinking Vertex AI is the live stack, and (c) means any new environment that runs `make install` will install a GCP SDK for a dead project.

**Note:** `google-adk` is also a GCP-adjacent dependency, though it may be legitimately retained if the ADK agent framework is kept for local development. The aiplatform SDK specifically has no live use.

**Suggested correction:** Remove `google-cloud-aiplatform[evaluation]` from core deps. If `embedder.py`, `storage.py`, and `deploy_index.py` are archived, the dependency can be dropped entirely. `faiss-cpu` and `numpy` should be added as declared dependencies since `build_local_indexes.py` and `query_local_indexes.py` use them but they appear nowhere in `pyproject.toml` (faiss-cpu is not even in `uv.lock`).

**Severity: HIGH**

---

### F-08 · HIGH · Dead Infra — `GEMINI.md` is the Google ADK boilerplate guide; entire document is stale

**File:line:** `GEMINI.md` (entire file, 69 lines)

**What it says:** Instructs coding agents to use `gemini-3-flash-preview` or `gemini-3.1-pro-preview` for new agents, references ADK documentation URLs, describes a 6-phase GCP deployment workflow (Phase 5: `make deploy` to Cloud Run, Phase 6: CI/CD with `uvx agent-starter-pack setup-cicd`), references `make setup-dev-env` (Terraform — a command that does not exist in the Makefile), and references Terraform conflict resolution.

**Why it's wrong:**
- Model names `gemini-3-flash-preview` and `gemini-3.1-pro-preview` are GCP-hosted Gemini models — dead stack.
- "NEVER change the model unless explicitly asked. Use `gemini-3-flash-preview`..." directly contradicts the sovereign-local strategy.
- Phase 5/6 GCP deploy workflow is dead (GCP torn down 2026-06-06).
- `make setup-dev-env` does not exist as a Makefile target.
- The document describes GCP ADK (`google.adk`) as the primary framework, not the sovereign cascade.
- `README.md` recommends "Use Gemini CLI for AI-assisted development — project context is pre-configured in `GEMINI.md`" — this tip is also stale.

**Suggested correction:** Archive `GEMINI.md` to `GEMINI.md.archive` or delete it. Replace with a `CLAUDE.md`-aligned sovereign development guide that references the local cascade and FAISS pipeline. Update the README tip accordingly. This is the same pattern as `primordial-galaxy`'s `GEMINI_HANDOFF.md` archival recommendation.

**Severity: HIGH** (active agent-facing instructions pointing to dead infra)

---

### F-09 · HIGH · Dead Infra — `app/fast_api_app.py` wires live telemetry to GCS/Cloud Logging

**File:line:** `app/fast_api_app.py:17-28`, `app/app_utils/telemetry.py:20-50`

**What it says:** At module import time, `app/fast_api_app.py` calls `google.auth.default()` (requires GCP ADC credentials), instantiates `google.cloud.logging.Client()`, and constructs an artifact service URI pointing to a GCS bucket (`gs://{LOGS_BUCKET_NAME}`). `telemetry.py` configures OpenTelemetry upload to GCS (`gs://{bucket}/{path}`).

**Why it's wrong:** GCP is torn down. `google.auth.default()` will fail or return no-op credentials. `google.cloud.logging.Client()` will attempt to connect to Cloud Logging for a dead project. Any `LOGS_BUCKET_NAME` env var would point to a deleted GCS bucket. The FastAPI server cannot start cleanly in the sovereign-local environment without GCP credentials configured.

**Suggested correction:** Replace Cloud Logging with local structured logging (Python `logging` module or similar). Remove the GCS artifact URI. If the FastAPI layer is retained, decouple it from GCP at the import level.

**Severity: HIGH**

---

### F-10 · MEDIUM · Wrong Regulatory Citation — `pipeline/__init__.py` region note (`us-east5`) is stale AND reflects a twice-obsolete position

**File:line:** `pipeline/__init__.py:2` — `# CMMC Level 2 | Region: us-east5`

**What it says:** Declares `us-east5` as the CMMC-mandated region.

**Why it's wrong:** As of the 2026-05-14 regulatory audit (documented in `data_arsenal_roadmap.md`), `us-east5` was confirmed NOT mandated by CMMC L2, DFARS 252.239-7010, or FedRAMP Moderate. The correct region was `us-central1` (required for Vertex AI Vector Search). Then GCP was torn down entirely on 2026-06-06. So this comment is wrong on two levels: wrong region, and no longer a GCP pipeline at all.

**Suggested correction:** Update header as noted in F-06.

**Severity: MEDIUM**

---

### F-11 · MEDIUM · Wrong Regulatory Citation — First `OMB M-26-04` corpus entry has wrong title and no source URL

**File:line:** `data/raw/legal_corpus.jsonl` — first `OMB M-26-04` entry (id="OMB M-26-04", title="Federal AI Transparency and Accountability Requirements")

**What it says:** The `clause_text` describes this as "OMB M-26-04 (Accelerating Federal Use of AI through Innovation, Governance, and Public Trust, December 11, 2025)". This is wrong on two counts: (a) "Accelerating Federal Use of AI through Innovation, Governance, and Public Trust" is the title of OMB M-25-21, not M-26-04. M-26-04's actual title is "Increasing Public Trust in Artificial Intelligence Through Unbiased AI Principles" (correctly captured in the second M-26-04 entry). (b) This entry has no `source_url` field (the second M-26-04 entry correctly includes the whitehouse.gov PDF URL). The rule requires primary-source URLs for all regulatory citations.

**Suggested correction:** Fix the `clause_text` to use M-26-04's correct title. Add `source_url` matching the second entry (`https://www.whitehouse.gov/wp-content/uploads/2025/12/M-26-04-Increasing-Public-Trust-in-Artificial-Intelligence-Through-Unbiased-AI-Principles-1.pdf`). Consider merging the two M-26-04 entries into one.

**Severity: MEDIUM**

---

### F-12 · MEDIUM · Wrong Regulatory Citation — `DFARS 252.204-7021` in legal corpus has no renumbering note

**File:line:** `data/raw/legal_corpus.jsonl` — entry `id="DFARS 252.204-7021"`

**What it says:** Presents DFARS 252.204-7021 (CMMC Requirements) without any note that it has been renumbered per the Feb 2026 RFO. The sibling clause 252.204-7020 was correctly renumbered to 252.240-7997 (with a `notes` field). 252.204-7021 (CMMC Requirements) was also renumbered in the same Feb 2026 RFO — it should carry a similar annotation.

**Additional impact:** `pipeline/query_local_indexes.py:63` uses `"252.204-7021" in i` as the acceptance gate. If the corpus ID were updated to the new renumbered form, this gate would break.

**Suggested correction:** Add `"notes": "Renumbered per Feb 2026 RFO"` (with the new clause number once confirmed) to the 252.204-7021 corpus entry. Update the acceptance gate in `query_local_indexes.py` to match.

**Severity: MEDIUM**

---

### F-13 · MEDIUM · Stale CLAUDE.md — references Vertex AI Vector Search as current infrastructure

**File:line:** `CLAUDE.md:3`

**What it says:** "Region `us-central1` is required for Vertex AI Vector Search (FedRAMP High authorized)."

**Why it's wrong:** Vertex AI Vector Search was torn down 2026-06-06. This CLAUDE.md instruction will mislead coding agents into believing Vertex AI is the live infra. The rest of CLAUDE.md is largely good (sovereign-local intent, regulatory citation rules, STATE.md requirement), but this one sentence is directly contradicted by reality.

**Suggested correction:** Replace with: "The sovereign-local stack uses FAISS indexes on `G:\AI-Models\indexes\` with nomic-embed-text-v1.5 via LM Studio. Vertex AI Vector Search was torn down 2026-06-06."

**Severity: MEDIUM**

---

### F-14 · MEDIUM · Missing declared dependencies — `faiss-cpu` and `numpy` used but not in `pyproject.toml`

**File:line:** `pyproject.toml` (missing entries); `pipeline/build_local_indexes.py:35-36`; `pipeline/query_local_indexes.py:19-20`

**What it says:** `build_local_indexes.py` and `query_local_indexes.py` both `import faiss` and `import numpy`. Neither `faiss-cpu` nor `numpy` (standalone) appears in `pyproject.toml` dependencies. A check of `uv.lock` confirms `faiss-cpu` is absent entirely; `numpy` is present only as a transitive dependency of other packages.

**Why it's wrong:** If `uv sync` is run on a fresh checkout, the sovereign retrieval pipeline will fail to import with `ModuleNotFoundError: No module named 'faiss'`. This is a broken toolchain on the sovereign pipeline that replaced the dead GCP stack.

**Suggested correction:** Add `faiss-cpu>=1.7.4` and `numpy>=1.26.0` to `pyproject.toml` core dependencies. Run `uv lock` to update `uv.lock`.

**Severity: MEDIUM**

---

### F-15 · LOW · Dead Infra framing in `app/census_ingest.py` and `app/ecfr_ingest.py` docstrings

**File:line:** `app/census_ingest.py:22` — "structured JSON payloads optimized for Vertex AI Vector Search staging"; `app/ecfr_ingest.py:66` — "Awaiting downstream Vector Search ingester."

**What it says:** Both ingest scripts describe their output as staged for Vertex AI Vector Search.

**Why it's wrong:** The downstream is now the local FAISS pipeline, not Vertex AI. These are log messages and docstrings, not functional code, so they cause no runtime failure. But they mislead agents about the pipeline's downstream.

**Suggested correction:** Update docstrings and log messages to reference the local FAISS pipeline.

**Severity: LOW**

---

### F-16 · LOW · `app/puf_to_master_jsonl.py` hardcodes absolute paths to a stale workspace location

**File:line:** `app/puf_to_master_jsonl.py:7-8`

**What it says:**
```python
EXCEL_PATH = Path(r"C:\Users\Jnel9\Workspaces\AI-Agents\Active\data-arsenal\data\raw\census_final\Govt_Units_2022_Final.xlsx")
OUTPUT_JSONL = Path(r"C:\Users\Jnel9\Workspaces\AI-Agents\Active\data-arsenal\data\processed\census\master_gov_units_2022.jsonl")
```

**Why it's wrong:** The canonical workspace is `C:\Users\jnel9\OneDrive\Workspaces\` (note: `jnel9\OneDrive\` not `Jnel9\Workspaces\`). The input Excel path points to `census_final\` (not `temp_census\` where `Govt_Units_2022_Final.xlsx` is actually tracked). This script would fail on the current machine. Also, the script generates the 38.6 MB JSONL that is currently tracked in git (F-01).

**Suggested correction:** Update paths to current workspace locations. Better: use relative paths from repo root or environment variables. Document in README that this one-time script should not be rerun without first cleaning the data from git.

**Severity: LOW**

---

### F-17 · LOW · `pyproject.toml` has placeholder author information

**File:line:** `pyproject.toml:5-7`

**What it says:** `{name = "Your Name", email = "your@email.com"}` — boilerplate from agent-starter-pack that was never filled in.

**Why it's wrong:** If this repo is published (even as "tooling only"), the placeholder authorship is unprofessional and prevents correct attribution.

**Suggested correction:** Update to Jay Nelson / jsn.nlsn@gmail.com or the apex-ronin org identity.

**Severity: LOW**

---

### F-18 · LOW · `README.md` is the Google ADK agent-starter-pack boilerplate; misleads on stack identity

**File:line:** `README.md` (entire file)

**What it says:** "Simple ReAct agent. Agent generated with `googleCloudPlatform/agent-starter-pack` version 0.40.1." Recommends Google Cloud SDK, `make deploy` to Cloud Run, observability via Cloud Trace/BigQuery/Cloud Logging, and Gemini CLI.

**Why it's wrong:** This is now a sovereign-local data acquisition and ETL repo, not a GCP ReAct agent. A developer reading the README has no idea what this repo actually does (FAISS index building, regulatory corpus management, Census ingest). All the GCP references are dead.

**Suggested correction:** Rewrite README to describe the actual sovereign-local pipeline: FAISS index building (`build_local_indexes.py`), local query (`query_local_indexes.py`), Census ingest, eCFR/FAR corpus management. Remove GCP Cloud Run deploy, Cloud SDK requirement, and Gemini CLI tip.

**Severity: LOW**

---

### F-19 · INFO · `data_arsenal_roadmap.md` correctly documents GCP teardown but exposes deleted GCP resource IDs

**File:line:** `data_arsenal_roadmap.md:29-31`

**What it says:**
```
Index:    projects/776676408891/locations/us-central1/indexes/1040747129317883904
Endpoint: projects/776676408891/locations/us-central1/indexEndpoints/6319845501898326016
```

**Assessment:** The roadmap correctly marks these as deleted ("DELETED 2026-06-06"). The GCP project number `776676408891` is exposed but is no longer active. This is informational rather than a security risk (deleted project, public-domain data, no live credentials). However, if this repo goes public, the project number could be scraped.

**Suggested correction:** Redact or remove the deleted resource IDs. They serve no operational purpose now that the resources are gone.

**Severity: INFO**

---

### F-20 · INFO · `Makefile` `deploy` target is dead GCP Cloud Run deployment

**File:line:** `Makefile:42-55`

**What it says:** `make deploy` runs `gcloud beta run deploy data-arsenal --source . --region "us-central1"` — deploys the ADK Gemini agent to Cloud Run.

**Assessment:** This will fail (no active GCP project), but since the Makefile is tooling (not data), it's informational. The target should be removed or replaced with sovereign-local deployment instructions once the agent is redesigned. The `make deploy` is not dangerous to leave in the Makefile (it will just fail), but it misleads agents.

**Suggested correction:** Remove or comment out the `deploy` and `backend` targets. Add a note: `# GCP deploy removed — use local FAISS pipeline. See data_arsenal_roadmap.md.`

**Severity: INFO**

---

### F-21 · INFO · Dockerfile exposes port 8080 for Cloud Run (not the `:8080 dashboard` concern)

**File:line:** `Dockerfile:33-35`

**Assessment:** The Dockerfile exposes port 8080 and runs uvicorn on 8080. This is Cloud Run's expected port, not the "Hetzner `:8080` dashboard" cited in the audit brief. The Hetzner IP `89.167.127.154` does not appear anywhere in this repo. The Dockerfile is dead infra (no active GCP project to deploy to), but the port reference is an artifact of Cloud Run configuration, not the Hetzner monitoring dashboard.

**Suggested correction:** No urgent action needed on the port number itself. The Dockerfile as a whole is dead infra — archive or replace when the stack is redesigned.

**Severity: INFO**

---

### F-22 · INFO · `tests/eval/eval_config.json` uses `gemini-3-flash-preview` as the LLM judge model

**File:line:** `tests/eval/eval_config.json:6` — `"judgeModel": "gemini-3-flash-preview"`

**Assessment:** The evaluation judge model is a dead GCP Gemini model. `make eval` will fail. This is an operational nuisance rather than a publication safety issue.

**Suggested correction:** Replace with a local or Anthropic judge model appropriate for the sovereign-local stack (e.g., `claude-sonnet-4-6` via Anthropic API, or remove the eval tooling if the ADK eval framework is being replaced).

**Severity: INFO**

---

## CROSS-REFERENCE CONTRADICTIONS

| Location A | Location B | Contradiction |
|-----------|-----------|---------------|
| `CLAUDE.md:3` — "us-central1 required for Vertex AI Vector Search" | `data_arsenal_roadmap.md` — "GCP torn down 2026-06-06" | CLAUDE.md describes dead infra as active requirement |
| `GEMINI.md` — "Use gemini-3-flash-preview for new agents" | `CLAUDE.md` implicit sovereign-local intent | GEMINI.md tells agents to use dead GCP models |
| `pipeline/__init__.py` — "Vertex AI Vector Search Ingestion Pipeline, Region: us-east5" | `pipeline/build_local_indexes.py` — "Replaces the deleted Vertex AI Vector Search stack" | __init__.py describes the paradigm that build_local_indexes.py replaced |
| `pyproject.toml` — `google-cloud-aiplatform[evaluation]` as core dep | Sovereign stack uses FAISS/local | Core dep pulls in dead infrastructure SDK |
| `app/agent.py` — `GOOGLE_GENAI_USE_VERTEXAI = "True"` | GCP torn down 2026-06-06 | Routes inference through dead Vertex AI |
| `data_arsenal_roadmap.md` — "Repo boundary: This repo is infrastructure only. No agent client code here." | `app/agent.py`, `app/fast_api_app.py` — full agent client code | Roadmap's "settled decision" is contradicted by what's actually in `app/` |

---

## GITIGNORE COVERAGE ASSESSMENT

| Pattern | Covered? | Notes |
|---------|----------|-------|
| `.env` files | YES | Two separate `.env` entries in .gitignore |
| `.venv/` | YES | Covered via `.venv`, `.venv*` |
| `lib/` | YES | `lib/` entry present |
| `data/processed/embeddings/census_govs_embeddings.jsonl` | YES | Specific file gitignored (large embeddings, 289.8 MB) |
| `data/` (general) | **NO** — MISSING | Five data files committed (F-01, F-02) |
| API keys / `.env.local` / secrets | YES (`.env` covered) | No secret files found tracked |
| `__pycache__/`, `.pytest_cache/` | YES | Standard Python ignores present |
| Terraform state | YES | `.terraform*` covered |

**Verdict:** The gitignore was correctly designed to exclude the large embeddings file but was never extended to cover the rest of `data/`. Remediation: add `data/` at the top of the gitignore with exceptions for any non-data files that should remain tracked.

---

*End of audit. 22 findings total. No files were modified during this audit.*
