"""Formation extraction, change detection, and tactical metrics from Opta events."""

from collections import Counter
import pandas as pd
from data.event_parser import (
    extract_formation, extract_passes, extract_tackles,
    extract_interceptions, extract_ball_recoveries, extract_all_touches,
)
from config import (
    EVENT_FORMATION_CHANGE, EVENT_TEAM_SETUP,
    QUAL_FORMATION, QUAL_FORMATION_TYPE, OPTA_FORMATION_MAP,
)


def get_match_formations(events: list[dict], home_id: str, away_id: str) -> dict:
    """Extract formations for both teams in a match.

    Returns: {
        'home': {formation_str, starters, subs, ...},
        'away': {formation_str, starters, subs, ...},
    }
    """
    home_formation = extract_formation(events, home_id)
    away_formation = extract_formation(events, away_id)
    return {
        "home": home_formation,
        "away": away_formation,
    }


def detect_formation_changes(events: list[dict], team_id: str) -> list[dict]:
    """Detect all formation changes during a match (typeId=40).

    Uses qualifier 130 (FormationType) for the new formation, falling
    back to qualifier 44 row-value derivation if unavailable.

    Returns list of dicts: [{minute, period, formation_str}]
    """
    from data.event_parser import _get_qualifier

    changes = []
    for e in events:
        if e.get("typeId") != EVENT_FORMATION_CHANGE:
            continue
        if e.get("contestantId") != team_id:
            continue

        quals = e.get("qualifier", [])
        formation_type_id = _get_qualifier(quals, QUAL_FORMATION_TYPE)
        formation_str = OPTA_FORMATION_MAP.get(formation_type_id, "") if formation_type_id else ""

        if not formation_str:
            # Fallback: derive from qualifier 44 row values
            formation_raw = _get_qualifier(quals, QUAL_FORMATION)
            if not formation_raw:
                continue
            vals = [int(v.strip()) for v in formation_raw.split(",") if v.strip()]
            field_vals = [v for v in vals if 2 <= v <= 4]
            row_counts = Counter(field_vals)
            formation_str = "-".join(str(row_counts[r]) for r in sorted(row_counts.keys()))

        if not formation_str:
            continue

        changes.append({
            "minute": int(e.get("timeMin", 0)),
            "period": int(e.get("periodId", 0)),
            "formation_str": formation_str,
        })

    return changes


def compute_possession_zones(events: list[dict], team_id: str,
                             period: int | None = None) -> dict:
    """Compute possession broken down by thirds of the pitch.

    Returns dict with: {defensive_third, middle_third, attacking_third}
    as percentages (0-100).
    """
    touches = extract_all_touches(events, team_id)
    if touches.empty:
        return {"defensive_third": 33.3, "middle_third": 33.3, "attacking_third": 33.3}

    if period is not None:
        touches = touches[touches["period"] == period]

    if touches.empty:
        return {"defensive_third": 33.3, "middle_third": 33.3, "attacking_third": 33.3}

    total = len(touches)
    defensive = len(touches[touches["x"] < 33.33])
    middle = len(touches[(touches["x"] >= 33.33) & (touches["x"] < 66.66)])
    attacking = len(touches[touches["x"] >= 66.66])

    return {
        "defensive_third": round(defensive / total * 100, 1),
        "middle_third": round(middle / total * 100, 1),
        "attacking_third": round(attacking / total * 100, 1),
    }


def compute_ppda(events: list[dict], pressing_team_id: str,
                 opponent_id: str, period: int | None = None) -> float:
    """Compute PPDA (Passes Per Defensive Action) — a pressing intensity metric.

    Standard definition: opponent passes in own half / pressing team's
    defensive actions in opponent's half. Only tackles + interceptions
    count as pressing actions (ball recoveries excluded per convention).

    Lower PPDA = more intense pressing. Typical EPL range: 7-15.
    """
    # Opponent passes in their own half (x < 50 from their perspective)
    opp_passes = extract_passes(events, team_id=opponent_id)
    if period is not None and not opp_passes.empty:
        opp_passes = opp_passes[opp_passes["period"] == period]
    opp_passes_count = len(opp_passes[opp_passes["x"] < 50]) if not opp_passes.empty else 0

    # Pressing team's defensive actions IN OPPONENT'S HALF ONLY (x > 50)
    tackles = extract_tackles(events, pressing_team_id)
    interceptions = extract_interceptions(events, pressing_team_id)

    if period is not None:
        if not tackles.empty:
            tackles = tackles[tackles["period"] == period]
        if not interceptions.empty:
            interceptions = interceptions[interceptions["period"] == period]

    # Filter to opponent's half (pressing team x > 50 = in opponent territory)
    high_tackles = len(tackles[tackles["x"] > 50]) if not tackles.empty else 0
    high_interceptions = len(interceptions[interceptions["x"] > 50]) if not interceptions.empty else 0

    def_actions = high_tackles + high_interceptions
    if def_actions == 0:
        return 99.0  # No defensive actions in opponent's half = no press
    return round(opp_passes_count / def_actions, 1)


def compute_field_tilt(events: list[dict], team_id: str, opponent_id: str,
                       period: int | None = None) -> float:
    """Compute field tilt — % of total touches in the attacking third.

    Field tilt = team's attacking third touches / (team ATT + opponent ATT touches).
    Range: 0-100. Above 50 means territorial dominance.
    """
    team_touches = extract_all_touches(events, team_id)
    opp_touches = extract_all_touches(events, opponent_id)

    if period is not None:
        if not team_touches.empty:
            team_touches = team_touches[team_touches["period"] == period]
        if not opp_touches.empty:
            opp_touches = opp_touches[opp_touches["period"] == period]

    team_att = len(team_touches[team_touches["x"] >= 66.66]) if not team_touches.empty else 0
    opp_att = len(opp_touches[opp_touches["x"] >= 66.66]) if not opp_touches.empty else 0

    total_att = team_att + opp_att
    if total_att == 0:
        return 50.0
    return round(team_att / total_att * 100, 1)


def compute_tactical_kpis(events: list[dict], team_id: str, opponent_id: str,
                          period: int | None = None) -> dict:
    """Compute a suite of tactical KPIs for the selected team.

    Returns dict with: possession_pct, ppda, field_tilt,
    pass_accuracy, progressive_pass_count, high_press_recoveries,
    defensive_line_height.
    """
    # Possession
    team_touches = extract_all_touches(events, team_id)
    opp_touches = extract_all_touches(events, opponent_id)
    if period is not None:
        if not team_touches.empty:
            team_touches = team_touches[team_touches["period"] == period]
        if not opp_touches.empty:
            opp_touches = opp_touches[opp_touches["period"] == period]
    t_count = len(team_touches)
    o_count = len(opp_touches)
    poss = round(t_count / (t_count + o_count) * 100, 1) if (t_count + o_count) > 0 else 50.0

    # Pass accuracy
    passes = extract_passes(events, team_id=team_id)
    if period is not None and not passes.empty:
        passes = passes[passes["period"] == period]
    total_passes = len(passes)
    succ_passes = len(passes[passes["outcome"] == 1]) if not passes.empty else 0
    pass_acc = round(succ_passes / total_passes * 100, 1) if total_passes > 0 else 0

    # Progressive passes (> 25 yard progression)
    prog_count = 0
    if not passes.empty and "end_x" in passes.columns:
        prog = passes.dropna(subset=["end_x"])
        prog_count = len(prog[(prog["end_x"] - prog["x"]) > 25])

    # High press recoveries (opponent half, x > 50)
    recoveries = extract_ball_recoveries(events, team_id)
    if period is not None and not recoveries.empty:
        recoveries = recoveries[recoveries["period"] == period]
    high_recoveries = len(recoveries[recoveries["x"] > 50]) if not recoveries.empty else 0

    # Defensive line height — avg x of defensive actions
    tackles = extract_tackles(events, team_id)
    interceptions = extract_interceptions(events, team_id)
    if period is not None:
        if not tackles.empty:
            tackles = tackles[tackles["period"] == period]
        if not interceptions.empty:
            interceptions = interceptions[interceptions["period"] == period]

    def_x_vals = []
    if not tackles.empty:
        def_x_vals.extend(tackles["x"].tolist())
    if not interceptions.empty:
        def_x_vals.extend(interceptions["x"].tolist())
    avg_def_line = round(sum(def_x_vals) / len(def_x_vals), 1) if def_x_vals else 45.0

    return {
        "possession_pct": poss,
        "ppda": compute_ppda(events, team_id, opponent_id, period),
        "field_tilt": compute_field_tilt(events, team_id, opponent_id, period),
        "pass_accuracy": pass_acc,
        "total_passes": total_passes,
        "progressive_passes": prog_count,
        "high_press_recoveries": high_recoveries,
        "defensive_line_height": avg_def_line,
    }
