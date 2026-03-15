"""Aggregated team stat computation for radar charts and comparisons."""

import unicodedata
import pandas as pd
import streamlit as st
from data.loader import load_team_season_stats, load_standings, load_all_season_results
from data.paths import list_team_folders
from config import MU_TEAM_FOLDER


def _nfc(text: str) -> str:
    """Normalize to NFC — fixes macOS NFD filesystem encoding."""
    return unicodedata.normalize("NFC", text)


RADAR_CATEGORIES = [
    "Goals/Match", "Possession", "Pass Accuracy", "Shots/Match",
    "Tackles/Match", "Interceptions/Match", "Aerial Won/Match", "Clean Sheets"
]


@st.cache_data(ttl=3600)
def compute_team_radar_data(league: str, season: str,
                            team_folders: list[str] | None = None) -> dict[str, list[float]]:
    """Compute normalized radar data for teams.

    Returns {team_name: [value_per_category]} normalized to 0-100 scale.
    """
    if team_folders is None:
        team_folders = list_team_folders(league, season)

    raw_stats = {}
    for folder in team_folders:
        stats = load_team_season_stats(league, season, folder)
        if not stats:
            continue

        team_name = _nfc(folder.replace("_", " "))

        # Extract stats — handle two possible JSON structures:
        # Format A (legacy): {"stat": [{"type": "goals", "value": 50}]}
        # Format B (Opta):   {"contestant": {"stat": [{"name": "Goals", "value": "44"}]}}
        stat_dict = {}

        contestant = stats.get("contestant", {}) if isinstance(stats, dict) else {}
        stat_list = contestant.get("stat", []) if isinstance(contestant, dict) else []

        if stat_list:
            # Format B: name/value pairs with human-readable names
            for s in stat_list:
                if isinstance(s, dict) and "name" in s:
                    stat_dict[s["name"]] = float(s.get("value", 0))
        else:
            # Format A: type/value pairs with camelCase names
            stat_list_a = stats.get("stat", []) if isinstance(stats, dict) else []
            for s in stat_list_a:
                if isinstance(s, dict) and "type" in s:
                    stat_dict[s["type"]] = float(s.get("value", 0))

        # Resolve games played from either format
        games = (stat_dict.get("Games Played")        # Format B
                 or stat_dict.get("gamesPlayed")       # Format A
                 or 38)
        games = max(games, 1)

        raw_stats[team_name] = {
            "Goals/Match": (stat_dict.get("Goals", 0) or stat_dict.get("goals", 0)) / games,
            "Possession": stat_dict.get("Possession Percentage", 0) or stat_dict.get("possessionPercentage", 50),
            "Pass Accuracy": stat_dict.get("Passing Accuracy", 0) or stat_dict.get("accuratePassPercentage", 0),
            "Shots/Match": (stat_dict.get("Total Shots", 0) or stat_dict.get("totalScoringAtt", 0)) / games,
            "Tackles/Match": (stat_dict.get("Tackles Won", 0) or stat_dict.get("wonTackle", 0)) / games,
            "Interceptions/Match": (stat_dict.get("Interceptions", 0) or stat_dict.get("interception", 0)) / games,
            "Aerial Won/Match": (stat_dict.get("Aerial Duels won", 0) or stat_dict.get("aerialWon", 0)) / games,
            "Clean Sheets": stat_dict.get("Clean Sheets", 0) or stat_dict.get("cleanSheet", 0),
        }

    if not raw_stats:
        return {}

    # Normalize each category to 0-100 across all teams
    all_teams = list(raw_stats.keys())
    normalized = {t: [] for t in all_teams}

    for cat in RADAR_CATEGORIES:
        values = [raw_stats[t].get(cat, 0) for t in all_teams]
        max_val = max(values) if max(values) > 0 else 1
        min_val = min(values)
        range_val = max_val - min_val if max_val != min_val else 1

        for t in all_teams:
            norm = ((raw_stats[t].get(cat, 0) - min_val) / range_val) * 100
            normalized[t].append(round(norm, 1))

    return normalized


def get_team_folder_map(league: str, season: str) -> dict[str, str]:
    """Map team display names to folder names.

    Applies NFC normalization so macOS NFD folder names match NFC data names.
    """
    folders = list_team_folders(league, season)
    return {_nfc(f.replace("_", " ")): f for f in folders}


@st.cache_data(ttl=3600)
def build_team_name_lookup(league: str, season: str) -> dict[str, str]:
    """Map standings team names → folder names via fuzzy substring matching.

    Handles cases where standings use 'Manchester United' but folder is
    'Manchester_United_FC', or accented characters differ.
    """
    standings = load_standings(league, season)
    folder_map = get_team_folder_map(league, season)

    # Direct match first
    lookup: dict[str, str] = {}
    unmatched_names: list[str] = []
    for _, row in standings.iterrows():
        sname = row["team_name"]
        if sname in folder_map:
            lookup[sname] = folder_map[sname]
        else:
            unmatched_names.append(sname)

    # Fuzzy: try substring containment for remaining
    if unmatched_names:
        remaining_folders = {k: v for k, v in folder_map.items() if v not in lookup.values()}
        for sname in unmatched_names:
            s_clean = sname.lower().replace(" fc", "").replace(" cf", "").strip()
            for f_display, f_folder in remaining_folders.items():
                f_clean = f_display.lower().replace(" fc", "").replace(" cf", "").strip()
                if s_clean in f_clean or f_clean in s_clean:
                    lookup[sname] = f_folder
                    break

    return lookup


@st.cache_data(ttl=3600)
def compute_standings_from_results(league: str, season: str) -> pd.DataFrame:
    """Build a full league table from match results.

    Used when the static standings.json is stale (fewer matches than
    what the event data contains).  Produces the same columns as
    ``load_standings``: rank, team_name, played, won, drawn, lost,
    gf, ga, gd, points — so it's a drop-in replacement.
    """
    results = load_all_season_results(league, season)
    if results.empty:
        return pd.DataFrame()

    teams: dict[str, dict] = {}
    team_ids: dict[str, str] = {}           # team_name → team_id

    for _, row in results.iterrows():
        ht, at = row["home_team"], row["away_team"]
        hs, as_ = int(row["home_score"]), int(row["away_score"])

        for team in (ht, at):
            if team not in teams:
                teams[team] = {"won": 0, "drawn": 0, "lost": 0, "gf": 0, "ga": 0}

        # Track team IDs (from results columns)
        if "home_id" in row.index and row["home_id"]:
            team_ids.setdefault(ht, row["home_id"])
        if "away_id" in row.index and row["away_id"]:
            team_ids.setdefault(at, row["away_id"])

        # Home team
        teams[ht]["gf"] += hs
        teams[ht]["ga"] += as_
        if hs > as_:
            teams[ht]["won"] += 1
            teams[at]["lost"] += 1
        elif hs == as_:
            teams[ht]["drawn"] += 1
            teams[at]["drawn"] += 1
        else:
            teams[ht]["lost"] += 1
            teams[at]["won"] += 1

        # Away team
        teams[at]["gf"] += as_
        teams[at]["ga"] += hs

    # Also build an ID→name mapping from the JSON standings so we can
    # enrich our computed table with the "official" long names (e.g.
    # "Manchester United FC" instead of the short "Manchester United").
    json_st = load_standings(league, season)
    id_to_official: dict[str, str] = {}
    if not json_st.empty and "team_id" in json_st.columns:
        for _, r in json_st.iterrows():
            id_to_official[r["team_id"]] = r["team_name"]

    rows = []
    for name, s in teams.items():
        played = s["won"] + s["drawn"] + s["lost"]
        gd = s["gf"] - s["ga"]
        pts = s["won"] * 3 + s["drawn"]
        tid = team_ids.get(name, "")
        # Use the official (long) team name when available
        official_name = id_to_official.get(tid, name)
        rows.append({
            "team_name": official_name,
            "team_id": tid,
            "team_code": "",
            "played": played,
            "won": s["won"],
            "drawn": s["drawn"],
            "lost": s["lost"],
            "gf": s["gf"],
            "ga": s["ga"],
            "gd": gd,
            "points": pts,
        })

    df = pd.DataFrame(rows)
    # Sort: points desc → GD desc → GF desc (standard tiebreakers)
    df = df.sort_values(["points", "gd", "gf"], ascending=[False, False, False])
    df["rank"] = range(1, len(df) + 1)
    df = df.reset_index(drop=True)
    return df


def compute_points_by_matchday(league: str, season: str, team_name: str,
                                team_id: str | None = None) -> pd.DataFrame:
    """Compute cumulative points by matchday for a team.

    Handles name mismatches between standings and results by resolving
    the team name through team_id or aliases.
    """
    results = load_all_season_results(league, season)
    if results.empty:
        return pd.DataFrame()

    # Resolve name: standings may use "Manchester United FC" but results have "Manchester United"
    from processing.poisson import _resolve_team_in_results, _get_team_id
    if not team_id:
        standings = load_standings(league, season)
        team_id = _get_team_id(results, standings, team_name)
    resolved = _resolve_team_in_results(results, team_name, team_id)

    team_matches = results[
        (results["home_team"] == resolved) | (results["away_team"] == resolved)
    ].copy()

    points = []
    cum_points = 0
    for _, row in team_matches.iterrows():
        is_home = row["home_team"] == resolved
        hs, as_ = row["home_score"], row["away_score"]
        if is_home:
            p = 3 if hs > as_ else (1 if hs == as_ else 0)
        else:
            p = 3 if as_ > hs else (1 if hs == as_ else 0)
        cum_points += p
        points.append({
            "matchday": row["matchday"],
            "points": p,
            "cumulative_points": cum_points,
        })

    return pd.DataFrame(points)
