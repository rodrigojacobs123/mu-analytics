"""Team gap analysis and scouting recommendations using position-specific ratings."""

import pandas as pd
import numpy as np
from config import POSITION_CATEGORY_DISPLAY
from processing.player_ratings import POSITION_ATTR_KEYS, LEGACY_MAPPING


# Key attributes per position group (for gap detection) — now position-specific
KEY_ATTRIBUTES = {
    "Goalkeeper": ["GK_ShotStop", "GK_Dist", "GK_Command"],
    "Defender":   ["DEF_Tackle", "DEF_Position", "DEF_BallPlay"],
    "Midfielder": ["MID_Pass", "MID_Create", "MID_DefWork"],
    "Forward":    ["FWD_Finish", "FWD_Chance", "FWD_Dribble"],
    "Attacker":   ["FWD_Finish", "FWD_Chance", "FWD_Dribble"],
}


def _get_pos_attrs(position: str) -> list[str]:
    """Return position-specific attribute keys + OVR for analysis."""
    keys = POSITION_ATTR_KEYS.get(position, POSITION_ATTR_KEYS.get("Midfielder", []))
    return keys + ["OVR"]


def compute_team_gaps(ratings_df: pd.DataFrame, team_name: str) -> pd.DataFrame:
    """Compare a team's position-group ratings against the league average.

    Uses position-specific attributes (e.g. GK_ShotStop for Goalkeepers)
    instead of generic PAC/SHO/PAS/DRI/DEF/PHY.

    Returns DataFrame with: position, attribute, display_name, team_avg,
                            league_avg, gap, gap_pct
    Sorted by gap (most negative = biggest weakness).
    """
    if ratings_df.empty:
        return pd.DataFrame()

    team_df = ratings_df[ratings_df["equipo"] == team_name].copy()
    if team_df.empty:
        # Fuzzy match on first word
        team_df = ratings_df[ratings_df["equipo"].str.contains(
            team_name.split()[0], na=False, case=False
        )]

    if team_df.empty:
        return pd.DataFrame()

    rows = []
    for pos in ratings_df["posicion"].dropna().unique():
        team_pos = team_df[team_df["posicion"] == pos]
        league_pos = ratings_df[ratings_df["posicion"] == pos]

        if team_pos.empty or league_pos.empty:
            continue

        attrs = _get_pos_attrs(pos)
        for attr in attrs:
            if attr not in team_pos.columns:
                continue
            team_vals = team_pos[attr].dropna()
            league_vals = league_pos[attr].dropna()
            if team_vals.empty or league_vals.empty:
                continue

            team_avg = team_vals.mean()
            league_avg = league_vals.mean()
            gap = team_avg - league_avg
            gap_pct = (gap / league_avg * 100) if league_avg > 0 else 0

            rows.append({
                "position": pos,
                "attribute": attr,
                "display_name": POSITION_CATEGORY_DISPLAY.get(attr, attr),
                "team_avg": round(team_avg, 1),
                "league_avg": round(league_avg, 1),
                "gap": round(gap, 1),
                "gap_pct": round(gap_pct, 1),
            })

    result = pd.DataFrame(rows)
    if not result.empty:
        result = result.sort_values("gap").reset_index(drop=True)
    return result


def compute_position_depth(ratings_df: pd.DataFrame, team_name: str) -> pd.DataFrame:
    """Analyze squad depth: count and avg OVR per position.

    Returns DataFrame: position, count, avg_ovr, min_ovr, max_ovr, depth_rating
    depth_rating = "Strong" (4+ players, avg > league), "Adequate" (2-3),
                   "Thin" (1), "Empty" (0)
    """
    if ratings_df.empty:
        return pd.DataFrame()

    team_df = ratings_df[ratings_df["equipo"] == team_name].copy()
    if team_df.empty:
        team_df = ratings_df[ratings_df["equipo"].str.contains(
            team_name.split()[0], na=False, case=False
        )]

    if team_df.empty:
        return pd.DataFrame()

    rows = []
    for pos in sorted(team_df["posicion"].dropna().unique()):
        pos_players = team_df[team_df["posicion"] == pos]
        count = len(pos_players)
        avg_ovr = pos_players["OVR"].mean()
        min_ovr = pos_players["OVR"].min()
        max_ovr = pos_players["OVR"].max()

        if count >= 4 and avg_ovr >= 65:
            depth = "Strong"
        elif count >= 2:
            depth = "Adequate"
        elif count == 1:
            depth = "Thin"
        else:
            depth = "Empty"

        rows.append({
            "position": pos,
            "count": count,
            "avg_ovr": round(avg_ovr, 1),
            "min_ovr": int(min_ovr),
            "max_ovr": int(max_ovr),
            "depth_rating": depth,
        })

    return pd.DataFrame(rows).sort_values("avg_ovr", ascending=False).reset_index(drop=True)


def find_recommendations(ratings_df: pd.DataFrame, team_name: str,
                         top_n: int = 5) -> pd.DataFrame:
    """Find league players who could strengthen the team's weakest positions.

    Identifies positions where the team is below league average, then finds
    top-rated players from OTHER teams in those positions.

    Returns DataFrame: nombre, equipo, posicion, OVR, key_attribute,
                       key_display, key_value, fills_gap
    """
    if ratings_df.empty:
        return pd.DataFrame()

    gaps = compute_team_gaps(ratings_df, team_name)
    if gaps.empty:
        return pd.DataFrame()

    team_df = ratings_df[ratings_df["equipo"] == team_name]
    if team_df.empty:
        team_df = ratings_df[ratings_df["equipo"].str.contains(
            team_name.split()[0], na=False, case=False
        )]

    # Find positions where team is weakest (OVR gap most negative)
    ovr_gaps = gaps[gaps["attribute"] == "OVR"].copy()
    weak_positions = ovr_gaps[ovr_gaps["gap"] < 0]["position"].tolist()

    if not weak_positions:
        # If team is above average everywhere, pick the lowest-gap positions
        weak_positions = ovr_gaps.nsmallest(3, "gap")["position"].tolist()

    # Find best available players from other teams
    other_teams = ratings_df[~ratings_df["equipo"].str.contains(
        team_name.split()[0], na=False, case=False
    )]

    recommendations = []
    for pos in weak_positions:
        # Get the most deficient attribute for this position (excluding OVR)
        pos_gaps = gaps[(gaps["position"] == pos) & (gaps["attribute"] != "OVR")]
        if pos_gaps.empty:
            key_attr = "OVR"
        else:
            key_attr = pos_gaps.iloc[0]["attribute"]  # Most negative gap

        key_display = POSITION_CATEGORY_DISPLAY.get(key_attr, key_attr)

        # Find top players from other teams in this position
        pos_players = other_teams[other_teams["posicion"] == pos].copy()
        if pos_players.empty:
            continue

        # Sort by the key attribute (prioritize filling the gap)
        if key_attr in pos_players.columns:
            pos_players = pos_players.sort_values(key_attr, ascending=False)
        else:
            pos_players = pos_players.sort_values("OVR", ascending=False)

        # Get position-specific attrs for display
        pos_attr_keys = POSITION_ATTR_KEYS.get(pos, [])

        for _, p in pos_players.head(top_n).iterrows():
            key_val = int(p.get(key_attr, 0)) if key_attr in p.index else 0

            rec = {
                "nombre": p.get("nombre", "Unknown"),
                "equipo": p.get("equipo", "Unknown"),
                "posicion": pos,
                "OVR": int(p.get("OVR", 0)),
                "key_attribute": key_attr,
                "key_display": key_display,
                "key_value": key_val,
                "fills_gap": f"{pos} ({key_display})",
            }

            # Add position-specific attributes
            for attr_key in pos_attr_keys:
                display = POSITION_CATEGORY_DISPLAY.get(attr_key, attr_key)
                val = p.get(attr_key)
                rec[display] = int(val) if pd.notna(val) else 40

            # Also include legacy for backward compat
            for legacy in ["PAC", "SHO", "PAS", "DRI", "DEF", "PHY"]:
                rec[legacy] = int(p.get(legacy, 40))

            recommendations.append(rec)

    result = pd.DataFrame(recommendations)
    if not result.empty:
        result = result.sort_values("OVR", ascending=False).reset_index(drop=True)
    return result


def find_players_by_role(ratings_df: pd.DataFrame, team_name: str,
                         sub_position: str, top_n: int = 10) -> pd.DataFrame:
    """Find top-rated players from other teams for a specific sub-position.

    Uses the 'sub_posicion' column (e.g., "Winger", "Full-Back", "DM")
    to filter candidates. Returns the same shape as find_recommendations().
    """
    from processing.player_ratings import SUB_TO_PARENT, POSITION_ATTR_KEYS

    if ratings_df.empty or "sub_posicion" not in ratings_df.columns:
        return pd.DataFrame()

    parent_pos = SUB_TO_PARENT.get(sub_position, "Midfielder")

    # Exclude the target team
    other = ratings_df[~ratings_df["equipo"].str.contains(
        team_name.split()[0], na=False, case=False
    )]

    candidates = other[other["sub_posicion"] == sub_position].copy()
    if candidates.empty:
        return pd.DataFrame()

    candidates = candidates.sort_values("OVR", ascending=False).head(top_n)

    pos_attr_keys = POSITION_ATTR_KEYS.get(parent_pos, [])
    recommendations = []
    for _, p in candidates.iterrows():
        # Pick the player's best attribute as the "key" highlight
        best_attr = "OVR"
        best_val = 0
        for k in pos_attr_keys:
            v = p.get(k, 0)
            if pd.notna(v) and v > best_val:
                best_val, best_attr = v, k

        key_display = POSITION_CATEGORY_DISPLAY.get(best_attr, best_attr)

        rec = {
            "nombre": p.get("nombre", "Unknown"),
            "equipo": p.get("equipo", "Unknown"),
            "posicion": parent_pos,
            "sub_posicion": sub_position,
            "OVR": int(p.get("OVR", 0)),
            "key_attribute": best_attr,
            "key_display": key_display,
            "key_value": int(best_val) if pd.notna(best_val) else 0,
            "fills_gap": f"{sub_position} (Top by OVR)",
        }

        # Add position-specific attributes
        for attr_key in pos_attr_keys:
            display = POSITION_CATEGORY_DISPLAY.get(attr_key, attr_key)
            val = p.get(attr_key)
            rec[display] = int(val) if pd.notna(val) else 40

        # Legacy for backward compat
        for legacy in ["PAC", "SHO", "PAS", "DRI", "DEF", "PHY"]:
            rec[legacy] = int(p.get(legacy, 40))

        recommendations.append(rec)

    result = pd.DataFrame(recommendations)
    if not result.empty:
        result = result.sort_values("OVR", ascending=False).reset_index(drop=True)
    return result


def compute_team_attribute_profile(ratings_df: pd.DataFrame,
                                   team_name: str) -> dict:
    """Compute average attribute profile for a team (for radar comparison).

    Returns dict: {PAC, SHO, PAS, DRI, DEF, PHY} as averages.
    Kept for backward compatibility.
    """
    if ratings_df.empty:
        return {}

    team_df = ratings_df[ratings_df["equipo"] == team_name]
    if team_df.empty:
        team_df = ratings_df[ratings_df["equipo"].str.contains(
            team_name.split()[0], na=False, case=False
        )]

    if team_df.empty:
        return {}

    attrs = ["PAC", "SHO", "PAS", "DRI", "DEF", "PHY"]
    return {attr: round(team_df[attr].mean(), 1)
            for attr in attrs if attr in team_df.columns}
