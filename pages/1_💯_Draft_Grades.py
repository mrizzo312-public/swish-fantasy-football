import streamlit as st
import requests
import numpy as np
import pandas as pd

# -------------------
# Helper Functions
# -------------------

def get_league_data(league_id: str):
    """Fetch league metadata (name, scoring, users, rosters)."""
    league = requests.get(f"https://api.sleeper.app/v1/league/{league_id}").json()
    users = requests.get(f"https://api.sleeper.app/v1/league/{league_id}/users").json()
    rosters = requests.get(f"https://api.sleeper.app/v1/league/{league_id}/rosters").json()

    # Map roster_id -> display name
    roster_to_owner = {}
    for roster in rosters:
        roster_id = roster["roster_id"]
        owner_id = roster["owner_id"]
        user = next((u for u in users if u["user_id"] == owner_id), None)
        if user:
            display_name = user.get("display_name", "Unknown")
            roster_to_owner[roster_id] = display_name
        else:
            roster_to_owner[roster_id] = f"Team {roster_id}"

    return league, league.get("scoring_settings", {}), roster_to_owner

def get_draft(league_id: str):
    draft_resp = requests.get(f"https://api.sleeper.app/v1/league/{league_id}/drafts").json()
    if not draft_resp:
        return None, None
    draft_id = draft_resp[0]["draft_id"]
    picks = requests.get(f"https://api.sleeper.app/v1/draft/{draft_id}/picks").json()
    return draft_id, picks

import pandas as pd
import requests
import streamlit as st

def fetch_fp_projections(position: str) -> pd.DataFrame:
    """
    Fetch FantasyPros seasonal projections table for a given position
    using html5lib parser to avoid lxml dependency.
    """
    url = f"https://www.fantasypros.com/nfl/projections/{position}.php?week=draft"
    r = requests.get(url)
    r.raise_for_status()

    # Use html5lib to parse HTML tables
    tables = pd.read_html(r.text, flavor='html5lib')
    if not tables:
        st.warning(f"No tables found for {position.upper()} projections.")
        return pd.DataFrame()
    
    df = tables[0]
    df['Position'] = position.upper()
    return df

def get_all_projections() -> pd.DataFrame:
    """
    Fetch projections for all main positions (QB, RB, WR, TE)
    and combine into a single DataFrame.
    """
    dfs = []
    for pos in ['qb', 'rb', 'wr', 'te']:
        try:
            df = fetch_fp_projections(pos)
            if not df.empty:
                dfs.append(df)
        except Exception as e:
            st.error(f"Error fetching {pos.upper()} projections: {e}")
    return pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()



def calculate_fantasy_points(player_stats: dict, scoring: dict) -> float:
    """Apply league scoring settings to player stats."""
    points = 0
    for stat, value in player_stats.items():
        if stat in scoring:
            points += value * scoring[stat]
    return points

def calculate_dynamic_vorp(proj_df: pd.DataFrame):
    """
    Calculate VORP using dynamic replacement levels:
    QB13, RB25, WR37, TE13 based on FPTS projections.
    
    proj_df: DataFrame with columns ['Player', 'FPTS', 'Position']
    Returns: dict mapping player name -> VORP
    """
    replacement_targets = {'QB': 13, 'RB': 25, 'WR': 37, 'TE': 13}
    vorp = {}

    # Group by position
    for pos, group in proj_df.groupby('Position'):
        group_sorted = group.sort_values('FPTS', ascending=False).reset_index(drop=True)
        cutoff_idx = replacement_targets.get(pos, len(group_sorted)) - 1
        cutoff_idx = min(cutoff_idx, len(group_sorted) - 1)
        replacement_value = group_sorted.loc[cutoff_idx, 'FPTS']

        for _, row in group_sorted.iterrows():
            vorp[row['Player']] = row['FPTS'] - replacement_value

    return vorp


def assign_grades(team_scores):
    values = list(team_scores.values())
    mean = np.mean(values)
    std = np.std(values) if np.std(values) > 0 else 1
    grades = {}
    for team, score in team_scores.items():
        z = (score - mean) / std
        if z > 1.0:
            grade = "A"
        elif z > 0.5:
            grade = "B"
        elif z > -0.5:
            grade = "C"
        elif z > -1.0:
            grade = "D"
        else:
            grade = "F"
        grades[team] = (score, grade)
    return grades

# -------------------
# Streamlit App
# -------------------

st.title("💯 Draft Grades")

league_ids = {
    "League 1": "1264083534415396864",
    "League 2": "1264093436445741056",
    "League 3": "1264093787064377344",
    "League 4": "1264094054845513728",
}

# Show league names
st.write("### Available Leagues")
for name in league_ids.keys():
    st.write(f"- {name}")

# League selector
selected_league_name = st.sidebar.selectbox("Select League", list(league_ids.keys()))
league_id = league_ids[selected_league_name]

# Fetch draft + league info
league, scoring, roster_to_owner = get_league_data(league_id)
draft_id, picks = get_draft(league_id)

if not draft_id:
    st.warning("No draft found yet for this league.")
    st.stop()

# Fetch projections + calculate VORP
proj_df = get_all_projections()
if proj_df.empty:
    st.error("Failed to fetch projections from FantasyPros.")
    st.stop()

st.dataframe(proj_df.head())

# Example: extract FPTS and player name
proj_df = proj_df[['Player', 'FPTS', 'Position']]
proj_df = proj_df.dropna(subset=['FPTS']).copy()
proj_df['FPTS'] = proj_df['FPTS'].astype(float)

vorp = calculate_dynamic_vorp(proj_df, scoring)

# Tally team draft scores
team_scores = {}
team_picks = {}

for pick in picks:
    player_name = pick.get("metadata", {}).get("first_name", "") + " " + pick.get("metadata", {}).get("last_name", "")
    roster_id = pick["roster_id"]

    value = vorp.get(player_name, 0)

    if roster_id not in team_scores:
        team_scores[roster_id] = 0
        team_picks[roster_id] = []
    team_scores[roster_id] += value
    team_picks[roster_id].append((player_name, value))

grades = assign_grades(team_scores)

# Build results table
results = []
for roster_id, (score, grade) in grades.items():
    owner_name = roster_to_owner.get(roster_id, f"Team {roster_id}")
    best_pick = max(team_picks[roster_id], key=lambda x: x[1], default=(None, 0))
    worst_pick = min(team_picks[roster_id], key=lambda x: x[1], default=(None, 0))

    results.append({
        "Owner": owner_name,
        "Score": round(score, 1),
        "Grade": grade,
        "Best Pick": f"{best_pick[0]} (+{round(best_pick[1],1)})" if best_pick[0] else "-",
        "Worst Pick": f"{worst_pick[0]} ({round(worst_pick[1],1)})" if worst_pick[0] else "-"
    })

df = pd.DataFrame(results)
df = df.sort_values("Score", ascending=False).reset_index(drop=True)
df.index = df.index + 1  # Rank starting at 1

st.subheader(f"Draft Grades — {selected_league_name}")
st.dataframe(df, use_container_width=True)
