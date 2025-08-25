import requests
import pandas as pd
import numpy as np
from datetime import datetime, timezone
import streamlit as st
import sys, os
from zoneinfo import ZoneInfo

# -------------------------
# League / Draft Functions
# -------------------------

def get_league_data(league_id: str):
    """Fetch league metadata (name, scoring, users, rosters)."""
    league = requests.get(f"https://api.sleeper.app/v1/league/{league_id}").json()
    users = requests.get(f"https://api.sleeper.app/v1/league/{league_id}/users").json()
    rosters = requests.get(f"https://api.sleeper.app/v1/league/{league_id}/rosters").json()

    roster_to_owner = {}
    for roster in rosters:
        roster_id = roster["roster_id"]
        owner_id = roster.get("owner_id")
        user = next((u for u in users if u["user_id"] == owner_id), None)
        roster_to_owner[roster_id] = user.get("display_name", f"Team {roster_id}") if user else f"Team {roster_id}"

    return league, league.get("scoring_settings", {}), roster_to_owner


def get_draft(league_id: str):
    """Fetch draft ID, picks, and draft time."""
    try:
        drafts = requests.get(f"https://api.sleeper.app/v1/league/{league_id}/drafts").json()
        if not drafts:
            return None, [], None
        draft = drafts[0]
        draft_id = draft.get("draft_id")
        draft_time = None
        start_ms = draft.get("start_time")
        st.markdown(start_ms)
        if start_ms:
            draft_time = datetime.fromtimestamp(start_ms / 1000, tz=timezone.utc)
            st.markdown(draft_time)
            draft_time = draft_time.astimezone(ZoneInfo("America/Los_Angeles"))
            st.markdown(draft_time)
        picks = requests.get(f"https://api.sleeper.app/v1/draft/{draft_id}/picks").json() if draft_id else []
        return draft_id, picks, draft_time
    except Exception as e:
        print(f"Error fetching draft for league {league_id}: {e}")
        return None, [], None


def get_standings(league_id: str, week=None):
    """Fetch standings (Owner, Wins, Losses, PF)."""
    try:
        users = requests.get(f"https://api.sleeper.app/v1/league/{league_id}/users").json()
        rosters = requests.get(f"https://api.sleeper.app/v1/league/{league_id}/rosters").json()
        user_map = {u["user_id"]: u["display_name"] for u in users}

        rows = []
        for r in rosters:
            owner = user_map.get(r.get("owner_id"), f"Team {r['roster_id']}")
            settings = r.get("settings", {})
            rows.append({"Owner": owner, "Wins": settings.get("wins", 0),
                         "Losses": settings.get("losses", 0), "PF": settings.get("fpts", 0)})
        return pd.DataFrame(rows)
    except Exception as e:
        print(f"Error fetching standings: {e}")
        return pd.DataFrame()


# -------------------------
# Draft Grades / Projections
# -------------------------

def fetch_fp_projections(position: str) -> pd.DataFrame:
    """Fetch FantasyPros seasonal projections using html5lib."""
    url = f"https://www.fantasypros.com/nfl/projections/{position}.php?week=draft"
    r = requests.get(url)
    r.raise_for_status()
    tables = pd.read_html(r.text, flavor='html5lib')
    if not tables:
        st.warning(f"No tables found for {position.upper()} projections.")
        return pd.DataFrame()
    df = tables[0]
    df['Position'] = position.upper()
    return df


def get_all_projections() -> pd.DataFrame:
    dfs = []
    for pos in ['qb', 'rb', 'wr', 'te']:
        try:
            df = fetch_fp_projections(pos)
            if not df.empty:
                dfs.append(df)
        except Exception as e:
            st.error(f"Error fetching {pos.upper()} projections: {e}")
    return pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()


def calculate_dynamic_vorp(proj_df: pd.DataFrame):
    """Calculate VORP based on replacement-level players."""
    replacement_targets = {'QB': 13, 'RB': 25, 'WR': 37, 'TE': 13}
    vorp = {}
    for pos, group in proj_df.groupby('Position'):
        group_sorted = group.sort_values('FPTS', ascending=False).reset_index(drop=True)
        cutoff_idx = min(replacement_targets.get(pos, len(group_sorted)) - 1, len(group_sorted) - 1)
        replacement_value = group_sorted.loc[cutoff_idx, 'FPTS']
        for _, row in group_sorted.iterrows():
            vorp[row['Player']] = row['FPTS'] - replacement_value
    return vorp


def assign_grades(team_scores: dict):
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


def split_player_team(proj_df: pd.DataFrame):
    """Split 'Player' into name and team, handling Jr./III etc."""
    def parse_name_team(s):
        tokens = s.strip().split()
        if len(tokens) < 2:
            return pd.Series([s, None])
        team = tokens[-1].upper()
        name = ' '.join(tokens[:-1])
        return pd.Series([name, team])
    proj_df[['Player', 'Team']] = proj_df['Player'].apply(parse_name_team)
    return proj_df


def get_league_names(league_ids: dict):
    """Fetch names for all league IDs."""
    for lid in league_ids.keys():
        try:
            data = requests.get(f"https://api.sleeper.app/v1/league/{lid}").json()
            league_ids[lid] = data.get("name", f"League {lid}")
        except:
            league_ids[lid] = f"League {lid}"
    return league_ids


def get_draft_grades(league_id: str) -> pd.DataFrame:
    """
    Returns a DataFrame with draft scores per team:
    Columns: ['Owner', 'Draft Score']
    """
    # Fetch league + roster info
    league, scoring, roster_to_owner = get_league_data(league_id)
    draft_id, picks, draft_time = get_draft(league_id)
    if not picks:
        return pd.DataFrame()

    # Get projections
    proj_df = get_all_projections()
    if proj_df.empty:
        return pd.DataFrame()

    # Flatten multi-level columns if needed
    if isinstance(proj_df.columns, pd.MultiIndex):
        proj_df.columns = ['_'.join(filter(None, col)).strip() for col in proj_df.columns.values]

    proj_df = proj_df.rename(columns={'MISC_FPTS': 'FPTS','Unnamed: 0_level_0_Player':'Player'})
    proj_df = split_player_team(proj_df)
    proj_df = proj_df[['Player', 'FPTS', 'Position']].dropna(subset=['FPTS'])
    proj_df['FPTS'] = proj_df['FPTS'].astype(float)

    vorp = calculate_dynamic_vorp(proj_df)

    # Tally team draft scores
    team_scores = {}
    for pick in picks:
        player_name = pick.get("metadata", {}).get("first_name", "") + " " + pick.get("metadata", {}).get("last_name", "")
        roster_id = pick["roster_id"]
        value = vorp.get(player_name, 0)
        team_scores[roster_id] = team_scores.get(roster_id, 0) + value

    # Build DataFrame
    results = []
    for roster_id, score in team_scores.items():
        owner_name = roster_to_owner.get(roster_id, f"Team {roster_id}")
        results.append({"Owner": owner_name, "Draft Score": score})

    df = pd.DataFrame(results)
    return df

# ------------------------
# Player metadata helper
# ------------------------
def get_player_map(csv_path="player_ids.csv") -> dict:
    """
    Returns a dictionary mapping Sleeper player_id -> player_name.
    Saves locally to CSV to avoid repeated API calls.
    """
    if os.path.exists(csv_path):
        player_df = pd.read_csv(csv_path)
    else:
        try:
            resp = requests.get("https://api.sleeper.app/v1/players/nfl")
            resp.raise_for_status()
            data = resp.json()
            player_df = pd.DataFrame.from_dict(data, orient="index")
            player_df = player_df[['full_name']]
            player_df.reset_index(inplace=True)
            player_df.rename(columns={"index":"player_id", "full_name":"player_name"}, inplace=True)
            player_df.to_csv(csv_path, index=False)
        except Exception as e:
            st.error(f"Failed to fetch player metadata: {e}")
            return {}

    return dict(zip(player_df["player_id"], player_df["player_name"]))

