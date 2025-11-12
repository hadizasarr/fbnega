# - Reads ALL FY folders (2023–2025), concatenates into one continuous time series
# - Outputs:
#     1) One CSV per county (full 2023–2025)
#     2) One master CSV combining all counties (adds County column)
# - Computes delta and pct_change (pct in percent units, 3 decimals)
# - Collapses consecutive zero stretches (dist_volume==0 & delta==0) to "YYYY-MM to YYYY-MM"

import pandas as pd
from pathlib import Path

def _compress_zero_runs(df, group_cols):
    """
    Collapse consecutive rows per group (e.g., ['County','Agency']) where
    dist_volume==0 and delta==0 into one row with Time like "YYYY-MM to YYYY-MM".
    Expects columns: group_cols + ['Time','dist_volume','delta','pct_change'].
    Returns compressed DataFrame with same columns.
    """
    out_rows = []
    sort_cols = group_cols + ["Time"]
    df_sorted = df.sort_values(sort_cols).copy()

    # Normalize Time to monthly string
    df_sorted["Time"] = pd.PeriodIndex(df_sorted["Time"], freq="M").astype(str)
    df_sorted = df_sorted.sort_values(sort_cols)

    for keys, g in df_sorted.groupby(group_cols, sort=False, dropna=False):
        g = g.copy().sort_values("Time")
        run_open = False
        run_start = run_end = None

        for _, row in g.iterrows():
            is_zero = (float(row["dist_volume"]) == 0.0) and (float(row["delta"]) == 0.0)
            t = row["Time"]

            if is_zero:
                if not run_open:
                    run_open = True
                    run_start = t
                    run_end = t
                else:
                    run_end = t
            else:
                if run_open:
                    label = f"{run_start} to {run_end}" if run_start != run_end else run_start
                    newrow = {c: row[c] for c in group_cols}
                    newrow.update({"Time": label, "dist_volume": 0.0, "delta": 0.0, "pct_change": 0.0})
                    out_rows.append(newrow)
                    run_open = False
                newrow = {c: row[c] for c in group_cols}
                newrow.update({
                    "Time": t,
                    "dist_volume": float(row["dist_volume"]),
                    "delta": float(row["delta"]),
                    "pct_change": float(row["pct_change"]),
                })
                out_rows.append(newrow)

        if run_open:
            label = f"{run_start} to {run_end}" if run_start != run_end else run_start
            # Pull group keys from the last row to fill group_cols
            last = g.iloc[-1]
            newrow = {c: last[c] for c in group_cols}
            newrow.update({"Time": label, "dist_volume": 0.0, "delta": 0.0, "pct_change": 0.0})
            out_rows.append(newrow)

    return pd.DataFrame(out_rows, columns=group_cols + ["Time","dist_volume","delta","pct_change"])

def monthly_agencies_overtime():
    # Update paths if yours differ
    input_dirs = [
        "../data/FY 2023 Split by County",
        "../data/FY 2024 Split by County",
        "../data/FY 2025 Split by County",
    ]

    out_dir = Path("../output/agency_overtime")
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1) Clear output directory (files only)
    for p in out_dir.glob("*"):
        if p.is_file():
            p.unlink()

    # Discover counties from filenames across all folders
    counties = set()
    for folder in input_dirs:
        p = Path(folder)
        if not p.exists():
            continue
        for f in p.glob("*.csv"):
            # county name assumed at start of filename; take everything before first '(' if present
            county = f.stem.split("(")[0].strip()
            if county:
                counties.add(county)

    def read_county_frames(county):
        frames = []
        for folder in input_dirs:
            folder_path = Path(folder)
            if not folder_path.exists():
                continue
            for f in folder_path.glob("*.csv"):
                if county not in f.stem:
                    continue
                try:
                    df = pd.read_csv(f, dtype=str)
                except Exception as e:
                    print(f"[warn] Could not read {f}: {e}")
                    continue

                # Normalize columns
                df.columns = df.columns.str.strip()
                agency_col = "Agency Name"
                weight_col = "Weight"
                date_col   = "Pickup Delivery Date"
                need = {agency_col, weight_col, date_col}
                if not need.issubset(df.columns):
                    lower = {c.lower(): c for c in df.columns}
                    if {"agency name","weight","pickup delivery date"}.issubset(lower):
                        agency_col = lower["agency name"]
                        weight_col = lower["weight"]
                        date_col   = lower["pickup delivery date"]
                    else:
                        print(f"[skip] Missing cols in {f.name}: need {need}")
                        continue

                # Parse date (strict first, then fallback)
                dt = pd.to_datetime(df[date_col], format="%m/%d/%Y %I:%M:%S %p", errors="coerce")
                if dt.isna().all():
                    dt = pd.to_datetime(df[date_col], errors="coerce")
                df = df[~dt.isna()].copy()
                df["Month"] = dt.dt.to_period("M").astype(str)

                # Weight to float
                df[weight_col] = pd.to_numeric(df[weight_col], errors="coerce").fillna(0.0)

                # Aggregate -> Month × Agency, add County
                part = (
                    df.groupby(["Month", agency_col], as_index=False)[weight_col]
                      .sum()
                      .rename(columns={agency_col: "Agency", weight_col: "dist_volume"})
                )
                part["County"] = county
                frames.append(part)
        return frames

    all_counties_rows = []  # to build one master CSV at the end

    for county in sorted(counties):
        parts = read_county_frames(county)
        if not parts:
            continue

        monthly = pd.concat(parts, ignore_index=True)

        # Aggregate across all years (this is the key concatenation step)
        monthly = (
            monthly.groupby(["County","Month","Agency"], as_index=False)["dist_volume"]
                   .sum()
        )

        # Build complete Month × Agency panel per county
        monthly["Month"] = pd.PeriodIndex(monthly["Month"], freq="M").astype(str)
        min_m = monthly["Month"].min()
        max_m = monthly["Month"].max()
        full_index = pd.period_range(min_m, max_m, freq="M").astype(str)

        # Pivot within county, then restack to ensure continuous monthly coverage
        wide = (
            monthly.pivot_table(index=["County","Agency"], columns="Month", values="dist_volume", fill_value=0.0)
                   .reindex(columns=full_index, fill_value=0.0)
        )

        long_df = (
            wide.stack()
                .rename("dist_volume")
                .reset_index()
                .rename(columns={"level_2": "Time"})
        )

        # Compute deltas and pct_change within each County×Agency
        long_df = long_df.sort_values(["County","Agency","Time"]).reset_index(drop=True)
        long_df["delta"] = long_df.groupby(["County","Agency"])["dist_volume"].diff().fillna(0.0)

        prev = long_df.groupby(["County","Agency"])["dist_volume"].shift(1)
        pct = (long_df["dist_volume"] - prev) / prev
        pct.loc[(prev == 0) & (long_df["dist_volume"] == 0)] = 0.0
        long_df["pct_change"] = (pct.fillna(0.0) * 100).round(3)

        # Compress zero runs per County×Agency
        compressed = _compress_zero_runs(
            long_df[["County","Agency","Time","dist_volume","delta","pct_change"]],
            group_cols=["County","Agency"]
        )

        # Save per-county CSV (full 2023–2025)
        base = county.replace(" ","_")
        (out_dir / f"{base}_agency_timeseries.csv").write_text(
            compressed.to_csv(index=False)
        )

        all_counties_rows.append(compressed)

        print(f"[OK] {county}: wrote {base}_agency_timeseries.csv")

    # Write one master CSV with ALL counties combined
    if all_counties_rows:
        master = pd.concat(all_counties_rows, ignore_index=True)
        master_csv = out_dir / "ALLCOUNTIES_agency_timeseries.csv"
        master.to_csv(master_csv, index=False)
        print(f"[OK] Wrote {master_csv.name}")

if __name__ == "__main__":
    monthly_agencies_overtime()

