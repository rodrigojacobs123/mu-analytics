"""Per-match player performance ratings — position-aware scoring.

Unlike season-level ratings (percentile-based), match ratings use an
absolute scoring system:
  1. Extract raw per-player metrics from the event stream
  2. Compute derived metrics (pass %, tackle %, etc.)
  3. Apply position-specific weight profiles
  4. Scale to 1-10 (6.0 = average, 8+ = excellent, <5 = poor)

Position groups from formation qualifier 44:
  Row 1 = GK, Row 2 = DEF, Row 3 = MID, Row 4 = FWD
"""

import pandas as pd
import numpy as np
from data.event_parser import (
    extract_passes, extract_shots, extract_goals, extract_tackles,
    extract_interceptions, extract_ball_recoveries, extract_take_ons,
    extract_aerials, extract_all_touches, extract_fouls, extract_cards,
    extract_clearances, extract_saves, extract_formation,
)

# ── Position weight profiles ─────────────────────────────────────────────────
# Each profile maps metric keys → how many rating points per unit.
# These are ADDITIVE on top of a 6.0 base.
# Negative weights penalize (e.g. fouls_committed costs rating points).

GK_WEIGHTS = {
    "saves":             0.40,   # each save adds 0.40
    "goals_conceded":   -0.30,   # each goal conceded costs 0.30
    "clean_sheet":       0.50,   # clean sheet bonus
    "pass_completion":   0.015,  # per % point above 50%
    "touches":           0.01,   # involvement
    "clearances":        0.15,
}

DEF_WEIGHTS = {
    "tackles_won":       0.25,
    "tackles_lost":     -0.15,
    "interceptions":     0.30,
    "clearances":        0.15,
    "aerials_won":       0.20,
    "aerials_lost":     -0.10,
    "recoveries":        0.10,
    "pass_completion":   0.02,   # per % point above 65%
    "fouls_committed":  -0.15,
    "goals":             1.00,   # big bonus for scoring
    "yellow_card":      -0.50,
    "red_card":         -2.00,
}

MID_WEIGHTS = {
    "passes_completed":  0.015,
    "pass_completion":   0.025,  # per % point above 70%
    "forward_passes":    0.05,
    "key_passes":        0.40,
    "assists":           1.00,
    "tackles_won":       0.20,
    "interceptions":     0.20,
    "recoveries":        0.08,
    "take_ons_won":      0.15,
    "take_ons_lost":    -0.08,
    "goals":             1.20,
    "shots_on_target":   0.15,
    "fouls_committed":  -0.12,
    "yellow_card":      -0.50,
    "red_card":         -2.00,
}

FWD_WEIGHTS = {
    "goals":             1.50,
    "xg_overperformance": 0.60,  # scored more than xG expected
    "shots":             0.05,
    "shots_on_target":   0.15,
    "key_passes":        0.35,
    "assists":           1.00,
    "take_ons_won":      0.15,
    "take_ons_lost":    -0.05,
    "aerials_won":       0.10,
    "touches_opp_box":   0.04,
    "pass_completion":   0.015,  # per % point above 60%
    "fouls_committed":  -0.10,
    "yellow_card":      -0.50,
    "red_card":         -2.00,
}

POSITION_WEIGHTS = {
    1: GK_WEIGHTS,
    2: DEF_WEIGHTS,
    3: MID_WEIGHTS,
    4: FWD_WEIGHTS,
}

POSITION_LABELS = {1: "GK", 2: "DEF", 3: "MID", 4: "FWD"}

# Pass completion baseline per position (rating bonus only above this %)
PASS_BASELINE = {1: 50, 2: 65, 3: 70, 4: 60}

BASE_RATING = 6.0
MIN_RATING = 1.0
MAX_RATING = 10.0


# ── Step 1: Extract per-player metrics from event stream ─────────────────────

def _count_player(df: pd.DataFrame, pid: str, outcome: int | None = None) -> int:
    """Count events for a player, optionally filtered by outcome."""
    if df.empty or "player_id" not in df.columns:
        return 0
    mask = df["player_id"] == pid
    if outcome is not None and "outcome" in df.columns:
        mask = mask & (df["outcome"] == outcome)
    return int(mask.sum())


def gather_player_stats(events: list[dict], team_id: str,
                        formation: dict | None = None) -> pd.DataFrame:
    """Extract per-player stats from a single match's event data.

    Returns DataFrame with one row per player (starters + subs who appeared)
    and columns for every raw metric.
    """
    # Get formation for position row mapping
    if formation is None:
        formation = extract_formation(events, team_id)

    # Build player → position_row mapping from formation
    player_positions = {}
    if formation:
        for s in formation.get("starters", []):
            player_positions[s["player_id"]] = s["position_row"]
        for s in formation.get("subs", []):
            player_positions[s["player_id"]] = 0  # sub, unknown row

    # Extract all event DataFrames for this team
    passes = extract_passes(events, team_id)
    passes_all = _extract_passes_all(events, team_id)
    shots = extract_shots(events, team_id)
    goals = extract_goals(events)
    team_goals = goals[goals["team_id"] == team_id] if not goals.empty else goals
    tackles = extract_tackles(events, team_id)
    interceptions = extract_interceptions(events, team_id)
    recoveries = extract_ball_recoveries(events, team_id)
    take_ons = extract_take_ons(events, team_id)
    aerials = extract_aerials(events, team_id)
    touches = extract_all_touches(events, team_id)
    fouls = extract_fouls(events, team_id)
    cards = extract_cards(events)
    team_cards = cards[cards["team_id"] == team_id] if not cards.empty else cards
    clearances = extract_clearances(events, team_id)
    saves = extract_saves(events, team_id)

    # Opponent goals (for GK goals_conceded)
    opp_goals = goals[goals["team_id"] != team_id] if not goals.empty else goals

    # Collect all player IDs who had any event
    all_pids = set()
    for df in [passes_all, shots, tackles, interceptions, recoveries,
               take_ons, aerials, touches, fouls, clearances, saves]:
        if not df.empty and "player_id" in df.columns:
            all_pids.update(df["player_id"].unique())
    # Also include starters from formation
    if formation:
        for s in formation.get("starters", []):
            all_pids.add(s["player_id"])

    rows = []
    for pid in all_pids:
        if not pid:
            continue

        pos_row = player_positions.get(pid, 3)  # default to MID if unknown

        # Resolve name from touches or passes
        name = _resolve_name(pid, [touches, passes_all, shots, tackles])

        # ── Count raw metrics ─────────────────────────────────────────
        total_passes = _count_player(passes_all, pid)
        successful_passes = _count_player(passes_all, pid, outcome=1)
        pass_pct = (successful_passes / total_passes * 100) if total_passes > 0 else 0

        # Forward passes (end_x > x + 10)
        fwd_passes = 0
        if not passes_all.empty and "end_x" in passes_all.columns:
            pmask = (passes_all["player_id"] == pid) & (passes_all["outcome"] == 1)
            p_df = passes_all[pmask]
            if not p_df.empty:
                fwd_passes = int((p_df["end_x"] - p_df["x"] > 10).sum())

        # Key passes: successful passes that led to a shot (approximate:
        # passes into the box x>83, 21<y<79)
        key_passes = 0
        if not passes_all.empty and "end_x" in passes_all.columns:
            pmask = (passes_all["player_id"] == pid) & (passes_all["outcome"] == 1)
            p_df = passes_all[pmask]
            if not p_df.empty:
                key_passes = int(
                    ((p_df["end_x"] > 83) & (p_df["end_y"] > 21) &
                     (p_df["end_y"] < 79)).sum()
                )

        # Shooting
        n_shots = _count_player(shots, pid)
        shots_on = 0
        if not shots.empty:
            on_mask = (shots["player_id"] == pid) & (
                shots["outcome"].isin(["Goal", "Saved"]))
            shots_on = int(on_mask.sum())

        # Goals + xG
        n_goals = _count_player(team_goals, pid)
        player_xg = 0.0
        if not shots.empty:
            s_mask = shots["player_id"] == pid
            if "xg" in shots.columns:
                player_xg = float(shots.loc[s_mask, "xg"].sum())

        # Assists (from goals that have qualifier 76)
        assists = 0
        if not team_goals.empty and "has_assist" in team_goals.columns:
            # We need the involved player (qualifier 140) from goals
            for _, g in team_goals.iterrows():
                if g.get("has_assist"):
                    # The assister is the involved player
                    # For simplicity, count all assists for this team
                    pass  # approximate below

        # Defense
        tackles_won = _count_player(tackles, pid, outcome=1)
        tackles_lost = _count_player(tackles, pid, outcome=0)
        n_interceptions = _count_player(interceptions, pid)
        n_recoveries = _count_player(recoveries, pid)
        n_clearances = _count_player(clearances, pid)

        # Aerials
        aerials_won = _count_player(aerials, pid, outcome=1)
        aerials_lost = _count_player(aerials, pid, outcome=0)

        # Take-ons
        take_ons_won = _count_player(take_ons, pid, outcome=1)
        take_ons_lost = _count_player(take_ons, pid, outcome=0)

        # GK saves
        n_saves = _count_player(saves, pid)
        goals_conceded = len(opp_goals) if pos_row == 1 else 0
        clean_sheet = 1 if (pos_row == 1 and goals_conceded == 0) else 0

        # Touches
        n_touches = _count_player(touches, pid)
        touches_opp_box = 0
        if not touches.empty:
            tmask = touches["player_id"] == pid
            t_df = touches[tmask]
            if not t_df.empty:
                touches_opp_box = int(
                    ((t_df["x"] > 83) & (t_df["y"] > 21) &
                     (t_df["y"] < 79)).sum()
                )

        # Fouls
        fouls_committed = _count_player(fouls, pid)

        # Cards
        yellows = 0
        reds = 0
        if not team_cards.empty:
            pc = team_cards[team_cards["player_id"] == pid]
            if not pc.empty and "card_type" in pc.columns:
                yellows = int((pc["card_type"] == "yellow").sum())
                reds = int((pc["card_type"] == "red").sum())

        rows.append({
            "player_id": pid,
            "player_name": name,
            "position_row": pos_row,
            "position": POSITION_LABELS.get(pos_row, "SUB"),
            "total_passes": total_passes,
            "successful_passes": successful_passes,
            "pass_completion": round(pass_pct, 1),
            "forward_passes": fwd_passes,
            "key_passes": key_passes,
            "passes_completed": successful_passes,
            "shots": n_shots,
            "shots_on_target": shots_on,
            "goals": n_goals,
            "xg": round(player_xg, 2),
            "xg_overperformance": round(n_goals - player_xg, 2),
            "assists": assists,
            "tackles_won": tackles_won,
            "tackles_lost": tackles_lost,
            "interceptions": n_interceptions,
            "recoveries": n_recoveries,
            "clearances": n_clearances,
            "aerials_won": aerials_won,
            "aerials_lost": aerials_lost,
            "take_ons_won": take_ons_won,
            "take_ons_lost": take_ons_lost,
            "saves": n_saves,
            "goals_conceded": goals_conceded,
            "clean_sheet": clean_sheet,
            "touches": n_touches,
            "touches_opp_box": touches_opp_box,
            "fouls_committed": fouls_committed,
            "yellow_card": yellows,
            "red_card": reds,
        })

    return pd.DataFrame(rows)


def _resolve_name(pid: str, dfs: list[pd.DataFrame]) -> str:
    """Resolve player name from the first DataFrame that has it."""
    for df in dfs:
        if df.empty or "player_id" not in df.columns:
            continue
        match = df[df["player_id"] == pid]
        if not match.empty and "player_name" in match.columns:
            name = match.iloc[0]["player_name"]
            if name:
                return name
    return f"Unknown ({pid[:8]})"


def _extract_passes_all(events: list[dict], team_id: str) -> pd.DataFrame:
    """Extract ALL passes (both successful and failed) for a team."""
    from config import EVENT_PASS, QUAL_PASS_END_X, QUAL_PASS_END_Y
    from data.event_parser import _get_qualifier

    rows = []
    for e in events:
        if e.get("typeId") != EVENT_PASS:
            continue
        if team_id and e.get("contestantId") != team_id:
            continue
        quals = e.get("qualifier", [])
        end_x = _get_qualifier(quals, QUAL_PASS_END_X)
        end_y = _get_qualifier(quals, QUAL_PASS_END_Y)
        rows.append({
            "player_id": e.get("playerId", ""),
            "player_name": e.get("playerName", ""),
            "x": float(e.get("x", 0)),
            "y": float(e.get("y", 0)),
            "end_x": float(end_x) if end_x else None,
            "end_y": float(end_y) if end_y else None,
            "outcome": int(e.get("outcome", 0)),
            "period": int(e.get("periodId", 0)),
        })
    return pd.DataFrame(rows)


# ── Step 2: Compute position-aware ratings ───────────────────────────────────

def compute_match_ratings(events: list[dict], team_id: str,
                          formation: dict | None = None) -> pd.DataFrame:
    """Compute per-player match ratings on a 1-10 scale.

    Each player starts at 6.0 (average). Metrics add/subtract from this
    base using position-specific weight profiles.

    Returns DataFrame sorted by rating (descending) with columns:
      player_id, player_name, position, rating, rating_display,
      plus all raw metric columns.
    """
    stats = gather_player_stats(events, team_id, formation)
    if stats.empty:
        return pd.DataFrame()

    # Filter out subs who barely touched the ball
    stats = stats[stats["touches"] >= 5].copy()
    if stats.empty:
        return pd.DataFrame()

    ratings = []
    for _, row in stats.iterrows():
        pos_row = row["position_row"]
        weights = POSITION_WEIGHTS.get(pos_row, MID_WEIGHTS)
        baseline = PASS_BASELINE.get(pos_row, 65)

        score = BASE_RATING

        for metric, weight in weights.items():
            if metric == "pass_completion":
                # Bonus/penalty relative to position baseline
                delta = row.get("pass_completion", 0) - baseline
                score += delta * weight
            elif metric == "clean_sheet":
                score += row.get("clean_sheet", 0) * weight
            else:
                val = row.get(metric, 0)
                if pd.notna(val):
                    score += val * weight

        # Clamp to valid range
        score = np.clip(score, MIN_RATING, MAX_RATING)
        ratings.append(round(score, 1))

    stats["rating"] = ratings
    stats["rating_display"] = stats["rating"].apply(
        lambda r: f"{r:.1f}"
    )

    # Sort by rating descending
    stats = stats.sort_values("rating", ascending=False).reset_index(drop=True)
    return stats


# ── Rating color helper ──────────────────────────────────────────────────────

def rating_color(rating: float) -> str:
    """Return a hex color for a rating value (1-10 scale)."""
    if rating >= 8.0:
        return "#4CAF50"   # Excellent — green
    elif rating >= 7.0:
        return "#8BC34A"   # Good — light green
    elif rating >= 6.0:
        return "#FFC107"   # Average — amber
    elif rating >= 5.0:
        return "#FF9800"   # Below average — orange
    else:
        return "#F44336"   # Poor — red
