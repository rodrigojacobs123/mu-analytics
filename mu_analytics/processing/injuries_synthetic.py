"""Deterministic synthetic injury data generator."""

import hashlib
from datetime import datetime, timedelta
import numpy as np
import pandas as pd
import streamlit as st

INJURY_TYPES = [
    ("Hamstring Strain", "Lower Body", 14, 42),
    ("Ankle Sprain", "Lower Body", 7, 28),
    ("ACL Injury", "Lower Body", 120, 270),
    ("Muscle Fatigue", "Lower Body", 3, 10),
    ("Calf Strain", "Lower Body", 10, 28),
    ("Groin Injury", "Lower Body", 14, 42),
    ("Quadriceps Strain", "Lower Body", 10, 35),
    ("Shoulder Injury", "Upper Body", 7, 21),
    ("Back Spasm", "Upper Body", 3, 14),
    ("Concussion", "Head", 7, 21),
    ("Illness", "General", 3, 7),
    ("Knee Contusion", "Lower Body", 5, 14),
]

SPECIALISTS = [
    "Dr. Sarah Mitchell (Orthopaedics)",
    "Dr. James Wilson (Sports Medicine)",
    "Dr. Ana García (Physiotherapy)",
    "Dr. Mark Thompson (Recovery)",
]

POSITION_INJURY_WEIGHTS = {
    "Goalkeeper": 0.6,
    "Defender": 1.2,
    "Midfielder": 1.0,
    "Attacker": 1.1,
}


@st.cache_data(ttl=7200)
def generate_synthetic_injuries(squad: dict[str, dict], season: str,
                                 seed_salt: str = "mu_analytics") -> pd.DataFrame:
    """Generate deterministic synthetic injury data for a squad.

    Args:
        squad: {player_id: {name, position, team, ...}} from roster
        season: season string e.g. "2024-2025"
        seed_salt: salt for reproducible randomness

    Returns DataFrame: player_id, player_name, position, team,
                       injury_type, body_region, start_date, expected_return,
                       days_out, status, specialist
    """
    season_start = datetime(int(season[:4]), 8, 10)
    season_end = datetime(int(season[:4]) + 1, 5, 25)
    today = datetime.now()

    rows = []
    for pid, info in squad.items():
        if not info.get("name"):
            continue

        # Deterministic seed from player ID + season
        seed_str = f"{pid}_{season}_{seed_salt}"
        seed = int(hashlib.md5(seed_str.encode()).hexdigest()[:8], 16)
        rng = np.random.RandomState(seed)

        pos = info.get("position", "Midfielder")
        weight = POSITION_INJURY_WEIGHTS.get(pos, 1.0)

        # 0-3 injuries per player, weighted by position
        n_injuries = rng.choice([0, 0, 1, 1, 1, 2, 2, 3],
                                p=[0.15, 0.15, 0.2, 0.15, 0.1, 0.1, 0.1, 0.05])
        n_injuries = int(n_injuries * weight)
        n_injuries = min(n_injuries, 3)

        for i in range(n_injuries):
            injury_idx = rng.randint(0, len(INJURY_TYPES))
            inj_name, region, min_days, max_days = INJURY_TYPES[injury_idx]

            # Random start date within season
            days_into_season = rng.randint(0, (season_end - season_start).days)
            start = season_start + timedelta(days=days_into_season)
            duration = rng.randint(min_days, max_days + 1)
            expected_return = start + timedelta(days=duration)

            # Status based on today's date
            if today < start:
                status = "Upcoming"
            elif today > expected_return:
                status = "Recovered"
            else:
                status = "Active"

            specialist = SPECIALISTS[rng.randint(0, len(SPECIALISTS))]

            rows.append({
                "player_id": pid,
                "player_name": info["name"],
                "position": pos,
                "team": info.get("team", ""),
                "injury_type": inj_name,
                "body_region": region,
                "start_date": start.strftime("%Y-%m-%d"),
                "expected_return": expected_return.strftime("%Y-%m-%d"),
                "days_out": duration,
                "status": status,
                "specialist": specialist,
            })

    return pd.DataFrame(rows)
