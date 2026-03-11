"""Position-specific player ratings with versatility detection.

Replaces generic PAC/SHO/PAS/DRI/DEF/PHY with position-aware metrics:
  - Goalkeeper:  Shot Stopping · Distribution · Command · Reflexes · Clean Sheets
  - Defender:    Tackling · Aerial · Positioning · Ball Playing · Physicality
  - Midfielder:  Passing · Creativity · Ball Carrying · Defensive Work · Pressing
  - Forward:     Finishing · Movement · Chance Creation · Dribbling · Aerial Threat

Legacy PAC/SHO/PAS/DRI/DEF/PHY columns are still derived for backward
compatibility with play_style.py and other consumers.
"""

import numpy as np
import pandas as pd
import streamlit as st
from config import (
    MIN_APPEARANCES_FOR_RATING, MIN_MINUTES_FOR_RATING,
    RATING_FLOOR, RATING_CEILING,
    POSITION_CATEGORY_DISPLAY,
)

# ── Position-specific stat-to-attribute maps ─────────────────────────────────
# Each attribute is computed from weighted CSV stat columns.
# Negative weights penalize (e.g. Tackles Lost hurts Tackling rating).

GK_ATTRIBUTE_MAP = {
    "GK_ShotStop": {
        "stats": ["Saves Made", "Saves Made from Inside Box", "Total Big Chances Saved"],
        "weights": [0.4, 0.35, 0.25],
    },
    "GK_Dist": {
        "stats": ["GK Successful Distribution", "Successful Long Passes",
                   "GK Unsuccessful Distribution"],
        "weights": [0.4, 0.3, -0.3],
    },
    "GK_Command": {
        "stats": ["Catches", "Punches", "Goalkeeper Smother", "Crosses not Claimed"],
        "weights": [0.35, 0.25, 0.25, -0.15],
    },
    "GK_Reflex": {
        "stats": ["Saves made - parried", "Saves made - caught",
                   "Saves Made from Inside Box"],
        "weights": [0.4, 0.3, 0.3],
    },
    "GK_CleanSheet": {
        "stats": ["Clean Sheets", "Goals Conceded"],
        "weights": [0.7, -0.3],
    },
}

DEF_ATTRIBUTE_MAP = {
    "DEF_Tackle": {
        "stats": ["Tackles Won", "Tackles Lost", "Last Player Tackle"],
        "weights": [0.5, -0.3, 0.2],
    },
    "DEF_Aerial": {
        "stats": ["Aerial Duels won", "Total Clearances", "Headed Goals"],
        "weights": [0.45, 0.35, 0.2],
    },
    "DEF_Position": {
        "stats": ["Interceptions", "Blocks", "Blocked Shots", "Recoveries"],
        "weights": [0.3, 0.25, 0.25, 0.2],
    },
    "DEF_BallPlay": {
        "stats": ["Total Passes", "Successful Long Passes", "Progressive Carries",
                   "Successful Passes Opposition Half"],
        "weights": [0.25, 0.25, 0.25, 0.25],
    },
    "DEF_Physical": {
        "stats": ["Ground Duels won", "Duels won", "Aerial Duels won"],
        "weights": [0.35, 0.35, 0.3],
    },
}

MID_ATTRIBUTE_MAP = {
    "MID_Pass": {
        "stats": ["Total Passes", "Successful Long Passes", "Successful Short Passes",
                   "Successful Passes Opposition Half"],
        "weights": [0.25, 0.25, 0.25, 0.25],
    },
    "MID_Create": {
        "stats": ["Key Passes (Attempt Assists)", "Through balls", "Goal Assists",
                   "Total Big Chances Created"],
        "weights": [0.3, 0.25, 0.25, 0.2],
    },
    "MID_Carry": {
        "stats": ["Progressive Carries", "Successful Dribbles", "Carries"],
        "weights": [0.4, 0.35, 0.25],
    },
    "MID_DefWork": {
        "stats": ["Tackles Won", "Interceptions", "Recoveries", "Blocks"],
        "weights": [0.3, 0.3, 0.25, 0.15],
    },
    "MID_Press": {
        "stats": ["Duels won", "Ground Duels won", "Recoveries",
                   "Total Fouls Conceded"],
        "weights": [0.3, 0.3, 0.25, -0.15],
    },
}

FWD_ATTRIBUTE_MAP = {
    "FWD_Finish": {
        "stats": ["Goals", "Shots On Target ( inc goals )", "Total Big Chances Scored",
                   "Goals from Inside Box"],
        "weights": [0.35, 0.25, 0.25, 0.15],
    },
    "FWD_Move": {
        "stats": ["Total Touches In Opposition Box", "Total Big Chances Scored",
                   "Total Big Chances Missed", "Offsides"],
        "weights": [0.35, 0.3, 0.2, 0.15],
    },
    "FWD_Chance": {
        "stats": ["Goal Assists", "Key Passes (Attempt Assists)",
                   "Total Big Chances Created", "Through balls"],
        "weights": [0.3, 0.3, 0.25, 0.15],
    },
    "FWD_Dribble": {
        "stats": ["Successful Dribbles", "Total Fouls Won", "Carries"],
        "weights": [0.45, 0.3, 0.25],
    },
    "FWD_AerialThreat": {
        "stats": ["Aerial Duels won", "Headed Goals",
                   "Total Touches In Opposition Box"],
        "weights": [0.4, 0.35, 0.25],
    },
}

# ── Lookup tables ─────────────────────────────────────────────────────────────

# Position → its attribute map
POSITION_ATTRIBUTE_MAPS = {
    "Goalkeeper": GK_ATTRIBUTE_MAP,
    "Defender":   DEF_ATTRIBUTE_MAP,
    "Midfielder": MID_ATTRIBUTE_MAP,
    "Forward":    FWD_ATTRIBUTE_MAP,
    "Attacker":   FWD_ATTRIBUTE_MAP,  # Alias for Forward
}

# Position → ordered list of attribute column keys
POSITION_ATTR_KEYS = {
    pos: list(attr_map.keys())
    for pos, attr_map in POSITION_ATTRIBUTE_MAPS.items()
}

# All position-specific column names (flat list)
ALL_POS_ATTRS = list(POSITION_CATEGORY_DISPLAY.keys())

# ── Position OVR weights ─────────────────────────────────────────────────────

POS_OVR_WEIGHTS = {
    "Goalkeeper": {
        "GK_ShotStop": 0.30, "GK_Dist": 0.15, "GK_Command": 0.20,
        "GK_Reflex": 0.20, "GK_CleanSheet": 0.15,
    },
    "Defender": {
        "DEF_Tackle": 0.25, "DEF_Aerial": 0.20, "DEF_Position": 0.25,
        "DEF_BallPlay": 0.15, "DEF_Physical": 0.15,
    },
    "Midfielder": {
        "MID_Pass": 0.25, "MID_Create": 0.20, "MID_Carry": 0.20,
        "MID_DefWork": 0.20, "MID_Press": 0.15,
    },
    "Forward": {
        "FWD_Finish": 0.30, "FWD_Move": 0.20, "FWD_Chance": 0.20,
        "FWD_Dribble": 0.20, "FWD_AerialThreat": 0.10,
    },
    "Attacker": {
        "FWD_Finish": 0.30, "FWD_Move": 0.20, "FWD_Chance": 0.20,
        "FWD_Dribble": 0.20, "FWD_AerialThreat": 0.10,
    },
}

# ── Legacy PAC/SHO/PAS/DRI/DEF/PHY from position-specific attributes ────────
# Maps each legacy attribute to the most-relevant position-specific attribute.

LEGACY_MAPPING = {
    "Goalkeeper": {
        "PAC": "GK_Dist", "SHO": "GK_ShotStop", "PAS": "GK_Dist",
        "DRI": "GK_Command", "DEF": "GK_Command", "PHY": "GK_Reflex",
    },
    "Defender": {
        "PAC": "DEF_BallPlay", "SHO": "DEF_Aerial", "PAS": "DEF_BallPlay",
        "DRI": "DEF_BallPlay", "DEF": "DEF_Tackle", "PHY": "DEF_Physical",
    },
    "Midfielder": {
        "PAC": "MID_Carry", "SHO": "MID_Create", "PAS": "MID_Pass",
        "DRI": "MID_Carry", "DEF": "MID_DefWork", "PHY": "MID_Press",
    },
    "Forward": {
        "PAC": "FWD_Move", "SHO": "FWD_Finish", "PAS": "FWD_Chance",
        "DRI": "FWD_Dribble", "DEF": "FWD_Move", "PHY": "FWD_AerialThreat",
    },
    "Attacker": {
        "PAC": "FWD_Move", "SHO": "FWD_Finish", "PAS": "FWD_Chance",
        "DRI": "FWD_Dribble", "DEF": "FWD_Move", "PHY": "FWD_AerialThreat",
    },
}

# ── Versatility rules ─────────────────────────────────────────────────────────
# (source_position, {attr: min_threshold}, suggestion_text)

VERSATILITY_RULES = [
    ("Midfielder", {"MID_DefWork": 88, "MID_Press": 85},
     "Could play: Defensive Midfielder / Centre-Back"),
    ("Midfielder", {"MID_Create": 88, "MID_Carry": 85},
     "Could play: Attacking Midfielder / Winger"),
    ("Forward", {"FWD_Chance": 88, "FWD_Dribble": 85},
     "Could play: Attacking Midfielder"),
    ("Forward", {"FWD_AerialThreat": 90},
     "Could play: Target Man"),
    ("Defender", {"DEF_BallPlay": 88},
     "Could play: Defensive Midfielder"),
    ("Defender", {"DEF_Physical": 90, "DEF_Aerial": 88},
     "Could play: Centre-Back (Target Man at set pieces)"),
    ("Goalkeeper", {"GK_Dist": 88},
     "Sweeper Keeper"),
]


# ── Helper functions ──────────────────────────────────────────────────────────

def _percentile_rank(series: pd.Series) -> pd.Series:
    """Compute percentile rank (0-100) for a series."""
    return series.rank(pct=True) * 100


def _scale_to_rating(percentile: float) -> int:
    """Scale a percentile (0-100) to rating range."""
    return int(np.clip(
        RATING_FLOOR + (percentile / 100) * (RATING_CEILING - RATING_FLOOR),
        RATING_FLOOR, RATING_CEILING,
    ))


def _detect_versatility(row: pd.Series) -> list[str]:
    """Check versatility rules and return matching suggestions."""
    pos = row.get("posicion", "")
    tags = []
    for rule_pos, thresholds, suggestion in VERSATILITY_RULES:
        if pos != rule_pos:
            continue
        if all(row.get(attr, 0) >= thresh for attr, thresh in thresholds.items()):
            tags.append(suggestion)
    return tags


# ── Sub-position (role) classification ────────────────────────────────────────
# Derived from which of a player's 5 attributes is dominant.

SUB_POSITIONS = [
    "Shot Stopper", "Sweeper Keeper",
    "Centre-Back", "Full-Back",
    "Defensive Midfielder", "Central Midfielder", "Attacking Midfielder",
    "Striker", "Winger", "Target Man",
]

# Map each sub-position back to its parent broad position
SUB_TO_PARENT = {
    "Shot Stopper": "Goalkeeper",   "Sweeper Keeper": "Goalkeeper",
    "Centre-Back": "Defender",      "Full-Back": "Defender",
    "Defensive Midfielder": "Midfielder", "Central Midfielder": "Midfielder",
    "Attacking Midfielder": "Midfielder",
    "Striker": "Forward",           "Winger": "Forward",
    "Target Man": "Forward",
}


def classify_sub_position(row: pd.Series) -> str:
    """Derive a tactical role from the player's dominant attributes.

    Compares the player's 5 position-specific ratings to classify into
    a more granular sub-position (e.g., Full-Back, Winger, DM).
    """
    pos = row.get("posicion", "Midfielder")

    def _val(attr):
        v = row.get(attr, 40)
        return v if pd.notna(v) else 40

    if pos == "Goalkeeper":
        return "Sweeper Keeper" if _val("GK_Dist") > _val("GK_ShotStop") else "Shot Stopper"

    if pos == "Defender":
        bp = _val("DEF_BallPlay")
        aer = _val("DEF_Aerial")
        tkl = _val("DEF_Tackle")
        # Full-backs: ball-playing is their strongest suit
        if bp > aer and bp > tkl:
            return "Full-Back"
        return "Centre-Back"

    if pos == "Midfielder":
        create = _val("MID_Create")
        carry = _val("MID_Carry")
        defw = _val("MID_DefWork")
        # Dominant defensive work → DM; dominant creativity → AM; else CM
        if defw > create and defw > carry:
            return "Defensive Midfielder"
        if create > defw:
            return "Attacking Midfielder"
        return "Central Midfielder"

    if pos in ("Forward", "Attacker"):
        finish = _val("FWD_Finish")
        drib = _val("FWD_Dribble")
        aer = _val("FWD_AerialThreat")
        # Dominant dribbling → Winger; dominant aerial → Target Man; else Striker
        if drib > finish and drib > aer:
            return "Winger"
        if aer > finish and aer > drib:
            return "Target Man"
        return "Striker"

    return pos


def get_position_attrs(position: str) -> list[str]:
    """Return the 5 attribute column keys for a position."""
    return POSITION_ATTR_KEYS.get(position, POSITION_ATTR_KEYS["Midfielder"])


def get_position_display_names(position: str) -> list[str]:
    """Return display names for a position's attributes."""
    keys = get_position_attrs(position)
    return [POSITION_CATEGORY_DISPLAY.get(k, k) for k in keys]


# ── Main rating computation ──────────────────────────────────────────────────

@st.cache_data(ttl=3600)
def compute_fc_ratings(player_stats: pd.DataFrame,
                       min_apps: int = MIN_APPEARANCES_FOR_RATING) -> pd.DataFrame:
    """Compute position-specific ratings for all players.

    Pipeline:
      1. Per-90 normalize counting stats
      2. Compute weighted raw scores per attribute within each position group
      3. Percentile-rank within position group
      4. Scale to 40-99 range
      5. Derive legacy PAC/SHO/PAS/DRI/DEF/PHY for backward compat
      6. Compute OVR as position-weighted sum of 5 attributes
      7. Detect versatility via cross-position threshold rules

    Returns DataFrame with columns:
      nombre, posicion, equipo, id,
      GK_ShotStop..GK_CleanSheet (NaN for non-GK),
      DEF_Tackle..DEF_Physical (NaN for non-DEF),
      MID_Pass..MID_Press (NaN for non-MID),
      FWD_Finish..FWD_AerialThreat (NaN for non-FWD),
      PAC, SHO, PAS, DRI, DEF, PHY, OVR,
      versatility_tags
    """
    if player_stats.empty:
        return pd.DataFrame()

    # ── Filter by minimum appearances AND minutes ────────────────────────
    app_col = "Appearances" if "Appearances" in player_stats.columns else "Games Played"
    if app_col in player_stats.columns:
        df = player_stats[player_stats[app_col].fillna(0) >= min_apps].copy()
    else:
        df = player_stats.copy()

    # Also filter by minutes to avoid per-90 inflation on tiny samples
    if "Time Played" in df.columns:
        df = df[df["Time Played"].fillna(0) >= MIN_MINUTES_FOR_RATING]

    if df.empty:
        return pd.DataFrame()

    # ── Per-90 normalization factor ────────────────────────────────────────
    if "Time Played" in df.columns:
        minutes = df["Time Played"].fillna(1).clip(lower=1)
        per90_factor = 90 / minutes
    else:
        per90_factor = pd.Series(1.0, index=df.index)

    positions = (
        df["posicion"].fillna("Midfielder")
        if "posicion" in df.columns
        else pd.Series("Midfielder", index=df.index)
    )

    # ── Initialize position attribute columns ──────────────────────────────
    for attr in ALL_POS_ATTRS:
        df[attr] = np.nan

    # ── Compute raw scores per position group ──────────────────────────────
    for pos, attr_map in POSITION_ATTRIBUTE_MAPS.items():
        if pos == "Attacker":
            continue  # Handled via Forward mapping

        mask = positions == pos
        if mask.sum() == 0:
            continue

        for attr_key, cfg in attr_map.items():
            raw_score = pd.Series(0.0, index=df.index[mask])
            for stat, weight in zip(cfg["stats"], cfg["weights"]):
                if stat not in df.columns:
                    continue
                vals = df.loc[mask, stat].fillna(0).astype(float)
                if weight < 0:
                    # Invert: lower raw value → higher score
                    max_v = vals.max()
                    vals = max_v - vals if max_v > 0 else vals
                    weight = abs(weight)
                # Per-90 normalization for playing-time fairness
                normalized = vals * per90_factor[mask]
                raw_score += normalized * weight

            df.loc[mask, f"_raw_{attr_key}"] = raw_score

        # ── Percentile rank within position group → scale to rating ────────
        for attr_key in attr_map:
            raw_col = f"_raw_{attr_key}"
            if raw_col not in df.columns:
                continue
            pos_raw = df.loc[mask, raw_col]
            valid = pos_raw.notna()
            if valid.sum() >= 3:
                pctile = _percentile_rank(pos_raw[valid])
                df.loc[pctile.index, attr_key] = pctile.apply(_scale_to_rating)
            elif valid.sum() > 0:
                # Too few players for percentile — simple min-max scaling
                min_v, max_v = pos_raw[valid].min(), pos_raw[valid].max()
                rng = max_v - min_v if max_v != min_v else 1
                pctile = ((pos_raw[valid] - min_v) / rng) * 100
                df.loc[pctile.index, attr_key] = pctile.apply(_scale_to_rating)

    # ── Derive legacy PAC/SHO/PAS/DRI/DEF/PHY ─────────────────────────────
    for legacy_attr in ["PAC", "SHO", "PAS", "DRI", "DEF", "PHY"]:
        df[legacy_attr] = RATING_FLOOR

    for pos, mapping in LEGACY_MAPPING.items():
        if pos == "Attacker":
            continue
        mask = positions == pos
        if mask.sum() == 0:
            continue
        for legacy_attr, pos_attr in mapping.items():
            if pos_attr in df.columns:
                df.loc[mask, legacy_attr] = (
                    df.loc[mask, pos_attr].fillna(RATING_FLOOR).astype(int)
                )

    # ── Compute OVR ────────────────────────────────────────────────────────
    def _calc_ovr(row):
        pos = row.get("posicion", "Midfielder")
        weights = POS_OVR_WEIGHTS.get(pos, POS_OVR_WEIGHTS["Midfielder"])
        total = sum(
            (row.get(attr, RATING_FLOOR) if pd.notna(row.get(attr)) else RATING_FLOOR) * w
            for attr, w in weights.items()
        )
        return int(np.clip(total, RATING_FLOOR, RATING_CEILING))

    df["OVR"] = df.apply(_calc_ovr, axis=1)

    # ── Versatility detection ──────────────────────────────────────────────
    df["versatility_tags"] = df.apply(_detect_versatility, axis=1)

    # ── Sub-position (role) classification ─────────────────────────────────
    df["sub_posicion"] = df.apply(classify_sub_position, axis=1)

    # ── Select output columns ──────────────────────────────────────────────
    keep_cols = (
        ["nombre", "posicion", "sub_posicion", "equipo", "id"]
        + ALL_POS_ATTRS
        + ["PAC", "SHO", "PAS", "DRI", "DEF", "PHY", "OVR", "versatility_tags"]
    )
    available = [c for c in keep_cols if c in df.columns]
    result = df[available].copy()
    result = result.sort_values("OVR", ascending=False).reset_index(drop=True)
    return result
