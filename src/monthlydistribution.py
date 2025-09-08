import pandas as pd
import os

def monthly_distribution_counts():
    """
    Reads all county csv files in  and writes aggregate info (county, month, 
    total_weight, total_quantity, total_value) in a separate summary file. 
    """
    input_dirs = [
        "../data/FY 2023 Split by County", 
        "../data/FY 2024 Split by County", 
        "../data/FY 2025 Split by County", 
    ]

    output_file = "../data/total_monthly_distributions.csv"

    # clear old output file if it exists
    if os.path.exists(output_file):
        os.remove(output_file)

    summary_rows = []

    for input_dir in input_dirs:
        if not os.path.exists(input_dir):
            print(f"Missing directory: {input_dir}")
            continue

        for filename in os.listdir(input_dir):
            if not filename.endswith(".csv"):
                continue

            file_path = os.path.join(input_dir, filename)
            county_name = filename.split("_")[0]  # Get county from filename
            year_tag = input_dir.split("/")[-1]  # e.g., FH 2024 Split by County

            try:
                df = pd.read_csv(file_path)
            except Exception as e:
                print(f"Failed to load {filename}: {e}")
                continue

            df.columns = df.columns.str.strip()

            # Parse date column
            if "Pickup Delivery Date" not in df.columns:
                print("No 'Pickup Delivery Date' in {filename}, skipping.")
                continue

            df["Pickup Delivery Date"] = pd.to_datetime(
                df["Pickup Delivery Date"], 
                format="%m/%d/%Y %I:%M:%S %p", 
                errors='coerce'
                )

            df["Month"] = df["Pickup Delivery Date"].dt.to_period("M").astype(str)

            # Group by month
            grouped = df.groupby("Month").agg({
                "Weight": "sum",
                "Quantity": "sum", 
                "Total Value": "sum"
            }).reset_index()

            grouped["County"] = county_name
            grouped["Source"] = year_tag  # Optional: show FH/FY source

            # Reorder columns
            grouped = grouped[["County", "Month", "Weight", "Quantity", "Source"]]

            summary_rows.append(grouped)

    if summary_rows:
        result_df = pd.concat(summary_rows, ignore_index=True)
        # sorts by county and month
        result_df = result_df.sort_values(by=["County", "Month"])
        result_df.to_csv(output_file, index=False)
        print(f"Monthly totals written to: {output_file}")
    else:
        print("No data processed.")

monthly_distribution_counts()