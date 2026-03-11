"""Elo rating computation from historical match results (2008–2025).

Enhanced with cross-competition Elo lookup for UEFA competitions —
when a UCL/UEL team has no Elo history, falls back to their domestic
league rating where they have 100+ matches of history.
"""

import pandas as pd
import streamlit as st
from config import (
    ELO_INITIAL, ELO_K_FACTOR, ELO_HOME_ADVANTAGE, DEFAULT_LEAGUE,
    COMPETITIONS,
)
from data.loader import load_all_season_results, load_standings
from data.paths import list_seasons
from processing.poisson import _team_name_aliases, _resolve_team_in_results


def _expected_score(elo_a: float, elo_b: float) -> float:
    return 1.0 / (1.0 + 10 ** ((elo_b - elo_a) / 400))


@st.cache_data(ttl=7200)
def compute_elo_history(league: str = DEFAULT_LEAGUE,
                        seasons: list[str] | None = None) -> dict[str, list[tuple[str, float]]]:
    """Compute Elo rating history for all teams across multiple seasons.

    Returns {team_name: [(date_str, elo), ...]}.
    """
    if seasons is None:
        seasons = sorted(list_seasons(league))  # oldest first

    elo = {}  # team_name -> current rating
    history = {}  # team_name -> [(date, rating)]

    for season in seasons:
        results = load_all_season_results(league, season)
        if results.empty:
            continue

        for _, row in results.iterrows():
            home = row["home_team"]
            away = row["away_team"]
            date_str = str(row["date"])[:10]

            # Initialize new teams
            for team in (home, away):
                if team not in elo:
                    elo[team] = ELO_INITIAL
                    history[team] = [(date_str, ELO_INITIAL)]

            # Calculate expected scores with home advantage
            exp_home = _expected_score(elo[home] + ELO_HOME_ADVANTAGE, elo[away])
            exp_away = 1.0 - exp_home

            # Actual results
            hs, as_ = row["home_score"], row["away_score"]
            if hs > as_:
                actual_home, actual_away = 1.0, 0.0
            elif hs == as_:
                actual_home, actual_away = 0.5, 0.5
            else:
                actual_home, actual_away = 0.0, 1.0

            # Update ratings
            elo[home] += ELO_K_FACTOR * (actual_home - exp_home)
            elo[away] += ELO_K_FACTOR * (actual_away - exp_away)

            history[home].append((date_str, round(elo[home], 1)))
            history[away].append((date_str, round(elo[away], 1)))

    return history


def get_current_elo(elo_history: dict[str, list], team: str) -> float:
    """Return the latest Elo rating for a team.

    Tries exact name first, then common aliases (e.g., with/without "FC").
    """
    if team in elo_history and elo_history[team]:
        return elo_history[team][-1][1]

    # Try aliases: "Manchester United FC" → "Manchester United", etc.
    for alias in _team_name_aliases(team):
        if alias in elo_history and elo_history[alias]:
            return elo_history[alias][-1][1]

    return ELO_INITIAL


@st.cache_data(ttl=7200)
def get_cross_league_elo(team_name: str, team_id: str | None,
                         current_league: str, season: str) -> float:
    """Get the best available Elo rating for a team, searching across leagues.

    For UEFA competitions (UCL, UEL, UECL), teams often have sparse Elo
    history (5-13 matches). This function finds the team's domestic league
    and uses their full domestic Elo (built from 100+ matches over seasons).

    Strategy:
        1. For domestic leagues: use current league Elo directly
        2. For UEFA: always prefer domestic Elo (more reliable from 100+
           matches vs 5-13 in UEFA), fall back to UEFA Elo if no domestic found

    Returns the team's best available Elo rating.
    """
    is_uefa = current_league.startswith("UEFA")

    # 1. Try current league
    all_seasons = sorted(list_seasons(current_league))
    elo_history = compute_elo_history(current_league, all_seasons)
    current_elo = get_current_elo(elo_history, team_name)

    # For domestic leagues, current Elo is best (built from many seasons)
    if not is_uefa and current_elo != ELO_INITIAL:
        return current_elo

    # 2. Search domestic leagues for this team's Elo
    if not team_id:
        return current_elo

    domestic_leagues = [k for k in COMPETITIONS if not k.startswith("UEFA")]

    for dom_league in domestic_leagues:
        try:
            # Try recent seasons (newest first, max 3) — standings data quality
            # can vary by season (e.g. wrong division loaded for some years)
            dom_all_seasons = sorted(list_seasons(dom_league), reverse=True)
            found_standings = None
            found_season = None
            for s in dom_all_seasons[:3]:  # Only check 3 most recent seasons
                dom_standings = load_standings(dom_league, s)
                if dom_standings.empty or "team_id" not in dom_standings.columns:
                    continue
                if team_id in dom_standings["team_id"].values:
                    found_standings = dom_standings
                    found_season = s
                    break

            if found_standings is None:
                continue

            # Found the team's domestic league — compute their Elo there
            dom_elo_history = compute_elo_history(dom_league, sorted(dom_all_seasons))

            # Get the team name as used in the domestic league standings
            dom_row = found_standings[found_standings["team_id"] == team_id].iloc[0]
            dom_team_name = dom_row["team_name"]

            # Resolve standings name → results name (Elo is built from results)
            # e.g. "FC Internazionale Milano" → "Internazionale"
            dom_results = load_all_season_results(dom_league, found_season)
            resolved_name = _resolve_team_in_results(
                dom_results, dom_team_name, team_id
            )

            dom_elo = get_current_elo(dom_elo_history, resolved_name)
            if dom_elo != ELO_INITIAL:
                return dom_elo
        except Exception:
            continue

    return current_elo


def get_elo_dataframe(elo_history: dict[str, list], teams: list[str] | None = None) -> pd.DataFrame:
    """Convert Elo history to a DataFrame suitable for plotting.

    Returns DataFrame with columns: date, team, elo.
    """
    rows = []
    for team, entries in elo_history.items():
        if teams and team not in teams:
            continue
        for date_str, rating in entries:
            rows.append({"date": date_str, "team": team, "elo": rating})

    df = pd.DataFrame(rows)
    if not df.empty:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df = df.sort_values("date")
    return df
