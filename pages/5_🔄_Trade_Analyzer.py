import streamlit as st
import requests
import pandas as pd
import matplotlib.pyplot as plt
import sys, os

# Add parent folder to path for utils
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from utils import get_league_names, get_league_data, get_player_map

st.title("🔄 Trade Analyzer")

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
# Load player map CSV
# ------------------------
player_map = get_player_map("player_ids.csv")

# ------------------------
# Fetch trades from Sleeper API
# ------------------------
def fetch_trades(league_id):
    url = f"https://api.sleeper.app/v1/league/{league_id}/transactions"
    resp = requests.get(url)
    if resp.ok:
        trades = [t for t in resp.json() if t.get("type") == "trade"]
        return trades
    return []

trades = fetch_trades(league_id)
if not trades:
    st.info("No trades found for this league.")
    st.stop()

# ------------------------
# Fetch FantasyCalc player values (re-draft)
# ------------------------
def fetch_trade_values():
    url = "https://api.fantasycalc.com/values/current?isDynasty=false&numQbs=1&numTeams=12&ppr=1"
    resp = requests.get(url)
    if resp.ok:
        return {p['player']: p['value'] for p in resp.json()}
    return {}

trade_values = fetch_trade_values()
if not trade_values:
    st.warning("Failed to fetch FantasyCalc values, grades may be inaccurate.")

# ------------------------
# Grade trades A-F
# ------------------------
def grade_trade(value_diff):
    if value_diff > 20:
        return "A"
    elif value_diff > 10:
        return "B"
    elif value_diff > 0:
        return "C"
    elif value_diff > -10:
        return "D"
    else:
        return "F"

# ------------------------
# Evaluate trades and replace player IDs with names
# ------------------------
trade_data = []

for trade in trades:
    adds = trade.get("adds", {})
    drops = trade.get("drops", {})

    # Flatten player IDs for each side
    team1_players = [player_map.get(pid, str(pid)) for sublist in adds.values() for pid in sublist]
    team2_players = [player_map.get(pid, str(pid)) for sublist in drops.values() for pid in sublist]

    # Sum FantasyCalc values
    t1_value = sum([trade_values.get(name, 0) for name in team1_players])
    t2_value = sum([trade_values.get(name, 0) for name in team2_players])

    grade = grade_trade(t1_value - t2_value)

    trade_data.append({
        "Team 1 Players": ", ".join(team1_players),
        "Team 2 Players": ", ".join(team2_players),
        "Team 1 Value": t1_value,
        "Team 2 Value": t2_value,
        "Grade": grade
    })

df = pd.DataFrame(trade_data)
st.subheader("Trades and Grades")
st.dataframe(df, use_container_width=True)

# ------------------------
# Plot stacked bar chart for each trade
# ------------------------
st.subheader("Trade Value Comparison")
for i, row in df.iterrows():
    fig, ax = plt.subplots(figsize=(6,2))
    ax.barh([f"Team 1: {row['Team 1 Players']}"], row["Team 1 Value"], color='skyblue', label="Team 1")
    ax.barh([f"Team 2: {row['Team 2 Players']}"], row["Team 2 Value"], color='salmon', label="Team 2")
    ax.set_xlabel("Fantasy Value")
    ax.set_title(f"Trade {i+1} - Grade: {row['Grade']}")
    ax.legend()
    st.pyplot(fig)
