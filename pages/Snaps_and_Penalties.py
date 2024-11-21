import requests
from bs4 import BeautifulSoup
import pandas as pd
import os
import shutil
from collections import defaultdict
import re
import streamlit as st

# Base URL for the schedule page
schedule_url = "https://therzb.com/RZB/leaguehtml/19schedule.html"
base_url = "https://therzb.com/RZB/leaguehtml/"
log_dir = "logs"

# Function to determine the most recent year
def get_most_recent_year():
    url_index = "https://therzb.com/RZB/leaguehtml/index.html"
    response = requests.get(url_index)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, 'html.parser')

    recent_year = max(int(link.text.strip()) for link in soup.find_all("a") if link.text.strip().isdigit())
    return recent_year

# Streamlit App for Snaps and Penalties
st.title("Snaps and Penalties Analysis")
st.markdown("Analyze player performance for **New York (A)** from regular season logs.")

# Get the most recent year and set up the dropdown
try:
    most_recent_year = get_most_recent_year()
    years = list(range(most_recent_year, 2044, -1))  # Range from most recent year to 2045
except Exception as e:
    st.error(f"Failed to fetch recent year: {e}")
    years = list(range(2065, 2044, -1))  # Fallback years from 2065 to 2045

selected_year = st.selectbox("Select the Year", years, index=0)

# Single button for scraping and processing logs
if st.button("Scrape and Process Logs"):
    # Clear logs directory if it exists
    if os.path.exists(log_dir):
        shutil.rmtree(log_dir)
    os.makedirs(log_dir, exist_ok=True)

    def find_regular_season_rows(soup, year):
        # Find the header row for the selected year
        header_row = soup.find("td", string=re.compile(rf"{year} Regular Season.*"))
        if not header_row:
            st.error(f"{year} Regular Season header not found!")
            return []

        # Display header row text
        st.write("Now scraping:", header_row.text)

        # Collect all rows following this header until another season's header is encountered
        season_rows = []
        for row in header_row.find_parent("tr").find_next_siblings("tr"):
            if "Season" in row.get_text():
                break
            season_rows.append(row)
        return season_rows

    def scrape_logs(schedule_url, year):
        response = requests.get(schedule_url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        regular_season_rows = find_regular_season_rows(soup, year)
        if not regular_season_rows:
            st.error(f"No logs found for the {year} Regular Season!")
            return False

        log_links = []
        for row in regular_season_rows:
            log_link = row.find("a", string="Log")
            if log_link:
                log_links.append(base_url + log_link['href'])
        st.write(f"Found {len(log_links)} log links for {year}.")

        for i, log_link in enumerate(log_links, start=1):
            try:
                log_response = requests.get(log_link)
                log_response.raise_for_status()
                log_filename = f"{log_dir}/log_page_{i}.html"
                with open(log_filename, "w", encoding="utf-8") as file:
                    file.write(log_response.text)
                st.write(f"Downloaded log {i} to {log_filename}")
            except Exception as e:
                st.error(f"Failed to scrape {log_link}: {e}")
        return True

    def process_logs():
        player_stats = defaultdict(lambda: {'Plus': 0, 'Minus': 0, 'Pen': 0})
        penalty_details = []

        for log_file in os.listdir(log_dir):
            if log_file.endswith('.html'):
                with open(os.path.join(log_dir, log_file), 'r', encoding='utf-8') as file:
                    html_content = file.read()
                soup = BeautifulSoup(html_content, 'html.parser')
                new_york_table = soup.find('th', text='New York (A)')
                if new_york_table:
                    rows = new_york_table.find_parent('table').find_all('tr')[1:]
                    for row in rows:
                        cells = row.find_all('td')
                        player_name = cells[0].text.strip()
                        plus = int(cells[1].text.strip())
                        minus = int(cells[2].text.strip())
                        player_stats[player_name]['Plus'] += plus
                        player_stats[player_name]['Minus'] += minus
                penalty_lines = soup.find_all(string=re.compile(r"PENALTY:"))
                for line in penalty_lines:
                    match = re.search(r"PENALTY: ([A-Za-z\s]+) of New York \(A\) was called for (.+)\.", line)
                    if match:
                        player_name = match.group(1).strip()
                        penalty_type = match.group(2).strip()
                        player_stats[player_name]['Pen'] += 1
                        penalty_details.append({'Player': player_name, 'Penalty': penalty_type})

        # Convert data to a DataFrame
        data = [{'Player': player,
                 'Plus': stats['Plus'],
                 'Minus': stats['Minus'],
                 'Snaps': stats['Plus'] + stats['Minus'],
                 'Pen': stats['Pen']} for player, stats in player_stats.items()]
        df = pd.DataFrame(data)

        if df.empty:
            st.error("No data found in the logs.")
        else:
            df['pct_minus'] = (df['Minus'] / df['Snaps'] * 100).round(1)
            df['Pen_per_snap'] = (df['Pen'] / df['Snaps'] * 100).round(1)
            df = df.sort_values(by='Snaps', ascending=False)

            total_minus = df['Minus'].sum()
            total_snaps = df['Snaps'].sum()
            total_penalties = df['Pen'].sum()
            avg_pen_per_snap = (total_penalties / total_snaps * 100).round(2) if total_snaps > 0 else 0
            overall_pct_minus = (total_minus / total_snaps * 100).round(1) if total_snaps > 0 else 0

            # Display results
            st.write("Aggregated Player Stats:")
            st.dataframe(df)
            st.write(f"**Total Penalties:** {total_penalties}")
            st.write(f"**Average Penalties Per Snap:** {avg_pen_per_snap}%")
            st.write(f"**Overall pct_minus:** {overall_pct_minus}%")

    # Scrape and process logs
    if scrape_logs(schedule_url, selected_year):
        process_logs()