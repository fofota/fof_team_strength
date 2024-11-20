import streamlit as st

# Set the page title and layout
st.set_page_config(
    page_title="Scatter Plots",
    layout='wide'
)

from Team_Stats_Benchmarking import raw_data
import matplotlib.pyplot as plt
import numpy as np

# Title
st.title("Scatter Plots")

# Exclude 'team' column from selectboxes
columns_to_plot = [col for col in raw_data.columns if col != "team"]

# Add scatter plots of raw_data with selectbox for x and y axis
x_axis = st.selectbox("X-axis", columns_to_plot, index=columns_to_plot.index("pythag_wins"))
y_axis = st.selectbox("Y-axis", columns_to_plot, index=columns_to_plot.index("ypt"))

st.write(f"Scatter plot of {x_axis} vs {y_axis}")

# Calculate correlation and R-squared
x_data = raw_data[x_axis]
y_data = raw_data[y_axis]
correlation = np.corrcoef(x_data, y_data)[0, 1]
r_squared = correlation ** 2

# Perform linear regression to calculate the regression line
slope, intercept = np.polyfit(x_data, y_data, 1)
regression_line = slope * x_data + intercept

# Create a figure and axis explicitly
fig, ax = plt.subplots(figsize=(8, 6))

# Plot the scatter points
ax.scatter(x_data, y_data, label="Data Points")

# Plot the regression line without legend
ax.plot(x_data, regression_line, color="red")

# Add correlation and R-squared values to the plot
ax.text(
    0.05, 0.95,  # Position in axes coordinates
    f"Correlation: {correlation:.2f}\nR-squared: {r_squared:.2f}",
    transform=ax.transAxes,  # Use axes coordinates for positioning
    fontsize=10,
    verticalalignment='top',
    bbox=dict(boxstyle="round", facecolor="white", edgecolor="gray")
)

# Add axis labels
ax.set_xlabel(x_axis)
ax.set_ylabel(y_axis)

# Pass the figure to st.pyplot()
st.pyplot(fig)