import pandas as pd
import matplotlib.pyplot as plt
import os

def plot_all_counties():
    # Load CSV
    file_path = "../data/total_monthly_distributions.csv"
    output_dir = "../data/Year-Over-Year Plots"
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

    df["Fiscal Year"] = df["Source"].str.extract(r'(FY \d{4})')
    df["Fiscal Month"] = df["Month"].dt.month

    # Get unique counties
    unique_counties = df["County"].dropna().unique()

    # we want to plot from Jul of one year to Jun of the next year
    month_pos = {7:0,8:1,9:2,10:3,11:4,12:5,1:6,2:7,3:8,4:9,5:10,6:11}
    month_labels = ['Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun']
    bar_width = 0.20
    x_base = list(range(12))
    fiscal_years = ['FY 2023', 'FY 2024', 'FY 2025']

    for county in unique_counties:
        county_df = df[df["County"] == county].copy()

        plt.figure(figsize=(12,6))
        fy_y_values = {}

        for i, fy in enumerate (fiscal_years):
            fy_data = county_df[county_df['Fiscal Year'] == fy]

            # initialize y values for all months to 0, so missing data values are taken care of
            y_values = [0] * 12
            for index, row in fy_data.iterrows():
                month_index = month_pos[row["Fiscal Month"]]
                y_values[month_index] = row["Weight"]

            # for each year, calculate list of all x positions where we want to plot a bar,
            # positions are offset by (i - 1) * bar_width to group bars for year side-by-side 
            # ex. positions for 2023 are shifted left by bar_width,
            # Jul 2023, Aug 2023, . . . would be 0 - bar_width, 1 - bar_width, . . . 
            x_positions = [x + (i - 1) * (bar_width + 0.05) for x in x_base]
            # here, each element of x positions is paired with each element of y values
            plt.bar(x_positions, y_values, width=bar_width, label=fy, alpha=0.91)
            fy_y_values[fy] = y_values

        # after plotting all bars, print ratios of 2024 values / 2023 values and
        # 2025 values / 2024 values
        for i in range(0, 2):
            # use default values to account for missing years
            prev_fy_values = fy_y_values.get(fiscal_years[i], [0] * 12)
            current_fy_values = fy_y_values.get(fiscal_years[i + 1], [0] * 12)

            for j in range(0, 12):
                prev_month_val = prev_fy_values[j]
                curr_month_val = current_fy_values[j]
                if (prev_month_val != 0):
                    ratio = curr_month_val / prev_month_val
                    ratio_display = f"{ratio:.1f}"
                    x_pos = j + (i) * bar_width
                    y_pos = curr_month_val + 200
                    plt.text(x_pos, y_pos, ratio_display, ha='center', va='bottom', fontsize=10, color='black', rotation=45, fontweight='semibold')

        plt.xticks(ticks = x_base, labels = month_labels)
        plt.xlabel("Month")
        plt.ylabel("Food distribution weight")
        plt.title(f"Year-Over-Year Food Distribution by Month - {county}")
        plt.legend(title = "Fiscal Year")
        plt.grid(True, axis = 'y')
        plt.tight_layout()

        # Save plot to file
        filename = county.replace(" ", "_").upper() + "_plot.png"
        filepath = os.path.join(output_dir, filename)
        plt.savefig(filepath)
        plt.close()

        print(f"Saved plot: {filepath}")

plot_all_counties()