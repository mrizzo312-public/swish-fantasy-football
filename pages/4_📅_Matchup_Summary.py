import streamlit as st
import pandas as pd
import requests
import sys, os

# Add parent folder to path for utils
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from utils import (
    get_league_data, get_league_names, get_standings, get_draft_grades,
    get_all_projections, calculate_dynamic_vorp, split_player_team, get_player_map
)

st.title("📅 Matchup Summary")

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
# Determine previous week
# ------------------------
league, _, roster_to_owner = get_league_data(league_id)
current_week = league.get("settings", {}).get("leg", 1)
prev_week = current_week - 1

# ------------------------
# Fetch previous week matchups
# ------------------------
try:
    resp = requests.get(f"https://api.sleeper.app/v1/league/{league_id}/matchups/{prev_week}")
    resp.raise_for_status()
    matchups = pd.DataFrame(resp.json())
except:
    st.error("Failed to fetch previous week matchups from Sleeper API.")
    st.stop()

if matchups.empty:
    st.info(f"No matchups found for week {prev_week}")
    st.stop()

# ------------------------
# Load player map
# ------------------------
player_map = get_player_map("player_ids.csv")

# ------------------------
# Power rankings for default matchup
# ------------------------
standings_df = get_standings(league_id)
draft_grades_df = get_draft_grades(league_id)
merged = pd.merge(standings_df, draft_grades_df, left_on="Owner", right_on="Owner", how="left")
merged["Draft Score"] = merged["Draft Score"].fillna(0)
merged["Win %"] = merged["Wins"] / (merged["Wins"] + merged["Losses"]).replace(0,1)
merged["Record Score"] = 0.5*(merged["Win %"]*100) + 0.5*merged["Draft Score"]

# ------------------------
# Identify default matchup (closest matchup by lowest average power score)
# ------------------------
default_matchup_idx = None
min_avg_score = float("inf")
for idx, row in matchups.iterrows():
    teams = [roster_to_owner.get(rid, f"Team {rid}") for rid in row["roster_id"]]
    avg_score = merged[merged["Owner"].isin(teams)]["Record Score"].mean()
    if avg_score < min_avg_score:
        min_avg_score = avg_score
        default_matchup_idx = idx

# ------------------------
# Matchup selector
# ------------------------
selected_matchup_idx = st.selectbox(
    "Select Matchup",
    options=list(range(len(matchups))),
    format_func=lambda x: " vs ".join([roster_to_owner.get(rid, f"Team {rid}") for rid in matchups.loc[x, "roster_id"]]),
    index=default_matchup_idx
)

matchup_row = matchups.loc[selected_matchup_idx]
is_default = selected_matchup_idx == default_matchup_idx
st.subheader("🔥 Closest Matchup of the Week!" if is_default else "Selected Matchup")

# ------------------------
# Load projections + VORP
# ------------------------
proj_df = get_all_projections()
proj_df = split_player_team(proj_df)
vorp = calculate_dynamic_vorp(proj_df)

# ------------------------
# Display starters with points and position comparison
# ------------------------
team_pos_points = {}  # store points by position for each team
all_players = []

for roster_id in matchup_row["roster_id"]:
    owner = roster_to_owner.get(roster_id, f"Team {roster_id}")
    st.markdown(f"### {owner} Starters")

    starters = matchup_row.get("starters", [])
    starter_rows = []
    pos_points = {}

    for player_id in starters:
        player_name = player_map.get(player_id, "Unknown Player")
        # Projection
        proj_points = vorp.get(player_name, 0)
        # Actual points from Sleeper API
        points_scored = matchup_row.get("players_points", {}).get(str(player_id), 0)

        starter_rows.append({
            "Player": player_name,
            "Position": proj_df[proj_df["Player"]==player_name]["Position"].values[0] if not proj_df[proj_df["Player"]==player_name].empty else "?",
            "Proj Points": round(proj_points,1),
            "Actual Points": points_scored
        })

        # Aggregate points by position
        position = starter_rows[-1]["Position"]
        pos_points[position] = pos_points.get(position, 0) + points_scored

        # Save for highlighting highest scorer
        all_players.append((player_name, points_scored))

    team_pos_points[owner] = pos_points

    # Highlight highest scoring player
    if starter_rows:
        max_points = max(r["Actual Points"] for r in starter_rows)
        for r in starter_rows:
            if r["Actual Points"] == max_points:
                r["Player"] = f"🔥 {r['Player']} 🔥"

    st.table(pd.DataFrame(starter_rows))

# ------------------------
# Points by position comparison
# ------------------------
st.subheader("Position Advantage Comparison")
positions = set()
for points in team_pos_points.values():
    positions.update(points.keys())

comparison_rows = []
teams = list(team_pos_points.keys())
for pos in positions:
    p1 = team_pos_points[teams[0]].get(pos,0)
    p2 = team_pos_points[teams[1]].get(pos,0)
    winner = teams[0] if p1>p2 else (teams[1] if p2>p1 else "Tie")
    comparison_rows.append({"Position": pos, teams[0]: p1, teams[1]: p2, "Winner": winner})

st.table(pd.DataFrame(comparison_rows))
