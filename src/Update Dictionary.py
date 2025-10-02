import pandas as pd
import os

def update_dictionary():

    file_path = "../data/data csv/FY 2025 by County Totals.csv" # change path each time you sort a new file
    dict_path = "../data/data csv/FBNEGA Dictionary.csv"
    output_dir = "../data/data csv"

    print(file_path)

    try:
        df = pd.read_csv(file_path)
        dict_df = pd.read_csv(dict_path)
    except Exception as e:
        print(f"Could not load the CSV file: {e}")
        return

    # Get unique product names from both sources
    existing_dict_items = set(dict_df['Product Name'])
    new_data_items = set(df['Product Name'])

    # Find items in the data that are NOT in the dictionary
    missing_items = new_data_items - existing_dict_items

    print(f"Dictionary currently has: {len(existing_dict_items)} unique products")
    print(f"New data has: {len(new_data_items)} unique products")
    print(f"New products to add: {len(missing_items)}")

    if len(missing_items) > 0:
        # Create DataFrame for new items
        new_items_df = pd.DataFrame({'Product Name': list(missing_items)})

        # Append new items to the dictionary
        updated_dict = pd.concat([dict_df, new_items_df], ignore_index=True)

        # Remove any duplicates that might have been created
        updated_dict = updated_dict.drop_duplicates(subset=['Product Name'])

        print(f"Updated dictionary now has: {len(updated_dict)} unique products")
        print(updated_dict.shape)

        # Optional: Save the updated dictionary
        updated_dict.to_csv(f"{output_dir}/FBNEGA Dictionary.csv", index=False)

        return updated_dict
    else:
        print("No new products to add.")
        return dict_df



# Call the function
updated_dictionary = update_dictionary()
