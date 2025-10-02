import pandas as pd
import os

def fh2025_by_county():

    file_path = "../data/data csv/FH 2025 by County Totals.csv"
    output_dir = "../data/Sorted Food/Sorted_FH2025 Split By County"
    dict_path = "../data/data csv/FBNEGA Dictionary.csv"
    sorted_whole_output_dir = "../data/data csv/Sorted_FH2025.csv"

     # delete old files in output folder
    for file in os.listdir(output_dir):
        if file.endswith(".csv"):
            os.remove(os.path.join(output_dir, file))

    print(file_path)

    try:
        df = pd.read_csv(file_path)
        dict_data = pd.read_csv(dict_path)
    except Exception as e:
        print(f"Could not load the CSV file: {e}")
        return

    # sort data frame
    sorted_fh2025 = pd.merge(df, dict_data, how='left', on='Product Name')

    # prepend shelf life type to Food Category
    def prepend_shelf_life(product_ref, category):
        if pd.isna(product_ref) or pd.isna(category):
            return category
        if str(product_ref).startswith("C-"):
            return f"Cooled {category}"
        elif str(product_ref).startswith("F-"):
            return f"Frozen {category}"
        else:
            return f"Dry {category}"

    sorted_fh2025["Food Category"] = sorted_fh2025.apply(
        lambda row: prepend_shelf_life(row["Product Ref"], row["Food Category"]),
        axis=1
    )

    sorted_fh2025.to_csv(sorted_whole_output_dir, index=False)

    # ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)

    row_summary = {}
    # Split and write files
    for county in sorted_fh2025["County"].unique():
        county_df = sorted_fh2025[sorted_fh2025["County"] == county]
        safe_name = county.replace(" ", "_").replace("/", "-")
        output_path = os.path.join(output_dir, f"{safe_name}_Sorted_FH2025.csv")

        county_df.to_csv(output_path, index=False)

        count = len(county_df)
        row_summary[county] = count

        print(f"Written: {output_path}")

    # Final Summary
    print("\n*** County Row Summary ***")
    for county, count in row_summary.items():
        print(f"{county}: {count} rows")

    total_rows = sum(row_summary.values())
    print(f"\nTotal rows in all county files: {total_rows}")
    print(f"Original total rows: {len(df)}")

    if total_rows == len(df):
        print("All rows accounted for.")
    else:
        print("Row count mismatch. Check for filtering errors.")


fh2025_by_county()
