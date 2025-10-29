import pandas as pd
import matplotlib.pyplot as plt
import os
import matplotlib.ticker as mtick

def plot_FH_totals():
    # Load CSV
    file_path = "../data/FH_total_monthly_distributions.csv"
    output_dir = "../data/FH_totals_by_county Plot"
    os.makedirs(output_dir, exist_ok=True)

    # delete old plot in output folder
    for file in os.listdir(output_dir):
        if file.endswith(".png"):
            os.remove(os.path.join(output_dir, file))

    try:
        df = pd.read_csv(file_path)
    except Exception as e:
        print(f"Error loading file: {e}")
        return

    df["First Half"] = df["Source"].str.extract(r'(FH \d{4})')

    # Pick up from here
    grouped_df = df.groupby(['County', 'First Half']).agg({
        "Weight": "sum",
    }).reset_index()

    pivot_df = grouped_df.pivot(index='County', columns='First Half', values='Weight').fillna(0)

    plot = pivot_df.plot(kind='bar', figsize=(12,6))

    plot.yaxis.set_major_formatter(mtick.StrMethodFormatter('{x:,.0f}'))

    plot.set_xlabel("County")
    plot.set_ylabel("Food distribution weight")
    plot.set_title(f"FH 2024 and FH 2025 food distribution totals by county")
    plot.legend(title = "First Half")
    plot.grid(True, axis = 'y')
    plt.tight_layout()

    # Save plot to file
    filename = "plot.png"
    filepath = os.path.join(output_dir, filename)
    plt.savefig(filepath)
    plt.close()

    print(f"Saved plot: {filepath}")

plot_FH_totals()