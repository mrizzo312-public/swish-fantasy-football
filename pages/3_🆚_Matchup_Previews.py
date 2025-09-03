import streamlit as st
import pandas as pd
import requests
import os
import sys

# Add parent folder to path for utils
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from utils import (
    get_league_data, get_league_names, get_standings, get_draft_grades, get_matchups_with_owners,
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

week = current_week  # e.g., league.get("settings", {}).get("leg", 1)
matchups_week = requests.get(f"https://api.sleeper.app/v1/league/{league_id}/matchups/{week}").json()
matchups_df = pd.DataFrame(matchups_week)  # must include 'matchup_id' and 'roster_id' or 'rosters'

# Expand so each row = roster in that matchup
rosters_for_week = []
for m in matchups_week:
    for rid in m.get("rosters", []):
        rosters_for_week.append({"roster_id": rid, "matchup_id": m["matchup_id"]})
rosters_df = pd.DataFrame(rosters_for_week)

matchups = get_matchups_with_owners(rosters_df, roster_to_owner, merged)

# Pick Matchup of the Week (highest avg_power)
default_matchup_id = matchups.loc[matchups["avg_power"].idxmax(), "matchup_id"]

# Dropdown
selected_matchup_id = st.selectbox(
    "Select Matchup",
    matchups["matchup_id"].tolist(),
    format_func=lambda mid: " vs ".join(matchups.loc[matchups["matchup_id"] == mid, "owners"].values[0]),
    index=matchups.index[matchups["matchup_id"] == default_matchup_id][0]
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
