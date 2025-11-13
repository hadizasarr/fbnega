# declining_agency_watchlist.py
# Inputs: ../data/Agency Distribution Over Time/*_agency_timeseries*.csv
# Outputs (per county): ../data/Agency Insights/<County>_declining_agency_watchlist.csv
#
# Flags agencies that are steadily trending down and/or more inconsistent lately.
# Explanations are plain-English and include a "same months last year" snapshot.

from pathlib import Path
import numpy as np
import pandas as pd

# ------------------ Tunable thresholds ------------------
MIN_MONTHS = 10        # need at least this many total months to evaluate
RECENT_WIN = 12        # "recent" window size; auto-shrinks if history is short
DECLINE_SLOPE_PERC = -0.02   # normalized slope threshold per month (~ -2%/mo)
RECENT_DROP_PERC   = -0.15   # recent median <= prior median -15%
CV_INCREASE_PERC   = 0.50    # recent variability >= 50% higher than prior
MOM_VOL_INCREASE   = 0.30    # recent MoM swing up by >= 30 percentage points
MIN_NONZERO_SHARE  = 0.50    # each window must be >= 50% non-zero months
# --------------------------------------------------------

# ---------- Loaders (handles monthly rows and compressed intervals) ----------
def _expand_time_col(df: pd.DataFrame) -> pd.DataFrame:
    """Accepts 'YYYY-MM' or 'YYYY-MM to YYYY-MM'; returns monthly rows only."""
    rows = []
    for _, r in df.iterrows():
        t = str(r["Time"])
        if " to " in t:  # compressed zero-run
            start, end = t.split(" to ")
            months = pd.period_range(start, end, freq="M").astype(str)
            for m in months:
                rows.append({"Agency": r["Agency"], "Time": m, "dist_volume": 0.0})
        else:
            rows.append({"Agency": r["Agency"], "Time": t, "dist_volume": float(r["dist_volume"])})
    return pd.DataFrame(rows)

def load_from_agency_timeseries(folder: str = "../data/Agency Distribution Over Time") -> pd.DataFrame:
    """Reads *_agency_timeseries*.csv → columns: County, Agency, Time (YYYY-MM), dist_volume."""
    folder_p = Path(folder)
    parts = []
    for f in folder_p.glob("*_agency_timeseries*.csv"):
        county = f.stem.split("_")[0].title()  # e.g., Banks_agency_timeseries -> Banks
        df = pd.read_csv(f)
        needed = {"Agency", "Time", "dist_volume"}
        if not needed.issubset(df.columns):
            print(f"[WARN] {f.name} missing {needed - set(df.columns)}; skipping.")
            continue
        df_expanded = _expand_time_col(df[["Agency", "Time", "dist_volume"]].copy())
        df_expanded["County"] = county
        parts.append(df_expanded[["County", "Agency", "Time", "dist_volume"]])
    if not parts:
        return pd.DataFrame(columns=["County", "Agency", "Time", "dist_volume"])

    all_df = pd.concat(parts, ignore_index=True)

    # Ensure each County–Agency has a contiguous month grid
    rows = []
    for (county, agency), g in all_df.groupby(["County", "Agency"], sort=False):
        g = g.sort_values("Time")
        rng = pd.period_range(g["Time"].min(), g["Time"].max(), freq="M").astype(str)
        s = g.set_index("Time")["dist_volume"].reindex(rng, fill_value=0.0)
        rows.append(pd.DataFrame({"County": county, "Agency": agency, "Time": rng, "dist_volume": s.values}))
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame(columns=["County","Agency","Time","dist_volume"])
# ---------------------------------------------------------------------------

# ------------------------- Metric helpers ----------------------------------
def _clean_pct(x: pd.Series) -> pd.Series:
    return x.replace([np.inf, -np.inf], np.nan).fillna(0.0)

def _coef_of_variation(x: np.ndarray) -> float:
    m = np.nanmean(x)
    s = np.nanstd(x, ddof=1) if len(x) > 1 else 0.0
    return (s / m) if m > 0 else np.nan

def _linear_slope_per_month(y: np.ndarray) -> float:
    n = len(y)
    if n < 2:
        return 0.0
    x = np.arange(n, dtype=float)
    if np.all(np.isnan(y)) or np.nanstd(y) == 0:
        return 0.0
    y_fit = np.nan_to_num(y, nan=0.0)
    slope, _ = np.polyfit(x, y_fit, 1)
    return float(slope)
# ---------------------------------------------------------------------------

def declining_agency_watchlist():
    """
    Writes one CSV per county to ../data/Agency Insights/<County>_declining_agency_watchlist.csv
    Flags agencies that are steadily trending down and/or more inconsistent recently.
    Includes a "same months last year" snapshot and plain-English explanations.
    """
    # ---- Load per-county timeseries CSVs as inputs ----
    df = load_from_agency_timeseries("../data/Agency Distribution Over Time")

    out_dir = Path("../data/Agency Insights")
    out_dir.mkdir(parents=True, exist_ok=True)

    # ---- Clear previous outputs so this folder only has the latest run ----
    for p in out_dir.glob("*.csv"):
        p.unlink()

    if df.empty:
        print(f"[OK] No input series found. Wrote no county files.")
        return

    total_series = 0
    total_flagged = 0

    # Standard column order for outputs
    out_columns = [
        "County","Agency",
        "median_prev","median_recent","median_change_pct",
        "slope_per_month","slope_normalized",
        "mom_vol_prev","mom_vol_recent",
        "nonzero_share_prev","nonzero_share_recent",
        "last_year_median","last_year_total","last_year_nonzero_share","last_year_info",
        "flags","explanations",
    ]

    # Process and write per county
    for county, df_c in df.groupby("County", sort=False):
        results = []
        for agency, g in df_c.groupby("Agency", sort=False):
            g = g.sort_values("Time").reset_index(drop=True)
            y = g["dist_volume"].astype(float).values
            n = len(y)
            if n < MIN_MONTHS:
                continue

            # Window split
            recent = min(RECENT_WIN, n // 2)
            recent = max(recent, 6)
            prev_win = n - recent
            if prev_win < 4:
                continue

            total_series += 1

            y_prev = y[:prev_win]
            y_recent = y[prev_win:]

            # Core signals
            med_prev = float(np.median(y_prev)) if len(y_prev) else 0.0
            med_recent = float(np.median(y_recent)) if len(y_recent) else 0.0
            median_change_pct = (med_recent - med_prev) / med_prev if med_prev > 0 else (0.0 if med_recent == 0 else -1.0)

            slope = _linear_slope_per_month(y)
            overall_median = float(np.median(y)) if np.median(y) > 0 else 1.0
            slope_norm = slope / overall_median

            prev_full = np.roll(y, 1); prev_full[0] = np.nan
            valid = (~np.isnan(prev_full)) & (prev_full > 0) & (y > 0)
            mom_pct = np.zeros_like(y, dtype=float)
            mom_pct[valid] = (y[valid] - prev_full[valid]) / prev_full[valid]
            mom_pct = _clean_pct(pd.Series(mom_pct)).values
            mom_prev = float(np.nanmean(np.abs(mom_pct[1:prev_win]))) if prev_win > 1 else 0.0
            mom_recent = float(np.nanmean(np.abs(mom_pct[prev_win+1:]))) if recent > 1 else 0.0
            nz_prev = float(np.mean(y_prev > 0)) if len(y_prev) else 0.0
            nz_recent = float(np.mean(y_recent > 0)) if len(y_recent) else 0.0

            # "Same months last year" = 12 months immediately before the recent window
            ly_start = max(0, prev_win - 12)
            ly_end = prev_win
            y_lastyear = y[ly_start:ly_end]
            has_lastyear = len(y_lastyear) >= 6

            last_year_median = float(np.median(y_lastyear)) if has_lastyear else np.nan
            last_year_total  = float(np.nansum(y_lastyear)) if has_lastyear else np.nan
            last_year_nzshare = float(np.mean(y_lastyear > 0)) if has_lastyear else np.nan

            # Flags + plain-English messages
            flags, messages = [], []

            if slope_norm <= DECLINE_SLOPE_PERC:
                flags.append("DECLINING_TREND")
                messages.append(f"Steady decline about {slope_norm:.1%} per month.")

            if (median_change_pct <= RECENT_DROP_PERC) and (nz_prev >= MIN_NONZERO_SHARE) and (nz_recent >= MIN_NONZERO_SHARE):
                flags.append("LOWER_RECENT_MEDIAN")
                messages.append(f"Typical month now {median_change_pct:.0%} vs earlier "
                                f"(~{med_prev:,.0f} lb → ~{med_recent:,.0f} lb).")

            # Inconsistency (reader-friendly wording)
            cv_prev = _coef_of_variation(y_prev)
            cv_recent = _coef_of_variation(y_recent)
            cv_change_ok = (
                (cv_prev is not None) and (not np.isnan(cv_prev)) and (not np.isnan(cv_recent))
                and (cv_recent > cv_prev) and ((cv_recent - cv_prev) / (cv_prev if cv_prev else 1) >= CV_INCREASE_PERC)
            )
            if cv_change_ok and (nz_prev >= MIN_NONZERO_SHARE) and (nz_recent >= MIN_NONZERO_SHARE):
                flags.append("VARIABILITY_UP")
                messages.append("More up-and-down lately.")

            mom_delta = mom_recent - mom_prev
            if (mom_delta >= MOM_VOL_INCREASE) and (nz_prev >= MIN_NONZERO_SHARE) and (nz_recent >= MIN_NONZERO_SHARE):
                flags.append("MOM_VOLATILITY_UP")
                messages.append("Bigger swings between months in the recent period.")

            # De-emphasize mostly-zero patterns unless clear decline
            if (nz_prev < MIN_NONZERO_SHARE or nz_recent < MIN_NONZERO_SHARE):
                if "DECLINING_TREND" not in flags and "LOWER_RECENT_MEDIAN" not in flags:
                    flags, messages = [], []

            if not flags:
                continue

            # Headline + last-year line
            if "DECLINING_TREND" in flags and ("VARIABILITY_UP" in flags or "MOM_VOLATILITY_UP" in flags):
                headline = "Declining and less consistent recently."
            elif "DECLINING_TREND" in flags or "LOWER_RECENT_MEDIAN" in flags:
                headline = "Declining distribution."
            else:
                headline = "Growing inconsistency."

            ly_line = ""
            if has_lastyear and (last_year_median > 0) and (med_recent > 0):
                ly_change = (med_recent - last_year_median) / last_year_median
                ly_line = f" Compared to same months last year: typical month {ly_change:.0%} "\
                          f"({last_year_median:,.0f} lb → {med_recent:,.0f} lb)."

            explanation = (headline + " " + " ".join(messages) + ly_line).strip()
            last_year_info = (
                f"Last year (12 mo): median {last_year_median:,.0f} lb, total {last_year_total:,.0f} lb, "
                f"non-zero {last_year_nzshare:.0%}."
                if has_lastyear else "Not enough data for same-month last year."
            )

            results.append({
                "County": county,
                "Agency": agency,
                "median_prev": round(med_prev, 0),
                "median_recent": round(med_recent, 0),
                "median_change_pct": round(median_change_pct, 3),
                "slope_per_month": round(slope, 2),
                "slope_normalized": round(slope_norm, 4),
                "mom_vol_prev": round(mom_prev, 2),
                "mom_vol_recent": round(mom_recent, 2),
                "nonzero_share_prev": round(nz_prev, 2),
                "nonzero_share_recent": round(nz_recent, 2),
                "last_year_median": round(last_year_median, 0) if has_lastyear else np.nan,
                "last_year_total": round(last_year_total, 0) if has_lastyear else np.nan,
                "last_year_nonzero_share": round(last_year_nzshare, 2) if has_lastyear else np.nan,
                "last_year_info": last_year_info,
                "flags": ",".join(flags),
                "explanations": explanation
            })
            total_flagged += 1

        # --- safe build even if empty (no KeyError) ---
        if results:
            county_df = pd.DataFrame(results)[out_columns].sort_values(
                ["Agency", "flags", "slope_normalized", "median_change_pct"]
            )
        else:
            county_df = pd.DataFrame(columns=out_columns)

        out_path = out_dir / f"{county.replace(' ', '_')}_declining_agency_watchlist.csv"
        county_df.to_csv(out_path, index=False)
        print(f"[OK] {county}: wrote {out_path.name} (rows={len(county_df)})")

    print(f"[OK] Evaluated series: {total_series}; flagged rows: {total_flagged}.")


if __name__ == "__main__":
    declining_agency_watchlist()
