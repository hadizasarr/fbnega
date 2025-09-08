import pandas as pd
import os

def fh2024_by_county():
    """
    Reads 'FH 2024 by County Totals.csv' and writes separate per-county CSV files.
    Prints a row count summary to confirm integrity.
    """
    file_path = "../data/data csv/FH 2024 by County Totals.csv"
    output_dir = "../data/FH2024 Split by County"

    print(file_path)

    try:
        df = pd.read_csv(file_path)
    except Exception as e:
        print(f"Could not load the CSV file: {e}")
        return

    # Basic preview
    print("File loaded successfully!")
    print("Columns:", list(df.columns))
    print("Number of rows:", len(df))
    print("Counties found:", df["County"].unique())

    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)

    # Dictionary to store row counts per county
    row_summary = {}

    # Split and write files
    for county in df["County"].unique():
        county_df = df[df["County"] == county]
        safe_name = county.replace(" ", "_").replace("/", "-")
        output_path = os.path.join(output_dir, f"{safe_name}_FH2024.csv")
        
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

fh2024_by_county()
