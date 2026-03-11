"""Player selector with position filter."""

import streamlit as st
import pandas as pd
from data.loader import load_squad_roster, load_player_season_stats
from config import MU_TEAM_ID, MU_TEAM_FOLDER


def player_selector(league: str, season: str, team_folder: str = MU_TEAM_FOLDER,
                    key: str = "player_sel", multi: bool = False,
                    label: str = "Select Player") -> str | list[str] | None:
    """Render a player selector. Returns player_id or list of player_ids."""
    roster = load_squad_roster(league, season)
    if not roster:
        st.warning("No squad data available.")
        return None

    # Filter to team
    team_players = {pid: info for pid, info in roster.items()
                    if team_folder.replace("_", " ").rstrip("FC").strip() in info.get("team", "")}
    if not team_players:
        team_players = roster  # fallback to all

    # Position filter
    positions = sorted(set(info["position"] for info in team_players.values() if info["position"]))
    if positions:
        pos_filter = st.multiselect("Filter by Position", positions, key=f"{key}_pos")
        if pos_filter:
            team_players = {pid: info for pid, info in team_players.items()
                           if info["position"] in pos_filter}

    # Build options
    options = {f"{info['name']} ({info['position']})": pid
               for pid, info in sorted(team_players.items(), key=lambda x: x[1]["name"])}

    if multi:
        selected = st.multiselect(label, list(options.keys()), key=key)
        return [options[s] for s in selected] if selected else []
    else:
        selected = st.selectbox(label, list(options.keys()), key=key)
        return options.get(selected) if selected else None


def league_player_selector(league: str, season: str, key: str = "league_player_sel",
                           label: str = "Select Player") -> str | None:
    """Player selector across the entire league."""
    roster = load_squad_roster(league, season)
    if not roster:
        return None

    # Position filter
    positions = sorted(set(info["position"] for info in roster.values() if info["position"]))
    pos_filter = st.multiselect("Filter by Position", positions, key=f"{key}_pos")

    filtered = roster
    if pos_filter:
        filtered = {pid: info for pid, info in roster.items() if info["position"] in pos_filter}

    options = {f"{info['name']} · {info['team']} ({info['position']})": pid
               for pid, info in sorted(filtered.items(), key=lambda x: x[1]["name"])
               if info["name"].strip()}

    selected = st.selectbox(label, list(options.keys()), key=key)
    return options.get(selected) if selected else None
