import pandas as pd
import json
import os
from pathlib import Path

# Repo-relative paths (data/ is gitignored — local only). One-time conversion script;
# do not rerun without first confirming data/ is not tracked in git.
REPO_ROOT = Path(__file__).resolve().parents[1]
EXCEL_PATH = REPO_ROOT / "data" / "raw" / "temp_census" / "Govt_Units_2022_Final.xlsx"
OUTPUT_JSONL = REPO_ROOT / "data" / "processed" / "census" / "master_gov_units_2022.jsonl"

# Sheets to process
SHEETS = ['General Purpose', 'Special District', 'DEP School District']

def generate_semantic_content(row):
    """Generate a rich natural language string for the local FAISS embeddings."""
    name = str(row.get('UNIT_NAME', 'Unknown Entity')).title()
    govt_type = str(row.get('UNIT_TYPE', 'Government Unit'))
    state = str(row.get('STATE', 'Unknown State'))
    county = str(row.get('COUNTY_AREA_NAME', 'Unknown County')).title()
    pop = row.get('POPULATION', 0)
    
    content = f"The {name} is a {govt_type} located in {county}, {state}. "
    if pop and pop > 0:
        try:
            content += f"It has a documented population of approximately {int(pop):,}. "
        except:
            pass
    content += f"Census GIDID: {row.get('CENSUS_ID_GIDID')}. "
    content += f"This entity is a sovereign government unit tracked in the 2022 Census of Governments."
    return content

def run_ingest():
    # Ensure output directory exists
    OUTPUT_JSONL.parent.mkdir(parents=True, exist_ok=True)
    
    print(f"Starting master ingest from {EXCEL_PATH}...")
    total_count = 0
    
    try:
        xl = pd.ExcelFile(EXCEL_PATH)
        available_sheets = xl.sheet_names
        print(f"Available sheets: {available_sheets}")
        
        # Use only sheets that exist and are relevant
        sheets_to_process = [s for s in SHEETS if s in available_sheets]
        
        with open(OUTPUT_JSONL, mode='w', encoding='utf-8') as f_out:
            for sheet_name in sheets_to_process:
                print(f"Processing sheet: {sheet_name}...")
                df = pd.read_excel(xl, sheet_name=sheet_name)
                print(f"  Loaded {len(df)} records from {sheet_name}.")
                
                for _, row in df.iterrows():
                    # Construct Sovereign Record
                    record = {
                        "id": str(row.get('CENSUS_ID_GIDID')),
                        "name": str(row.get('UNIT_NAME')).title(),
                        "content": generate_semantic_content(row),
                        "metadata": {
                            "state_code": str(row.get('STATE')),
                            "government_type": str(row.get('UNIT_TYPE')),
                            "county": str(row.get('COUNTY_AREA_NAME')).title(),
                            "population": int(row.get('POPULATION', 0)) if pd.notnull(row.get('POPULATION')) else 0,
                            "fips_state": int(row.get('FIPS_STATE', 0)) if pd.notnull(row.get('FIPS_STATE')) else 0
                        },
                        "contact_skeleton": {
                            "web_address": str(row.get('WEB_ADDRESS')) if pd.notnull(row.get('WEB_ADDRESS')) else None,
                            "caio_email": None
                        }
                    }
                    
                    # Write as JSONL
                    f_out.write(json.dumps(record) + "\n")
                    total_count += 1
                    
                    if total_count % 10000 == 0:
                        print(f"Processed {total_count} Sovereign records...")
                        
        print(f"Success! Sovereign Arsenal Master created at {OUTPUT_JSONL}")
        print(f"Grand Total High-Authority Units: {total_count}")
        
    except Exception as e:
        print(f"Error during master ingest: {e}")

if __name__ == "__main__":
    run_ingest()
