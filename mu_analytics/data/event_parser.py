"""Opta event JSON parser — extracts shots, passes, tackles, etc. into DataFrames."""

import pandas as pd
from config import (
    EVENT_PASS, EVENT_GOAL, EVENT_MISS, EVENT_POST, EVENT_ATTEMPT_SAVED,
    EVENT_TAKE_ON, EVENT_TACKLE, EVENT_INTERCEPTION, EVENT_CARD,
    EVENT_TEAM_SETUP, EVENT_PLAYER_OFF, EVENT_PLAYER_ON,
    EVENT_BALL_RECOVERY, EVENT_CLEARANCE, EVENT_CORNER, EVENT_FOUL,
    EVENT_AERIAL, EVENT_SAVE,
    SHOT_TYPE_IDS, QUAL_XG, QUAL_BODY_PART, QUAL_SHOT_DISTANCE, QUAL_SHOT_ANGLE,
    QUAL_ASSIST, QUAL_PENALTY, QUAL_OWN_GOAL, QUAL_PASS_END_X, QUAL_PASS_END_Y,
    QUAL_FORMATION, QUAL_FORMATION_TYPE, QUAL_PLAYER_IDS, QUAL_SHIRT_NUMBERS,
    QUAL_PLAYER_POSITION,
    QUAL_INVOLVED_PLAYER, QUAL_ZONE, QUAL_HEAD, SHOT_OUTCOME_MAP,
    QUAL_CORNER_TYPE, OPTA_FORMATION_MAP,
)
from processing.xg_model import estimate_xg, PENALTY_XG


def _get_qualifier(qualifiers: list[dict], type_id: int) -> str | None:
    """Extract a qualifier value by its typeId from the qualifiers list."""
    for q in qualifiers:
        if q.get("qualifierId") == type_id:
            return q.get("value", "1")  # boolean qualifiers have no value
    return None


def _has_qualifier(qualifiers: list[dict], type_id: int) -> bool:
    """Check if a qualifier exists."""
    return any(q.get("qualifierId") == type_id for q in qualifiers)


def parse_match_info(raw: dict) -> dict:
    """Extract match metadata from the raw JSON."""
    info = raw.get("matchInfo", {})
    live = raw.get("liveData", {})
    details = live.get("matchDetails", {})
    scores = details.get("scores", {})
    total = scores.get("total", {})
    ht = scores.get("ht", {})
    contestants = info.get("contestant", [])

    home = next((c for c in contestants if c.get("position") == "home"), {})
    away = next((c for c in contestants if c.get("position") == "away"), {})
    venue = info.get("venue", {})

    # Match status: "Played" = finished, "Fixture" = not yet played
    match_status = details.get("matchStatus", "")

    return {
        "match_id": info.get("id", ""),
        "date": info.get("date", ""),
        "time": info.get("time", ""),
        "matchday": int(info.get("week", 0)),
        "home_team": home.get("name", ""),
        "away_team": away.get("name", ""),
        "home_id": home.get("id", ""),
        "away_id": away.get("id", ""),
        "home_code": home.get("code", ""),
        "away_code": away.get("code", ""),
        "home_score": int(total.get("home", 0)),
        "away_score": int(total.get("away", 0)),
        "ht_home": int(ht.get("home", 0)),
        "ht_away": int(ht.get("away", 0)),
        "venue": venue.get("shortName", venue.get("longName", "")),
        "winner": details.get("winner", ""),
        "match_length_min": details.get("matchLengthMin", 90),
        "match_status": match_status,
    }


def extract_shots(events: list[dict], team_id: str | None = None) -> pd.DataFrame:
    """Extract all shot events into a DataFrame with xG, outcome, position.

    xG resolution order:
      1. Opta qualifier 395 (only present on goals) → divide by 100
      2. Penalty detected → use standard PENALTY_XG (0.76)
      3. Positional estimate from ``processing.xg_model.estimate_xg``
    """
    rows = []
    for e in events:
        tid = e.get("typeId")
        if tid not in SHOT_TYPE_IDS:
            continue
        if team_id and e.get("contestantId") != team_id:
            continue

        quals = e.get("qualifier", [])
        sx = float(e.get("x", 0))
        sy = float(e.get("y", 0))
        is_header = _has_qualifier(quals, QUAL_HEAD)
        is_own_goal = _has_qualifier(quals, QUAL_OWN_GOAL)

        # ── Resolve xG ─────────────────────────────────────────────
        xg_raw = _get_qualifier(quals, QUAL_XG)
        if xg_raw is not None:
            # Opta stores xG as a percentage (e.g. 97.5 → 0.975)
            xg = float(xg_raw) / 100.0
        elif is_own_goal:
            xg = 0.0   # own-goals don't carry xG
        else:
            # Positional estimate (distance + angle + header)
            xg = estimate_xg(sx, sy, is_header=is_header)

        body = _get_qualifier(quals, QUAL_ZONE)
        distance = _get_qualifier(quals, QUAL_SHOT_DISTANCE)
        angle = _get_qualifier(quals, QUAL_SHOT_ANGLE)

        rows.append({
            "event_id": e.get("eventId"),
            "type_id": tid,
            "minute": int(e.get("timeMin", 0)),
            "second": int(e.get("timeSec", 0)),
            "team_id": e.get("contestantId", ""),
            "player_id": e.get("playerId", ""),
            "player_name": e.get("playerName", ""),
            "x": sx,
            "y": sy,
            "xg": xg,
            "outcome": SHOT_OUTCOME_MAP.get(tid, "Unknown"),
            "body_part": body or "Unknown",
            "distance": float(distance) if distance else None,
            "angle": float(angle) if angle else None,
            "is_header": is_header,
            "is_own_goal": is_own_goal,
            "period": int(e.get("periodId", 0)),
        })
    return pd.DataFrame(rows)


def extract_passes(events: list[dict], team_id: str | None = None,
                   successful_only: bool = False) -> pd.DataFrame:
    """Extract pass events. Optionally filter to successful passes only."""
    rows = []
    for e in events:
        if e.get("typeId") != EVENT_PASS:
            continue
        if team_id and e.get("contestantId") != team_id:
            continue
        outcome = int(e.get("outcome", 0))
        if successful_only and outcome != 1:
            continue

        quals = e.get("qualifier", [])
        end_x = _get_qualifier(quals, QUAL_PASS_END_X)
        end_y = _get_qualifier(quals, QUAL_PASS_END_Y)
        receiver_id = _get_qualifier(quals, QUAL_INVOLVED_PLAYER)

        rows.append({
            "event_id": e.get("eventId"),
            "minute": int(e.get("timeMin", 0)),
            "second": int(e.get("timeSec", 0)),
            "team_id": e.get("contestantId", ""),
            "player_id": e.get("playerId", ""),
            "player_name": e.get("playerName", ""),
            "x": float(e.get("x", 0)),
            "y": float(e.get("y", 0)),
            "end_x": float(end_x) if end_x else None,
            "end_y": float(end_y) if end_y else None,
            "receiver_id": receiver_id,
            "outcome": outcome,
            "period": int(e.get("periodId", 0)),
        })
    return pd.DataFrame(rows)


def extract_goals(events: list[dict]) -> pd.DataFrame:
    """Extract goal events with full detail."""
    rows = []
    for e in events:
        if e.get("typeId") != EVENT_GOAL:
            continue
        quals = e.get("qualifier", [])
        xg_raw = _get_qualifier(quals, QUAL_XG)
        sx = float(e.get("x", 0))
        sy = float(e.get("y", 0))
        is_header = _has_qualifier(quals, QUAL_HEAD)
        is_own_goal = _has_qualifier(quals, QUAL_OWN_GOAL)

        # Resolve xG (same logic as extract_shots)
        if xg_raw is not None:
            xg = float(xg_raw) / 100.0
        elif is_own_goal:
            xg = 0.0
        else:
            xg = estimate_xg(sx, sy, is_header=is_header)

        rows.append({
            "event_id": e.get("eventId"),
            "minute": int(e.get("timeMin", 0)),
            "second": int(e.get("timeSec", 0)),
            "team_id": e.get("contestantId", ""),
            "player_id": e.get("playerId", ""),
            "player_name": e.get("playerName", ""),
            "x": sx,
            "y": sy,
            "xg": xg,
            "is_penalty": _has_qualifier(quals, QUAL_PENALTY),
            "is_own_goal": is_own_goal,
            "has_assist": _has_qualifier(quals, QUAL_ASSIST),
            "period": int(e.get("periodId", 0)),
        })
    return pd.DataFrame(rows)


def extract_cards(events: list[dict]) -> pd.DataFrame:
    """Extract card events (yellow, red, second yellow)."""
    rows = []
    for e in events:
        if e.get("typeId") != EVENT_CARD:
            continue
        quals = e.get("qualifier", [])
        card_type = _get_qualifier(quals, 32)  # qualifier 32 = card type

        rows.append({
            "event_id": e.get("eventId"),
            "minute": int(e.get("timeMin", 0)),
            "team_id": e.get("contestantId", ""),
            "player_id": e.get("playerId", ""),
            "player_name": e.get("playerName", ""),
            "card_type": card_type or "Yellow",
            "period": int(e.get("periodId", 0)),
        })
    return pd.DataFrame(rows)


def extract_substitutions(events: list[dict]) -> pd.DataFrame:
    """Extract substitution events (player on/off)."""
    rows = []
    for e in events:
        tid = e.get("typeId")
        if tid not in (EVENT_PLAYER_ON, EVENT_PLAYER_OFF):
            continue
        rows.append({
            "event_id": e.get("eventId"),
            "minute": int(e.get("timeMin", 0)),
            "team_id": e.get("contestantId", ""),
            "player_id": e.get("playerId", ""),
            "player_name": e.get("playerName", ""),
            "type": "on" if tid == EVENT_PLAYER_ON else "off",
            "period": int(e.get("periodId", 0)),
        })
    return pd.DataFrame(rows)


def extract_tackles(events: list[dict], team_id: str | None = None) -> pd.DataFrame:
    """Extract tackle events with positions."""
    rows = []
    for e in events:
        if e.get("typeId") != EVENT_TACKLE:
            continue
        if team_id and e.get("contestantId") != team_id:
            continue
        rows.append({
            "minute": int(e.get("timeMin", 0)),
            "team_id": e.get("contestantId", ""),
            "player_id": e.get("playerId", ""),
            "player_name": e.get("playerName", ""),
            "x": float(e.get("x", 0)),
            "y": float(e.get("y", 0)),
            "outcome": int(e.get("outcome", 0)),
            "period": int(e.get("periodId", 0)),
        })
    return pd.DataFrame(rows)


def extract_interceptions(events: list[dict], team_id: str | None = None) -> pd.DataFrame:
    """Extract interception events with positions."""
    rows = []
    for e in events:
        if e.get("typeId") != EVENT_INTERCEPTION:
            continue
        if team_id and e.get("contestantId") != team_id:
            continue
        rows.append({
            "minute": int(e.get("timeMin", 0)),
            "team_id": e.get("contestantId", ""),
            "player_id": e.get("playerId", ""),
            "player_name": e.get("playerName", ""),
            "x": float(e.get("x", 0)),
            "y": float(e.get("y", 0)),
            "outcome": int(e.get("outcome", 0)),
            "period": int(e.get("periodId", 0)),
        })
    return pd.DataFrame(rows)


def extract_ball_recoveries(events: list[dict], team_id: str | None = None) -> pd.DataFrame:
    """Extract ball recovery events for pressing analysis."""
    rows = []
    for e in events:
        if e.get("typeId") != EVENT_BALL_RECOVERY:
            continue
        if team_id and e.get("contestantId") != team_id:
            continue
        rows.append({
            "minute": int(e.get("timeMin", 0)),
            "team_id": e.get("contestantId", ""),
            "player_id": e.get("playerId", ""),
            "player_name": e.get("playerName", ""),
            "x": float(e.get("x", 0)),
            "y": float(e.get("y", 0)),
            "period": int(e.get("periodId", 0)),
        })
    return pd.DataFrame(rows)


def extract_take_ons(events: list[dict], team_id: str | None = None) -> pd.DataFrame:
    """Extract take-on (dribble) events with positions and outcomes."""
    rows = []
    for e in events:
        if e.get("typeId") != EVENT_TAKE_ON:
            continue
        if team_id and e.get("contestantId") != team_id:
            continue
        rows.append({
            "minute": int(e.get("timeMin", 0)),
            "team_id": e.get("contestantId", ""),
            "player_id": e.get("playerId", ""),
            "player_name": e.get("playerName", ""),
            "x": float(e.get("x", 0)),
            "y": float(e.get("y", 0)),
            "outcome": int(e.get("outcome", 0)),
            "period": int(e.get("periodId", 0)),
        })
    return pd.DataFrame(rows)


def extract_aerials(events: list[dict], team_id: str | None = None) -> pd.DataFrame:
    """Extract aerial duel events with positions and outcomes."""
    rows = []
    for e in events:
        if e.get("typeId") != EVENT_AERIAL:
            continue
        if team_id and e.get("contestantId") != team_id:
            continue
        rows.append({
            "minute": int(e.get("timeMin", 0)),
            "team_id": e.get("contestantId", ""),
            "player_id": e.get("playerId", ""),
            "player_name": e.get("playerName", ""),
            "x": float(e.get("x", 0)),
            "y": float(e.get("y", 0)),
            "outcome": int(e.get("outcome", 0)),
            "period": int(e.get("periodId", 0)),
        })
    return pd.DataFrame(rows)


def extract_all_touches(events: list[dict], team_id: str | None = None) -> pd.DataFrame:
    """Extract all events with x,y for a team — used for heatmaps."""
    rows = []
    for e in events:
        if team_id and e.get("contestantId") != team_id:
            continue
        x = e.get("x")
        y = e.get("y")
        if x is None or y is None:
            continue
        rows.append({
            "minute": int(e.get("timeMin", 0)),
            "team_id": e.get("contestantId", ""),
            "player_id": e.get("playerId", ""),
            "player_name": e.get("playerName", ""),
            "x": float(x),
            "y": float(y),
            "type_id": e.get("typeId"),
            "period": int(e.get("periodId", 0)),
        })
    return pd.DataFrame(rows)


def extract_formation(events: list[dict], team_id: str) -> dict | None:
    """Extract formation from typeId=34 (team setup) event for a team.

    Uses qualifier 130 (FormationType ID) for the formation string when
    available, falling back to qualifier 44 row-value derivation.  Qualifier
    44's 3-row system (DEF/MID/FWD) collapses multi-row formations like
    4-2-3-1 into "4-5-1", so qualifier 130 is strongly preferred.

    Returns dict with formation_str, starters, subs, raw_positions.
    """
    from collections import Counter

    for e in events:
        if e.get("typeId") != EVENT_TEAM_SETUP:
            continue
        if e.get("contestantId") != team_id:
            continue

        quals = e.get("qualifier", [])
        formation_raw = _get_qualifier(quals, QUAL_FORMATION)
        formation_type_id = _get_qualifier(quals, QUAL_FORMATION_TYPE)
        player_ids_raw = _get_qualifier(quals, QUAL_PLAYER_IDS)
        shirt_nums_raw = _get_qualifier(quals, QUAL_SHIRT_NUMBERS)

        if not formation_raw or not player_ids_raw:
            continue

        formation_vals = [int(v.strip()) for v in formation_raw.split(",")]
        player_ids = [v.strip() for v in player_ids_raw.split(",")]
        shirt_nums = [v.strip() for v in shirt_nums_raw.split(",")] if shirt_nums_raw else []

        # Build starter / sub lists from qualifier 44 row values
        starters = []
        subs = []
        for i, pos in enumerate(formation_vals):
            pid = player_ids[i] if i < len(player_ids) else ""
            shirt = shirt_nums[i] if i < len(shirt_nums) else ""
            entry = {"player_id": pid, "shirt": shirt, "position_row": pos}
            if 1 <= pos <= 4:
                starters.append(entry)
            else:
                subs.append(entry)

        # Determine formation string: prefer qualifier 130 lookup
        formation_str = OPTA_FORMATION_MAP.get(formation_type_id, "") if formation_type_id else ""

        if not formation_str:
            # Fallback: derive from qualifier 44 row values (less precise)
            field_rows = [v for v in formation_vals if 2 <= v <= 4]
            row_counts = Counter(field_rows)
            formation_str = "-".join(str(row_counts[r]) for r in sorted(row_counts.keys()))

        return {
            "formation_str": formation_str,
            "starters": starters,
            "subs": subs,
            "raw_positions": formation_vals,
        }

    return None


def extract_key_events(events: list[dict]) -> pd.DataFrame:
    """Extract goals, cards, and substitutions for a match timeline."""
    key_types = {EVENT_GOAL, EVENT_CARD, EVENT_PLAYER_ON, EVENT_PLAYER_OFF}
    rows = []
    for e in events:
        tid = e.get("typeId")
        if tid not in key_types:
            continue

        event_label = {
            EVENT_GOAL: "Goal",
            EVENT_CARD: "Card",
            EVENT_PLAYER_ON: "Sub On",
            EVENT_PLAYER_OFF: "Sub Off",
        }.get(tid, "Other")

        rows.append({
            "minute": int(e.get("timeMin", 0)),
            "second": int(e.get("timeSec", 0)),
            "team_id": e.get("contestantId", ""),
            "player_name": e.get("playerName", ""),
            "event_type": event_label,
            "period": int(e.get("periodId", 0)),
        })
    return pd.DataFrame(rows)


def extract_corners(events: list[dict], team_id: str | None = None) -> pd.DataFrame:
    """Extract corner-kick events with delivery type from qualifier 56."""
    rows = []
    for e in events:
        if e.get("typeId") != EVENT_CORNER:
            continue
        if team_id and e.get("contestantId") != team_id:
            continue
        quals = e.get("qualifier", [])
        delivery = _get_qualifier(quals, QUAL_CORNER_TYPE) or "Unknown"
        rows.append({
            "minute": int(e.get("timeMin", 0)),
            "second": int(e.get("timeSec", 0)),
            "team_id": e.get("contestantId", ""),
            "player_id": e.get("playerId", ""),
            "player_name": e.get("playerName", ""),
            "x": float(e.get("x", 0)),
            "y": float(e.get("y", 0)),
            "delivery_type": delivery,
            "period": int(e.get("periodId", 0)),
        })
    return pd.DataFrame(rows)


def extract_fouls(events: list[dict], team_id: str | None = None) -> pd.DataFrame:
    """Extract foul events (the team that *committed* the foul).

    To find fouls *won* by a team, call with the opponent's team_id,
    or filter the result by the opposing team_id.
    """
    rows = []
    for e in events:
        if e.get("typeId") != EVENT_FOUL:
            continue
        if team_id and e.get("contestantId") != team_id:
            continue
        rows.append({
            "minute": int(e.get("timeMin", 0)),
            "second": int(e.get("timeSec", 0)),
            "team_id": e.get("contestantId", ""),
            "player_id": e.get("playerId", ""),
            "player_name": e.get("playerName", ""),
            "x": float(e.get("x", 0)),
            "y": float(e.get("y", 0)),
            "outcome": int(e.get("outcome", 0)),
            "period": int(e.get("periodId", 0)),
        })
    return pd.DataFrame(rows)


def extract_clearances(events: list[dict], team_id: str | None = None) -> pd.DataFrame:
    """Extract clearance events (typeId=12)."""
    rows = []
    for e in events:
        if e.get("typeId") != EVENT_CLEARANCE:
            continue
        if team_id and e.get("contestantId") != team_id:
            continue
        rows.append({
            "minute": int(e.get("timeMin", 0)),
            "team_id": e.get("contestantId", ""),
            "player_id": e.get("playerId", ""),
            "player_name": e.get("playerName", ""),
            "x": float(e.get("x", 0)),
            "y": float(e.get("y", 0)),
            "outcome": int(e.get("outcome", 0)),
            "period": int(e.get("periodId", 0)),
        })
    return pd.DataFrame(rows)


def extract_saves(events: list[dict], team_id: str | None = None) -> pd.DataFrame:
    """Extract goalkeeper save events (typeId=10)."""
    rows = []
    for e in events:
        if e.get("typeId") != EVENT_SAVE:
            continue
        if team_id and e.get("contestantId") != team_id:
            continue
        rows.append({
            "minute": int(e.get("timeMin", 0)),
            "team_id": e.get("contestantId", ""),
            "player_id": e.get("playerId", ""),
            "player_name": e.get("playerName", ""),
            "x": float(e.get("x", 0)),
            "y": float(e.get("y", 0)),
            "outcome": int(e.get("outcome", 0)),
            "period": int(e.get("periodId", 0)),
        })
    return pd.DataFrame(rows)
