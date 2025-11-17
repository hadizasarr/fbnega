import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib
import os


def plot_categories():
    # Load CSV
    file_path = "../data/category plots/category_totals_by_county.csv"
    output_dir = "../data/Food Category plots/Top2 Categories per month by county"
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
    df["Month"] = pd.to_datetime(df["Month"], format="%Y-%m").dt.to_period("M")

    # Get unique counties
    unique_counties = df["County"].dropna().unique()

    # list of 12 unique colors for unique agencies
    colors = matplotlib.colormaps["tab20"].colors

    for county in unique_counties:
        county_df = df[df["County"] == county].copy()
        # Get all unique agencies in either top agency 1 list or top agency 2 list
        # We know the max. number of unique agencies here is 12
        unique_categories = pd.concat([county_df["TopCategory1Name"], county_df["TopCategory2Name"]]).dropna().unique()

        # since zip() stops at the shorter list of the 2 arguments, every
        # agency is assigned to a unique color at the same index as the agency, until the end of unique agencies
        colors_dict = {agency: color for agency, color in zip(unique_categories, colors)}

        # Sort by Month
        county_df = county_df.sort_values("Month")

        # Plot all 3 bars stacked on top of each other, starting from bottom
        # first, top agency 1 weight, then, top agency 2 weight, then total weight - top 1 weight - top 2 weight,
        # in this case, the total height of the bar equals the total weight of food distributed for the county in a month
        plt.figure(figsize=(10, 6))
        plt.bar(county_df["Month"].astype(str), county_df["TopCategory1Weight"], width=0.7, label="Weight",
                color=county_df["TopCategory1Name"].map(colors_dict))

        plt.bar(county_df["Month"].astype(str), county_df["TopCategory2Weight"], width=0.7,
                bottom=county_df["TopCategory1Weight"], label="Weight",
                color=county_df["TopCategory2Name"].map(colors_dict))

        remainder = county_df["Weight"] - county_df["TopCategory1Weight"] - county_df["TopCategory2Weight"]

        plt.bar(county_df["Month"].astype(str), remainder, width=0.7,
                bottom=county_df["TopCategory1Weight"] + county_df["TopCategory2Weight"], label="Weight", color='lightgray')

        # print(county_df)
        # print(unique_agencies)

        legend_handles = [
            mpatches.Patch(color=color, label=agency)
            for agency, color in colors_dict.items()
        ]
        if county == "STEPHENS":
            plt.title(f"{county.title().upper()} - Monthly Weight Distribution with Top 2 Categories every month")
            plt.xlabel("Month")
            plt.ylabel("Total Weight")
            plt.xticks(rotation=45, fontsize=9, ha='right')
            plt.grid(True)
            plt.grid(axis="x", visible=False)
            plt.tight_layout()
            plt.legend(handles=legend_handles, loc='upper left', title="Categories", fontsize="small")
        else:
            plt.title(f"{county.title().upper()} - Monthly Weight Distribution with Top 2 Categories every month")
            plt.xlabel("Month")
            plt.ylabel("Total Weight")
            plt.xticks(rotation=45, fontsize=9, ha='right')
            plt.grid(True)
            plt.grid(axis="x", visible=False)
            plt.tight_layout()
            plt.legend(handles=legend_handles, title="Categories", fontsize="small")

        # Save plot to file
        filename = county.replace(" ", "_").upper() + "_plot.png"
        filepath = os.path.join(output_dir, filename)
        plt.savefig(filepath)
        plt.close()

        print(f"Saved plot: {filepath}")


plot_categories()