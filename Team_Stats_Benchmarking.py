import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd

# Function to determine the most recent year
def get_most_recent_year():
    url_index = "https://therzb.com/RZB/leaguehtml/index.html"
    response = requests.get(url_index)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, 'html.parser')

    recent_year = max(int(link.text.strip()) for link in soup.find_all("a") if link.text.strip().isdigit())
    return recent_year

def scrape_year(year):
    # URL for the stats and standings page of a specific year
    url_stats = f"https://therzb.com/RZB/leaguehtml/{year}teamstats.html"
    url_standings = f"https://therzb.com/RZB/leaguehtml/{year}standings.html"

    # Get stats page content
    response_stats = requests.get(url_stats)
    response_stats.raise_for_status()
    html_content_stats = response_stats.text
    soup_stats = BeautifulSoup(html_content_stats, 'html.parser')

    # Get standings page content
    response_standings = requests.get(url_standings)
    response_standings.raise_for_status()
    html_content_standings = response_standings.text
    soup_standings = BeautifulSoup(html_content_standings, 'html.parser')

    # Locate tables for stats
    tables_stats = soup_stats.find_all("table", {"bordercolor": "#800000", "width": "95%"})
    table_dict = {
        "Rushing Offense": None,
        "Rushing Defense": None,
        "Passing Offense": None,
        "Passing Defense": None,
        "Misc. Passing Offense": None,
        "Misc. Passing Defense": None,
        "Linemen": None,
        "Opp. Linemen": None,
        "Red Zone Offense": None,
        "Red Zone Defense": None,
        "Miscellaneous": None,
        "Misc. Opponents": None,
        "Kicking": None,
        "Opp. Kicking": None,
        "Returns": None,
        "Scoring/Turnovers": None,
    }

    # Find and assign each table to the corresponding key in table_dict
    for table in tables_stats:
        first_cell = table.find("tr").find("th").get_text(strip=True)
        if first_cell in table_dict:
            table_dict[first_cell] = table

    # Helper function to extract headers and data from a table
    def extract_table_data(table):
        headers = [th.get_text(strip=True) for th in table.find_all("tr")[0].find_all("th")]
        data = []
        for row in table.find_all("tr")[1:]:  # Skip header row
            cells = row.find_all("td")
            row_data = [cell.get_text(strip=True) for cell in cells]
            data.append(row_data)
        return headers, data

    # Create DataFrames for each table
    dfs = {}
    for key, table in table_dict.items():
        if table:  # Check if table is not None
            headers, data = extract_table_data(table)
            df = pd.DataFrame(data, columns=headers)
            df.rename(columns={df.columns[0]: "Team"}, inplace=True)  # Standardize team column name
            dfs[key] = df

    # Start merging with the first DataFrame and add each subsequent one
    merged_df = dfs["Rushing Offense"]
    for key in list(table_dict.keys())[1:]:
        suffix = '_vs' if key in [
            "Rushing Defense", "Passing Defense", "Misc. Passing Defense", "Opp. Linemen",
            "Red Zone Defense", "Misc. Opponents", "Opp. Kicking"
        ] else f'_{key.replace(" ", "").replace(".", "")}'
        merged_df = pd.merge(merged_df, dfs[key], on="Team", suffixes=('', suffix))

    # Scrape the standings table for W, L, T, PF, PA data
    standings_table = soup_standings.find("table", {"bordercolor": "#800000", "width": "80%"})

    # Extract standings data
    def extract_standings_data(table):
        standings_data = []
        for row in table.find_all("tr")[1:]:
            cells = row.find_all("td")
            if len(cells) == 9:
                row_data = [cell.get_text(strip=True) for cell in cells]
                standings_data.append(row_data)
        standings_headers = ["Team", "W", "L", "T", "Pct", "PF", "PA", "Conf", "Div"]
        return standings_headers, standings_data

    standings_headers, standings_data = extract_standings_data(standings_table)
    standings_df = pd.DataFrame(standings_data, columns=standings_headers)
    standings_df["Team"] = standings_df["Team"].str.replace(r"\s+\([^)]*\)$", "", regex=True).str.strip()
    standings_df = standings_df[["Team", "W", "L", "T", "PF", "PA"]]
    standings_df[["W", "L", "T", "PF", "PA"]] = standings_df[["W", "L", "T", "PF", "PA"]].apply(pd.to_numeric, errors="coerce")
    standings_df["Wins"] = standings_df["W"] + (standings_df["T"] / 2)
    standings_df["pythag_wins"] = ((standings_df["PF"] ** 2.37) / ((standings_df["PF"] ** 2.37) + (standings_df["PA"] ** 2.37)) * 16).round(1)

    # Merge standings data with merged_df
    merged_df = pd.merge(merged_df, standings_df[["Team", "W", "L", "T", "PF", "PA", "Wins", "pythag_wins"]], on="Team", how="left")
    merged_df["Year"] = year  # Add a column for the year

    # Add a prefix number to all column names in ascending order
    merged_df.columns = [f"{i+1}{col}" for i, col in enumerate(merged_df.columns)]

    return merged_df

def predict_wins_all_metrics(smoothed_avg, team_data):
    """
    Predicts the number of wins for a team based on all metrics.

    Parameters:
    - smoothed_avg: DataFrame, containing historic averages by wins.
    - team_data: DataFrame, containing metrics for the selected team.

    Returns:
    - A dictionary with metrics as keys and the predicted wins as values.
    """
    # Extract team metrics (assume single-row DataFrame for the selected team)
    team_metrics = team_data.iloc[0]
    
    # Initialize dictionary to store predictions
    predictions = {}
    
    # Iterate over the team's metrics (excluding non-metric columns)
    for metric in team_data.columns:
        if metric in ['team', 'year', 'wins']:  # Skip non-metric columns
            continue
        
        if metric in smoothed_avg.columns:
            # Find the closest value in smoothed_avg for the current metric
            closest_index = (smoothed_avg[metric] - team_metrics[metric]).abs().idxmin()
            
            # Get the corresponding number of wins
            predicted_wins = smoothed_avg.loc[closest_index, 'wins']
            predictions[metric] = predicted_wins
    
    return predictions

# Function to color text in the "Avg Wins" column based on the value ranges
def color_wins_column(val):
    if 1 <= val <= 4:
        return "color: #ff4d4d;"  # Red
    elif 5 <= val <= 8:
        return "color: #ffcc00;"  # Amber
    elif 9 <= val <= 12:
        return "color: #b3ffb3;"  # Light Green
    elif 13 <= val <= 16:
        return "color: #33cc33;"  # Dark Green
    return ""

# function to fill the value of Unit column based on the value of Metric column
def fill_unit_column(row):
    if row["Metric"] in ["pythag_wins", "yds_per_game", "ydsvs_per_game", "Pen_per_snap", "Fum_per_snap"]:
        return "All"
    elif row["Metric"] in ["Rate", "ypt", "Int_per_Att", "SPct"]:
        return "Pass"
    elif row["Metric"] in ["ypc", "KRB_per_Rply"]:
        return "Run"
    elif row["Metric"] in ["Rate_vs", "PDPct", "Intvs_per_Att", "ypt_vs", "SPct_vs"]:
        return "Pass D"
    elif row["Metric"] in ["KRBvs_per_Rply", "ypc_vs"]:
        return "Run D"
    else:
        return "Spec Tms"
         
# load in smoothed averages dataframe
smoothed_url = "https://raw.githubusercontent.com/fofota/fof_html_scraper/main/smoothed_avg.csv"
smoothed_avg = pd.read_csv(smoothed_url)
if 'wins.1' in smoothed_avg.columns:
    smoothed_avg = smoothed_avg.drop(columns=['wins.1'])
smoothed_avg.reset_index(drop=True, inplace=True)

metric_importance_dict = {
    'pythag_wins': 5,
    'yds_per_game': 5,
    'ydsvs_per_game': 5,
    'Rate': 5,
    'ypt': 5,
    'Rate_vs': 4,
    'ypc': 3,
    'Int_per_Att': 3,
    'PDPct': 3,
    'PR_avg': 3,
    'KRB_per_Rply': 3,
    'Pen_per_snap': 3,
    'Intvs_per_Att': 2,
    'SPct': 2,
    'KR_avg': 2,
    'ypt_vs': 2,
    'SPct_vs': 2,
    'KRBvs_per_Rply': 2,
    'Net_punt': 2,
    'OppPR_avg': 2,
    'Fum_per_snap': 2,
    'Net_punt_vs': 2,
    'Punt_for': 2,
    'OppKR_avg': 2,
    'ypc_vs': 1}

# Filter and rename columns
columns_to_keep = {
    "1Team": "team",
    "3Yards": "run_yds",
    "4Avg": "ypc",
    "14Yards_vs": "run_yds_vs",
    "15Avg_vs": "ypc_vs",
    "24Att": "Att",
    "27Yards_PassingOffense": "pass_yds",
    "29Yds/A": "ypt",
    "31Rate": "Rate",
    "32PPly": "Pply",
    "36Att_vs": "Att_vs",
    "39Yards_vs": "pass_yds_vs",
    "41Yds/A_vs": "ypt_vs",
    "43Rate_vs": "Rate_vs",
    "46OpPDPct_vs": "PDPct",
    "72KRB": "KRB",
    "75RPly": "Rply",
    "80SPct": "SPct",
    "84KRB_vs": "KRB_vs",
    "87RPly_vs": "Rply_vs",
    "92SPct_vs": "SPct_vs",
    "131Pnlty": "Pnlty",
    "154Avg_Kicking": "Punt_for",
    "156Avg_Kicking": "Net_punt",
    "167Avg_vs": "Net_punt_vs",
    "169Avg_Returns": "PR_avg",
    "171Avg_Returns": "KR_avg",
    "173Avg_Returns": "OppPR_avg",
    "175Avg_Returns": "OppKR_avg",
    "178Yds/G": "yds_per_game",
    "179OpYds/G": "ydsvs_per_game",
    "180Fum": "Fum",
    "181Int": "Int",
    "184Int": "Int_vs",
    "187W": "W",
    "188L": "L",
    "189T": "T",
    "190PF": "PF",
    "191PA": "PA",
    "192Wins": "wins",
    "193pythag_wins": "pythag_wins",
    "194Year": "year"
    }

columns_to_include = [
    'team', 'year', 'pythag_wins', 'wins', 'yds_per_game', 
    'ydsvs_per_game', 'Pen_per_snap', 'Fum_per_snap', 'Rate', 'ypt', 
    'Int_per_Att', 'SPct', 'ypc', 'KRB_per_Rply', 'Rate_vs', 'PDPct', 
    'Intvs_per_Att', 'ypt_vs', 'SPct_vs', 'KRBvs_per_Rply', 'ypc_vs', 
    'PR_avg', 'KR_avg', 'Net_punt_vs', 'OppPR_avg', 'OppKR_avg', 
    'Net_punt', 'Punt_for'
]

rounding_rules = {
    'year': 0,
    'pythag_wins': 1,
    'wins': 0,
    'yds_per_game': 1,
    'ydsvs_per_game': 1,
    'Pen_per_snap': 1,
    'Rate': 1,
    'ypt': 2,
    'Int_per_Att': 2,
    'SPct': 2,
    'ypc': 2,
    'KRB_per_Rply': 1,
    'Rate_vs': 1,
    'PDPct': 1,
    'Intvs_per_Att': 2,
    'ypt_vs': 2,
    'SPct_vs': 2,
    'KRBvs_per_Rply': 1,
    'ypc_vs': 2,
    'PR_avg': 1,
    'KR_avg': 1,
    'Net_punt_vs': 1,
    'OppPR_avg': 1,
    'OppKR_avg': 1,
    'Net_punt': 1,
    'Punt_for': 1
}

# load in raw_data dataframe
raw_data_url = "https://raw.githubusercontent.com/fofota/fof_html_scraper/main/filtered_stats_2045_2063.csv"
raw_data = pd.read_csv(raw_data_url)
raw_data.reset_index(drop=True, inplace=True)
raw_data = raw_data[raw_data['team'] != 'League'] # remove league averages
raw_data = raw_data[columns_to_include]
raw_data['year'] = raw_data['year'].astype(str)
            

# Streamlit App
st.set_page_config(
    page_title="RZB Team Stats Benchmarking",
    layout='wide'
)
st.title("RZB Team Stats Benchmarking")
st.sidebar.header("Select Team to Evaluate")

with st.expander("Use the sidebar to select a team to evaluate. Select here for more on how this tool works"):
    st.write('''
        This tool answers the question 'how good is my team' by comparing its statistical performance against historic benchmarks.
        
        What the tool does:
        1. Collects team-level statistics from the RZB html website for a selected team and year (e.g. the 2064 New York Jets)
        2. Compares vs historic benchmarks for 2045-64, which is the current 'tzach patch' era
        3. Provides an assessment of unit strength and overall team quality
        
        The benchmarks are measured in 'average wins' for a regular season:
        1. For the 2045-64 seasons all teams were grouped by regular season wins and then mean averages calculated for each metric (e.g. 'what was the average yards per target (ypt) for all teams with a 7-win record?')
        2. To simplify the analysis, a smoothed 'one way' line was fitted to the data for each metric manually
        3. This tool then uses that smoothed average line to compare the regular season record of a selected team, i.e. the 2064 New York Jets, to the historic benchmarks
        ''')

# Get the most recent year
most_recent_year = get_most_recent_year()

# Select year in sidebar
selected_year = st.sidebar.selectbox("Select season", range(most_recent_year, 2044, -1))
data = scrape_year(selected_year)

# process the scraped data for that year and add additional columns
filtered_data = data[list(columns_to_keep.keys())]
filtered_data = filtered_data.rename(columns=columns_to_keep)
filtered_data.iloc[:, 1:] = filtered_data.iloc[:, 1:].apply(pd.to_numeric, errors="coerce")
filtered_data[["Att", "Att_vs", "Int", "Int_vs", "Fum", "Pply", "Rply", "Pnlty", "KRB", "KRB_vs", "Rply_vs", "yds_per_game", "ydsvs_per_game"]] = filtered_data[["Att", "Att_vs", "Int", "Int_vs", "Fum", "Pply", "Rply", "Pnlty", "KRB", "KRB_vs", "Rply_vs", "yds_per_game", "ydsvs_per_game"]].apply(pd.to_numeric, errors="coerce")
filtered_data["SPct"] = pd.to_numeric(filtered_data["SPct"], errors="coerce")
filtered_data["Int_per_Att"] = ((filtered_data["Int"] / filtered_data["Att"]) * 100).round(2)
filtered_data["Intvs_per_Att"] = ((filtered_data["Int_vs"] / filtered_data["Att_vs"]) * 100).round(2)
filtered_data["Fum_per_snap"] = ((filtered_data["Fum"] / (filtered_data["Pply"] + filtered_data["Rply"])) * 100).round(3)
filtered_data["KRB"] = pd.to_numeric(filtered_data["KRB"], errors="coerce")
filtered_data["KRB_per_Rply"] = ((filtered_data["KRB"] / filtered_data["Rply"]) * 100).round(1)
filtered_data["KRBvs_per_Rply"] = ((filtered_data["KRB_vs"] / filtered_data["Rply_vs"]) * 100).round(1)
filtered_data["Pen_per_snap"] = ((filtered_data["Pnlty"] / (filtered_data["Pply"] + filtered_data["Rply"])) * 100).round(1)
filtered_data["Ydsgain_per_game"] = filtered_data["yds_per_game"] - filtered_data["ydsvs_per_game"]
filtered_data = filtered_data[filtered_data['team'] != 'League'] # remove league averages
filtered_data = filtered_data[columns_to_include]
for column, decimals in rounding_rules.items():
    if column in filtered_data.columns:
        filtered_data[column] = filtered_data[column].round(decimals)

# Select team in sidebar
team_list = filtered_data["team"].unique()
default_team = "New York (A) Jets" if "New York (A) Jets" in team_list else team_list[0]
selected_team = st.sidebar.selectbox("Select team", team_list, index=team_list.tolist().index(default_team))

# When analyse team button is clicked
if st.sidebar.button("Analyze Team"):
    with st.spinner("Collecting and Analysing team data..."):
                
        # Filter data for the selected team and display
        team_data = filtered_data[filtered_data["team"] == selected_team]
        team_data['year'] = team_data['year'].astype(int)
        
        # Filter columns and apply rounding for team_data
        team_data = team_data[columns_to_include]
        for column, decimals in rounding_rules.items():
            if column in team_data.columns:
                team_data[column] = team_data[column].round(decimals)
        
        # Display filtered data
        st.success("Data scraping complete!")
        
        # Predict Wins
        if not team_data.empty:
            predictions = predict_wins_all_metrics(smoothed_avg, team_data)
            st.write(f"Benchmarking of metrics for {selected_year} {selected_team}")

            # Convert predictions to a DataFrame
            predictions_df = pd.DataFrame.from_dict(predictions, orient="index", columns=["Avg Wins"])

            # Add the corresponding metric values from team_data as strings
            predictions_df["Value"] = predictions_df.index.map(
                lambda metric: str(team_data[metric].values[0]) if metric in team_data.columns else None
            )
                        
            # Reset the index to make "Metric" a column and rename columns
            predictions_df.reset_index(inplace=True)
            predictions_df.rename(columns={"index": "Metric"}, inplace=True)
            
            # Add and fill the Unit column
            predictions_df["Roster Unit"] = predictions_df.apply(fill_unit_column, axis=1)
            predictions_df = predictions_df[["Metric", "Value", "Avg Wins", "Roster Unit"]]       

            # Add the Metric Importance column using the dictionary
            predictions_df["Metric Importance"] = predictions_df["Metric"].map(metric_importance_dict)
            predictions_df["Metric Importance"] = predictions_df["Metric Importance"].apply(lambda x: int(x) if pd.notnull(x) else None)

            # Set index and use index to apply text colouring
            predictions_df = predictions_df.set_index("Metric")
            styled_predictions_df = predictions_df.style.applymap(
                color_wins_column, subset=["Avg Wins"]
            )
            
            # Display the benchmarked metrics dataframe
            st.dataframe(styled_predictions_df)

            # Display team metrics
            st.write(f"Metrics for the selected team: {selected_year} {selected_team}")
            team_data['year'] = team_data['year'].astype(str)
            st.dataframe(team_data.set_index("team"))
        else:
            st.error("Team data is not available.")
            
        st.write(f"All {most_recent_year} team-by-team data")
        filtered_data['year'] = filtered_data['year'].astype(str)
        st.dataframe(filtered_data.set_index(filtered_data.columns[0]))
        st.write("Historic (2045-64) RZB averages for each metric, by team regular season win record")
        st.dataframe(smoothed_avg.set_index(smoothed_avg.columns[0]))
        st.write("All 2045-64 RZB teams for each metric")
        st.dataframe(raw_data.set_index(raw_data.columns[0]))    