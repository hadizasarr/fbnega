import pandas as pd
import os

def monthly_cats():
    input_dirs = [
        "../data/Sorted Food/Sorted_FY2023 Split by County",
        "../data/Sorted Food/Sorted_FY2024 Split by County",
        "../data/Sorted Food/Sorted_FY2025 Split by County",
    ]

    output_file = "../data/category plots/category_totals_by_county.csv"

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
            year_tag = input_dir.split("/")[-1]  # e.g., Sorted_FH 2024 Split by County

            if (county_name == "FBSHARE" or county_name == "OTHER"):
                continue

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

            # if (county_name == "BANKS" and year_tag == "FY 2024 Split by County"):
                # print("\n========df========\n", df)

            # Group by food category and month and sum weight
            # to find the top 2 partner agencies for each month and their weights
            group_by_category = df.groupby(["Month", "Food Category"]).agg({
                "Weight": "sum",
            }).reset_index()

            group_by_category = group_by_category.sort_values(["Month", "Weight"], ascending=[True, False])

            top_2_rows_month = group_by_category.groupby("Month").head(2).reset_index(drop=True)

            # if (county_name == "BANKS" and year_tag == "FY 2024 Split by County"):
                # print("\n========top_2_rows_month========\n", top_2_rows_month)

            # Extract top 1 agency and top 2 agency information in 2 data frames
            top1 = (top_2_rows_month.groupby("Month").first()
                .reset_index()
                .rename(columns={
                    "Food Category": "TopCategory1Name",
                    "Weight": "TopCategory1Weight"
                })
            )

            # if (county_name == "BANKS" and year_tag == "FY 2024 Split by County"):
                # print("\n========top1========\n", top1)

            top2 = (top_2_rows_month.groupby("Month").nth(1)
                .reset_index()
                .rename(columns={
                    "Food Category": "TopCategory2Name",
                    "Weight": "TopCategory2Weight"
                })
            )

            # if (county_name == "BANKS" and year_tag == "FY 2024 Split by County"):
                # print("\n========top2========\n", top2)


            # Group by month
            grouped = df.groupby("Month").agg({
                "Weight": "sum",
                "Food Category": "nunique"
            }).reset_index()

            grouped = grouped.rename(columns={"Food Category": "Num. of Unique Categories"})

            # merge columns from top1 and top2 to grouped where the month is the same in both data frames
            grouped = grouped.merge(top1, on="Month", how="left").merge(top2, on="Month", how="left")

            grouped["County"] = county_name
            grouped["Source"] = year_tag  # Optional: show FH/FY source

            # Reorder columns
            grouped = grouped[["County", "Month", "Weight", "TopCategory1Name", "TopCategory1Weight",
                              "TopCategory2Name", "TopCategory2Weight", "Num. of Unique Categories", "Source"]]

            summary_rows.append(grouped)
    if summary_rows:
        result_df = pd.concat(summary_rows, ignore_index=True)
        # sorts by county and month
        result_df = result_df.sort_values(by=["County", "Month"])
        result_df.to_csv(output_file, index=False)
        print(f"Monthly totals written to: {output_file}")
    else:
        print("No data processed.")


monthly_cats()