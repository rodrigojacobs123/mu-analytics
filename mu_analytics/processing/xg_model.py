"""Positional xG estimation model.

When the Opta feed doesn't provide an xG value (qualifier 395 only appears
on goals), this module estimates xG from shot position, angle, and body part.

The model is calibrated from 7,014 non-OG shots in the EPL 2025-2026 dataset:
- Distance to goal centre (strongest predictor)
- Angle subtended by the goal (7.32 m wide)
- Header penalty (headers convert ~55 % less than foot shots at same distance)

Coordinate system
─────────────────
Opta uses 0-100 for both x and y:
  x = 0 → own goal-line,  x = 100 → opponent goal-line
  y = 0 → right touch-line (from the team's perspective), y = 100 → left
  Goal centre is at (100, 50).
Real pitch ≈ 105 m × 68 m → scale factors: 1.05 m per x-unit, 0.68 m per y-unit.
"""

import math

# ── Pitch / goal constants ──────────────────────────────────────────────────
PITCH_LENGTH_M = 105.0
PITCH_WIDTH_M = 68.0
GOAL_WIDTH_M = 7.32
GOAL_HALF_WIDTH = GOAL_WIDTH_M / 2  # 3.66 m

# Scale factors: Opta units → metres
_X_SCALE = PITCH_LENGTH_M / 100.0   # 1.05
_Y_SCALE = PITCH_WIDTH_M / 100.0    # 0.68

# ── Calibration look-up table (from 7 014 shots, EPL 2025-26) ──────────────
# Pairs of (distance_metres, base_xg)
# "base_xg" is the observed foot-shot conversion rate at that distance.
_DIST_XG_TABLE = [
    (0.0,  0.95),   # on the line
    (2.0,  0.70),   # tap-in range
    (4.0,  0.55),   # close range
    (6.0,  0.35),   # 6-yard box edge
    (8.0,  0.27),   # inside box, good position
    (10.0, 0.22),   # inside box, wider
    (12.0, 0.17),   # penalty spot area
    (14.0, 0.11),   # edge of box
    (18.0, 0.07),   # just outside box
    (22.0, 0.050),  # long range
    (28.0, 0.040),  # very long range
    (35.0, 0.025),  # half-way speculative
    (50.0, 0.010),  # centre-circle shot
]

# Header adjustment: headers convert at roughly 55 % the rate of foot shots.
_HEADER_FACTOR = 0.55

# Penalty xG (standard value used across the industry)
PENALTY_XG = 0.76


# ── Core helpers ────────────────────────────────────────────────────────────

def _lerp(x: float, x0: float, x1: float, y0: float, y1: float) -> float:
    """Linear interpolation between (x0, y0) and (x1, y1)."""
    if x1 == x0:
        return y0
    t = (x - x0) / (x1 - x0)
    return y0 + t * (y1 - y0)


def _interpolate_distance_xg(distance_m: float) -> float:
    """Look up base xG for a given distance (metres) with linear interpolation."""
    table = _DIST_XG_TABLE
    if distance_m <= table[0][0]:
        return table[0][1]
    if distance_m >= table[-1][0]:
        return table[-1][1]
    for i in range(len(table) - 1):
        d0, xg0 = table[i]
        d1, xg1 = table[i + 1]
        if d0 <= distance_m <= d1:
            return _lerp(distance_m, d0, d1, xg0, xg1)
    return table[-1][1]


def _shot_distance(x: float, y: float) -> float:
    """Distance from shot position to goal centre in metres."""
    dx = (100.0 - x) * _X_SCALE
    dy = (y - 50.0) * _Y_SCALE
    return math.sqrt(dx * dx + dy * dy)


def _goal_angle(x: float, y: float) -> float:
    """Angle (radians) subtended by the goal from the shot position."""
    dx = (100.0 - x) * _X_SCALE
    dy = (y - 50.0) * _Y_SCALE
    # Angles to each post
    a1 = math.atan2(GOAL_HALF_WIDTH - dy, max(dx, 0.1))
    a2 = math.atan2(-GOAL_HALF_WIDTH - dy, max(dx, 0.1))
    return abs(a1 - a2)


def _angle_modifier(angle_rad: float) -> float:
    """Multiplicative modifier based on angle to goal.

    - Central shots (wide angle ≥ 40°) → modifier ≈ 1.15 (slight boost)
    - Medium angle (20-40°) → modifier ≈ 1.0 (neutral)
    - Tight angle (10-20°) → modifier ≈ 0.6
    - Very tight (< 10°) → modifier ≈ 0.3
    """
    angle_deg = math.degrees(angle_rad)
    if angle_deg >= 40:
        return 1.15
    elif angle_deg >= 30:
        return 1.05
    elif angle_deg >= 20:
        return 0.85
    elif angle_deg >= 10:
        return 0.55
    elif angle_deg >= 5:
        return 0.30
    else:
        return 0.15


# ── Public API ──────────────────────────────────────────────────────────────

def estimate_xg(x: float, y: float, is_header: bool = False) -> float:
    """Estimate xG from shot coordinates.

    Args:
        x: Opta x-coordinate (0-100, 100 = opponent goal-line)
        y: Opta y-coordinate (0-100, 50 = centre)
        is_header: True if the shot was a header

    Returns:
        Estimated xG in [0.01, 0.95]
    """
    # Shots with x < 50 are likely own-goals or data artifacts → minimal xG
    if x < 50:
        return 0.01

    distance = _shot_distance(x, y)
    angle = _goal_angle(x, y)

    # Base xG from distance
    xg = _interpolate_distance_xg(distance)

    # Angle modifier
    xg *= _angle_modifier(angle)

    # Header penalty
    if is_header:
        xg *= _HEADER_FACTOR

    return max(0.01, min(0.95, xg))
