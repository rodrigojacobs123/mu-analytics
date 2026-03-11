"""Manager profile statistics — record, formations, tactical tendencies.

Supports tenure-aware filtering: pass start_date/end_date to scope stats
to a specific manager's period in charge.
"""

import pandas as pd
from collections import Counter
from data.loader import (
    load_all_season_results, load_season_matches, load_match_raw,
    load_managers, load_standings,
)
from data.event_parser import extract_formation, parse_match_info
from data.paths import list_match_files


# ── Tenure date helpers ──────────────────────────────────────────────────────

def _parse_date(date_str: str) -> pd.Timestamp | None:
    """Parse Opta date string (e.g. '2024-11-11Z') to Timestamp."""
    if not date_str:
        return None
    clean = date_str.replace("Z", "").strip()
    try:
        return pd.Timestamp(clean)
    except Exception:
        return None


def _filter_by_tenure(df: pd.DataFrame, start_date: str = "",
                      end_date: str = "") -> pd.DataFrame:
    """Filter a results DataFrame to matches within a manager's tenure."""
    if df.empty or "date" not in df.columns:
        return df

    filtered = df.copy()
    start = _parse_date(start_date)
    end = _parse_date(end_date)

    if start is not None:
        filtered = filtered[filtered["date"] >= start]
    if end is not None:
        filtered = filtered[filtered["date"] <= end]

    return filtered


# ── Coach queries ────────────────────────────────────────────────────────────

def get_head_coaches(league: str, season: str) -> list[dict]:
    """Return only head coaches (type == 'coach'), one per team.

    Filters out assistant coaches and inactive entries where possible.
    """
    managers = load_managers(league, season)
    # Keep only head coaches
    coaches = [m for m in managers if m["type"] == "coach" and m["active"]]
    # Fallback: if a team has no active coach, include inactive ones
    teams_with_coach = {c["team_id"] for c in coaches}
    for m in managers:
        if m["type"] == "coach" and m["team_id"] not in teams_with_coach:
            coaches.append(m)
            teams_with_coach.add(m["team_id"])
    return coaches


def get_all_team_coaches(league: str, season: str, team_id: str) -> list[dict]:
    """Return ALL head coaches for a specific team, sorted by start date.

    Includes both active and inactive coaches — captures full managerial
    history within the season (e.g., Ten Hag → Van Nistelrooij → Amorim).
    """
    managers = load_managers(league, season)
    team_coaches = [
        m for m in managers
        if m["team_id"] == team_id and m["type"] == "coach"
    ]
    # Sort by start_date (earliest first)
    team_coaches.sort(key=lambda c: c.get("start_date", "") or "9999")
    return team_coaches


# ── Tenure-aware stats ───────────────────────────────────────────────────────

def compute_manager_record(league: str, season: str, team_id: str,
                           start_date: str = "", end_date: str = "") -> dict:
    """Compute a manager's W/D/L record from season results.

    If start_date/end_date are provided, filters to that tenure window.

    Returns dict with: played, won, drawn, lost, win_pct, gf, ga, gd,
    points, ppg (points per game).
    """
    results = load_all_season_results(league, season)
    if results.empty:
        return _empty_record()

    # Filter by team
    team_results = results[
        (results["home_id"] == team_id) | (results["away_id"] == team_id)
    ]
    # Filter by tenure
    team_results = _filter_by_tenure(team_results, start_date, end_date)

    if team_results.empty:
        return _empty_record()

    wins, draws, losses = 0, 0, 0
    gf, ga = 0, 0

    for _, r in team_results.iterrows():
        is_home = r["home_id"] == team_id
        my_goals = r["home_score"] if is_home else r["away_score"]
        opp_goals = r["away_score"] if is_home else r["home_score"]
        gf += my_goals
        ga += opp_goals

        if my_goals > opp_goals:
            wins += 1
        elif my_goals == opp_goals:
            draws += 1
        else:
            losses += 1

    played = wins + draws + losses
    points = wins * 3 + draws
    return {
        "played": played,
        "won": wins,
        "drawn": draws,
        "lost": losses,
        "win_pct": (wins / played * 100) if played > 0 else 0,
        "gf": gf,
        "ga": ga,
        "gd": gf - ga,
        "points": points,
        "ppg": round(points / played, 2) if played > 0 else 0,
    }


def compute_formation_usage(league: str, season: str, team_id: str,
                            start_date: str = "", end_date: str = "") -> list[dict]:
    """Scan all matches for a team and count formation usage.

    If start_date/end_date are provided, only counts matches in that window.

    Returns list of dicts sorted by frequency: [{formation, count, pct}]
    """
    from data.loader import load_match_raw
    from data.paths import partidos_dir
    import json

    start = _parse_date(start_date)
    end = _parse_date(end_date)
    formation_counter = Counter()

    pdir = partidos_dir(league, season)
    if pdir.exists():
        for fpath in pdir.iterdir():
            if fpath.suffix != ".json":
                continue
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                info = parse_match_info(raw)
                if team_id not in (info["home_id"], info["away_id"]):
                    continue

                # Date filter for tenure
                if start or end:
                    match_date = _parse_date(info.get("date", ""))
                    if match_date:
                        if start and match_date < start:
                            continue
                        if end and match_date > end:
                            continue

                events = raw.get("liveData", {}).get("event", [])
                fm = extract_formation(events, team_id)
                if fm and fm["formation_str"]:
                    formation_counter[fm["formation_str"]] += 1
            except (json.JSONDecodeError, KeyError):
                continue

    total = sum(formation_counter.values())
    result = []
    for formation, count in formation_counter.most_common():
        result.append({
            "formation": formation,
            "count": count,
            "pct": round(count / total * 100, 1) if total > 0 else 0,
        })
    return result


def compute_recent_form(league: str, season: str, team_id: str,
                        n: int = 5, start_date: str = "",
                        end_date: str = "") -> list[str]:
    """Get the last N results as W/D/L strings within tenure window."""
    results = load_all_season_results(league, season)
    if results.empty:
        return []

    team_results = results[
        (results["home_id"] == team_id) | (results["away_id"] == team_id)
    ]
    team_results = _filter_by_tenure(team_results, start_date, end_date)
    team_results = team_results.tail(n)

    form = []
    for _, r in team_results.iterrows():
        is_home = r["home_id"] == team_id
        my = r["home_score"] if is_home else r["away_score"]
        opp = r["away_score"] if is_home else r["home_score"]
        if my > opp:
            form.append("W")
        elif my == opp:
            form.append("D")
        else:
            form.append("L")
    return form


def compute_home_away_split(league: str, season: str, team_id: str,
                            start_date: str = "", end_date: str = "") -> dict:
    """Compute home vs away performance split within tenure window.

    Returns dict with home_{w,d,l,gf,ga} and away_{w,d,l,gf,ga}.
    """
    results = load_all_season_results(league, season)
    if results.empty:
        return _empty_split()

    team_results = results[
        (results["home_id"] == team_id) | (results["away_id"] == team_id)
    ]
    team_results = _filter_by_tenure(team_results, start_date, end_date)

    split = _empty_split()

    for _, r in team_results.iterrows():
        is_home = r["home_id"] == team_id
        my = r["home_score"] if is_home else r["away_score"]
        opp = r["away_score"] if is_home else r["home_score"]
        prefix = "home" if is_home else "away"

        split[f"{prefix}_gf"] += my
        split[f"{prefix}_ga"] += opp

        if my > opp:
            split[f"{prefix}_w"] += 1
        elif my == opp:
            split[f"{prefix}_d"] += 1
        else:
            split[f"{prefix}_l"] += 1

    return split


def compute_goals_timeline(league: str, season: str, team_id: str,
                           start_date: str = "", end_date: str = "") -> pd.DataFrame:
    """Build a matchday-by-matchday goals scored/conceded timeline.

    Returns DataFrame: match_num, matchday, gf, ga, gd_cumulative.
    """
    results = load_all_season_results(league, season)
    if results.empty:
        return pd.DataFrame()

    team_results = results[
        (results["home_id"] == team_id) | (results["away_id"] == team_id)
    ]
    team_results = _filter_by_tenure(team_results, start_date, end_date)

    rows = []
    cum_gd = 0
    for i, (_, r) in enumerate(team_results.iterrows(), 1):
        is_home = r["home_id"] == team_id
        my = r["home_score"] if is_home else r["away_score"]
        opp = r["away_score"] if is_home else r["home_score"]
        cum_gd += my - opp
        rows.append({
            "match_num": i,
            "matchday": r.get("matchday", i),
            "gf": my,
            "ga": opp,
            "gd_cumulative": cum_gd,
        })

    return pd.DataFrame(rows)


# ── Comparison helper ────────────────────────────────────────────────────────

def compare_managers(league: str, season: str, team_id: str,
                     coaches: list[dict]) -> pd.DataFrame:
    """Build a comparison DataFrame across multiple coaches for the same team.

    Returns DataFrame with one row per coach: name, tenure, record, PPG,
    win rate, GF/game, GA/game, preferred formation.
    """
    rows = []
    for c in coaches:
        rec = compute_manager_record(
            league, season, team_id,
            start_date=c.get("start_date", ""),
            end_date=c.get("end_date", ""),
        )
        forms = compute_formation_usage(
            league, season, team_id,
            start_date=c.get("start_date", ""),
            end_date=c.get("end_date", ""),
        )
        pref_formation = forms[0]["formation"] if forms else "N/A"

        start = c.get("start_date", "")[:10] or "?"
        end = c.get("end_date", "")[:10] or "Present"

        rows.append({
            "Manager": c["name"],
            "Tenure": f"{start} → {end}",
            "P": rec["played"],
            "W": rec["won"],
            "D": rec["drawn"],
            "L": rec["lost"],
            "Win %": round(rec["win_pct"], 1),
            "PPG": rec["ppg"],
            "GF/G": round(rec["gf"] / rec["played"], 2) if rec["played"] else 0,
            "GA/G": round(rec["ga"] / rec["played"], 2) if rec["played"] else 0,
            "GD": rec["gd"],
            "Formation": pref_formation,
        })

    return pd.DataFrame(rows)


# ── Internal helpers ─────────────────────────────────────────────────────────

def _empty_record() -> dict:
    return {
        "played": 0, "won": 0, "drawn": 0, "lost": 0,
        "win_pct": 0, "gf": 0, "ga": 0, "gd": 0,
        "points": 0, "ppg": 0,
    }


def _empty_split() -> dict:
    return {
        "home_w": 0, "home_d": 0, "home_l": 0, "home_gf": 0, "home_ga": 0,
        "away_w": 0, "away_d": 0, "away_l": 0, "away_gf": 0, "away_ga": 0,
    }
