import os
import time
import requests
import json
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

# Standing Rule: Hyper-conservative rate limiting
RATE_LIMIT_DELAY = 3.0  # seconds
BASE_URL = "https://www.ecfr.gov/api/v1"

def fetch_title_48():
    """
    Fetches Title 48 data using a strictly throttled execution.
    Requires ECFR_API_KEY environment variable.
    """
    endpoint = f"https://www.ecfr.gov/api/versioner/v1/structure/2024-01-01/title-48.json"
    api_key = os.environ.get("ECFR_API_KEY")
    
    headers = {
        "User-Agent": "ApexRonin-DataArsenal/1.0",
        "Accept": "application/json"
    }

    if api_key:
        logger.info("Credentials found. Initializing authenticated pipeline.")
        headers["Authorization"] = f"Bearer {api_key}"
    else:
        logger.warning("No ECFR_API_KEY detected in environment. Attempting anonymous request.")

    logger.info(f"Targeting: {endpoint}")
    logger.info(f"Applying mandatory {RATE_LIMIT_DELAY}s delay prior to execution...")
    time.sleep(RATE_LIMIT_DELAY)

    try:
        response = requests.get(endpoint, headers=headers, timeout=15)
        
        if response.status_code == 403:
            logger.error(f"403 Forbidden: Endpoint returned a ban or requires API key/whitelisting. Body: {response.text}")
            return None
            
        response.raise_for_status()
        data = response.json()
        
        # Save payload logic (staging area for Vertex)
        output_dir = Path("data/raw")
        output_dir.mkdir(parents=True, exist_ok=True)
        out_file = output_dir / "ecfr_title_48.json"
        
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
            
        logger.info(f"Successfully extracted {len(str(data))} bytes. Saved to {out_file}.")
        return out_file

    except requests.exceptions.RequestException as e:
        logger.error(f"Pipeline failure: {e}")
        return None

if __name__ == "__main__":
    result = fetch_title_48()
    if result:
        logger.info("Extraction complete. Awaiting downstream Vector Search ingester.")
