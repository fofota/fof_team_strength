import streamlit as st
st.set_page_config(
    page_title="Metric Importance",
    layout='wide'
)
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
from Team_Stats_Benchmarking import raw_data
import os

# calculate metric importance based on correlation to pythag_wins
def calculate_metric_importance(abs_corr):
    """Assign Metric Importance based on abs_corr value."""
    if abs_corr < 0.15:
        return 1
    elif abs_corr < 0.3:
        return 2
    elif abs_corr < 0.45:
        return 3
    elif abs_corr < 0.6:
        return 4
    else:
        return 5
    
st.title("Metric Importance")
st.write("Metric importance is determined based on the correlation of each metric to Pythagorean Wins in the period 2046-63.")

# Filter numeric columns
numeric_data = raw_data.select_dtypes(include=[float, int])
corr_matrix = numeric_data.corr()

# Create a dataframe with correlations to 'pythag_wins'
corr_matrix_pythag_wins = pd.DataFrame(corr_matrix['pythag_wins'])
corr_matrix_pythag_wins['abs_corr'] = corr_matrix_pythag_wins['pythag_wins'].abs()
corr_matrix_pythag_wins = corr_matrix_pythag_wins.sort_values(by='abs_corr', ascending=False)

# Conditional formatting for text color of abs_corr
def color_abs_corr(row):
    color = 'red' if row['pythag_wins'] > 0 else 'blue'
    return [f"color: {color}" if col == 'abs_corr' else '' for col in row.index]

# Add a new column 'Metric Importance' with a value of 1 for all rows
corr_matrix_pythag_wins['Metric Importance'] = corr_matrix_pythag_wins['abs_corr'].apply(calculate_metric_importance)

# Reset index and rename the first column to "Metric"; then create dictionary
corr_matrix_pythag_wins = corr_matrix_pythag_wins.reset_index().rename(columns={'index': 'Metric'})
metric_importance_dict = corr_matrix_pythag_wins.set_index('Metric')['Metric Importance'].to_dict()
corr_matrix_pythag_wins = corr_matrix_pythag_wins.set_index("Metric")

# Apply color styling while 'pythag_wins' still exists
styled_corr = corr_matrix_pythag_wins.style.apply(color_abs_corr, axis=1)

# Display the styled dataframe in Streamlit
st.subheader("Correlations with Pythag Wins (Modified)")
st.dataframe(styled_corr)
st.subheader("Correlation Matrix")
st.write(corr_matrix)
# Plot improved heatmap
fig, ax = plt.subplots(figsize=(16, 14))  # Increase figure size
sns.heatmap(corr_matrix, annot=True, fmt=".2f", cmap="coolwarm", ax=ax, 
            cbar_kws={"shrink": 0.8})  # Shrink color bar for better alignment
plt.xticks(rotation=45, ha="right", fontsize=10)  # Rotate x-axis labels
plt.yticks(fontsize=10)  # Adjust y-axis label font size
plt.title("Correlation Heatmap", fontsize=16)  # Add title to the heatmap
st.pyplot(fig)

# results from regression analysis
st.subheader("Results from Regression Analysis on Pythagorean Wins 2046-63")
st.write("Variables included vs R Squared")
# Get the absolute path of the current script
current_dir = os.path.dirname(os.path.abspath(__file__))
image_path = os.path.join(current_dir, "regression.png")
# Display the image
st.image(image_path, use_container_width=True)