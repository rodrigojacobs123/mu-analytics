"""Goal build-up sequence extraction — traces each goal back to its origin."""

import pandas as pd

from config import (
    EVENT_PASS, EVENT_GOAL, EVENT_CORNER, EVENT_FOUL, EVENT_OUT,
    EVENT_TAKE_ON, EVENT_BALL_RECOVERY, EVENT_INTERCEPTION,
    EVENT_AERIAL, EVENT_CLEARANCE, EVENT_BALL_TOUCH,
    EVENT_MISS, EVENT_POST, EVENT_ATTEMPT_SAVED,
    QUAL_PASS_END_X, QUAL_PASS_END_Y, QUAL_PENALTY, QUAL_OWN_GOAL,
)

# Events that belong to a possession sequence (attacking team)
_POSSESSION_TYPES = {
    EVENT_PASS, EVENT_TAKE_ON, EVENT_BALL_RECOVERY, EVENT_AERIAL,
    EVENT_BALL_TOUCH, EVENT_CLEARANCE, EVENT_CORNER,
    EVENT_MISS, EVENT_POST, EVENT_ATTEMPT_SAVED, EVENT_GOAL,
}

# Max events / seconds to trace back
_LOOKBACK_EVENTS = 30
_LOOKBACK_SECS = 60


def _get_qualifier(quals: list[dict], qid: int):
    for q in quals:
        if q.get("qualifierId") == qid:
            return q.get("value")
    return None


def _event_time_secs(e: dict) -> int:
    return int(e.get("timeMin", 0)) * 60 + int(e.get("timeSec", 0))


def extract_goal_buildups(events: list[dict]) -> list[dict]:
    """Extract build-up sequences for every goal in the match.

    Returns a list of dicts, one per goal:
        goal_minute, goal_second, scorer, team_id,
        origin (OPEN_PLAY / CORNER / FREE_KICK / THROW_IN / PENALTY / OWN_GOAL),
        sequence (list of event dicts with x, y, end_x, end_y, player_name, typeId),
        duration_secs
    """
    # Index goal events
    goal_indices = [
        i for i, e in enumerate(events)
        if e.get("typeId") == EVENT_GOAL
    ]

    results = []
    for gi in goal_indices:
        goal_ev = events[gi]
        quals = goal_ev.get("qualifier", [])
        team_id = goal_ev.get("contestantId", "")
        goal_time = _event_time_secs(goal_ev)

        # Quick classification for penalties and own goals
        if _get_qualifier(quals, QUAL_PENALTY):
            results.append(_make_result(
                goal_ev, "PENALTY", [_event_to_row(goal_ev)], 0,
            ))
            continue
        if _get_qualifier(quals, QUAL_OWN_GOAL):
            results.append(_make_result(
                goal_ev, "OWN_GOAL", [_event_to_row(goal_ev)], 0,
            ))
            continue

        # Walk backwards to build the possession sequence
        sequence = []
        origin = "OPEN_PLAY"
        opp_streak = 0  # consecutive opponent events (allow skipping a few)

        for j in range(gi - 1, max(0, gi - _LOOKBACK_EVENTS) - 1, -1):
            ev = events[j]
            ev_time = _event_time_secs(ev)

            # Time window guard
            if (goal_time - ev_time) > _LOOKBACK_SECS:
                break

            ev_team = ev.get("contestantId", "")
            ev_type = ev.get("typeId")

            # Opponent event handling — skip defensive touches (saves, blocks)
            # but stop on true possession change (successful pass, clearance)
            if ev_team != team_id:
                # Opponent foul = free kick for us → origin
                if ev_type == EVENT_FOUL:
                    origin = "FREE_KICK"
                    sequence.insert(0, _event_to_row(ev))
                    break
                # Allow skipping up to 3 opponent defensive touches
                opp_streak += 1
                if opp_streak > 3:
                    break
                # Stop if opponent makes a successful pass (real possession)
                if ev_type == EVENT_PASS and int(ev.get("outcome", 0)) == 1:
                    break
                if ev_type == EVENT_CLEARANCE:
                    break
                continue  # skip this opponent event

            # Reset opponent streak when we see our own event
            opp_streak = 0

            # Corner — set piece origin
            if ev_type == EVENT_CORNER:
                origin = "CORNER"
                sequence.insert(0, _event_to_row(ev))
                break

            # Throw-in (OUT event by same team)
            if ev_type == EVENT_OUT:
                origin = "THROW_IN"
                sequence.insert(0, _event_to_row(ev))
                break

            # Ball recovery or interception = start of attacking move
            if ev_type in (EVENT_BALL_RECOVERY, EVENT_INTERCEPTION):
                sequence.insert(0, _event_to_row(ev))
                break

            # Accumulate possession events
            if ev_type in _POSSESSION_TYPES or ev_type == EVENT_FOUL:
                sequence.insert(0, _event_to_row(ev))

        # Add the goal event itself at the end
        sequence.append(_event_to_row(goal_ev))

        duration = (goal_time - _event_time_secs(events[max(0, gi - len(sequence) + 1)])) if len(sequence) > 1 else 0

        results.append(_make_result(goal_ev, origin, sequence, duration))

    return results


def _event_to_row(e: dict) -> dict:
    """Convert a raw event to a simplified row for the build-up sequence."""
    quals = e.get("qualifier", [])
    end_x = _get_qualifier(quals, QUAL_PASS_END_X)
    end_y = _get_qualifier(quals, QUAL_PASS_END_Y)
    return {
        "event_id": e.get("eventId", ""),
        "typeId": e.get("typeId"),
        "minute": int(e.get("timeMin", 0)),
        "second": int(e.get("timeSec", 0)),
        "player_name": e.get("playerName", ""),
        "player_id": e.get("playerId", ""),
        "team_id": e.get("contestantId", ""),
        "x": float(e.get("x", 0)),
        "y": float(e.get("y", 0)),
        "end_x": float(end_x) if end_x else None,
        "end_y": float(end_y) if end_y else None,
        "outcome": int(e.get("outcome", 0)),
    }


def _make_result(goal_ev: dict, origin: str, sequence: list[dict],
                 duration: int) -> dict:
    return {
        "goal_minute": int(goal_ev.get("timeMin", 0)),
        "goal_second": int(goal_ev.get("timeSec", 0)),
        "scorer": goal_ev.get("playerName", ""),
        "scorer_id": goal_ev.get("playerId", ""),
        "team_id": goal_ev.get("contestantId", ""),
        "origin": origin,
        "sequence": sequence,
        "duration_secs": duration,
        "n_passes": sum(1 for s in sequence if s["typeId"] == EVENT_PASS),
    }
