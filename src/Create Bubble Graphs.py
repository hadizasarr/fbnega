import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
import plotly.express as px
import os


'''Create a bubble graph for each county where each bubble represents an agency
and it's size is proportional to the amount of weight it distributed'''
def agencybubbles():
    file_path = "../data/category plots/BubbleGraphs.csv"
    output_dir = "../data/Food Category plots/BubbleGraphs Per County"
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

    df_abs = df.copy()
    df_abs['Weight_Abs'] = df_abs['Weight'].abs()

    for county in df.County.unique():
        # create a figure for county
        county_data = df_abs[df_abs['County'] == county]
        fig = px.scatter(
            county_data,
            x="Month",
            y="Food Type",
            size="Weight_Abs",
            hover_name="Agency Name",
            color='Storage Method',
            hover_data={
                "Weight": ":.0f",
                "Weight_Abs": ":.0f",
                "Month": True,
                "Food Category": True,
                "Fiscal Year": True
            },
            title=f"Food Distribution by Type - {county}",
            size_max=50,
            opacity=0.7
        )

        # Customize layout
        fig.update_layout(
            xaxis_tickangle=-45,
            height=600,
            showlegend=True
        )

        fig.write_html(f"{output_dir}/{county.upper()}bubble.html")


agencybubbles()