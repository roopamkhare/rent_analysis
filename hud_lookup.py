import argparse
import json
import os
from pathlib import Path

import pandas as pd
import requests


DATA_DIR = Path("hud_data")
DATA_DIR.mkdir(exist_ok=True)

# URLs (from HUD User dataset pages)
MULTIFAMILY_XLS = (
    "https://www.huduser.gov/portal/sites/default/files/xls/multifamily_physical_inspection_scores_08252025.xlsx"
)
PUBLIC_HOUSING_XLS = (
    "https://www.huduser.gov/portal/sites/default/files/xls/public_housing_physical_inspection_scores_08252025.xlsx"
)


def download(url: str, dest: Path) -> Path:
    if dest.exists():
        return dest
    r = requests.get(url, stream=True, timeout=60)
    r.raise_for_status()
    with open(dest, "wb") as f:
        for chunk in r.iter_content(1024 * 1024):
            if chunk:
                f.write(chunk)
    return dest


def load_excel(path: Path) -> pd.DataFrame:
    # Read all sheets into a single DataFrame (concatenate)
    xls = pd.read_excel(path, sheet_name=None)
    dfs = []
    for name, df in xls.items():
        df = df.copy()
        df["_sheet"] = name
        dfs.append(df)
    if dfs:
        return pd.concat(dfs, ignore_index=True, sort=False)
    return pd.DataFrame()


def find_matches(df: pd.DataFrame, query: str):
    q = query.lower()
    matches = []
    # Search across string columns for query substring
    str_cols = [c for c in df.columns if df[c].dtype == object]
    for idx, row in df.iterrows():
        for c in str_cols:
            val = row.get(c)
            if isinstance(val, str) and q in val.lower():
                matches.append((idx, c, val))
                break
    return matches


def main():
    parser = argparse.ArgumentParser(description="HUD dataset address/property lookup")
    parser.add_argument("query", nargs="+", help="Address or search string")
    args = parser.parse_args()
    query = " ".join(args.query)

    print("Downloading HUD datasets (may take a moment)...")
    mf_path = download(MULTIFAMILY_XLS, DATA_DIR / os.path.basename(MULTIFAMILY_XLS))
    ph_path = download(PUBLIC_HOUSING_XLS, DATA_DIR / os.path.basename(PUBLIC_HOUSING_XLS))

    print(f"Loading {mf_path}...")
    mf_df = load_excel(mf_path)
    print(f"Loaded multifamily rows: {len(mf_df)}")

    print(f"Searching for '{query}' in multifamily dataset...")
    mf_matches = find_matches(mf_df, query)

    print(f"Loading {ph_path}...")
    ph_df = load_excel(ph_path)
    print(f"Loaded public housing rows: {len(ph_df)}")

    print(f"Searching for '{query}' in public housing dataset...")
    ph_matches = find_matches(ph_df, query)

    out = {
        "query": query,
        "multifamily_matches": [],
        "public_housing_matches": [],
    }

    for idx, col, val in mf_matches:
        row = mf_df.loc[idx].to_dict()
        out["multifamily_matches"].append({"match_column": col, "match_value": val, "row": row})

    for idx, col, val in ph_matches:
        row = ph_df.loc[idx].to_dict()
        out["public_housing_matches"].append({"match_column": col, "match_value": val, "row": row})

    Path("json").mkdir(exist_ok=True)
    out_file = Path(f"json/hud_lookup_{query.replace(' ', '_')}.json")
    with open(out_file, "w") as f:
        json.dump(out, f, indent=2, default=str)

    print(f"Results saved to {out_file}")


if __name__ == "__main__":
    main()
