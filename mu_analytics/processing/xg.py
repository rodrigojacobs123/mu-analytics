"""xG extraction, timelines, and season aggregation."""

import pandas as pd
import numpy as np
import streamlit as st
from data.event_parser import extract_shots, extract_goals
from data.loader import load_match_events, load_match_raw
from data.event_parser import parse_match_info


def compute_match_xg(events: list[dict], team_id: str) -> float:
    """Sum xG for all shots by a team in a match."""
    shots = extract_shots(events, team_id)
    return shots["xg"].sum() if not shots.empty else 0.0


def compute_xg_timeline(events: list[dict], home_id: str, away_id: str) -> pd.DataFrame:
    """Build cumulative xG by minute for both teams.

    Returns DataFrame: minute, home_xg, away_xg (cumulative).
    """
    shots = extract_shots(events)
    if shots.empty:
        return pd.DataFrame({"minute": [0, 90], "home_xg": [0, 0], "away_xg": [0, 0]})

    # Build minute-by-minute cumulative xG
    max_min = max(90, int(shots["minute"].max()) + 1)
    timeline = []
    home_cum = 0.0
    away_cum = 0.0

    for m in range(0, max_min + 1):
        min_shots = shots[shots["minute"] == m]
        home_cum += min_shots[min_shots["team_id"] == home_id]["xg"].sum()
        away_cum += min_shots[min_shots["team_id"] == away_id]["xg"].sum()
        timeline.append({"minute": m, "home_xg": round(home_cum, 2), "away_xg": round(away_cum, 2)})

    df = pd.DataFrame(timeline)
    df.attrs["home_id"] = home_id
    df.attrs["away_id"] = away_id
    return df


def compute_shot_map_data(events: list[dict], team_id: str | None = None) -> pd.DataFrame:
    """Extract all shots with x, y, xG, player, outcome, body_part."""
    return extract_shots(events, team_id)


@st.cache_data(ttl=3600)
def compute_mu_season_xg(league: str, season: str, mu_team_id: str) -> pd.DataFrame:
    """Compute xG for all Manchester United matches in a season.

    Iterates through MU match files, extracting shot data.
    Returns DataFrame: matchday, date, opponent, is_home, mu_xg, opp_xg, mu_goals, opp_goals.
    """
    from data.loader import load_mu_match_list, load_match_raw
    from data.event_parser import parse_match_info

    matches = load_mu_match_list(league, season)
    if matches.empty:
        return pd.DataFrame()

    rows = []
    for _, match in matches.iterrows():
        match_id = match.get("match_id", "")
        if not match_id:
            continue

        raw = load_match_raw(league, season, match_id)
        if not raw:
            continue

        info = parse_match_info(raw)
        events = raw.get("liveData", {}).get("event", [])
        if not events:
            continue

        home_id = info["home_id"]
        away_id = info["away_id"]
        is_home = home_id == mu_team_id
        opp_id = away_id if is_home else home_id

        mu_xg = compute_match_xg(events, mu_team_id)
        opp_xg = compute_match_xg(events, opp_id)

        rows.append({
            "matchday": info["matchday"],
            "date": info["date"],
            "opponent": info["away_team"] if is_home else info["home_team"],
            "is_home": is_home,
            "mu_xg": round(mu_xg, 2),
            "opp_xg": round(opp_xg, 2),
            "mu_goals": match["mu_score"],
            "opp_goals": match["opp_score"],
        })

    return pd.DataFrame(rows)
