import pandas as pd
import os
import re
from collections import defaultdict
from pathlib import Path

def monthly_agencies_time():
    """
    Build one CSV per county with rows=agencies and columns=YYYY-MM + month-to-month deltas,
    summed across FY 2023–2025.
    """
    input_dirs = [
        "../data/FY 2023 Split by County", 
        "../data/FY 2024 Split by County", 
        "../data/FY 2025 Split by County", 
    ]
    out_dir = Path("../data/Agency Distribution Over Time")
    out_dir.mkdir(parents=True, exist_ok=True)

    # collect per-county long tables here
    by_county_long = defaultdict(list)

    def get_county_from_filename(name: str) -> str:
        stem = Path(name).stem
        m = re.match(r"([A-Za-z\s]+?)(?:[_\-\s]|$)", stem)
        return (m.group(1) if m else stem).strip().title()

    for input_dir in input_dirs:
        if not os.path.exists(input_dir):
            print(f"Missing directory: {input_dir}")
            continue

        for filename in os.listdir(input_dir):
            if not filename.lower().endswith(".csv"):
                continue

            county_name = get_county_from_filename(filename)
            if county_name in {"Fbshare", "Other"}:
                continue

            file_path = os.path.join(input_dir, filename)
            try:
                df = pd.read_csv(file_path)
            except Exception as e:
                print(f"Failed to load {filename}: {e}")
                continue

            df.columns = df.columns.str.strip()

            # Required columns
            agency_col = "Agency Name" 
            weight_col = "Weight" 
            date_col = "Pickup Delivery Date" 

            if not agency_col or not weight_col or not date_col:
                print(f"Missing expected columns in {filename}; skipping.")
                continue

            # Parse date → month (YYYY-MM)
            df[date_col] = pd.to_datetime(
                df[date_col],
                format="%m/%d/%Y %I:%M:%S %p",  # e.g., 04/15/2024 03:27:00 PM
                errors="coerce",
                )
            df["Month"] = df[date_col].dt.to_period("M").astype(str)

            # Long table: Month, Agency, Weight (summed)
            group_by_agency = (
                df.groupby(["Month", agency_col], as_index=False)[weight_col]
                  .sum()
                  .rename(columns={agency_col: "Agency", weight_col: "Weight"})
            )

            # Store for this county
            by_county_long[county_name].append(group_by_agency)

    # Build per-county wide output with deltas
    for county, parts in by_county_long.items():
        long_df = pd.concat(parts, ignore_index=True)
        # Combine again in case multiple files share same (Month, Agency)
        long_df = (
            long_df.groupby(["Month", "Agency"], as_index=False)["Weight"]
                   .sum()
        )

        # Pivot → rows=Agency, cols=YYYY-MM
        months = sorted(long_df["Month"].unique())
        wide = (
            long_df.pivot(index="Agency", columns="Month", values="Weight")
                   .reindex(columns=months)
                   .fillna(0.0)
        )

        # Month-to-month deltas
        for i in range(1, len(months)):
            cur_m, prev_m = months[i], months[i-1]
            wide[f"{cur_m}_delta"] = wide[cur_m] - wide[prev_m]

        wide = wide.reset_index()

        out_path = out_dir / f"{county.replace(' ', '_')}_agency_monthly_2023_2025.csv"
        wide.to_csv(out_path, index=False)
        print(f"[OK] Wrote {out_path} (rows={len(wide)})")

monthly_agencies_time()