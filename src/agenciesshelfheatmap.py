# fy2023_2025_agency_shelflife_heatmaps.py
#
# Inputs:
#   ../data/Sorted Food/Sorted_FY2023 Split By County/*.csv
#   ../data/Sorted Food/Sorted_FY2024 Split By County/*.csv
#   ../data/Sorted Food/Sorted_FY2025 Split By County/*.csv
#
# Outputs (per county, into ../data/Agency Insights/FY2023_2025_Heatmaps_ShelfLife/):
#   <County>_FY2023_2025_agency_shelflife_heatmap.png
#
# Rows    = agencies (top N by FY2023–25 volume)
# Columns = shelf types (Dry, Frozen, Cooled, etc.)
# Cell    = share of that agency's FY2023–25 volume in that shelf type (0–1)
#
# Color scale: low share = cool (navy/blue), high share = warm (yellow/orange/red)

from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib as mpl

YEAR_DIRS = [
    Path("../data/Sorted Food/Sorted_FY2023 Split By County"),
    Path("../data/Sorted Food/Sorted_FY2024 Split By County"),
    Path("../data/Sorted Food/Sorted_FY2025 Split By County"),
]

OUT_DIR  = Path("../data/Agency Insights/FY2023_2025_Heatmaps_ShelfLife")

MIN_TOTAL_WEIGHT = 500.0   # ignore tiny agencies (3-year total)
MAX_AGENCIES     = 25      # max agencies per county to show


# ---------- helpers to detect columns on a raw CSV ----------
def _pick_cols(df: pd.DataFrame):
    cols = [c.strip() for c in df.columns]
    df.columns = cols

    # agency col
    agency_candidates = [
        c for c in cols
        if c.lower() in ("agency", "agency name", "agency_name", "partner", "partner name")
    ]
    agency_col = agency_candidates[0] if agency_candidates else cols[0]

    # food category col (we'll take shelf prefix from here)
    cat_candidates = [
        c for c in cols
        if c.lower() in ("food category", "food_category", "category", "item category")
    ]
    if not cat_candidates:
        raise ValueError("No 'Food Category' column found.")
    cat_col = cat_candidates[0]

    # weight col
    w_candidates = [
        c for c in cols
        if c.lower() in ("weight", "dist_volume", "pounds",
                         "qty_lbs", "quantity_lbs", "lb", "lbs")
    ]
    if not w_candidates:
        num_cols = df.select_dtypes(include="number").columns.tolist()
        if not num_cols:
            raise ValueError("No numeric column found for weights.")
        weight_col = num_cols[0]
    else:
        weight_col = w_candidates[0]

    return agency_col, cat_col, weight_col


def _extract_shelf_type(cat_series: pd.Series) -> pd.Series:
    """
    Takes 'Dry Beverages', 'Frozen Proteins', 'Cooled Fruits', etc.
    Returns just the shelf prefix: 'Dry', 'Frozen', 'Cooled', ...
    """
    vals = []
    for v in cat_series.fillna("Unknown"):
        text = str(v).strip()
        parts = text.split(" ", 1)
        vals.append(parts[0].strip().rstrip("."))
    return pd.Series(vals, index=cat_series.index, name="ShelfType")


# ---------- load all counties across years ----------
def _load_all_years() -> dict[str, pd.DataFrame]:
    """
    Returns dict: county_name -> DataFrame with columns [Agency, FoodCategory, Weight]
    aggregated across FY2023–FY2025.
    """
    county_parts: dict[str, list[pd.DataFrame]] = {}

    for year_dir in YEAR_DIRS:
        if not year_dir.exists():
            print(f"[WARN] Missing directory: {year_dir}")
            continue

        for f in year_dir.glob("*_Sorted_FY*.csv"):
            county = f.stem.split("_")[0].title()
            try:
                raw = pd.read_csv(f)
            except Exception as e:
                print(f"[WARN] Failed to read {f}: {e}")
                continue

            try:
                agency_col, cat_col, weight_col = _pick_cols(raw)
            except Exception as e:
                print(f"[WARN] {f}: {e}")
                continue

            df = raw[[agency_col, cat_col, weight_col]].copy()
            df.columns = ["Agency", "FoodCategory", "Weight"]

            county_parts.setdefault(county, []).append(df)

    county_to_df: dict[str, pd.DataFrame] = {}
    for county, parts in county_parts.items():
        county_to_df[county] = pd.concat(parts, ignore_index=True)

    return county_to_df


# ---------- core: one county ----------
def _plot_county_heatmap(county: str, df: pd.DataFrame):
    # build ShelfType from FoodCategory prefix
    df = df.copy()
    df["ShelfType"] = _extract_shelf_type(df["FoodCategory"])

    # total by agency & filter small ones
    total_by_agency = (
        df.groupby("Agency", as_index=True)["Weight"]
          .sum()
          .rename("total_weight")
    )
    total_by_agency = total_by_agency[total_by_agency >= MIN_TOTAL_WEIGHT]
    if total_by_agency.empty:
        print(f"[WARN] {county}: no agencies above {MIN_TOTAL_WEIGHT} lbs; skipping")
        return

    # restrict to top MAX_AGENCIES agencies by volume
    top_agencies = (
        total_by_agency.sort_values(ascending=False)
                       .head(MAX_AGENCIES)
                       .index.tolist()
    )
    df = df[df["Agency"].isin(top_agencies)]

    # aggregate by Agency × ShelfType
    agg = (
        df.groupby(["Agency", "ShelfType"], as_index=False)["Weight"]
          .sum()
          .rename(columns={"Weight": "lbs"})
    )

    # pivot to agency × shelf type
    pivot = agg.pivot(index="Agency", columns="ShelfType", values="lbs").fillna(0.0)

    # compute shares per agency
    totals = pivot.sum(axis=1)
    totals_safe = totals.replace(0, np.nan)
    shares = pivot.div(totals_safe, axis=0).fillna(0.0)
    shares = shares.clip(lower=0.0, upper=1.0)

    # order agencies by total volume
    shares = shares.loc[totals.sort_values(ascending=False).index]

    # order columns: custom order if possible, else alphabetical
    col_names = list(shares.columns)
    preferred = ["Dry", "Cooled", "Frozen", "Non-Food", "Unsorted", "Other"]
    ordered_cols: list[str] = []

    for p in preferred:
        matches = [c for c in col_names if c.startswith(p)]
        for m in matches:
            if m not in ordered_cols:
                ordered_cols.append(m)

    for c in sorted(col_names):
        if c not in ordered_cols:
            ordered_cols.append(c)

    shares = shares[ordered_cols]

    # ------------- plotting -------------
    colors = [
        "#0b1f4b",  # deep navy
        "#1f5fbf",  # medium blue
        "#c7c4ff",  # light lavender
        "#fff4b3",  # pale yellow
        "#ffb347",  # orange
        "#e53e3e",  # red
    ]
    cmap = mpl.colors.LinearSegmentedColormap.from_list("cool_to_warm", colors)

    fig, ax = plt.subplots(figsize=(8, max(4, 0.4 * len(shares))))

    im = ax.imshow(
        shares.values,
        aspect="auto",
        cmap=cmap,
        vmin=0.0,
        vmax=1.0,
    )

    # ticks & labels
    ax.set_xticks(np.arange(len(ordered_cols)))
    ax.set_xticklabels(ordered_cols, rotation=30, ha="right")
    ax.set_yticks(np.arange(len(shares.index)))
    ax.set_yticklabels(shares.index)

    ax.set_xlabel("Shelf Type (share of agency volume, FY2023–2025)")
    ax.set_ylabel("Agency")
    ax.set_title(f"FY2023–2025 Agency × Shelf Type Mix — {county} County")

    # colorbar
    cbar = fig.colorbar(im, ax=ax)
    cbar.set_label("Share of agency's FY2023–2025 pounds")

    plt.tight_layout()
    out_png = OUT_DIR / f"{county}_FY2023_2025_agency_shelflife_heatmap.png"
    fig.savefig(out_png, dpi=220, bbox_inches="tight")
    plt.close(fig)
    print(f"[OK] {county}: wrote {out_png.name}")


def main():
    print("[HEATMAP-SHELF] Building FY2023–2025 agency × shelf-type heatmaps")
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # clear previous outputs from this task
    for p in OUT_DIR.glob("*_FY2023_2025_agency_shelflife_heatmap.png"):
        p.unlink()

    county_to_df = _load_all_years()
    if not county_to_df:
        print("[WARN] No county data found across FY2023–2025.")
        return

    for county in sorted(county_to_df.keys()):
        try:
            _plot_county_heatmap(county, county_to_df[county])
        except Exception as e:
            print(f"[WARN] {county}: failed — {e}")


if __name__ == "__main__":
    main()
