import os
import re
from pathlib import Path
from collections import defaultdict

import numpy as np
import pandas as pd

try:
    from sklearn.ensemble import IsolationForest
    SKLEARN_OK = True
except Exception:
    SKLEARN_OK = False


# ---------- NEW: helper to compress zero runs (unchanged from before) ----------
def _compress_zero_runs(long_full: pd.DataFrame) -> pd.DataFrame:
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
                start = i
                end = i
                while (
                    end + 1 < n
                    and is_zero_row(end + 1)
                    and g.loc[end + 1, "_Period"] == g.loc[end, "_Period"] + 1
                ):
                    end += 1

                if end > start:
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


# ---------- NEW: anomaly helpers ----------
def _robust_z(series: pd.Series) -> pd.Series:
    """Median/MAD z-score (scaled). If MAD==0, returns 0."""
    med = series.median()
    mad = (series - med).abs().median()
    if mad == 0 or np.isnan(mad):
        return pd.Series(np.zeros(len(series)), index=series.index, dtype=float)
    return 0.6745 * (series - med) / mad

def _seasonal_expected_by_month(df_agency: pd.DataFrame) -> pd.Series:
    """Expected value = median dist by month-of-year over history."""
    months = pd.PeriodIndex(df_agency["Time"], freq="M").month
    by_m = df_agency.assign(_m=months).groupby("_m")["dist_volume"].median()
    return months.map(by_m).astype(float)

def _yoy_change(series: pd.Series) -> pd.Series:
    """YoY % change vs t-12, handling div-by-zero."""
    prev = series.shift(12)
    yoy = (series - prev) / prev
    yoy.loc[(prev == 0) & (series == 0)] = 0.0
    return yoy

def _run_isoforest(df_agency: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    """Return (iso_label, iso_score). If sklearn unavailable or too few rows, zeros."""
    n = len(df_agency)
    if not SKLEARN_OK or n < 12:
        return pd.Series(np.zeros(n, dtype=int), index=df_agency.index), pd.Series(np.zeros(n), index=df_agency.index)

    feats = df_agency[["dist_volume", "delta", "pct_change", "residual", "robust_z", "yoy_pct_change"]].fillna(0.0)
    try:
        iso = IsolationForest(random_state=0, contamination="auto")
        iso.fit(feats)
        labels = iso.predict(feats)  # -1 anomaly, 1 normal
        scores = iso.decision_function(feats)  # lower is more anomalous
        return pd.Series(labels, index=df_agency.index), pd.Series(scores, index=df_agency.index)
    except Exception:
        return pd.Series(np.zeros(n, dtype=int), index=df_agency.index), pd.Series(np.zeros(n), index=df_agency.index)

def _detect_anomalies(long_full: pd.DataFrame, county: str,
                      z_thresh: float = 3.5,
                      yoy_thresh: float = 1.0) -> pd.DataFrame:
    """
    long_full: monthly, per agency (UNCOMPRESSED). Columns: Agency, Time, dist_volume, delta, pct_change
    Returns only anomalous rows with reason codes.
    """
    df = long_full.copy()
    df = df.sort_values(["Agency", "Time"]).reset_index(drop=True)

    # Seasonality baseline & residuals per agency
    df["expected_seasonal"] = df.groupby("Agency", group_keys=False).apply(_seasonal_expected_by_month)
    df["residual"] = df["dist_volume"] - df["expected_seasonal"]

    # Robust z of residuals per agency
    df["robust_z"] = df.groupby("Agency")["residual"].transform(_robust_z)

    # YoY % change (series is continuous monthly due to earlier reindex)
    df["yoy_pct_change"] = df.groupby("Agency")["dist_volume"].transform(_yoy_change)

    # Isolation Forest per agency
    iso_labels = []
    iso_scores = []
    for agency, g in df.groupby("Agency"):
        labels, scores = _run_isoforest(g)
        iso_labels.append(labels)
        iso_scores.append(scores)
    df["iso_label"] = pd.concat(iso_labels).sort_index()
    df["iso_score"] = pd.concat(iso_scores).sort_index()

    # Rule flags
    df["flag_z"] = df["robust_z"].abs() >= z_thresh
    df["flag_iso"] = df["iso_label"].eq(-1)
    df["flag_yoy"] = df["yoy_pct_change"].abs() >= yoy_thresh

    # Build reason codes
    def reasons(row):
        r = []
        if row["flag_z"]:
            r.append(f"ROBUST_Z={row['robust_z']:.2f}")
        if row["flag_yoy"]:
            r.append(f"YOY={row['yoy_pct_change']:.2f}")
        if row["flag_iso"]:
            r.append("ISOFOREST")
        return "; ".join(r)

    df["reasons"] = df.apply(reasons, axis=1)
    df["County"] = county

    anomalies = df[(df["flag_z"]) | (df["flag_yoy"]) | (df["flag_iso"])].copy()
    keep_cols = [
        "County", "Agency", "Time",
        "dist_volume", "delta", "pct_change",
        "expected_seasonal", "residual", "robust_z",
        "yoy_pct_change", "iso_label", "iso_score", "reasons"
    ]
    return anomalies[keep_cols].reset_index(drop=True)


def monthly_agencies_time():
    """
    Reads FY 2023–2025 county CSVs and writes, for each county, a long time series:
    Agency, Time (YYYY-MM or compressed 'YYYY-MM to YYYY-MM' for zero-runs),
    dist_volume, delta, pct_change
    Also writes anomalies.csv across all counties with reason codes.
    """
    input_dirs = [
        "../data/FY 2023 Split by County",
        "../data/FY 2024 Split by County",
        "../data/FY 2025 Split by County",
    ]

    out_dir = Path("../data/Agency Distribution Over Time")
    out_dir.mkdir(parents=True, exist_ok=True)
    for p in out_dir.glob("*.csv"):
        p.unlink()

    by_county_parts = defaultdict(list)
    all_anomalies = []  # NEW: collect anomalies across counties

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

            df.columns = df.columns.str.strip()
            agency_col = "Agency Name"
            weight_col = "Weight"
            date_col   = "Pickup Delivery Date"

            required = {agency_col, weight_col, date_col}
            missing = required - set(df.columns)
            if missing:
                print(f"Missing columns {missing} in {filename}; skipping.")
                continue

            dt = pd.to_datetime(df[date_col], format="%m/%d/%Y %I:%M:%S %p", errors="coerce")
            if dt.isna().all():
                dt = pd.to_datetime(df[date_col], errors="coerce")
            df[date_col] = dt
            df = df.dropna(subset=[date_col])
            df["Month"] = df[date_col].dt.to_period("M").astype(str)

            part = (
                df.groupby(["Month", agency_col], as_index=False)[weight_col]
                  .sum()
                  .rename(columns={agency_col: "Agency", weight_col: "dist_volume"})
            )
            by_county_parts[county].append(part)

    # Build per-county long outputs, detect anomalies on UNCOMPRESSED, then write compressed CSVs
    for county, parts in by_county_parts.items():
        long_df = pd.concat(parts, ignore_index=True)
        long_df = long_df.groupby(["Month", "Agency"], as_index=False)["dist_volume"].sum()

        months_sorted = sorted(long_df["Month"].unique())
        wide = (
            long_df.pivot(index="Agency", columns="Month", values="dist_volume")
                  .reindex(columns=months_sorted)
                  .fillna(0.0)
        )
        wide.columns.name = "Time"
        long_full = (
            wide.stack()
            .rename("dist_volume")
            .reset_index()
        )
        if "Time" not in long_full.columns:
            long_full = long_full.rename(columns={"Month": "Time", "level_1": "Time"})

        long_full = long_full.sort_values(["Agency", "Time"])
        long_full["delta"] = long_full.groupby("Agency")["dist_volume"].diff().fillna(0.0)

        prev = long_full.groupby("Agency")["dist_volume"].shift(1)
        pct = (long_full["dist_volume"] - prev) / prev
        pct.loc[prev.eq(0) & long_full["dist_volume"].eq(0)] = 0.0
        long_full["pct_change"] = pct.fillna(0.0).round(3)

        long_full = long_full[["Agency", "Time", "dist_volume", "delta", "pct_change"]]

        # --- NEW: anomaly detection on the monthly (uncompressed) table ---
        anomalies = _detect_anomalies(long_full, county)
        if len(anomalies):
            all_anomalies.append(anomalies)

        # --- Write compressed per-county CSV (same as before) ---
        compressed = _compress_zero_runs(long_full)
        out_path = out_dir / f"{county.replace(' ', '_')}_agency_timeseries_2023_2025.csv"
        compressed.to_csv(out_path, index=False)
        print(f"[OK] Wrote {out_path} (rows={len(compressed)})")

    # --- Write anomalies.csv across all counties ---
    if all_anomalies:
        anomalies_df = pd.concat(all_anomalies, ignore_index=True).sort_values(["County", "Agency", "Time"])
        anomalies_df.to_csv(out_dir / "anomalies.csv", index=False)
        print(f"[OK] Wrote {out_dir/'anomalies.csv'} (rows={len(anomalies_df)})")
    else:
        # Still write an empty file with headers for consistency
        pd.DataFrame(
            columns=[
                "County","Agency","Time","dist_volume","delta","pct_change",
                "expected_seasonal","residual","robust_z","yoy_pct_change",
                "iso_label","iso_score","reasons"
            ]
        ).to_csv(out_dir / "anomalies.csv", index=False)
        print(f"[OK] Wrote {out_dir/'anomalies.csv'} (rows=0)")


if __name__ == "__main__":
    monthly_agencies_time()
