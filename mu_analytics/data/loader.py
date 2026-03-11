"""Core data loading module with Streamlit caching."""

import json
import pandas as pd
import streamlit as st
from pathlib import Path

from config import MU_TEAM_ID, MU_TEAM_NAME, MU_TEAM_FOLDER
from data.paths import (
    jsons_dir, partidos_dir, equipos_dir, team_dir, team_jsons_dir,
    find_match_file, list_match_files, list_team_folders, list_seasons,
    equipos_csv, matches_ids_csv, jugadores_seasonstats_csv, seasons_csv,
)


# ── Raw JSON loaders ────────────────────────────────────────────────────────

def _load_json(path: Path) -> dict | list:
    """Load a JSON file and return parsed content."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ── Season-level data ───────────────────────────────────────────────────────

@st.cache_data(ttl=3600)
def load_season_matches(league: str, season: str) -> list[dict]:
    """Load matches.json — all match summaries with full event data.

    Returns the raw list of match dicts from the JSON.
    """
    path = jsons_dir(league, season) / "matches.json"
    if not path.exists():
        return []
    data = _load_json(path)
    return data.get("match", data) if isinstance(data, dict) else data


@st.cache_data(ttl=3600)
def load_standings(league: str, season: str) -> pd.DataFrame:
    """Load standings.json → league table DataFrame.

    Returns DataFrame with: rank, team_name, team_id, team_code, played,
    won, drawn, lost, gf, ga, gd, points, last_six.
    """
    path = jsons_dir(league, season) / "standings.json"
    if not path.exists():
        return pd.DataFrame()

    data = _load_json(path)
    stages = data.get("stage", [])
    if not stages:
        return pd.DataFrame()

    # Find the "total" division (overall standings)
    rows = []
    for stage in stages:
        for div in stage.get("division", []):
            if div.get("type", "") != "total":
                continue
            for r in div.get("ranking", []):
                rows.append({
                    "rank": int(r.get("rank", 0)),
                    "team_name": r.get("contestantName", ""),
                    "team_id": r.get("contestantId", ""),
                    "team_code": r.get("contestantCode", ""),
                    "played": int(r.get("matchesPlayed", 0)),
                    "won": int(r.get("matchesWon", 0)),
                    "drawn": int(r.get("matchesDrawn", 0)),
                    "lost": int(r.get("matchesLost", 0)),
                    "gf": int(r.get("goalsFor", 0)),
                    "ga": int(r.get("goalsAgainst", 0)),
                    "gd": int(r.get("goaldifference", 0)),
                    "points": int(r.get("points", 0)),
                    "last_six": r.get("lastSix", ""),
                })
            break  # only need "total" division
        if rows:
            break

    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values("rank").reset_index(drop=True)
    return df


@st.cache_data(ttl=3600)
def load_squad_roster(league: str, season: str) -> dict[str, dict]:
    """Load squads.json → {player_id: {name, position, nationality, shirtNumber, team}}.

    This is the primary source for resolving player names.
    """
    path = jsons_dir(league, season) / "squads.json"
    if not path.exists():
        return {}

    data = _load_json(path)
    squads = data.get("squad", data) if isinstance(data, dict) else data
    player_map = {}

    for squad in squads:
        team_name = squad.get("contestantName", "")
        team_id = squad.get("contestantId", "")
        for person in squad.get("person", []):
            if person.get("type") != "player":
                continue
            pid = person.get("id", "")
            player_map[pid] = {
                "name": person.get("matchName", f"{person.get('firstName', '')} {person.get('lastName', '')}").strip(),
                "first_name": person.get("firstName", ""),
                "last_name": person.get("lastName", ""),
                "position": person.get("position", ""),
                "nationality": person.get("nationality", ""),
                "shirt_number": person.get("shirtNumber", ""),
                "team": team_name,
                "team_id": team_id,
                "active": person.get("active", "") == "yes",
            }

    return player_map


@st.cache_data(ttl=3600)
def load_managers(league: str, season: str) -> list[dict]:
    """Load squads.json → list of manager/coach dicts.

    Returns list of dicts with: id, name, first_name, last_name, nationality,
    place_of_birth, type (coach/assistant coach), team, team_id, start_date,
    end_date, active.
    """
    path = jsons_dir(league, season) / "squads.json"
    if not path.exists():
        return []

    data = _load_json(path)
    squads = data.get("squad", data) if isinstance(data, dict) else data
    managers = []

    for squad in squads:
        team_name = squad.get("contestantName", "")
        team_id = squad.get("contestantId", "")
        for person in squad.get("person", []):
            ptype = person.get("type", "")
            if ptype not in ("coach", "assistant coach"):
                continue
            managers.append({
                "id": person.get("id", ""),
                "name": person.get("matchName", f"{person.get('firstName', '')} {person.get('lastName', '')}").strip(),
                "first_name": person.get("firstName", ""),
                "last_name": person.get("lastName", ""),
                "nationality": person.get("nationality", ""),
                "second_nationality": person.get("secondNationality", ""),
                "place_of_birth": person.get("placeOfBirth", ""),
                "type": ptype,
                "team": team_name,
                "team_id": team_id,
                "start_date": person.get("startDate", ""),
                "end_date": person.get("endDate", ""),
                "active": person.get("active", "") == "yes",
            })

    return managers


@st.cache_data(ttl=3600)
def load_rankings(league: str, season: str) -> dict:
    """Load rankings.json → raw dict with match-by-match team stats."""
    path = jsons_dir(league, season) / "rankings.json"
    if not path.exists():
        return {}
    return _load_json(path)


# ── Match-level data ────────────────────────────────────────────────────────

@st.cache_data(ttl=3600)
def load_match_events(league: str, season: str, match_id: str) -> list[dict]:
    """Load a single match JSON → list of raw event dicts."""
    path = find_match_file(league, season, match_id)
    if path is None or not path.exists():
        return []
    data = _load_json(path)
    return data.get("liveData", {}).get("event", [])


@st.cache_data(ttl=3600)
def load_match_raw(league: str, season: str, match_id: str) -> dict:
    """Load a single match JSON → full raw dict (matchInfo + liveData)."""
    path = find_match_file(league, season, match_id)
    if path is None or not path.exists():
        return {}
    return _load_json(path)


# ── Team-level data ─────────────────────────────────────────────────────────

@st.cache_data(ttl=3600)
def load_team_season_stats(league: str, season: str, team_folder: str) -> dict:
    """Load team-level seasonstats.json."""
    path = team_jsons_dir(league, season, team_folder) / "seasonstats.json"
    if not path.exists():
        return {}
    return _load_json(path)


@st.cache_data(ttl=3600)
def load_team_matches(league: str, season: str, team_folder: str) -> list[dict]:
    """Load matches_equipo.json for a specific team."""
    path = team_jsons_dir(league, season, team_folder) / "matches_equipo.json"
    if not path.exists():
        return []
    data = _load_json(path)
    return data.get("match", data) if isinstance(data, dict) else data


# ── Player stats ────────────────────────────────────────────────────────────

@st.cache_data(ttl=3600)
def load_player_season_stats(league: str, season: str, team_folder: str) -> pd.DataFrame:
    """Load jugadores_seasonstats.csv for a specific team."""
    path = jugadores_seasonstats_csv(league, season, team_folder)
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


@st.cache_data(ttl=3600)
def load_all_player_season_stats(league: str, season: str) -> pd.DataFrame:
    """Load player season stats for ALL teams in the league. Concatenates all CSVs."""
    frames = []
    for team_folder in list_team_folders(league, season):
        df = load_player_season_stats(league, season, team_folder)
        if not df.empty:
            frames.append(df)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


# ── Player name resolution ──────────────────────────────────────────────────

@st.cache_data(ttl=3600)
def build_player_name_map(league: str, season: str) -> dict[str, str]:
    """Build {player_id: display_name} from squads.json."""
    roster = load_squad_roster(league, season)
    return {pid: info["name"] for pid, info in roster.items()}


def resolve_player_name(player_id: str, player_name: str, name_map: dict[str, str]) -> str:
    """Resolve a player name using the name map, falling back to the event name."""
    if player_id in name_map:
        return name_map[player_id]
    return player_name or f"Unknown ({player_id[:8]})"


# ── Match list builders ─────────────────────────────────────────────────────

@st.cache_data(ttl=3600)
def load_matches_index(league: str, season: str) -> pd.DataFrame:
    """Load matches_ids.csv → DataFrame of match index with teams and dates."""
    path = matches_ids_csv(league, season)
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


@st.cache_data(ttl=3600)
def load_equipos(league: str, season: str) -> pd.DataFrame:
    """Load equipos CSV → DataFrame of teams with logos and IDs."""
    path = equipos_csv(league, season)
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


# ── Season results extraction ───────────────────────────────────────────────

@st.cache_data(ttl=3600)
def load_all_season_results(league: str, season: str) -> pd.DataFrame:
    """Extract match results from matches.json + partidos/.

    matches.json may lag behind the actual match files in partidos/.
    We use matches.json first (fast), then supplement with any played
    matches found in partidos/ that matches.json still marks as Fixture.

    Returns DataFrame: date, home_team, away_team, home_id, away_id,
    home_score, away_score, matchday.
    """
    from data.event_parser import parse_match_info
    import json as _json

    matches = load_season_matches(league, season)
    rows = []
    seen_ids = set()

    # ── Pass 1: matches.json (fast, most matches) ──────────────────────
    for m in matches:
        info = parse_match_info(m)
        if info.get("match_status") == "Fixture":
            continue
        if info["home_score"] is not None:
            rows.append({
                "date": info["date"],
                "matchday": info["matchday"],
                "home_team": info["home_team"],
                "away_team": info["away_team"],
                "home_id": info["home_id"],
                "away_id": info["away_id"],
                "home_score": info["home_score"],
                "away_score": info["away_score"],
            })
            if info["match_id"]:
                seen_ids.add(info["match_id"])

    # ── Pass 2: partidos/ files (catches matches.json lag) ─────────────
    pdir = partidos_dir(league, season)
    if pdir.exists():
        for fpath in sorted(pdir.iterdir()):
            if fpath.suffix != ".json":
                continue
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    raw = _json.load(f)
            except (_json.JSONDecodeError, OSError):
                continue

            info = parse_match_info(raw)
            # Skip if already captured from matches.json
            if info["match_id"] and info["match_id"] in seen_ids:
                continue
            # Skip unplayed matches
            if info.get("match_status") == "Fixture":
                continue
            if info["home_score"] is not None:
                rows.append({
                    "date": info["date"],
                    "matchday": info["matchday"],
                    "home_team": info["home_team"],
                    "away_team": info["away_team"],
                    "home_id": info["home_id"],
                    "away_id": info["away_id"],
                    "home_score": info["home_score"],
                    "away_score": info["away_score"],
                })
                if info["match_id"]:
                    seen_ids.add(info["match_id"])

    df = pd.DataFrame(rows)
    if not df.empty:
        df["date"] = pd.to_datetime(df["date"].str.replace("Z", "", regex=False), errors="coerce")
        df = df.sort_values("date").reset_index(drop=True)
    return df


# ── MU-specific helpers ─────────────────────────────────────────────────────

@st.cache_data(ttl=3600)
def load_mu_match_list(league: str, season: str) -> pd.DataFrame:
    """Get a list of all Manchester United matches with scores and opponents."""
    results = load_all_season_results(league, season)
    if results.empty:
        return results
    mu_matches = results[
        (results["home_id"] == MU_TEAM_ID) | (results["away_id"] == MU_TEAM_ID)
    ].copy()
    mu_matches["is_home"] = mu_matches["home_id"] == MU_TEAM_ID
    mu_matches["opponent"] = mu_matches.apply(
        lambda r: r["away_team"] if r["is_home"] else r["home_team"], axis=1
    )
    mu_matches["mu_score"] = mu_matches.apply(
        lambda r: r["home_score"] if r["is_home"] else r["away_score"], axis=1
    )
    mu_matches["opp_score"] = mu_matches.apply(
        lambda r: r["away_score"] if r["is_home"] else r["home_score"], axis=1
    )
    mu_matches["result"] = mu_matches.apply(
        lambda r: "W" if r["mu_score"] > r["opp_score"]
        else ("D" if r["mu_score"] == r["opp_score"] else "L"),
        axis=1,
    )
    mu_matches["match_id"] = mu_matches.apply(
        lambda r: _find_match_id_for_row(league, season, r), axis=1
    )
    return mu_matches.reset_index(drop=True)


def _find_match_id_for_row(league: str, season: str, row) -> str:
    """Find match_id by scanning matches_ids.csv for matching matchday + teams.

    Handles matchday format mismatch: matches.json stores week as int (e.g. 38),
    while matches_ids.csv stores "Matchday 38".
    """
    idx = load_matches_index(league, season)
    if idx.empty:
        # Fallback: try to find by filename in partidos/
        return _find_match_id_from_files(league, season, row)

    matchday = row["matchday"]
    # matches_ids.csv has "Matchday N" format
    md_str = f"Matchday {matchday}"
    mask = idx["matchday"].astype(str) == md_str
    if mask.sum() == 0:
        # Try direct numeric match in case format varies
        mask = idx["matchday"].astype(str) == str(matchday)

    home = row["home_team"]
    away = row["away_team"]

    for _, m in idx[mask].iterrows():
        local = str(m.get("equipo_local", ""))
        visitor = str(m.get("equipo_visitante", ""))
        # Check if team names match (partial match for short names)
        if (_team_name_match(home, local) and _team_name_match(away, visitor)):
            return str(m.get("id", ""))

    # Fallback: search partidos/ filenames directly
    return _find_match_id_from_files(league, season, row)


def _team_name_match(full_name: str, short_name: str) -> bool:
    """Check if a full team name matches a short/abbreviated name."""
    if not full_name or not short_name:
        return False
    full_lower = full_name.lower().replace(" fc", "").strip()
    short_lower = short_name.lower().replace(" fc", "").strip()
    # Exact match
    if full_lower == short_lower:
        return True
    # One contains the other
    if short_lower in full_lower or full_lower in short_lower:
        return True
    # Common abbreviation: "Manchester United" → "Man Utd"
    # Check first significant word
    full_words = full_lower.split()
    short_words = short_lower.split()
    if full_words and short_words and full_words[0][:3] == short_words[0][:3]:
        return True
    return False


def _find_match_id_from_files(league: str, season: str, row) -> str:
    """Fallback: find match ID by scanning partidos/ filenames directly."""
    pdir = partidos_dir(league, season)
    if not pdir.exists():
        return ""
    matchday = int(row["matchday"])
    home = row["home_team"]

    # Build short name variants for matching filenames
    home_short = _short_team_name(home)

    prefix = f"{matchday}_"
    for f in pdir.iterdir():
        if f.suffix == ".json" and f.name.startswith(prefix):
            # filename: "1_Man Utd_Fulham_9x16f7izg27mw8l6rxtehfitw.json"
            parts = f.stem.split("_")
            if len(parts) >= 4:
                # Extract the hash (last part)
                file_id = parts[-1]
                # Check if home team appears in filename
                file_teams = "_".join(parts[1:-1]).lower()
                if home_short.lower() in file_teams:
                    return file_id
    return ""


def _short_team_name(name: str) -> str:
    """Convert full team name to the short form used in filenames."""
    # Common mappings
    shorts = {
        "Manchester United": "Man Utd",
        "Manchester City": "Man City",
        "Wolverhampton Wanderers": "Wolves",
        "West Ham United": "West Ham",
        "Tottenham Hotspur": "Tottenham",
        "Brighton and Hove Albion": "Brighton",
        "Nottingham Forest": "Nott'm Forest",
        "Newcastle United": "Newcastle",
        "Leicester City": "Leicester",
        "Crystal Palace": "Crystal Palace",
        "Aston Villa": "Aston Villa",
    }
    clean = name.replace(" FC", "").strip()
    return shorts.get(clean, clean)


# ── Data source diagnostics ─────────────────────────────────────────────────

def get_data_diagnostics(league: str, season: str) -> dict:
    """Return diagnostic info about available data files."""
    from data.paths import jsons_dir as jd, partidos_dir as pd_dir

    jdir = jd(league, season)
    pdir = pd_dir(league, season)

    diag = {
        "jsons_path": str(jdir),
        "partidos_path": str(pdir),
        "jsons_exists": jdir.exists(),
        "partidos_exists": pdir.exists(),
        "json_files": [],
        "num_match_files": 0,
    }

    if jdir.exists():
        for f in jdir.iterdir():
            if f.suffix == ".json":
                diag["json_files"].append({
                    "name": f.name,
                    "size_mb": round(f.stat().st_size / (1024 * 1024), 2),
                    "modified": f.stat().st_mtime,
                })

    if pdir.exists():
        match_files = [f for f in pdir.iterdir() if f.suffix == ".json"]
        diag["num_match_files"] = len(match_files)

    return diag
