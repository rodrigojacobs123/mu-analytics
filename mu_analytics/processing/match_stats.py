"""Match-level stat aggregation for comparison bars."""

from data.event_parser import (
    extract_shots, extract_passes, extract_tackles,
    extract_interceptions, extract_all_touches,
)
from config import (
    EVENT_CORNER, EVENT_FOUL, SHOT_TYPE_IDS, EVENT_GOAL, EVENT_ATTEMPT_SAVED,
)


def crest_url(team_id: str) -> str:
    """Build the Opta badge/crest URL for any team given its ID."""
    return (
        "https://omo.akamai.opta.net/image.php?h=www.scoresway.com"
        "&sport=football&entity=team&description=badges&dimensions=150"
        f"&id={team_id}"
    )


def _count_events(events: list[dict], type_id: int, team_id: str) -> int:
    """Count events of a given type for a team."""
    return sum(
        1 for e in events
        if e.get("typeId") == type_id and e.get("contestantId") == team_id
    )


def _pct_pair(home_val: float, away_val: float) -> tuple[float, float]:
    """Normalize two values to percentages that sum to 100."""
    total = home_val + away_val
    if total == 0:
        return 50.0, 50.0
    return round(home_val / total * 100, 1), round(away_val / total * 100, 1)


def _fmt(value, fmt: str) -> str:
    """Format a value for display."""
    if fmt == "pct":
        return f"{value:.0f}%"
    if fmt == "float1":
        return f"{value:.1f}"
    return str(int(value))


def compute_match_stats(events: list[dict], home_id: str, away_id: str) -> list[dict]:
    """Compute aggregated match statistics for both teams.

    Returns list of dicts for stats_comparison_table(), each with:
        label, home_value, away_value, home_pct, away_pct, format
    """
    # Possession — approximate via touch event ratio
    touches_h = extract_all_touches(events, home_id)
    touches_a = extract_all_touches(events, away_id)
    poss_h = len(touches_h)
    poss_a = len(touches_a)
    poss_h_pct, poss_a_pct = _pct_pair(poss_h, poss_a)

    # Total shots
    shots_h = extract_shots(events, home_id)
    shots_a = extract_shots(events, away_id)

    # Shots on target (goals + saved)
    sot_h = len(shots_h[shots_h["outcome"].isin(["Goal", "Saved"])]) if not shots_h.empty else 0
    sot_a = len(shots_a[shots_a["outcome"].isin(["Goal", "Saved"])]) if not shots_a.empty else 0

    # Passes & accuracy
    all_passes_h = extract_passes(events, home_id)
    all_passes_a = extract_passes(events, away_id)
    succ_h = len(all_passes_h[all_passes_h["outcome"] == 1]) if not all_passes_h.empty else 0
    succ_a = len(all_passes_a[all_passes_a["outcome"] == 1]) if not all_passes_a.empty else 0
    acc_h = (succ_h / len(all_passes_h) * 100) if len(all_passes_h) > 0 else 0
    acc_a = (succ_a / len(all_passes_a) * 100) if len(all_passes_a) > 0 else 0

    # Corners & fouls
    corners_h = _count_events(events, EVENT_CORNER, home_id)
    corners_a = _count_events(events, EVENT_CORNER, away_id)
    fouls_h = _count_events(events, EVENT_FOUL, home_id)
    fouls_a = _count_events(events, EVENT_FOUL, away_id)

    # Tackles won
    tackles_h = extract_tackles(events, home_id)
    tackles_a = extract_tackles(events, away_id)
    tw_h = len(tackles_h[tackles_h["outcome"] == 1]) if not tackles_h.empty else 0
    tw_a = len(tackles_a[tackles_a["outcome"] == 1]) if not tackles_a.empty else 0

    # Interceptions
    inter_h = extract_interceptions(events, home_id)
    inter_a = extract_interceptions(events, away_id)

    def _stat(label, hv, av, fmt="int"):
        hp, ap = _pct_pair(hv, av)
        return {"label": label, "home_value": hv, "away_value": av,
                "home_pct": hp, "away_pct": ap, "format": fmt}

    return [
        {"label": "Possession", "home_value": poss_h_pct, "away_value": poss_a_pct,
         "home_pct": poss_h_pct, "away_pct": poss_a_pct, "format": "pct"},
        _stat("Total Shots", len(shots_h), len(shots_a)),
        _stat("Shots on Target", sot_h, sot_a),
        _stat("Passes", len(all_passes_h), len(all_passes_a)),
        {"label": "Pass Accuracy", "home_value": acc_h, "away_value": acc_a,
         "home_pct": acc_h, "away_pct": acc_a, "format": "pct"},
        _stat("Corners", corners_h, corners_a),
        _stat("Fouls", fouls_h, fouls_a),
        _stat("Tackles Won", tw_h, tw_a),
        _stat("Interceptions", len(inter_h), len(inter_a)),
    ]
