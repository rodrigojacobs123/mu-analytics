"""Team Analysis — Season trend, league table, Elo historical, team radar."""

import streamlit as st
import pandas as pd
import plotly.express as px
from components.sidebar import render_sidebar
from components.team_selector import team_selector
from viz.kpi_cards import section_header
from viz.tables import styled_league_table
from viz.charts import line_chart, multi_line_chart, goals_by_matchday
from viz.radar import team_radar
from data.loader import load_standings, load_mu_match_list
from processing.elo import compute_elo_history, get_elo_dataframe
from processing.team_stats import (
    compute_points_by_matchday, compute_team_radar_data,
    RADAR_CATEGORIES, get_team_folder_map,
)
from data.paths import list_seasons
from config import MU_TEAM_NAME, MU_RED

league, season = render_sidebar()

st.title("Team Analysis")

# ── Points Progression by Matchday ──────────────────────────────────────────
section_header("Points Progression")
compare_teams = team_selector(league, season, key="team_analysis_sel",
                              label="Compare teams by points")

points_data = {}
for team in compare_teams:
    pdf = compute_points_by_matchday(league, season, team)
    if not pdf.empty:
        points_data[team] = pdf["cumulative_points"].tolist()

if points_data:
    max_len = max(len(v) for v in points_data.values())
    plot_df = pd.DataFrame({"matchday": range(1, max_len + 1)})
    for team, pts in points_data.items():
        padded = pts + [pts[-1]] * (max_len - len(pts)) if len(pts) < max_len else pts
        plot_df[team] = padded[:max_len]

    fig = multi_line_chart(plot_df, x="matchday", y_cols=list(points_data.keys()),
                           title="Cumulative Points by Matchday", y_label="Points")
    st.plotly_chart(fig, width="stretch")

# ── League Table ────────────────────────────────────────────────────────────
st.markdown("---")
section_header("League Table")
standings = load_standings(league, season)
styled_league_table(standings)

# ── Elo Historical ──────────────────────────────────────────────────────────
st.markdown("---")
section_header("Elo Rating History")
elo_teams = st.multiselect("Select teams for Elo history",
                           compare_teams, default=[MU_TEAM_NAME] if MU_TEAM_NAME in compare_teams else compare_teams[:1],
                           key="elo_teams")

if elo_teams:
    with st.spinner("Computing Elo ratings across all seasons..."):
        elo_history = compute_elo_history(league, list_seasons(league))
    elo_df = get_elo_dataframe(elo_history, elo_teams)
    if not elo_df.empty:
        fig = px.line(elo_df, x="date", y="elo", color="team",
                      title="Elo Rating Over Time", template="mu_dark")
        fig.update_traces(line_width=2)
        st.plotly_chart(fig, width="stretch")
    else:
        st.info("No Elo data available for selected teams.")

# ── Team Radar Comparison ───────────────────────────────────────────────────
st.markdown("---")
section_header("Team Radar Comparison")
folder_map = get_team_folder_map(league, season)
folders = [folder_map.get(t, "") for t in compare_teams if t in folder_map]
radar_data = compute_team_radar_data(league, season, folders)
if radar_data:
    fig = team_radar(radar_data, RADAR_CATEGORIES, title="Team Comparison Radar")
    st.plotly_chart(fig, width="stretch")

# ── Goals Scored/Conceded by Matchday ───────────────────────────────────────
st.markdown("---")
section_header("Goals by Matchday")
mu_matches = load_mu_match_list(league, season)
if not mu_matches.empty:
    fig = goals_by_matchday(mu_matches, title="Manchester United — Goals by Matchday")
    st.plotly_chart(fig, width="stretch")
