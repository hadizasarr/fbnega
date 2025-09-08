import pandas as pd
import matplotlib.pyplot as plt
import os

def plot_all_counties():
    # Load CSV
    file_path = "../data/total_monthly_distributions.csv"
    output_dir = "../data/Monthly Plots"
    os.makedirs(output_dir, exist_ok=True)

    # delete old plots in output folder
    for file in os.listdir(output_dir):
        if file.endswith(".png"):
            os.remove(os.path.join(output_dir, file))

    try:
        df = pd.read_csv(file_path)
    except Exception as e:
        print(f"Error loading file: {e}")
        return

    df.columns = df.columns.str.strip()
    df["Month"] = pd.to_datetime(df["Month"], format="%Y-%m")

    # Get unique counties
    unique_counties = df["County"].dropna().unique()

    for county in unique_counties:
        county_df = df[df["County"] == county].copy()

        # Sort by Month
        county_df = county_df.sort_values("Month")

        # Plot
        plt.figure(figsize=(10, 6))
        plt.plot(county_df["Month"], county_df["Weight"], marker="o", label="Weight")

        plt.title(f"{county.title()} - Monthly Weight Distribution")
        plt.xlabel("Month")
        plt.ylabel("Total Weight")
        plt.xticks(rotation=45)
        plt.grid(True)
        plt.tight_layout()
        plt.legend()

        # Save plot to file
        filename = county.replace(" ", "_").upper() + "_plot.png"
        filepath = os.path.join(output_dir, filename)
        plt.savefig(filepath)
        plt.close()

        print(f"Saved plot: {filepath}")

plot_all_counties()
