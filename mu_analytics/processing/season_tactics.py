"""Season-level tactical aggregation — per-match KPIs over a full season."""

import json
import pandas as pd
import streamlit as st
from data.paths import partidos_dir, team_jsons_dir
from data.event_parser import parse_match_info, extract_passes, extract_corners, extract_shots
from processing.formations import compute_tactical_kpis, get_match_formations
from processing.set_pieces import compute_set_piece_stats


@st.cache_data(ttl=3600, show_spinner="Loading season tactical data...")
def compute_season_tactical_progression(
    league: str, season: str, team_id: str,
) -> pd.DataFrame:
    """Scan all matches for a team and compute per-match tactical KPIs.

    This is the "deep tier" — loads individual match JSONs from partidos/.
    Cached aggressively since historical data never changes.

    Returns DataFrame with columns:
        matchday, date, opponent, venue (H/A), result (W/D/L),
        score, formation, possession, ppda, field_tilt,
        pass_accuracy, total_passes, progressive_passes,
        high_press_recoveries, defensive_line_height,
        corners_won, fouls_won, sp_shots, sp_goals
    """
    pdir = partidos_dir(league, season)
    if not pdir.exists():
        return pd.DataFrame()

    rows = []
    match_num = 0

    for fpath in sorted(pdir.iterdir()):
        if fpath.suffix != ".json":
            continue
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                raw = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue

        info = parse_match_info(raw)
        home_id = info["home_id"]
        away_id = info["away_id"]

        # Skip matches where this team didn't play
        if team_id not in (home_id, away_id):
            continue

        match_num += 1
        is_home = team_id == home_id
        opponent_id = away_id if is_home else home_id
        events = raw.get("liveData", {}).get("event", [])

        # Result
        my_goals = info["home_score"] if is_home else info["away_score"]
        opp_goals = info["away_score"] if is_home else info["home_score"]
        if my_goals > opp_goals:
            result = "W"
        elif my_goals == opp_goals:
            result = "D"
        else:
            result = "L"

        # Tactical KPIs (full match)
        kpis = compute_tactical_kpis(events, team_id, opponent_id)

        # Formation
        formations = get_match_formations(events, home_id, away_id)
        my_formation = formations["home"] if is_home else formations["away"]
        formation_str = my_formation.get("formation_str", "?") if my_formation else "?"

        # Set pieces
        sp = compute_set_piece_stats(events, home_id, away_id)
        sp_side = sp["home"] if is_home else sp["away"]

        rows.append({
            "match_num": match_num,
            "matchday": info.get("matchday", match_num),
            "date": info.get("date", ""),
            "opponent": info["away_team"] if is_home else info["home_team"],
            "venue": "H" if is_home else "A",
            "result": result,
            "score": f"{my_goals}-{opp_goals}",
            "formation": formation_str,
            "possession": kpis["possession_pct"],
            "ppda": kpis["ppda"],
            "field_tilt": kpis["field_tilt"],
            "pass_accuracy": kpis["pass_accuracy"],
            "total_passes": kpis["total_passes"],
            "progressive_passes": kpis["progressive_passes"],
            "high_press_recoveries": kpis["high_press_recoveries"],
            "defensive_line_height": kpis["defensive_line_height"],
            "corners_won": sp_side["corners_won"],
            "fouls_won": sp_side["fouls_won"],
            "sp_shots": sp_side["set_piece_shots"],
            "sp_goals": sp_side["set_piece_goals"],
            "goals_for": my_goals,
            "goals_against": opp_goals,
        })

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    # Sort by matchday/match_num
    df = df.sort_values("match_num").reset_index(drop=True)
    return df


def load_team_season_agg(league: str, season: str, team_folder: str) -> dict:
    """Load seasonstats.json and return a clean dict of tactical KPIs.

    This is the "fast tier" — uses pre-aggregated season stats, no match loading.
    Returns dict with normalized keys for easy display.
    """
    path = team_jsons_dir(league, season, team_folder) / "seasonstats.json"
    if not path.exists():
        return {}

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}

    # Stats can be at top level or nested under 'contestant'
    stat_list = data.get("stat", [])
    if not stat_list and isinstance(data, dict):
        contestant = data.get("contestant", {})
        if isinstance(contestant, dict):
            stat_list = contestant.get("stat", [])

    raw = {}
    for s in stat_list:
        if isinstance(s, dict):
            # Handle both "type"/"value" and "name"/"value" formats
            key = s.get("type", s.get("name", ""))
            val = s.get("value", 0)
            try:
                raw[key] = float(val)
            except (ValueError, TypeError):
                raw[key] = 0

    games = raw.get("Games Played", raw.get("gamesPlayed", 38)) or 38

    return {
        "games_played": int(games),
        # Shooting
        "goals": raw.get("Goals", raw.get("goals", 0)),
        "goals_per_match": round(raw.get("Goals", raw.get("goals", 0)) / games, 2),
        "total_shots": raw.get("Total Shots", raw.get("totalScoringAtt", 0)),
        "shots_per_match": round(raw.get("Total Shots", raw.get("totalScoringAtt", 0)) / games, 1),
        "shooting_accuracy": round(raw.get("Shooting Accuracy", raw.get("shotAccuracy", 0)), 1),
        "shots_on_target": raw.get("Shots On Target (inc goals)", raw.get("ontargetScoringAtt", 0)),
        "big_chances_created": raw.get("Big Chances Created", 0),
        "big_chances_missed": raw.get("Big Chances Missed", 0),
        # Passing
        "pass_accuracy": round(raw.get("Passing Accuracy", raw.get("accuratePassPercentage", 0)), 1),
        "total_passes": raw.get("Total Passes", raw.get("totalPass", 0)),
        "key_passes": raw.get("Key Passes", 0),
        "successful_crosses": raw.get("Successful Crosses Open Play", 0),
        "crossing_accuracy": round(raw.get("Crossing Accuracy", 0), 1),
        "successful_long_passes": raw.get("Successful Long Passes", 0),
        "successful_short_passes": raw.get("Successful Short Passes", 0),
        # Possession
        "possession_pct": raw.get("Possession Percentage", raw.get("possessionPercentage", 50)),
        "successful_dribbles": raw.get("Successful Dribbles", 0),
        "total_losses": raw.get("Total Losses Of Possession", 0),
        "recoveries": raw.get("Recoveries", 0),
        # Defending
        "clean_sheets": raw.get("Clean Sheets", raw.get("cleanSheet", 0)),
        "goals_conceded": raw.get("Goals Conceded", raw.get("goalsConceded", 0)),
        "tackles_won": raw.get("Tackles Won", raw.get("wonTackle", 0)),
        "tackle_success": round(raw.get("Tackle Success %", raw.get("tackleSuccessRate", 0)), 1),
        "interceptions": raw.get("Interceptions", raw.get("interception", 0)),
        "total_clearances": raw.get("Total Clearances", 0),
        "blocks": raw.get("Blocks", 0),
        "aerial_duels_won": raw.get("Aerial Duels Won", raw.get("aerialWon", 0)),
        "aerial_duels_total": raw.get("Aerial Duels", 0),
        # Set pieces
        "corners_taken": raw.get("Corners Taken", 0),
        "corners_accurate": raw.get("Successful Corners into Box", 0),
        "set_piece_goals": raw.get("Set Pieces Goals", 0),
        "penalty_goals": raw.get("Penalty Goals", 0),
        "penalties_taken": raw.get("Penalties Taken", 0),
        # Discipline
        "yellow_cards": raw.get("Yellow Cards", 0),
        "red_cards": raw.get("Total Red Cards", 0),
        "fouls_committed": raw.get("Fouls Committed", raw.get("foulCommit", 0)),
        "fouls_won": raw.get("Total Fouls Won", 0),
    }


def compute_rolling_averages(df: pd.DataFrame, columns: list[str],
                              window: int = 5) -> pd.DataFrame:
    """Add rolling average columns for specified metrics.

    Adds columns named '{col}_rolling' for each column in the list.
    Uses min_periods=1 so early matches still show values.
    """
    result = df.copy()
    for col in columns:
        if col in result.columns:
            result[f"{col}_rolling"] = (
                result[col].rolling(window=window, min_periods=1).mean().round(1)
            )
    return result
