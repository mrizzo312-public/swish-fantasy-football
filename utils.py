import requests
import pandas as pd

# -------------------------
# League / Draft Functions
# -------------------------

def get_league_data(league_id):
    """Fetch league metadata, scoring settings, and roster->owner mapping"""
    league = requests.get(f"https://api.sleeper.app/v1/league/{league_id}").json()
    users = requests.get(f"https://api.sleeper.app/v1/league/{league_id}/users").json()
    rosters = requests.get(f"https://api.sleeper.app/v1/league/{league_id}/rosters").json()

    user_map = {u["user_id"]: u["display_name"] for u in users}
    roster_to_owner = {r["roster_id"]: user_map.get(r["owner_id"], "Unknown") for r in rosters}

    scoring = league.get("scoring_settings", {})
    return league, scoring, roster_to_owner


def get_draft(league_id):
    """Fetch draft ID and picks"""
    drafts = requests.get(f"https://api.sleeper.app/v1/league/{league_id}/drafts").json()
    if not drafts:
        return None, []
    draft_id = drafts[0]["draft_id"]
    picks = requests.get(f"https://api.sleeper.app/v1/draft/{draft_id}/picks").json()
    return draft_id, picks


def get_standings(league_id, week=None):
    """Fetch standings (Owner, Wins, Losses, PF)"""
    try:
        users = requests.get(f"https://api.sleeper.app/v1/league/{league_id}/users").json()
        rosters = requests.get(f"https://api.sleeper.app/v1/league/{league_id}/rosters").json()

        user_map = {u["user_id"]: u["display_name"] for u in users}

        rows = []
        for r in rosters:
            owner = user_map.get(r.get("owner_id"), "Unknown")
            wins = r.get("settings", {}).get("wins", 0)
            losses = r.get("settings", {}).get("losses", 0)
            pf = r.get("settings", {}).get("fpts", 0)
            rows.append({"Owner": owner, "Wins": wins, "Losses": losses, "PF": pf})
        return pd.DataFrame(rows)
    except Exception as e:
        print(f"Error fetching standings: {e}")
        return pd.DataFrame()


def get_draft_grades(league_id):
    """Calculate draft grades using z-scores"""
    league, scoring, roster_to_owner = get_league_data(league_id)
    draft_id, picks = get_draft(league_id)

    if not draft_id:
        return pd.DataFrame()

    df = pd.DataFrame(picks)
    df["Owner"] = df["roster_id"].map(roster_to_owner)

    # Example metric: ADP value
    df["value_score"] = df["metadata"].apply(
        lambda m: float(m.get("overall", 999)) if isinstance(m, dict) else 999
    )

    roster_scores = df.groupby("Owner")["value_score"].mean().reset_index()

    # Z-score scaling
    roster_scores["Draft Score"] = (
        (roster_scores["value_score"].mean() - roster_scores["value_score"])
        / roster_scores["value_score"].std(ddof=0)
    ) * 10 + 50

    return roster_scores[["Owner", "Draft Score"]]
