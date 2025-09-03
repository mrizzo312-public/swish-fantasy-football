import streamlit as st
import pandas as pd
import requests
import os
import sys

# Add parent folder to path for utils
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from utils import (
    get_league_data, get_league_names, get_standings, get_draft_grades,
    get_all_projections, calculate_dynamic_vorp, split_player_team, get_player_map, calculate_power_scores
)

st.title("🆚 Matchup Previews")

# ------------------------
# League selection
# ------------------------
league_ids = {
    "1264083534415396864": None,
    "1264093436445741056": None,
    "1264093787064377344": None,
    "1264094054845513728": None,
}
league_ids = get_league_names(league_ids)

league_id = st.sidebar.selectbox(
    "Select League",
    list(league_ids.keys()),
    format_func=lambda x: league_ids[x]
)
selected_league_name = league_ids[league_id]

# ------------------------
# Fetch power rankings
# ------------------------
standings_df = get_standings(league_id)
draft_grades_df = get_draft_grades(league_id)
if standings_df.empty or draft_grades_df.empty:
    st.info("Not enough data to generate matchup previews.")
    st.stop()

# ------------------------
# Fetch matchups
# ------------------------
league, _, roster_to_owner = get_league_data(league_id)
current_week = league.get("settings", {}).get("leg", 1)
merged = calculate_power_scores(standings_df, draft_grades_df, league)

try:
    resp = requests.get(f"https://api.sleeper.app/v1/league/{league_id}/matchups/{current_week}")
    resp.raise_for_status()
    matchups = pd.DataFrame(resp.json())
except:
    st.error("Failed to fetch matchups from Sleeper API.")
    st.stop()

if matchups.empty:
    st.info(f"No matchups found for week {current_week}")
    st.stop()

# ------------------------
# Load or fetch player ID → name mapping
# ------------------------
player_map = get_player_map("player_ids.csv")

# ------------------------
# Identify matchup of the week
# ------------------------
# Use two highest power score teams as default
# --- Determine Matchup of the Week (highest combined power score) ---
default_matchup_idx = None
max_avg_score = float('-inf')

for idx, row in matchups.iterrows():
    roster_ids = row["roster_id"]
    if not isinstance(roster_ids, list):
        roster_ids = [roster_ids]

    # Get the average power score of both teams in this matchup
    team_scores = merged[merged["Owner"].isin([roster_to_owner.get(rid, f"Team {rid}") for rid in roster_ids])]
    if not team_scores.empty:
        avg_score = team_scores["Power Score"].mean()
        if avg_score > max_avg_score:
            max_avg_score = avg_score
            default_matchup_idx = idx



def format_matchup(x):
    roster_ids = matchups.loc[x, "roster_id"]
    if not isinstance(roster_ids, list):
        roster_ids = [roster_ids]
    label = " vs ".join(roster_to_owner.get(rid, f"Team {rid}") for rid in roster_ids)
    if x == default_matchup_idx:
        label = f"⭐ Matchup of the Week: {label}"
    return label

selected_matchup_idx = st.selectbox(
    "Select Matchup",
    matchups.index,
    index=default_matchup_idx,
    format_func=format_matchup,
)

# ------------------------
# Display selected matchup
# ------------------------
matchup_row = matchups.loc[selected_matchup_idx]
is_matchup_of_week = selected_matchup_idx == default_matchup_idx
st.subheader("🔥 Matchup of the Week!" if is_matchup_of_week else "Selected Matchup")

proj_df = get_all_projections()
proj_df = split_player_team(proj_df)
vorp = calculate_dynamic_vorp(proj_df)

# Loop through each team in the matchup
for roster_id in matchup_row["roster_id"]:
    owner = roster_to_owner.get(roster_id, f"Team {roster_id}")
    st.markdown(f"### {owner} Starters")
    starters = matchup_row.get("starters", [])

    starter_rows = []
    for player_id in starters:
        player_name = player_map.get(player_id, "Unknown Player")
        proj_points = vorp.get(player_name, 0)
        starter_rows.append({"Player": player_name, "Proj Points": round(proj_points, 1)})

    st.table(pd.DataFrame(starter_rows))
