import streamlit as st
import requests
from datetime import datetime

st.title("💯 Draft Grades")
st.set_page_config(page_title="Draft Grades", page_icon="💯", layout="wide")

# League IDs
league_ids = [
    "1264083534415396864",
    "1264093436445741056",
    "1264093787064377344",
    "1264094054845513728",
]

# Fetch league names
league_names = []
league_info_map = {}
for lid in league_ids:
    try:
        res = requests.get(f"https://api.sleeper.app/v1/league/{lid}")
        data = res.json()
        league_names.append(data["name"])
        league_info_map[data["name"]] = data
    except Exception as e:
        league_names.append(f"League {lid} (Error fetching)")
        league_info_map[f"League {lid} (Error fetching)"] = {"league_id": lid}

# Sidebar league selector
selected_league_name = st.sidebar.selectbox("Select a League:", league_names)
selected_league = league_info_map[selected_league_name]
league_id = selected_league["league_id"]

# Fetch draft data
try:
    draft_res = requests.get(f"https://api.sleeper.app/v1/league/{league_id}/drafts")
    draft_data = draft_res.json()
    
    if not draft_data:
        st.warning("No draft has been scheduled for this league yet.")
    else:
        draft = draft_data[0]  # Take first draft
        if draft["status"] != "complete":
            # Draft not yet occurred
            draft_time = draft.get("drafted_at", draft.get("start_time", None))
            if draft_time:
                draft_dt = datetime.fromtimestamp(draft_time)
                st.info(f"Draft has not yet occurred. Scheduled time: {draft_dt.strftime('%Y-%m-%d %H:%M:%S')}")
            else:
                st.info("Draft has not yet occurred and time is not available.")
        else:
            # Draft complete — analyze picks
            rosters_res = requests.get(f"https://api.sleeper.app/v1/league/{league_id}/rosters")
            users_res = requests.get(f"https://api.sleeper.app/v1/league/{league_id}/users")
            rosters = rosters_res.json()
            users = users_res.json()
            user_map = {user["user_id"]: user["display_name"] for user in users}

            picks = draft.get("draft_picks", [])

            # Simple scoring: earlier pick of top-ranked player = better
            # We'll give a mock letter grade based on points scored by roster in draft order
            # (can refine with position weighting later)
            roster_scores = {r["roster_id"]: 0 for r in rosters}
            roster_picks = {r["roster_id"]: [] for r in rosters}

            for pick in picks:
                roster_id = pick["roster_id"]
                # Use pick slot as mock score (lower pick number = better)
                roster_scores[roster_id] += 1 / pick["draft_slot"]
                roster_picks[roster_id].append(pick)

            # Rank rosters by score
            ranked_rosters = sorted(roster_scores.items(), key=lambda x: x[1], reverse=True)

            st.subheader(f"Draft Grades - {selected_league_name}")
            for idx, (roster_id, score) in enumerate(ranked_rosters, start=1):
                # Letter grade: simple heuristic
                if idx == 1:
                    grade = "A+"
                elif idx == len(ranked_rosters):
                    grade = "D"
                else:
                    grade = ["A", "B+", "B", "C+", "C", "C-"][min(idx-1,5)]

                roster_name = user_map.get(roster_id, f"Team {roster_id}")
                st.markdown(f"**{idx}. {roster_name} — Grade: {grade}**")
                
                # Best and worst pick
                picks_sorted = sorted(roster_picks[roster_id], key=lambda x: x["draft_slot"])
                if picks_sorted:
                    best_pick = picks_sorted[0]["player_id"]
                    worst_pick = picks_sorted[-1]["player_id"]
                    st.write(f"Best pick: {best_pick}, Worst pick: {worst_pick}")
except Exception as e:
    st.error(f"Error fetching draft data: {e}")
