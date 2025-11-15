# fy2023_2025_agency_foodtype_heatmaps.py
#
# Inputs:
#   ../data/Sorted Food/Sorted_FY2023 Split By County/*.csv
#   ../data/Sorted Food/Sorted_FY2024 Split By County/*.csv
#   ../data/Sorted Food/Sorted_FY2025 Split By County/*.csv
#
# Outputs (per county, into ../data/Agency Insights/FY2023_2025_Heatmaps/):
#   <County>_FY2023_2025_agency_category_heatmap.png
#
# Rows    = agencies (top N by FY2023–25 volume)
# Columns = food types (top K, rest grouped as "Other")
# Cell    = share of that agency's FY2023–25 volume in that food type (0–1)
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

OUT_DIR  = Path("../data/Agency Insights/FY2023_2025_Heatmaps")

MIN_TOTAL_WEIGHT = 500.0   # ignore tiny agencies (3-year total)
MAX_AGENCIES     = 25      # max agencies per county to show
TOP_K_CATS       = 9       # number of named food types; 10th will be "Other"


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

    # food category col
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


def _extract_food_type(cat_series: pd.Series) -> pd.Series:
    """
    Takes 'Dry Beverages', 'Frozen Proteins', 'Cooled Fruits', etc.
    Returns just 'Beverages', 'Proteins', 'Fruits', ...
    """
    vals = []
    for v in cat_series.fillna("Unknown"):
        text = str(v)
        parts = text.split(" ", 1)
        if len(parts) > 1:
            vals.append(parts[1].strip().rstrip("."))
        else:
            vals.append(parts[0].strip().rstrip("."))
    return pd.Series(vals, index=cat_series.index, name="FoodType")


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
    # build FoodType
    df = df.copy()
    df["FoodType"] = _extract_food_type(df["FoodCategory"])

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

    # aggregate by Agency × FoodType
    agg = (
        df.groupby(["Agency", "FoodType"], as_index=False)["Weight"]
          .sum()
          .rename(columns={"Weight": "lbs"})
    )

    # pick top K food types overall, rest = "Other"
    food_totals = agg.groupby("FoodType")["lbs"].sum().sort_values(ascending=False)
    top_foods = food_totals.head(TOP_K_CATS).index.tolist()
    agg["FoodTypeCollapsed"] = np.where(
        agg["FoodType"].isin(top_foods), agg["FoodType"], "Other"
    )

    # recompute with collapsed categories
    agg2 = (
        agg.groupby(["Agency", "FoodTypeCollapsed"], as_index=False)["lbs"]
           .sum()
    )

    # pivot to agency × category
    pivot = agg2.pivot(index="Agency", columns="FoodTypeCollapsed", values="lbs").fillna(0.0)

    # compute shares per agency
    totals = pivot.sum(axis=1)
    totals_safe = totals.replace(0, np.nan)
    shares = pivot.div(totals_safe, axis=0).fillna(0.0)
    shares = shares.clip(lower=0.0, upper=1.0)

    # order agencies by total volume
    shares = shares.loc[totals.sort_values(ascending=False).index]

    # order columns: top_foods + "Other" at end (if present)
    cols = [c for c in top_foods if c in shares.columns]
    if "Other" in shares.columns:
        cols.append("Other")
    shares = shares[cols]

    # ------------- plotting -------------
    # custom cool→warm colormap: navy → blue → lavender → yellow → orange → red
    colors = [
        "#0b1f4b",  # deep navy
        "#1f5fbf",  # medium blue
        "#c7c4ff",  # light lavender
        "#fff4b3",  # pale yellow
        "#ffb347",  # orange
        "#e53e3e",  # red
    ]
    cmap = mpl.colors.LinearSegmentedColormap.from_list("cool_to_warm", colors)

    fig, ax = plt.subplots(figsize=(12, max(5, 0.4 * len(shares))))

    im = ax.imshow(
        shares.values,
        aspect="auto",
        cmap=cmap,
        vmin=0.0,
        vmax=1.0,  # shares are in [0,1]
    )

    # ticks & labels
    ax.set_xticks(np.arange(len(cols)))
    ax.set_xticklabels(cols, rotation=30, ha="right")
    ax.set_yticks(np.arange(len(shares.index)))
    ax.set_yticklabels(shares.index)

    ax.set_xlabel("Food Type (share of agency volume, FY2023–2025)")
    ax.set_ylabel("Agency")
    ax.set_title(f"FY2023–2025 Agency × Food Type Mix — {county} County")

    # colorbar
    cbar = fig.colorbar(im, ax=ax)
    cbar.set_label("Share of agency's FY2023–2025 pounds")

    plt.tight_layout()
    out_png = OUT_DIR / f"{county}_FY2023_2025_agency_category_heatmap.png"
    fig.savefig(out_png, dpi=220, bbox_inches="tight")
    plt.close(fig)
    print(f"[OK] {county}: wrote {out_png.name}")


def main():
    print("[HEATMAP] Building FY2023–2025 agency × food-type heatmaps")
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # clear previous outputs from this task
    for p in OUT_DIR.glob("*_FY2023_2025_agency_category_heatmap.png"):
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
