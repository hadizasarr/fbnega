# fy2025_county_category_donuts.py
# Inputs:  ../data/Sorted Food/Sorted_FY2025 Split By County/*.csv
# Outputs: ../data/Agency Insights/FY2025_Donuts/<County>_FY2025_donut.png
#          ../data/Agency Insights/FY2025_Donuts/<County>_FY2025_category_shares.csv

from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib as mpl

IN_DIR  = Path("../data/Sorted Food/Sorted_FY2025 Split By County")
OUT_DIR = Path("../data/FY2025 Category Donuts")
TOP_K   = 10


def _pick_cols(df: pd.DataFrame):
    cols = [c.strip() for c in df.columns]
    df.columns = cols

    # category column
    cat_candidates = [
        c for c in cols
        if c.lower() in ("food category", "food_category", "category", "item category")
    ]
    cat_col = cat_candidates[0] if cat_candidates else cols[0]

    # weight column
    w_candidates = [
        c for c in cols
        if c.lower() in ("weight", "dist_volume", "pounds", "qty_lbs", "quantity_lbs", "lb", "lbs")
    ]
    if not w_candidates:
        num_cols = df.select_dtypes(include="number").columns.tolist()
        if not num_cols:
            raise ValueError("No numeric column found for weights.")
        weight_col = num_cols[0]
    else:
        weight_col = w_candidates[0]

    return cat_col, weight_col


def _aggregate_topk(df: pd.DataFrame, cat_col: str, weight_col: str, top_k: int):
    g = (
        df.groupby(cat_col, dropna=False)[weight_col]
          .sum()
          .sort_values(ascending=False)
          .rename("total_weight")
          .reset_index()
    )
    g["total_weight"] = g["total_weight"].astype(float)

    if len(g) <= top_k:
        g2 = g.copy()
    else:
        head = g.iloc[:top_k].copy()
        other = pd.DataFrame(
            {cat_col: ["Other"], "total_weight": [g.iloc[top_k:]["total_weight"].sum()]}
        )
        g2 = pd.concat([head, other], ignore_index=True)

    total = g2["total_weight"].sum()
    g2["share"] = (g2["total_weight"] / total) if total > 0 else 0.0
    return g2.sort_values("share", ascending=False).reset_index(drop=True)


def _make_donut(agg: pd.DataFrame, cat_col: str, county: str, out_png: Path):
    names  = agg[cat_col].astype(str).tolist()
    values = agg["total_weight"].astype(float).tolist()
    total  = float(sum(values)) if values else 0.0

    # Label text ON the slices: "Category XX.X%"
    labels = [
        f"{name} {((val / total) * 100 if total else 0):.1f}%"
        for name, val in zip(names, values)
    ]

    # High-contrast colors using new colormap API
    cmap    = mpl.colormaps.get_cmap("tab20")
    palette = list(cmap.colors)
    base_idx = list(range(len(values)))
    idx = base_idx[::2] + base_idx[1::2]  # interleave for contrast
    colors = [palette[i % len(palette)] for i in idx]

    fig, ax = plt.subplots(figsize=(8, 8))

    wedges, _ = ax.pie(
        values,
        labels=labels,            # category + percent right next to each slice
        startangle=90,
        colors=colors,
        labeldistance=1.08,       # push labels slightly outside the ring
        wedgeprops=dict(linewidth=1.5, edgecolor="white"),  # thicker white borders
    )

    # Donut hole
    centre = plt.Circle((0, 0), 0.55, fc="white")
    ax.add_artist(centre)

    # NO LEGEND — labels carry both name and %
    ax.set_title(f"FY2025 Distribution by Food Category — {county} County")
    plt.tight_layout()
    fig.savefig(out_png, dpi=220, bbox_inches="tight")
    plt.close(fig)


def main():
    print("[DONUT] running updated script (labels only, no legend)")
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # Clear previous outputs from this task
    for p in OUT_DIR.glob("*_FY2025_donut.png"):
        p.unlink()
    for p in OUT_DIR.glob("*_FY2025_category_shares.csv"):
        p.unlink()

    files = sorted(IN_DIR.glob("*_Sorted_FY2025.csv"))
    if not files:
        print(f"[WARN] No files found in {IN_DIR}")
        return

    for f in files:
        county = f.stem.split("_")[0].title()
        try:
            df = pd.read_csv(f)
            cat_col, weight_col = _pick_cols(df)
            agg = _aggregate_topk(df, cat_col, weight_col, TOP_K)

            # Save shares table
            shares_path = OUT_DIR / f"{county}_FY2025_category_shares.csv"
            out_tbl = agg[[cat_col, "total_weight", "share"]].copy()
            out_tbl["share"] = out_tbl["share"].round(4)
            out_tbl.to_csv(shares_path, index=False)

            # Donut chart
            png_path = OUT_DIR / f"{county}_FY2025_donut.png"
            _make_donut(agg, cat_col, county, png_path)
            print(f"[OK] {county}: wrote {png_path.name} and {shares_path.name}")
        except Exception as e:
            print(f"[WARN] {county}: failed — {e}")


if __name__ == "__main__":
    main()
