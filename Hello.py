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

st.set_page_config(
    page_title="Unit Strength",
    )

# Streamlit App
st.title("RZB Team Stats Evaluator")
st.sidebar.header("Options")

# Step 1: Get the most recent year
most_recent_year = get_most_recent_year()
st.sidebar.write(f"Most recent year available: {most_recent_year}")

# Step 2: Select year
selected_year = st.sidebar.selectbox("Select year to scrape", range(most_recent_year, most_recent_year - 10, -1))
st.write("Use the sidebar to select which year to evaluate")
st.write(f"Scraping data for the year: {selected_year}")

# Step 3: Scrape data for the selected year
if st.sidebar.button("Scrape Data"):
    with st.spinner("Scraping data..."):
        data = scrape_year(selected_year)

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
        
        filtered_data = data[list(columns_to_keep.keys())]
        filtered_data = filtered_data.rename(columns=columns_to_keep)

        # Convert columns and calculate additional stats
        filtered_data.iloc[:, 1:] = filtered_data.iloc[:, 1:].apply(pd.to_numeric, errors="coerce")
        filtered_data["Int_per_Att"] = ((filtered_data["Int"] / filtered_data["Att"]) * 100).round(2)
        filtered_data["Intvs_per_Att"] = ((filtered_data["Int_vs"] / filtered_data["Att_vs"]) * 100).round(2)
        filtered_data["Fum_per_snap"] = ((filtered_data["Fum"] / (filtered_data["Pply"] + filtered_data["Rply"])) * 100).round(3)
        filtered_data["KRB_per_Rply"] = ((filtered_data["KRB"] / filtered_data["Rply"]) * 100).round(1)
        filtered_data["KRBvs_per_Rply"] = ((filtered_data["KRB_vs"] / filtered_data["Rply_vs"]) * 100).round(1)
        filtered_data["Pen_per_snap"] = ((filtered_data["Pnlty"] / (filtered_data["Pply"] + filtered_data["Rply"])) * 100).round(1)
        filtered_data["Ydsgain_per_game"] = filtered_data["yds_per_game"] - filtered_data["ydsvs_per_game"]


        # Display filtered data
        st.success("Data scraping complete!")
        st.write(f"Team-by-team Data for season: {most_recent_year}")

        st.dataframe(filtered_data.set_index(filtered_data.columns[0]))

        # Allow CSV download
        csv = filtered_data.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="Download CSV",
            data=csv,
            file_name=f"filtered_stats_{selected_year}.csv",
            mime="text/csv"
        )

st.write("Historic team averages by number of team wins, smoothed to simplify analysis")
smoothed_url = "https://raw.githubusercontent.com/fofota/fof_html_scraper/main/smoothed_avg.csv"
smoothed_avg = pd.read_csv(smoothed_url)
if 'wins.1' in smoothed_avg.columns:
    smoothed_avg = smoothed_avg.drop(columns=['wins.1'])
smoothed_avg.reset_index(drop=True, inplace=True)
st.dataframe(smoothed_avg.set_index(smoothed_avg.columns[0]))
