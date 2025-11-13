import pandas as pd
import os
import re
from pathlib import Path
from collections import defaultdict

def _compress_zero_runs(long_full: pd.DataFrame) -> pd.DataFrame:
    """
    For each Agency, collapse consecutive months where dist_volume == 0,
    delta == 0, and pct_change == 0 into a single row whose Time is
    'YYYY-MM to YYYY-MM'. Single zero months remain as-is.
    Assumes Time is 'YYYY-MM'.
    """
    df = long_full.copy()
    df["_Period"] = pd.PeriodIndex(df["Time"], freq="M")

    out_rows = []
    for agency, g in df.sort_values(["Agency", "_Period"]).groupby("Agency", sort=False):
        g = g.reset_index(drop=True)

        def is_zero_row(i):
            return (
                g.loc[i, "dist_volume"] == 0
                and g.loc[i, "delta"] == 0
                and g.loc[i, "pct_change"] == 0
            )

        i = 0
        n = len(g)
        while i < n:
            if is_zero_row(i):
                # start a zero run
                start = i
                end = i
                # extend while next is the next calendar month AND also zero row
                while (
                    end + 1 < n
                    and is_zero_row(end + 1)
                    and g.loc[end + 1, "_Period"] == g.loc[end, "_Period"] + 1
                ):
                    end += 1

                if end > start:  # compress run of length >= 2
                    out_rows.append(
                        {
                            "Agency": agency,
                            "Time": f"{g.loc[start,'Time']} to {g.loc[end,'Time']}",
                            "dist_volume": 0.0,
                            "delta": 0.0,
                            "pct_change": 0.0,
                        }
                    )
                else:
                    # single zero month, keep as-is
                    out_rows.append(
                        {
                            "Agency": agency,
                            "Time": g.loc[start, "Time"],
                            "dist_volume": g.loc[start, "dist_volume"],
                            "delta": g.loc[start, "delta"],
                            "pct_change": g.loc[start, "pct_change"],
                        }
                    )
                i = end + 1
            else:
                # nonzero row, keep
                out_rows.append(
                    {
                        "Agency": agency,
                        "Time": g.loc[i, "Time"],
                        "dist_volume": g.loc[i, "dist_volume"],
                        "delta": g.loc[i, "delta"],
                        "pct_change": g.loc[i, "pct_change"],
                    }
                )
                i += 1

    out = pd.DataFrame(out_rows)
    return out[["Agency", "Time", "dist_volume", "delta", "pct_change"]]


def monthly_agencies_time():
    """
    Reads FY 2023–2025 county CSVs and writes, for each county, a long time series:
    Agency, Time (YYYY-MM or 'YYYY-MM to YYYY-MM' for compressed zero runs),
    dist_volume, delta, pct_change
    """
    input_dirs = [
        "../data/FY 2023 Split by County",
        "../data/FY 2024 Split by County",
        "../data/FY 2025 Split by County",
    ]

    out_dir = Path("../data/Agency Distribution Over Time")
    out_dir.mkdir(parents=True, exist_ok=True)
    # clean the output folder to only contain most recent run
    for p in out_dir.glob("*.csv"):
        p.unlink()

    by_county_parts = defaultdict(list)

    def county_from_filename(filename: str) -> str:
        stem = Path(filename).stem
        m = re.match(r"([A-Za-z\s]+?)(?:[_\-\s]|$)", stem)
        return (m.group(1) if m else stem).strip().title()

    for input_dir in input_dirs:
        if not os.path.exists(input_dir):
            print(f"Missing directory: {input_dir}")
            continue

        for filename in os.listdir(input_dir):
            if not filename.lower().endswith(".csv"):
                continue

            county = county_from_filename(filename)
            if county.lower() in {"fbshare", "other"}:
                continue

            file_path = os.path.join(input_dir, filename)
            try:
                df = pd.read_csv(file_path)
            except Exception as e:
                print(f"Failed to load {filename}: {e}")
                continue

            # Clean columns
            df.columns = df.columns.str.strip()

            agency_col = "Agency Name"
            weight_col = "Weight"
            date_col   = "Pickup Delivery Date"

            required = {agency_col, weight_col, date_col}
            missing = required - set(df.columns)
            if missing:
                print(f"Missing columns {missing} in {filename}; skipping.")
                continue

            # Parse date -> month; try explicit format, then fallback
            dt = pd.to_datetime(df[date_col], format="%m/%d/%Y %I:%M:%S %p", errors="coerce")
            if dt.isna().all():
                dt = pd.to_datetime(df[date_col], errors="coerce")
            df[date_col] = dt
            df = df.dropna(subset=[date_col])
            df["Month"] = df[date_col].dt.to_period("M").astype(str)

            # Per-file aggregation (Month, Agency, Weight)
            part = (
                df.groupby(["Month", agency_col], as_index=False)[weight_col]
                  .sum()
                  .rename(columns={agency_col: "Agency", weight_col: "dist_volume"})
            )
            by_county_parts[county].append(part)

    # Build per-county long outputs with deltas
    for county, parts in by_county_parts.items():
        long_df = pd.concat(parts, ignore_index=True)

        # Combine again across files
        long_df = long_df.groupby(["Month", "Agency"], as_index=False)["dist_volume"].sum()

        # Ensure all months present per agency; fill missing with 0
        months_sorted = sorted(long_df["Month"].unique())
        wide = (
            long_df.pivot(index="Agency", columns="Month", values="dist_volume")
                  .reindex(columns=months_sorted)
                  .fillna(0.0)
        )
        # Ensure stacked column becomes 'Time'
        wide.columns.name = "Time"
        long_full = (
            wide.stack()
            .rename("dist_volume")
            .reset_index()
        )
        if "Time" not in long_full.columns:
            long_full = long_full.rename(columns={"Month": "Time", "level_1": "Time"})

        # Compute delta and pct_change per agency
        long_full = long_full.sort_values(["Agency", "Time"])
        long_full["delta"] = long_full.groupby("Agency")["dist_volume"].diff().fillna(0.0)

        prev = long_full.groupby("Agency")["dist_volume"].shift(1)
        pct = (long_full["dist_volume"] - prev) / prev
        pct.loc[prev.eq(0) & long_full["dist_volume"].eq(0)] = 0.0
        long_full["pct_change"] = pct.fillna(0.0).round(3)  # 3 decimals

        long_full = long_full[["Agency", "Time", "dist_volume", "delta", "pct_change"]]

        # >>> NEW: compress consecutive zero runs
        compressed = _compress_zero_runs(long_full)

        out_path = out_dir / f"{county.replace(' ', '_')}_agency_timeseries.csv"
        compressed.to_csv(out_path, index=False)
        print(f"[OK] Wrote {out_path} (rows={len(compressed)})")

if __name__ == "__main__":
    monthly_agencies_time()