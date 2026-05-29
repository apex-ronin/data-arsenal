"""
Sovereign Vertex AI Vector Search Index Deployment
Phase 3D: Census GOVS Ingestion Pipeline

Flow:
  1. Create TreeAH index from GCS embeddings (30-60 min LRO)
       → async polling loop logs progress every 60s
  2. Create VPC-peered private endpoint (no public endpoint provisioned)
  3. Deploy index to endpoint

CMMC Level 2 | VPC-Peered Private Endpoint | Region: us-central1
Compliance: Assured Workloads + Organization Policy (not region-locked).
us-central1 selected — Vector Search not supported in us-east5.

Required env vars:
  GCP_PROJECT_ID        — GCP project ID
  VPC_NETWORK           — VPC network resource path:
                          projects/{project_number}/global/networks/{network_name}
  CONTENTS_DELTA_URI    — GCS prefix from storage.py output:
                          gs://{bucket}/census-govs/embeddings

Optional env vars:
  GCP_LOCATION          — defaults to us-central1
"""

import argparse
import logging
import os
import threading
import time
from typing import Optional

from google.api_core import exceptions as gcp_exceptions
from google.cloud import aiplatform
from google.cloud import aiplatform_v1

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
PROJECT_ID: str = os.environ.get("GCP_PROJECT_ID", "")
LOCATION: str = os.environ.get("GCP_LOCATION", "us-central1")
VPC_NETWORK: str = os.environ.get("VPC_NETWORK", "")
CONTENTS_DELTA_URI: str = os.environ.get("CONTENTS_DELTA_URI", "")

INDEX_DISPLAY_NAME: str = "census-govs-2022-tree-ah"
ENDPOINT_DISPLAY_NAME: str = "census-govs-2022-private-endpoint"
DEPLOYED_INDEX_ID: str = "census_govs_2022"

# Vector Search index parameters for 78K corpus
DIMENSIONS: int = 768          # text-embedding-005 default output dimensionality
APPROX_NEIGHBORS: int = 150    # approximate_neighbors_count — standard for this corpus size
LEAF_NODE_EMBEDDINGS: int = 500
LEAF_NODES_TO_SEARCH_PERCENT: int = 7

# Polling configuration
POLL_INTERVAL_SECS: int = 60
MAX_POLL_MINUTES: int = 90     # safety ceiling beyond the expected 30-60 min window


# ---------------------------------------------------------------------------
# Step 1: Index Creation with async polling loop
# ---------------------------------------------------------------------------

def _create_index_blocking(
    contents_delta_uri: str,
    result_holder: dict,
    error_holder: dict,
) -> None:
    """Target for background thread: blocking SDK call (sync=True)."""
    try:
        index = aiplatform.MatchingEngineIndex.create_tree_ah_index(
            display_name=INDEX_DISPLAY_NAME,
            contents_delta_uri=contents_delta_uri,
            dimensions=DIMENSIONS,
            approximate_neighbors_count=APPROX_NEIGHBORS,
            leaf_node_embedding_count=LEAF_NODE_EMBEDDINGS,
            leaf_nodes_to_search_percent=LEAF_NODES_TO_SEARCH_PERCENT,
            description="Census GOVS 2022 — 78K government units. CMMC L2 CUI.",
            sync=True,
        )
        result_holder["index"] = index
    except Exception as exc:
        error_holder["error"] = exc


def _poll_index_state(resource_name: str) -> int:
    """
    Re-fetch the index via the low-level gapic client and return vectors_count.
    Returns 0 if the index is still building or if resource_name is not yet set.
    """
    if not resource_name:
        return 0
    try:
        gapic_client = aiplatform_v1.IndexServiceClient(
            client_options={"api_endpoint": f"{LOCATION}-aiplatform.googleapis.com"}
        )
        current = gapic_client.get_index(name=resource_name)
        return current.index_stats.vectors_count if current.index_stats else 0
    except Exception as exc:
        logger.debug("Poll fetch error (transient): %s", exc)
        return 0


def create_index(contents_delta_uri: str) -> aiplatform.MatchingEngineIndex:
    """
    Submit TreeAH index creation LRO and poll until READY.

    The SDK call blocks internally (sync=True); we run it in a background
    thread so the main thread can drive the polling loop and emit progress
    logs without silently blocking the terminal session.
    """
    logger.info("Submitting TreeAH index creation LRO...")
    logger.info("  display_name:     %s", INDEX_DISPLAY_NAME)
    logger.info("  source:           %s", contents_delta_uri)
    logger.info("  dimensions:       %d", DIMENSIONS)
    logger.info("  approx_neighbors: %d", APPROX_NEIGHBORS)
    logger.warning("  NOTE: Index creation takes 30-60 minutes. Do not interrupt.")

    result_holder: dict = {}
    error_holder: dict = {}

    thread = threading.Thread(
        target=_create_index_blocking,
        args=(contents_delta_uri, result_holder, error_holder),
        daemon=True,
    )
    thread.start()

    start_time = time.monotonic()
    deadline = start_time + MAX_POLL_MINUTES * 60
    poll_num = 0
    resource_name: str = ""

    while thread.is_alive():
        time.sleep(POLL_INTERVAL_SECS)
        poll_num += 1
        elapsed_min = (time.monotonic() - start_time) / 60

        if time.monotonic() > deadline:
            raise TimeoutError(
                f"Index creation exceeded {MAX_POLL_MINUTES} minute ceiling. "
                f"Last known resource: {resource_name or 'not yet assigned'}"
            )

        # Try to get vectors_count once we have a resource_name
        # (resource_name populates from the SDK after the initial HTTP call)
        if not resource_name and result_holder.get("index"):
            resource_name = result_holder["index"].resource_name or ""

        vectors_count = _poll_index_state(resource_name)
        logger.info(
            "[Poll %d | %.0f min elapsed] resource=%s | vectors_indexed=%d",
            poll_num,
            elapsed_min,
            resource_name or "pending",
            vectors_count,
        )

    thread.join()

    if "error" in error_holder:
        raise error_holder["error"]

    index = result_holder["index"]
    logger.info("Index READY: %s", index.resource_name)
    return index


# ---------------------------------------------------------------------------
# Step 2: Private VPC-Peered Endpoint
# ---------------------------------------------------------------------------

def create_private_endpoint() -> aiplatform.MatchingEngineIndexEndpoint:
    """
    Create a VPC-peered private endpoint.

    CMMC L2 CUI compliance: no public endpoint is provisioned.
    The `network` kwarg enforces VPC peering — the endpoint is only
    reachable from within the specified VPC, never via the public internet.

    Idempotent: reuses an existing endpoint with the same display name if
    found (handles partial failure recovery). Retries on 404 NotFound to
    tolerate GCP propagation lag after the create LRO completes.
    """
    logger.info("Checking for existing endpoint: %s", ENDPOINT_DISPLAY_NAME)
    existing = aiplatform.MatchingEngineIndexEndpoint.list(
        filter=f'display_name="{ENDPOINT_DISPLAY_NAME}"'
    )
    if existing:
        logger.info("Reusing existing endpoint: %s", existing[0].resource_name)
        return existing[0]

    logger.info("Creating VPC-peered private endpoint: %s", ENDPOINT_DISPLAY_NAME)
    logger.info("  VPC network: %s", VPC_NETWORK)

    for attempt in range(1, 4):
        try:
            endpoint = aiplatform.MatchingEngineIndexEndpoint.create(
                display_name=ENDPOINT_DISPLAY_NAME,
                description="Census GOVS 2022 private endpoint. CMMC L2 — no public internet access.",
                network=VPC_NETWORK,           # VPC peering — disables public endpoint entirely
                public_endpoint_enabled=False,  # Explicit: no public endpoint provisioned
            )
            logger.info("Private endpoint created: %s", endpoint.resource_name)
            return endpoint
        except gcp_exceptions.NotFound:
            if attempt == 3:
                raise
            logger.warning(
                "Endpoint 404 on post-create fetch (GCP propagation lag) — retry %d/3 in 30s...",
                attempt,
            )
            time.sleep(30)


# ---------------------------------------------------------------------------
# Step 3: Deploy Index to Endpoint
# ---------------------------------------------------------------------------

def deploy_to_endpoint(
    index: aiplatform.MatchingEngineIndex,
    endpoint: aiplatform.MatchingEngineIndexEndpoint,
) -> aiplatform.MatchingEngineIndexEndpoint:
    """Deploy the built index to the private VPC endpoint."""
    logger.info(
        "Deploying index to endpoint (deployed_index_id=%s)...",
        DEPLOYED_INDEX_ID,
    )
    endpoint.deploy_index(
        index=index,
        deployed_index_id=DEPLOYED_INDEX_ID,
        display_name=INDEX_DISPLAY_NAME,
        min_replica_count=1,
        max_replica_count=2,
    )
    logger.info("Deployment complete.")
    return endpoint


# ---------------------------------------------------------------------------
# Dry-run validation
# ---------------------------------------------------------------------------

def _validate_env() -> None:
    missing = []
    if not PROJECT_ID:
        missing.append("GCP_PROJECT_ID")
    if not VPC_NETWORK:
        missing.append("VPC_NETWORK")
    if not CONTENTS_DELTA_URI:
        missing.append("CONTENTS_DELTA_URI")
    if missing:
        raise EnvironmentError(
            f"Missing required environment variables: {', '.join(missing)}\n\n"
            "Set them before running:\n"
            "  export GCP_PROJECT_ID=ronin-sovereign-core\n"
            "  export VPC_NETWORK=projects/{project_number}/global/networks/{network_name}\n"
            "  export CONTENTS_DELTA_URI=gs://{bucket}/census-govs/embeddings"
        )


def dry_run_validate() -> None:
    """Validate environment config without making any GCP API calls."""
    logger.info("[DRY RUN] Validating configuration...")
    _validate_env()
    logger.info("[DRY RUN] Environment OK.")
    logger.info("[DRY RUN] Deployment plan:")
    logger.info("  Project:            %s", PROJECT_ID)
    logger.info("  Location:           %s", LOCATION)
    logger.info("  Source URI:         %s", CONTENTS_DELTA_URI)
    logger.info("  Index name:         %s", INDEX_DISPLAY_NAME)
    logger.info("  Dimensions:         %d", DIMENSIONS)
    logger.info("  Approx neighbors:   %d", APPROX_NEIGHBORS)
    logger.info("  VPC network:        %s", VPC_NETWORK)
    logger.info("  Endpoint name:      %s", ENDPOINT_DISPLAY_NAME)
    logger.info("  Deployed index ID:  %s", DEPLOYED_INDEX_ID)
    logger.info("[DRY RUN] All checks passed. Ready for live deployment.")


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def run(resume_index_name: Optional[str] = None) -> dict:
    _validate_env()
    aiplatform.init(project=PROJECT_ID, location=LOCATION)

    if resume_index_name:
        logger.info("Resuming with existing index (skipping LRO): %s", resume_index_name)
        index = aiplatform.MatchingEngineIndex(index_name=resume_index_name)
    else:
        # Step 1: Build the index (30-60 min LRO with progress polling)
        index = create_index(CONTENTS_DELTA_URI)

    # Step 2: Stand up a private VPC-peered endpoint
    endpoint = create_private_endpoint()

    # Step 3: Bind the index to the endpoint
    endpoint = deploy_to_endpoint(index, endpoint)

    result = {
        "index_resource_name": index.resource_name,
        "endpoint_resource_name": endpoint.resource_name,
        "deployed_index_id": DEPLOYED_INDEX_ID,
    }

    logger.info("=" * 65)
    logger.info("DEPLOYMENT COMPLETE — wire the following into ronin/ client:")
    logger.info("  Index:             %s", result["index_resource_name"])
    logger.info("  Endpoint:          %s", result["endpoint_resource_name"])
    logger.info("  Deployed index ID: %s", result["deployed_index_id"])
    logger.info("=" * 65)

    return result


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=(
            "Deploy Census GOVS TreeAH Vector Search index to a private VPC endpoint.\n\n"
            "Set env vars before running:\n"
            "  GCP_PROJECT_ID, VPC_NETWORK, CONTENTS_DELTA_URI"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate env config without making any GCP API calls.",
    )
    parser.add_argument(
        "--resume-from-index",
        metavar="RESOURCE_NAME",
        default=None,
        help=(
            "Skip the 30-60 min index creation LRO and resume from an existing index. "
            "Example: projects/776676408891/locations/us-central1/indexes/1040747129317883904"
        ),
    )
    args = parser.parse_args()

    if args.dry_run:
        dry_run_validate()
    else:
        result = run(resume_index_name=args.resume_from_index)
        print(f"\nPrivate endpoint:  {result['endpoint_resource_name']}")
        print(f"Deployed index ID: {result['deployed_index_id']}")
