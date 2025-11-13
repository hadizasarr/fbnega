# fy2025_agency_category_heatmaps.py
#
# Inputs:
#   ../data/Sorted Food/Sorted_FY2025 Split By County/*.csv
#
# Outputs (per county, into ../data/Agency Insights/FY2025_Heatmaps/):
#   <County>_FY2025_agency_category_heatmap.png
#
# Rows    = agencies (top N by FY2025 volume)
# Columns = food types (top K, rest grouped as "Other")
# Cell    = share of that agency's FY2025 volume in that food type (0–1)
#
# Color scale: low share = cool (navy/blue), high share = warm (yellow/orange/red)

from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib as mpl

IN_DIR   = Path("../data/Sorted Food/Sorted_FY2025 Split By County")
OUT_DIR  = Path("../data/Agency Insights/FY2025_Heatmaps")

MIN_TOTAL_WEIGHT = 500.0   # ignore tiny agencies
MAX_AGENCIES     = 25      # max agencies per county to show
TOP_K_CATS       = 9       # number of named food types; 10th will be "Other"


# ---------- helpers to detect columns ----------
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


# ---------- core: one county ----------
def _plot_county_heatmap(county: str, df: pd.DataFrame,
                         agency_col: str, cat_col: str, weight_col: str):
    # build FoodType
    df = df.copy()
    df["FoodType"] = _extract_food_type(df[cat_col])

    # total by agency & filter small ones
    total_by_agency = (
        df.groupby(agency_col, as_index=True)[weight_col]
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
    df = df[df[agency_col].isin(top_agencies)]

    # aggregate by Agency × FoodType
    agg = (
        df.groupby([agency_col, "FoodType"], as_index=False)[weight_col]
          .sum()
          .rename(columns={weight_col: "lbs"})
    )

    # pick top K food types overall, rest = "Other"
    food_totals = agg.groupby("FoodType")["lbs"].sum().sort_values(ascending=False)
    top_foods = food_totals.head(TOP_K_CATS).index.tolist()
    agg["FoodTypeCollapsed"] = np.where(
        agg["FoodType"].isin(top_foods), agg["FoodType"], "Other"
    )

    # recompute with collapsed categories
    agg2 = (
        agg.groupby([agency_col, "FoodTypeCollapsed"], as_index=False)["lbs"]
           .sum()
    )

    # pivot to agency × category
    pivot = agg2.pivot(index=agency_col, columns="FoodTypeCollapsed", values="lbs").fillna(0.0)

    # compute shares per agency
    totals = pivot.sum(axis=1)
    # avoid division by zero, though totals should all be >= MIN_TOTAL_WEIGHT
    totals_safe = totals.replace(0, np.nan)
    shares = pivot.div(totals_safe, axis=0).fillna(0.0)

    # clamp numerically so we are cleanly in [0, 1]
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

    ax.set_xlabel("Food Type (share of agency volume)")
    ax.set_ylabel("Agency")
    ax.set_title(f"FY2025 Agency × Food Type Mix — {county} County")

    # colorbar
    cbar = fig.colorbar(im, ax=ax)
    cbar.set_label("Share of agency's FY2025 pounds")

    plt.tight_layout()
    out_png = OUT_DIR / f"{county}_FY2025_agency_category_heatmap.png"
    fig.savefig(out_png, dpi=220, bbox_inches="tight")
    plt.close(fig)
    print(f"[OK] {county}: wrote {out_png.name}")


def main():
    print("[HEATMAP] Building FY2025 agency × food-type heatmaps")
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # clear previous outputs from this task
    for p in OUT_DIR.glob("*_FY2025_agency_category_heatmap.png"):
        p.unlink()

    files = sorted(IN_DIR.glob("*_Sorted_FY2025.csv"))
    if not files:
        print(f"[WARN] No FY2025 sorted food files found in {IN_DIR}")
        return

    for f in files:
        county = f.stem.split("_")[0].title()
        try:
            df = pd.read_csv(f)
            agency_col, cat_col, weight_col = _pick_cols(df)
            _plot_county_heatmap(county, df, agency_col, cat_col, weight_col)
        except Exception as e:
            print(f"[WARN] {county}: failed — {e}")


if __name__ == "__main__":
    main()
