import streamlit as st
import pandas as pd
import sys, os

# Add parent folder to path for utils
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from utils import get_league_data, get_draft, get_all_projections, calculate_dynamic_vorp, assign_grades, split_player_team, get_league_names

st.title("💯 Draft Grades")

# League IDs
league_ids = {
    "1264083534415396864": None,
    "1264093436445741056": None,
    "1264093787064377344": None,
    "1264094054845513728": None,
}

league_ids = get_league_names(league_ids)

st.write("### Available Leagues")
for lid, name in league_ids.items():
    st.write(f"- {name}")

league_id = st.sidebar.selectbox(
    "Select League",
    list(league_ids.keys()),
    format_func=lambda x: league_ids[x]
)
selected_league_name = league_ids[league_id]

# Fetch draft + league info
league, scoring, roster_to_owner = get_league_data(league_id)
draft_id, picks, draft_time = get_draft(league_id)

if not picks:
    if not draft_time:
        st.error("No draft time set for this league.")
        st.stop()
    st.error(f"No draft picks found yet. Draft is scheduled for {draft_time}.")
    st.stop()

# Projections
proj_df = get_all_projections()
if proj_df.empty:
    st.error("Failed to fetch projections from FantasyPros.")
    st.stop()

# Flatten multi-level headers if present
if isinstance(proj_df.columns, pd.MultiIndex):
    proj_df.columns = ['_'.join(filter(None, col)).strip() for col in proj_df.columns.values]

proj_df = proj_df.rename(columns={'MISC_FPTS': 'FPTS','Unnamed: 0_level_0_Player':'Player'})
proj_df = split_player_team(proj_df)

proj_df = proj_df[['Player', 'FPTS', 'Position']]
proj_df = proj_df.dropna(subset=['FPTS']).copy()
proj_df['FPTS'] = proj_df['FPTS'].astype(float)

vorp = calculate_dynamic_vorp(proj_df)

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
