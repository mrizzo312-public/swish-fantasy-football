import streamlit as st
import pandas as pd
import requests
import os
import sys

# Add parent folder to path for utils
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from utils import (
    get_league_data, get_league_names, get_standings, get_draft_grades, get_matchups_with_owners,
    get_all_projections, fetch_weekly_projections, split_player_team, get_player_map, calculate_power_scores
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

# --- Fetch matchups for the current week ---
matchups_week = requests.get(f"https://api.sleeper.app/v1/league/{league_id}/matchups/{current_week}").json()

# Directly create DataFrame assuming each row has 'roster_id' and 'matchup_id'
rosters_df = pd.DataFrame([{
    "roster_id": m.get("roster_id"),
    "matchup_id": m.get("matchup_id")
} for m in matchups_week])

matchups = get_matchups_with_owners(rosters_df, roster_to_owner, merged)

default_idx = matchups["avg_power"].idxmax()

# Dropdown
selected_matchup_idx = st.selectbox(
    "Select Matchup",
    matchups.index.tolist(),
    format_func=lambda idx: (
        f"⭐ {matchups.loc[idx, 'Matchup']}" if idx == default_idx else matchups.loc[idx, 'Matchup']
    ),
    index=default_idx
)

# ------------------------
# Display selected matchup
# ------------------------
matchup_row = matchups.loc[selected_matchup_idx]
is_matchup_of_week = selected_matchup_idx == default_idx
st.subheader("🔥 Matchup of the Week!" if is_matchup_of_week else "Selected Matchup")

weekly_proj_map = fetch_weekly_projections(current_week)
st.dataframe(weekly_proj_map, use_container_width=True)

roster_ids = matchup_row["roster_ids"]
owners = matchup_row["owners"]
matchup_id = matchup_row["matchup_id"]

def get_starters_df(matchups_week, selected_matchup_id, roster_to_owner, weekly_proj_map, player_map):
    """
    Returns a DataFrame of starters for a given matchup, with projected weekly_proj_map points.
    
    matchups_week: list of matchup dicts from Sleeper API
    selected_matchup_id: the matchup_id we want
    roster_to_owner: dict mapping roster_id -> owner name
    weekly_proj_map: dict mapping player_name -> projected points
    player_map: dict mapping player_id -> player_name
    """
    
    rows = []
    
    # Filter only the rows for the selected matchup
    matchup_rows = [m for m in matchups_week if m["matchup_id"] == selected_matchup_id]
    
    for m in matchup_rows:
        roster_id = m["roster_id"]
        owner = roster_to_owner.get(roster_id, f"Team {roster_id}")
        starters = m.get("starters", [])
        
        for player_id in starters:
            player_name = player_map.get(player_id, "Unknown Player")
            proj_points = weekly_proj_map.get(player_name, 0)
            rows.append({
                "Matchup ID": selected_matchup_id,
                "Roster ID": roster_id,
                "Owner": owner,
                "Player": player_name,
                "Proj Points": round(proj_points, 1)
            })
    
    df = pd.DataFrame(rows)
    return df


starters_df = get_starters_df(matchups_week, matchup_id, roster_to_owner, weekly_proj_map, player_map)

for owner in owners:
    st.markdown(f"### {owner} Starters")
    st.table(starters_df[starters_df["Owner"] == owner][["Player", "Proj Points"]])