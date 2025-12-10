import numpy as np
import pandas as pd
import os
import matplotlib.pyplot as plt


input_dirs = ["../data/data csv/Sorted_FH2024.csv",
              "../data/data csv/Sorted_FH2025.csv",
                "../data/data csv/Sorted_FY2023.csv",
              "../data/data csv/Sorted_FY2024.csv",
              "../data/data csv/Sorted_FY2025.csv",]
output_file = "../data/data csv/Summary.csv"
if os.path.exists(output_file):
    os.remove(output_file)

summary_rows = []

excluded_counties = ['FBSHARE', 'OTHER']

def summary_stats():
    for input_dir in input_dirs:
        if not os.path.exists(input_dir):
            print(f"Missing directory: {input_dir}")
            continue
        try:
            df = pd.read_csv(input_dir, low_memory=False)
        except Exception as e:
            print(f"Failed to load {input_dir}: {e}")
            continue

        df = df[~df['County'].isin(excluded_counties)]
        fiscal_year = input_dir.split('_')[-1].split('.')[0]
        df['Pickup Delivery Date'] = pd.to_datetime(df['Pickup Delivery Date'], format="%m/%d/%Y %I:%M:%S %p",
                errors='coerce')
        df['Month'] = df['Pickup Delivery Date'].dt.strftime('%Y-%m')
        num_months = len(df['Month'].unique())

        # averages considering all counties
        print(f'-----------------------{fiscal_year}-----------------------')
        total_lbs = df['Weight'].sum()
        print(f'Total Weight: {total_lbs}')

        n_agencies_fy = len(df['Agency Name'].unique())
        print(f'{n_agencies_fy} Unique Agencies')

        avg_lbs_permonth = total_lbs / num_months
        print(f'Average Weight Per Month: {avg_lbs_permonth}')

        avg_agencies_per_month = len(df['Agency Name'].unique()) / num_months
        print(f'Average # of Unique Agencies Per Month: {avg_agencies_per_month}')

        # exclude counties
        for county in sorted(df.County.unique()):
            county_df = df[df['County'] == county].reset_index(drop=True)
            num_months_county = len(county_df['Month'].unique())

            print(f'********* County:{county.upper()} ***********')
            county_avglbs_permonth = county_df['Weight'].sum() / num_months_county
            print(f'Average weight per month {county_avglbs_permonth}, # of Months {num_months_county}')

            print( len(county_df['Agency Name'].unique()))
            avg_agencies_per_month = len(county_df['Agency Name'].unique()) / num_months_county
            print(f'Average # of Unique Agencies Per Month: {avg_agencies_per_month}')


summary_stats()

