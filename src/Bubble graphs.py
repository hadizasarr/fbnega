from itertools import groupby
import pandas as pd
import matplotlib.pyplot as plt
import plotly.express as px
import os

""" Purpose: create bubble graphs that take into account the storage method of food items."""
def bubble_graphs():
    input_dirs = ["../data/data csv/Sorted_FY2023.csv",
                  "../data/data csv/Sorted_FY2024.csv",
                  "../data/data csv/Sorted_FY2025.csv"]
    output_file = "../data/category plots/BubbleGraphs.csv"

    if os.path.exists(output_file):
        os.remove(output_file)

    summary_rows = []

    excluded_counties = ['FBSHARE', 'OTHER']

    for input_dir in input_dirs:
        df = pd.read_csv(input_dir, low_memory=False)
        # exclude counties
        df = df[~df['County'].isin(excluded_counties)]
        # split food category column
        df[['Storage Method','Food Type']] = df['Food Category'].str.split(n=1, expand=True)
        df[['Fiscal Year']] = input_dir.split('_')[-1].split('.')[0]
        df['Pickup Delivery Date'] = pd.to_datetime(df['Pickup Delivery Date'])
        df['Month'] = df['Pickup Delivery Date'].dt.strftime('%Y-%m')
        bubbledata = pd.DataFrame(df[['County','Month','Agency Name','Weight','Food Category','Storage Method','Food Type', 'Fiscal Year']].reset_index(drop=True))
        bubbledata = bubbledata.sort_values(by=['Month','County'])
        bubbledata = bubbledata.groupby(['Month','County', 'Agency Name', 'Food Type', 'Storage Method','Fiscal Year', 'Food Category']).agg({"Weight": 'sum'}).reset_index()
        summary_rows.append(bubbledata)

    if summary_rows:
        result_df = pd.concat(summary_rows, ignore_index=True)
        result_df = result_df.sort_values(["Month", "County"], ascending=[True, True]).reset_index(drop=True)
        result_df.to_csv(output_file, index=False)
        print(f"Data saved to: {output_file}")
    else:
        print("No data processed.")


bubble_graphs()