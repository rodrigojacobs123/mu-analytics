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

    # Penalties: qualifier 9 = penalty kick.
    # (Qualifier 22 means "inside penalty area" on ALL shot types — not penalty kick.)
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


def compute_corner_shot_detail(
    events: list[dict],
    team_id: str,
    all_shots: pd.DataFrame | None = None,
    period: int | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Per-corner breakdown with full shot detail linked by time window.

    Returns
    -------
    corners_df : DataFrame
        One row per corner with corner_side, delivery info, and position.
    shots_df : DataFrame
        One row per shot linked to a corner, with corner_side inherited
        from the originating corner plus full shot detail (x, y, xg, outcome).
    """
    corners = _filter_period(extract_corners(events, team_id), period)
    if corners.empty:
        return pd.DataFrame(), pd.DataFrame()

    if all_shots is None:
        all_shots = _filter_period(extract_shots(events), period)
    else:
        all_shots = _filter_period(all_shots, period)

    # Build corners_df with corner_side
    corner_rows = []
    corner_times = []  # parallel list for fast lookup
    for i, c in corners.iterrows():
        side = "Left Corner" if c["y"] < 50 else "Right Corner"
        raw = c["delivery_type"]
        ct = _to_total_seconds(c["minute"], c["second"], c.get("period", 1))
        corner_times.append(ct)
        corner_rows.append({
            "minute": c["minute"],
            "second": c["second"],
            "delivery_type": raw,
            "delivery_label": CORNER_TYPE_LABELS.get(raw, raw),
            "corner_side": side,
            "x": c["x"],
            "y": c["y"],
            "player_name": c.get("player_name", ""),
            "period": c.get("period", 1),
        })
    corners_df = pd.DataFrame(corner_rows)

    # ── Find delivery destinations (first touch after each corner) ──
    # Opta corners have no end_x/end_y, so we approximate the delivery
    # location by finding the first non-flag event after each corner.
    # Skip: mirror corner events (typeId=6), non-touch events, and events
    # at any corner flag position (delivery kicks from the flag).
    _SKIP_TYPES = {6, 30, 32, 34, 40, 17, 18, 19, 20}
    _DELIVERY_SCAN = 60  # wider than shot window (Opta time = award, not kick)
    delivery_map: dict[tuple, tuple] = {}
    for ev_idx, e in enumerate(events):
        if e.get("typeId") != EVENT_CORNER or e.get("contestantId") != team_id:
            continue
        c_min = int(e.get("timeMin", 0))
        c_sec = int(e.get("timeSec", 0))
        c_per = int(e.get("periodId", 0))
        if period is not None and c_per != period:
            continue
        c_t = _to_total_seconds(c_min, c_sec, c_per)
        for j in range(ev_idx + 1, min(ev_idx + 80, len(events))):
            nxt = events[j]
            if nxt.get("typeId") in _SKIP_TYPES:
                continue
            nx, ny = float(nxt.get("x", 0)), float(nxt.get("y", 0))
            if nx == 0 and ny == 0:
                continue
            gap = _to_total_seconds(
                int(nxt.get("timeMin", 0)),
                int(nxt.get("timeSec", 0)),
                int(nxt.get("periodId", 0)),
            ) - c_t
            if gap > _DELIVERY_SCAN or gap < 0:
                break
            # Flip coordinates if from the opposing team
            if nxt.get("contestantId", "") != team_id:
                nx, ny = 100 - nx, 100 - ny
            # Skip events at corner flag positions (delivery kicks)
            if (nx < 5 or nx > 95) and (ny < 5 or ny > 95):
                continue
            delivery_map[(c_min, c_sec, c_per)] = (nx, ny)
            break

    del_x, del_y = [], []
    for _, r in corners_df.iterrows():
        dx, dy = delivery_map.get(
            (r["minute"], r["second"], r["period"]), (None, None)
        )
        del_x.append(dx)
        del_y.append(dy)
    corners_df["delivery_x"] = del_x
    corners_df["delivery_y"] = del_y

    # Link shots → most recent preceding corner within window
    team_shots = all_shots[all_shots["team_id"] == team_id] if not all_shots.empty else pd.DataFrame()
    shot_rows = []
    if not team_shots.empty and corner_times:
        for _, s in team_shots.iterrows():
            st_time = _to_total_seconds(s["minute"], s["second"], s.get("period", 1))
            # Find most recent corner before this shot within window
            best_idx = -1
            best_gap = SET_PIECE_WINDOW_SECS + 1
            for ci, ct in enumerate(corner_times):
                gap = st_time - ct
                if 0 < gap <= SET_PIECE_WINDOW_SECS and gap < best_gap:
                    best_gap = gap
                    best_idx = ci
            if best_idx >= 0:
                shot_rows.append({
                    "corner_idx": best_idx,
                    "corner_side": corner_rows[best_idx]["corner_side"],
                    "minute": s["minute"],
                    "second": s["second"],
                    "x": s["x"],
                    "y": s["y"],
                    "xg": s.get("xg", 0.0),
                    "outcome": s.get("outcome", ""),
                    "body_part": s.get("body_part", ""),
                    "period": s.get("period", 1),
                })

    shots_df = pd.DataFrame(shot_rows)
    return corners_df, shots_df


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
