import streamlit as st
import requests
import pandas as pd

st.title("🏈 Swish League Standings")

# ------------------------
# League selection
# ------------------------
league_ids = {
    "1264083534415396864": None,
    "1264093436445741056": None,
    "1264093787064377344": None,
    "1264094054845513728": None,
}

# Fetch league names
for lid in league_ids.keys():
    try:
        resp = requests.get(f"https://api.sleeper.app/v1/league/{lid}")
        resp.raise_for_status()
        data = resp.json()
        league_ids[lid] = data.get("name", f"League {lid}")
    except:
        league_ids[lid] = f"League {lid}"

league_id = st.sidebar.selectbox(
    "Select League",
    list(league_ids.keys()),
    format_func=lambda x: league_ids[x]
)
selected_league_name = league_ids[league_id]

# ------------------------
# Fetch rosters + users
# ------------------------
league_resp = requests.get(f"https://api.sleeper.app/v1/league/{league_id}").json()
users = requests.get(f"https://api.sleeper.app/v1/league/{league_id}/users").json()
rosters = requests.get(f"https://api.sleeper.app/v1/league/{league_id}/rosters").json()

# Map roster_id -> display_name
roster_to_owner = {}
for roster in rosters:
    roster_id = roster["roster_id"]
    owner_id = roster["owner_id"]
    user = next((u for u in users if u["user_id"] == owner_id), None)
    roster_to_owner[roster_id] = user.get("display_name", f"Team {roster_id}") if user else f"Team {roster_id}"

# ------------------------
# Build table data
# ------------------------
table_data = []
for roster in rosters:
    owner = roster_to_owner[roster["roster_id"]]
    wins = roster.get("settings", {}).get("wins", 0)
    losses = roster.get("settings", {}).get("losses", 0)
    pf = roster.get("settings", {}).get("fpts", 0.0)
    pa = roster.get("settings", {}).get("fpts_against", 0.0)  # Points Against
    table_data.append({
        "Team Name": owner,
        "Wins": wins,
        "Losses": losses,
        "Points For": round(pf, 2),
        "Points Against": round(pa, 2)
    })

df = pd.DataFrame(table_data)
df = df.sort_values(["Wins", "Points For"], ascending=[False, False]).reset_index(drop=True)

st.subheader(f"Standings — {selected_league_name}")
st.dataframe(df, use_container_width=True)
