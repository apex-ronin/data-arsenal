# data-arsenal — sovereign-local data acquisition + FAISS retrieval pipeline.
# (GCP/Vertex/ADK Cloud Run targets were removed 2026-06-12 — see _archive_gcp/.)

# ==============================================================================
# Installation & Setup
# ==============================================================================

# Install dependencies using uv package manager
install:
	@command -v uv >/dev/null 2>&1 || { echo "uv is not installed. Installing uv..."; curl -LsSf https://astral.sh/uv/0.8.13/install.sh | sh; source $HOME/.local/bin/env; }
	uv sync

# ==============================================================================
# Sovereign Retrieval Pipeline (local FAISS via LM Studio nomic-embed)
# ==============================================================================

# Build the local FAISS indexes (requires LM Studio serving nomic-embed on localhost:1234)
# Usage: make build-indexes [ONLY=legal|princ]
build-indexes:
	uv run python pipeline/build_local_indexes.py $(if $(ONLY),--only $(ONLY),)

# Run the retrieval acceptance gates (CMMC clause + CA irrigation district)
acceptance:
	uv run python pipeline/query_local_indexes.py --acceptance

# ==============================================================================
# Testing & Code Quality
# ==============================================================================

# Run unit tests
test:
	uv sync --dev
	uv run pytest tests/unit

# Run code quality checks (codespell, ruff, ty)
lint:
	uv sync --extra lint
	uv run codespell
	uv run ruff check . --diff
	uv run ruff format . --check --diff
	uv run ty check .
