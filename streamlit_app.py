# app.py
import streamlit as st
import requests

st.set_page_config(page_title="Sleeper League Analyzer", layout="wide")
st.title("🏈 Sleeper League Analyzer")

# League IDs
league_ids = [
    "1264083534415396864",
    "1264093436445741056",
    "1264093787064377344",
    "1264094054845513728",
]

# Fetch league names from Sleeper
league_names = []
league_info_map = {}  # store full league info
for lid in league_ids:
    try:
        res = requests.get(f"https://api.sleeper.app/v1/league/{lid}")
        data = res.json()
        league_names.append(data["name"])
        league_info_map[data["name"]] = data
    except Exception as e:
        league_names.append(f"League {lid} (Error fetching)")
        league_info_map[f"League {lid} (Error fetching)"] = {"league_id": lid}

# Display all league names
st.subheader("All Leagues:")
for name in league_names:
    st.write(f"- {name}")

# Dropdown to select league by name
selected_league_name = st.selectbox("Select a League:", league_names)
selected_league = league_info_map[selected_league_name]
league_id = selected_league["league_id"]

# Fetch current standings
try:
    rosters_res = requests.get(f"https://api.sleeper.app/v1/league/{league_id}/rosters")
    users_res = requests.get(f"https://api.sleeper.app/v1/league/{league_id}/users")

    rosters = rosters_res.json()
    users = users_res.json()

    user_map = {user["user_id"]: user["display_name"] for user in users}

    # Sort by points if available
    standings = sorted(rosters, key=lambda r: r.get("settings", {}).get("fpts", 0), reverse=True)

    st.subheader(f"Current Standings - {selected_league_name}")
    for idx, roster in enumerate(standings, start=1):
        owner_name = user_map.get(roster["owner_id"], "Unknown")
        points = roster.get("settings", {}).get("fpts", 0)
        st.write(f"{idx}. {owner_name} — {points} points")
except Exception as e:
    st.error(f"Error fetching standings: {e}")
