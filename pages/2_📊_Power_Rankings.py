import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import requests

import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils import get_standings, get_draft_grades

# --- League IDs ---
league_ids = {
    "1264083534415396864": None,
    "1264093436445741056": None,
    "1264093787064377344": None,
    "1264094054845513728": None,
}

for lid in league_ids.keys():
    try:
        data = requests.get(f"https://api.sleeper.app/v1/league/{lid}").json()
        league_ids[lid] = data.get("name", f"League {lid}")
    except:
        league_ids[lid] = f"League {lid}"

selected_league_id = st.sidebar.selectbox(
    "Select League", list(league_ids.keys()), format_func=lambda x: league_ids[x]
)

st.title("📊 Power Rankings")

def get_power_rankings_over_time(league_id):
    league = requests.get(f"https://api.sleeper.app/v1/league/{league_id}").json()
    season_length = league.get("settings", {}).get("season_length", 14)
    current_week = league.get("settings", {}).get("leg", 1)

    all_weeks = []

    for week in range(1, current_week + 1):
        standings_df = get_standings(league_id)
        draft_grades = get_draft_grades(league_id)

        if standings_df.empty or draft_grades.empty:
            continue

        merged = pd.merge(standings_df, draft_grades, on="Owner", how="left")

        merged["Win %"] = merged["Wins"] / (merged["Wins"] + merged["Losses"]).replace(0, 1)
        merged["Win % Score"] = 100 * (merged["Win %"] - merged["Win %"].min()) / (
            merged["Win %"].max() - merged["Win %"].min() + 1e-6
        )
        merged["PF Score"] = 100 * (merged["PF"] - merged["PF"].min()) / (
            merged["PF"].max() - merged["PF"].min() + 1e-6
        )
        merged["Draft Score Norm"] = 100 * (merged["Draft Score"] - merged["Draft Score"].min()) / (
            merged["Draft Score"].max() - merged["Draft Score"].min() + 1e-6
        )

        weeks_remaining = max(season_length - week + 1, 0)
        projection_weight = weeks_remaining / season_length
        record_weight = 1 - projection_weight

        merged["Record Score"] = 0.6 * merged["Win % Score"] + 0.4 * merged["PF Score"]
        merged["Power Score"] = (
            record_weight * merged["Record Score"] +
            projection_weight * merged["Draft Score Norm"]
        )

        merged["Week"] = week
        all_weeks.append(
            merged[["Owner", "Wins", "Losses", "PF", "Draft Score", "Power Score", "Week"]]
        )

    if not all_weeks:
        return pd.DataFrame()
    return pd.concat(all_weeks, ignore_index=True)


trend_df = get_power_rankings_over_time(selected_league_id)

if not trend_df.empty:
    latest_week = trend_df["Week"].max()
    latest_df = trend_df[trend_df["Week"] == latest_week].sort_values("Power Score", ascending=False)

    st.subheader(f"Current Rankings (Week {latest_week})")
    st.dataframe(latest_df[["Owner", "Wins", "Losses", "PF", "Draft Score", "Power Score"]])

    st.subheader("Power Score Trends")
    fig, ax = plt.subplots(figsize=(10, 6))
    for owner in trend_df["Owner"].unique():
        owner_data = trend_df[trend_df["Owner"] == owner]
        ax.plot(owner_data["Week"], owner_data["Power Score"], marker="o", label=owner)

    ax.set_title("Power Score Trend by Team")
    ax.set_xlabel("Week")
    ax.set_ylabel("Power Score")
    ax.legend(bbox_to_anchor=(1.05, 1), loc="upper left")
    st.pyplot(fig)

else:
    st.info("Not enough data yet.")
