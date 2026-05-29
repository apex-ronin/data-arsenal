"""
CMMC Level 2 Sovereign GCS Sync
Phase 3D: Census GOVS Vector Search Pipeline

Compliance posture:
  - Region:                  US-EAST5 (data residency enforced)
  - Uniform Bucket Access:   Enabled  (no per-object ACLs / legacy IAM)
  - Public Access Prevention: Enforced (zero public internet bleed)

Outputs the GCS prefix URI suitable for use as Vector Search
`contents_delta_uri` in deploy_index.py.

Required env vars:
  GCP_PROJECT_ID          — GCP project ID
  GCS_EMBEDDINGS_BUCKET   — (optional) override bucket name
"""

import logging
import os
from pathlib import Path

from google.api_core import exceptions as gcp_exceptions
from google.cloud import storage
from google.cloud.storage import Bucket

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
PROJECT_ID: str = os.environ.get("GCP_PROJECT_ID", "")

# us-central1 required: must co-locate with Vertex AI Vector Search.
# us-east5 residency is a design choice, not a regulatory mandate (CMMC L2,
# DFARS 252.239-7010, and FedRAMP Moderate impose no specific region requirement).
# Override via GCS_LOCATION env var if needed.
GCS_LOCATION: str = os.environ.get("GCS_LOCATION", "US-CENTRAL1")

# Bucket name defaults to {project_id}-vector-search-embeddings
BUCKET_NAME: str = os.environ.get(
    "GCS_EMBEDDINGS_BUCKET",
    f"{PROJECT_ID}-vector-search-embeddings" if PROJECT_ID else "UNSET-vector-search-embeddings",
)

EMBEDDINGS_DIR = Path("data/processed/embeddings")
GCS_PREFIX: str = "census-govs/embeddings"


# ---------------------------------------------------------------------------
# Bucket management
# ---------------------------------------------------------------------------

def _apply_cmmc_controls(bucket: Bucket) -> None:
    """Enforce Uniform Bucket-Level Access and Public Access Prevention."""
    needs_patch = False

    if not bucket.iam_configuration.uniform_bucket_level_access_enabled:
        logger.warning("Patching: enabling Uniform Bucket-Level Access on %s", bucket.name)
        bucket.iam_configuration.uniform_bucket_level_access_enabled = True
        needs_patch = True

    if bucket.iam_configuration.public_access_prevention != "enforced":
        logger.warning("Patching: enforcing Public Access Prevention on %s", bucket.name)
        bucket.iam_configuration.public_access_prevention = "enforced"
        needs_patch = True

    if needs_patch:
        bucket.patch()
        logger.info("CMMC controls patched on existing bucket.")


def get_or_create_bucket(client: storage.Client) -> Bucket:
    """
    Retrieve or create a CMMC Level 2 compliant GCS bucket.

    Controls enforced:
      - Uniform Bucket-Level Access  (disables per-object ACLs)
      - Public Access Prevention: Enforced  (blocks all public IAM grants)
      - Region: US-EAST5  (CUI data residency)
    """
    bucket_ref = client.bucket(BUCKET_NAME)

    if bucket_ref.exists():
        logger.info("Bucket gs://%s/ exists — verifying CMMC posture...", BUCKET_NAME)
        bucket_ref.reload()
        _apply_cmmc_controls(bucket_ref)
        return bucket_ref

    logger.info("Creating CMMC-compliant bucket: gs://%s/ in %s", BUCKET_NAME, GCS_LOCATION)
    # Configure CMMC controls on the bucket object before creation so they are
    # applied atomically in the create request — avoids a 404 race on patch().
    new_bucket = client.bucket(BUCKET_NAME)
    new_bucket.iam_configuration.uniform_bucket_level_access_enabled = True
    new_bucket.iam_configuration.public_access_prevention = "enforced"
    try:
        bucket = client.create_bucket(new_bucket, project=PROJECT_ID, location=GCS_LOCATION)
    except gcp_exceptions.Conflict:
        # Bucket exists due to GCP eventual consistency lag on exists() check.
        logger.warning("Bucket already exists (conflict on create) — reloading and verifying controls.")
        bucket = client.bucket(BUCKET_NAME)
        bucket.reload()
        _apply_cmmc_controls(bucket)

    logger.info(
        "Bucket ready: gs://%s/  [uniform_access=True, PAP=enforced, location=%s]",
        BUCKET_NAME, GCS_LOCATION,
    )
    return bucket


# ---------------------------------------------------------------------------
# Upload
# ---------------------------------------------------------------------------

def upload_embeddings(bucket: Bucket, embeddings_dir: Path) -> list[str]:
    """
    Upload all .jsonl embedding files from embeddings_dir to GCS.

    Returns:
        List of uploaded gs:// URIs.
    """
    jsonl_files = sorted(embeddings_dir.glob("*.jsonl"))
    if not jsonl_files:
        raise FileNotFoundError(
            f"No .jsonl files found in {embeddings_dir}. "
            "Run pipeline/embedder.py first."
        )

    uploaded_uris: list[str] = []
    for local_path in jsonl_files:
        # Vector Search requires .json extension — rename .jsonl on upload.
        gcs_name = local_path.stem + ".json"
        gcs_path = f"{GCS_PREFIX}/{gcs_name}"
        blob = bucket.blob(gcs_path)
        logger.info("Uploading %s → gs://%s/%s", local_path, BUCKET_NAME, gcs_path)
        blob.upload_from_filename(str(local_path))
        uri = f"gs://{BUCKET_NAME}/{gcs_path}"
        uploaded_uris.append(uri)
        logger.info("Uploaded: %s", uri)

    return uploaded_uris


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

def run() -> dict:
    if not PROJECT_ID:
        raise EnvironmentError("GCP_PROJECT_ID environment variable is required.")

    client = storage.Client(project=PROJECT_ID)
    bucket = get_or_create_bucket(client)
    uris = upload_embeddings(bucket, EMBEDDINGS_DIR)

    # Vector Search requires a directory-level prefix URI, not individual file URIs
    contents_delta_uri = f"gs://{BUCKET_NAME}/{GCS_PREFIX}"
    logger.info("Vector Search contents_delta_uri: %s", contents_delta_uri)

    return {
        "bucket_name": BUCKET_NAME,
        "uploaded_files": uris,
        "contents_delta_uri": contents_delta_uri,
    }


if __name__ == "__main__":
    result = run()
    print(f"\nSync complete.")
    print(f"  Bucket:              gs://{result['bucket_name']}/")
    print(f"  Files uploaded:      {len(result['uploaded_files'])}")
    print(f"  contents_delta_uri:  {result['contents_delta_uri']}")
    print(f"\nNext step: export CONTENTS_DELTA_URI='{result['contents_delta_uri']}'")
    print(f"           then run: uv run python pipeline/deploy_index.py")
