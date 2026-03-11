"""Team selector for comparison views."""

import streamlit as st
from data.loader import load_standings
from config import MU_TEAM_NAME, BIG_SIX


def team_selector(league: str, season: str, key: str = "team_sel",
                  multi: bool = True, default_big_six: bool = True,
                  label: str = "Select Teams") -> list[str]:
    """Render a team selector. Returns list of team_names."""
    standings = load_standings(league, season)
    if standings.empty:
        return [MU_TEAM_NAME]

    teams = sorted(standings["team_name"].tolist())

    if multi:
        if default_big_six and league == "England_Premier_League":
            # Use Big Six for EPL
            defaults = [t for t in BIG_SIX.keys() if t in teams]
            if not defaults:
                defaults = teams[:6]
        elif default_big_six:
            # For other leagues: top 6 by standings rank
            top = standings.nsmallest(6, "rank")["team_name"].tolist()
            defaults = [t for t in top if t in teams]
            if not defaults:
                defaults = teams[:6]
        else:
            defaults = [MU_TEAM_NAME] if MU_TEAM_NAME in teams else teams[:1]
        defaults = [d for d in defaults if d in teams]
        selected = st.multiselect(label, teams, default=defaults, key=key)
        return selected if selected else teams[:1]
    else:
        idx = teams.index(MU_TEAM_NAME) if MU_TEAM_NAME in teams else 0
        selected = st.selectbox(label, teams, index=idx, key=key)
        return [selected] if selected else teams[:1]


def two_team_selector(league: str, season: str, key: str = "two_team_sel",
                      label_home: str = "Home Team",
                      label_away: str = "Away Team") -> tuple[str, str]:
    """Select two teams for head-to-head comparison.

    Works across any competition — defaults to first two teams in standings
    when MU is not present.
    """
    standings = load_standings(league, season)
    if standings.empty:
        return MU_TEAM_NAME, "Liverpool FC"

    teams = sorted(standings["team_name"].tolist())

    # Smart defaults: MU if present, else first team in standings
    default_home = MU_TEAM_NAME if MU_TEAM_NAME in teams else teams[0]
    home_idx = teams.index(default_home)

    col1, col2 = st.columns(2)
    with col1:
        home = st.selectbox(label_home, teams, index=home_idx, key=f"{key}_home")
    with col2:
        away_opts = [t for t in teams if t != home]
        away = st.selectbox(label_away, away_opts, key=f"{key}_away")

    return home, away
