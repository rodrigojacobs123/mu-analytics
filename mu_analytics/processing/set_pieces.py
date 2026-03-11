"""Set-piece analysis: corners, free kicks, and their outcomes."""

import pandas as pd
from data.event_parser import extract_corners, extract_fouls, extract_shots
from config import (
    EVENT_CORNER, EVENT_FOUL, SHOT_TYPE_IDS,
    CORNER_TYPE_LABELS, SET_PIECE_WINDOW_SECS,
)


def _to_total_seconds(minute: int, second: int, period: int) -> float:
    """Convert match time to a continuous total-seconds value.

    Opta ``timeMin`` is already absolute (e.g. 50th minute = 50, not 5
    into the second half), so we just convert minute:second to seconds.
    The ``period`` parameter is accepted for API consistency but unused.
    """
    return minute * 60 + second


def _filter_period(df: pd.DataFrame, period: int | None) -> pd.DataFrame:
    """Filter a DataFrame to a specific match period (or return as-is)."""
    if period is not None and not df.empty and "period" in df.columns:
        return df[df["period"] == period].copy()
    return df


# ─────────────────────────────────────────────────────────────────────────────
# Set-Piece Sequence Tracking
# ─────────────────────────────────────────────────────────────────────────────

def _attribute_shots_to_set_pieces(
    set_piece_events: pd.DataFrame,
    shots_df: pd.DataFrame,
    window: int = SET_PIECE_WINDOW_SECS,
) -> tuple[int, int]:
    """Count how many shots (and goals) occurred within `window` seconds
    after a set-piece event by the *same team*.

    Returns (set_piece_shots, set_piece_goals).
    """
    if set_piece_events.empty or shots_df.empty:
        return 0, 0

    sp_times = []
    for _, sp in set_piece_events.iterrows():
        t = _to_total_seconds(sp["minute"], sp["second"], sp["period"])
        sp_times.append((t, sp["team_id"]))

    sp_shots = 0
    sp_goals = 0
    for _, shot in shots_df.iterrows():
        shot_t = _to_total_seconds(shot["minute"], shot["second"], shot["period"])
        shot_team = shot["team_id"]

        for sp_t, sp_team in sp_times:
            if sp_team == shot_team and 0 < (shot_t - sp_t) <= window:
                sp_shots += 1
                if shot.get("outcome") == "Goal":
                    sp_goals += 1
                break  # attribute to at most one set piece

    return sp_shots, sp_goals


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def compute_set_piece_stats(
    events: list[dict],
    home_id: str,
    away_id: str,
    period: int | None = None,
) -> dict:
    """Compute set-piece KPIs for both teams in a match.

    Returns::

        {
            "home": {corners_won, corners_conceded, fouls_won, fouls_committed,
                     set_piece_shots, set_piece_goals, corner_shot_rate,
                     penalties_awarded},
            "away": { ... }
        }
    """
    corners_h = _filter_period(extract_corners(events, home_id), period)
    corners_a = _filter_period(extract_corners(events, away_id), period)
    # Fouls committed BY team — fouls_won by team X = fouls committed BY opponent
    fouls_by_h = _filter_period(extract_fouls(events, home_id), period)
    fouls_by_a = _filter_period(extract_fouls(events, away_id), period)

    all_shots = _filter_period(extract_shots(events), period)

    # Combine corners + fouls-won as set-piece origins for each team
    # Home set pieces = corners by home + fouls committed by away
    sp_home = pd.concat([corners_h, fouls_by_a], ignore_index=True) if not corners_h.empty or not fouls_by_a.empty else pd.DataFrame()
    sp_away = pd.concat([corners_a, fouls_by_h], ignore_index=True) if not corners_a.empty or not fouls_by_h.empty else pd.DataFrame()

    # For foul events: the team_id is the committer, but the *beneficiary* is
    # the opposing team.  We need to flip team_id for fouls-won so the
    # sequence tracker matches shots by the correct team.
    if not fouls_by_a.empty:
        fouls_won_h = fouls_by_a.copy()
        fouls_won_h["team_id"] = home_id
        sp_home = pd.concat([corners_h, fouls_won_h], ignore_index=True)
    else:
        sp_home = corners_h.copy() if not corners_h.empty else pd.DataFrame()

    if not fouls_by_h.empty:
        fouls_won_a = fouls_by_h.copy()
        fouls_won_a["team_id"] = away_id
        sp_away = pd.concat([corners_a, fouls_won_a], ignore_index=True)
    else:
        sp_away = corners_a.copy() if not corners_a.empty else pd.DataFrame()

    sp_shots_h, sp_goals_h = _attribute_shots_to_set_pieces(sp_home, all_shots)
    sp_shots_a, sp_goals_a = _attribute_shots_to_set_pieces(sp_away, all_shots)

    n_corners_h = len(corners_h)
    n_corners_a = len(corners_a)

    # Penalties: only count penalty GOALS (qualifier 22 on goal events).
    # Qualifier 22 on non-goal shots means "inside penalty area", not penalty kick.
    from data.event_parser import _has_qualifier
    from config import QUAL_PENALTY, EVENT_GOAL
    pen_h = sum(1 for e in events if e.get("typeId") == EVENT_GOAL
                and e.get("contestantId") == home_id
                and _has_qualifier(e.get("qualifier", []), QUAL_PENALTY))
    pen_a = sum(1 for e in events if e.get("typeId") == EVENT_GOAL
                and e.get("contestantId") == away_id
                and _has_qualifier(e.get("qualifier", []), QUAL_PENALTY))

    def _rate(shots, total):
        return round(shots / total * 100, 1) if total > 0 else 0.0

    return {
        "home": {
            "corners_won": n_corners_h,
            "corners_conceded": n_corners_a,
            "fouls_won": len(fouls_by_a),
            "fouls_committed": len(fouls_by_h),
            "set_piece_shots": sp_shots_h,
            "set_piece_goals": sp_goals_h,
            "corner_shot_rate": _rate(sp_shots_h, n_corners_h),
            "penalties_awarded": pen_h,
        },
        "away": {
            "corners_won": n_corners_a,
            "corners_conceded": n_corners_h,
            "fouls_won": len(fouls_by_h),
            "fouls_committed": len(fouls_by_a),
            "set_piece_shots": sp_shots_a,
            "set_piece_goals": sp_goals_a,
            "corner_shot_rate": _rate(sp_shots_a, n_corners_a),
            "penalties_awarded": pen_a,
        },
    }


def compute_corner_breakdown(
    events: list[dict],
    team_id: str,
    all_shots: pd.DataFrame | None = None,
    period: int | None = None,
) -> pd.DataFrame:
    """Per-corner breakdown with delivery type and whether it produced a shot.

    Returns DataFrame: minute, second, delivery_type, delivery_label,
                       had_shot, had_goal, x, y
    """
    corners = _filter_period(extract_corners(events, team_id), period)
    if corners.empty:
        return pd.DataFrame()

    if all_shots is None:
        all_shots = _filter_period(extract_shots(events), period)

    rows = []
    for _, c in corners.iterrows():
        c_t = _to_total_seconds(c["minute"], c["second"], c["period"])
        had_shot = False
        had_goal = False

        if not all_shots.empty:
            for _, s in all_shots.iterrows():
                if s["team_id"] != team_id:
                    continue
                s_t = _to_total_seconds(s["minute"], s["second"], s["period"])
                if 0 < (s_t - c_t) <= SET_PIECE_WINDOW_SECS:
                    had_shot = True
                    if s.get("outcome") == "Goal":
                        had_goal = True
                    break

        raw_type = c["delivery_type"]
        rows.append({
            "minute": c["minute"],
            "second": c["second"],
            "delivery_type": raw_type,
            "delivery_label": CORNER_TYPE_LABELS.get(raw_type, raw_type),
            "had_shot": had_shot,
            "had_goal": had_goal,
            "x": c["x"],
            "y": c["y"],
            "period": c["period"],
        })

    return pd.DataFrame(rows)


def compute_dangerous_fk_zones(
    events: list[dict],
    team_id: str,
    opponent_id: str,
    period: int | None = None,
) -> pd.DataFrame:
    """Locations where `team_id` WON free kicks (opponent committed fouls).

    The x/y coordinates are from the *fouling* team's perspective in Opta,
    so we flip x → 100-x to show the location from the *winning* team's
    attacking perspective.

    Adds `dangerous` = True for fouls won in the final third (flipped x > 66).
    """
    fouls_by_opponent = _filter_period(extract_fouls(events, opponent_id), period)
    if fouls_by_opponent.empty:
        return pd.DataFrame()

    df = fouls_by_opponent.copy()
    # Flip coordinates to winning team's perspective
    df["x"] = 100 - df["x"]
    df["y"] = 100 - df["y"]
    df["dangerous"] = df["x"] > 66
    return df
