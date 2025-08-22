import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import sys, os

# Add parent folder to path for utils
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from utils import get_league_data, get_standings, get_draft_grades, get_league_names

st.title("🏆 Power Rankings")

# League IDs
league_ids = {
    "1264083534415396864": None,
    "1264093436445741056": None,
    "1264093787064377344": None,
    "1264094054845513728": None,
}

# Fetch league names using utils
league_ids = get_league_names(league_ids)

league_id = st.sidebar.selectbox(
    "Select League",
    list(league_ids.keys()),
    format_func=lambda x: league_ids[x]
)
selected_league_name = league_ids[league_id]

# --- Fetch standings and draft grades ---
standings_df = get_standings(league_id)
draft_grades_df = get_draft_grades(league_id)

if standings_df.empty or draft_grades_df.empty:
    st.info("Not enough data to generate power rankings.")
    st.stop()

# Merge standings and draft grades
merged = pd.merge(standings_df, draft_grades_df, left_on="Owner", right_on="Owner", how="left")
merged["Draft Score"] = merged["Draft Score"].fillna(0)

# --- Compute Power Score ---
# Weight record vs draft grade based on season progress
league, _, _ = get_league_data(league_id)
season_length = league.get("settings", {}).get("season_length", 14)
current_week = league.get("settings", {}).get("leg", 1)
weeks_remaining = max(season_length - current_week + 1, 0)
projection_weight = weeks_remaining / season_length
record_weight = 1 - projection_weight

# Record score: normalize wins + PF
merged["Win %"] = merged["Wins"] / (merged["Wins"] + merged["Losses"]).replace(0, 1)
merged["Win % Score"] = 100 * (merged["Win %"] - merged["Win %"].min()) / (merged["Win %"].max() - merged["Win %"].min() + 1e-6)
merged["PF Score"] = 100 * (merged["PF"] - merged["PF"].min()) / (merged["PF"].max() - merged["PF"].min() + 1e-6)
merged["Record Score"] = 0.6 * merged["Win % Score"] + 0.4 * merged["PF Score"]

# Final power score
merged["Power Score"] = record_weight * merged["Record Score"] + projection_weight * merged["Draft Score"]

# Sort by power score
merged = merged.sort_values("Power Score", ascending=False).reset_index(drop=True)
merged.index = merged.index + 1  # ranking starts at 1

# --- Display table ---
st.subheader(f"Power Rankings — {selected_league_name}")
st.dataframe(merged[["Owner", "Wins", "Losses", "PF", "Draft Score", "Power Score"]], use_container_width=True)

# --- Optional trend chart ---
st.subheader("Power Score Trend")
fig, ax = plt.subplots(figsize=(10, 6))
for _, row in merged.iterrows():
    ax.barh(row["Owner"], row["Power Score"])

ax.set_xlabel("Power Score")
ax.set_ylabel("Team")
ax.invert_yaxis()
st.pyplot(fig)
