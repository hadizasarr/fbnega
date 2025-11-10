from logging import exception

import pandas as pd
import matplotlib.pyplot as plt
import os


def totals_by_category():
    input_dir = [ "../data/Sorted Food/Sorted_FY2023 Split by County",
                   "../data/Sorted Food/Sorted_FY2024 Split by County",
                  "../data/Sorted Food/Sorted_FY2025 Split by County"]

    output_file = "../data/category plots/category_monthly_totals.csv"

    # check if file exists and clear old plots if so
    if os.path.exists(output_file):
        os.remove(output_file)

    summary_rows = []

    for input_dir in input_dir:
        if not os.path.exists(input_dir):
            print(f"Missing directory: {input_dir}")
            continue

        for filename in os.listdir(input_dir):
            if not filename.endswith(".csv"):
                continue

            file_path = os.path.join(input_dir, filename)
            county_name = filename.split("_")[0]  # Get county from filename

            if (county_name == "FBSHARE" or county_name == "OTHER"):
                continue

            try:
                df = pd.read_csv(file_path)
            except Exception as e:
                print(f"Failed to load {filename}: {e}")
                continue

            df.columns = df.columns.str.strip()

            # modify date format for grouping
            df["Pickup Delivery Date"] = pd.to_datetime(
                df["Pickup Delivery Date"],
                format="%m/%d/%Y %I:%M:%S %p",
                errors='coerce'
            )

            df["Month"] = df["Pickup Delivery Date"].dt.to_period("M").astype(str)

            # group current data by month and food category and compute sum of weight
            groupby_category = df.groupby(["Month","County", "Food Category"]).agg({
               "Weight": "sum",}).reset_index()

            category_df = groupby_category.sort_values(["Food Category", "Month", "County"]
                                                       , ascending=[True, True, True]).reset_index(drop=True)
            summary_rows.append(category_df)
        if summary_rows:
            result_df = pd.concat(summary_rows, ignore_index=True)
            # result_df = result_df.sort_values(["Food Category", "Month", "County"], ascending=[True, True, True]).reset_index(drop=True)
            result_df.to_csv(output_file, index=False)
            print(f"Monthly totals written to: {output_file}")
        else:
            print("No data processed.")


totals_by_category()