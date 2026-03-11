"""Rivals & Rankings — Multi-team comparison across any league.

Sections:
  1. Team Selection (league-aware defaults)
  2. League Table (selected teams highlighted)
  3. Multi-Team Radar (fixed Unicode/folder mapping)
  4. Form Guide (cumulative points by matchday)
  5. Head-to-Head (side-by-side stat bars)
  6. Goals For vs Goals Against (scatter with quadrants)
  7. Key Stats Comparison (grouped bar charts)
  8. Full League Rankings
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from components.sidebar import render_sidebar
from components.team_selector import team_selector, two_team_selector
from viz.kpi_cards import section_header, kpi_row
from viz.radar import team_radar
from viz.charts import scatter_chart, grouped_bar_chart, multi_line_chart
from viz.tables import styled_league_table, styled_dataframe
from data.loader import load_standings
from processing.team_stats import (
    compute_team_radar_data, RADAR_CATEGORIES,
    build_team_name_lookup, compute_points_by_matchday,
)
from config import MU_TEAM_NAME, MU_RED, MU_GOLD, MU_WHITE

league, season = render_sidebar()

st.title("Rivals & Rankings")
st.caption("Compare teams across any competition")

# ── Load standings (used by most sections) ─────────────────────────────────
standings = load_standings(league, season)
if standings.empty:
    st.warning("No standings data available for this league/season.")
    st.stop()

# ─────────────────────────────────────────────────────────────────────────────
# 1. TEAM SELECTION
# ─────────────────────────────────────────────────────────────────────────────
selected_teams = team_selector(
    league, season, key="rivals_teams",
    label="Select teams to compare",
)

if not selected_teams:
    st.info("Select at least one team to begin.")
    st.stop()

# ─────────────────────────────────────────────────────────────────────────────
# 2. LEAGUE TABLE (selected teams highlighted)
# ─────────────────────────────────────────────────────────────────────────────
section_header("Standings Snapshot")
filtered_standings = standings[standings["team_name"].isin(selected_teams)].copy()
filtered_standings = filtered_standings.sort_values("rank")

display_cols = ["rank", "team_name", "played", "won", "drawn", "lost",
                "gf", "ga", "gd", "points"]
available = [c for c in display_cols if c in filtered_standings.columns]
renamed = {
    "rank": "Pos", "team_name": "Team", "played": "P", "won": "W",
    "drawn": "D", "lost": "L", "gf": "GF", "ga": "GA",
    "gd": "GD", "points": "Pts",
}
styled_dataframe(filtered_standings[available].rename(columns=renamed))

# Quick KPIs for the selection
if len(selected_teams) >= 2:
    top_team = filtered_standings.iloc[0]
    bot_team = filtered_standings.iloc[-1]
    gap = int(top_team.get("points", 0) - bot_team.get("points", 0))
    kpi_row([
        {"label": "Teams Selected", "value": len(selected_teams)},
        {"label": "Top Ranked", "value": f"#{int(top_team.get('rank', 0))} {top_team['team_name'][:15]}"},
        {"label": "Point Gap", "value": gap},
    ], cols=3)

# ─────────────────────────────────────────────────────────────────────────────
# 3. MULTI-TEAM RADAR
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("---")
section_header("Team Radar Comparison")

# Build name → folder lookup using fuzzy matching (handles Unicode + naming)
name_lookup = build_team_name_lookup(league, season)
folders = [name_lookup[t] for t in selected_teams if t in name_lookup]

if folders:
    radar_data = compute_team_radar_data(league, season, folders)
    if radar_data:
        fig = team_radar(radar_data, RADAR_CATEGORIES,
                         title="Multi-Team Comparison")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Radar data not available for the selected teams.")
else:
    st.info("Could not match selected teams to stat folders. "
            "This may happen for leagues with limited data.")

# ─────────────────────────────────────────────────────────────────────────────
# 4. FORM GUIDE (cumulative points by matchday)
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("---")
section_header("Season Form Guide")

form_data = {}
for team in selected_teams:
    pts_df = compute_points_by_matchday(league, season, team)
    if not pts_df.empty:
        form_data[team] = pts_df

if form_data:
    # Build a combined DataFrame for multi-line chart
    all_matchdays = sorted(set(
        md for df in form_data.values() for md in df["matchday"]
    ))
    combined = pd.DataFrame({"Matchday": all_matchdays})
    for team, pts_df in form_data.items():
        merged = pd.merge(
            combined, pts_df[["matchday", "cumulative_points"]],
            left_on="Matchday", right_on="matchday", how="left",
        )
        combined[team] = merged["cumulative_points"].ffill().fillna(0)
        if "matchday" in combined.columns:
            combined = combined.drop(columns=["matchday"])

    team_cols = [t for t in selected_teams if t in combined.columns]
    if team_cols:
        colors = [MU_RED, MU_GOLD, "#42A5F5", "#4CAF50", MU_WHITE,
                  "#FF9800", "#E91E63", "#9C27B0", "#00BCD4", "#8BC34A"]
        fig = multi_line_chart(
            combined, x="Matchday", y_cols=team_cols,
            colors=colors[:len(team_cols)],
            title="Cumulative Points",
            y_label="Points",
        )
        fig.update_layout(
            legend=dict(orientation="h", y=-0.15),
            height=450,
        )
        st.plotly_chart(fig, use_container_width=True)
else:
    st.info("Form data not available for the selected teams.")

# ─────────────────────────────────────────────────────────────────────────────
# 5. HEAD-TO-HEAD (pick two teams, side-by-side comparison)
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("---")
section_header("Head-to-Head")

team_a, team_b = two_team_selector(league, season, key="h2h_rivals")

h2h_standings = standings[standings["team_name"].isin([team_a, team_b])]
if len(h2h_standings) == 2:
    row_a = h2h_standings[h2h_standings["team_name"] == team_a].iloc[0]
    row_b = h2h_standings[h2h_standings["team_name"] == team_b].iloc[0]

    stat_pairs = [
        ("Points", "points"), ("Wins", "won"), ("Draws", "drawn"),
        ("Losses", "lost"), ("Goals For", "gf"), ("Goals Against", "ga"),
        ("Goal Diff", "gd"),
    ]

    stat_labels = []
    a_vals = []
    b_vals = []
    for label, col in stat_pairs:
        if col in row_a.index:
            stat_labels.append(label)
            a_vals.append(int(row_a.get(col, 0)))
            b_vals.append(int(row_b.get(col, 0)))

    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=stat_labels, x=a_vals, orientation="h",
        name=team_a[:20], marker_color=MU_RED,
    ))
    fig.add_trace(go.Bar(
        y=stat_labels, x=b_vals, orientation="h",
        name=team_b[:20], marker_color="#42A5F5",
    ))
    fig.update_layout(
        barmode="group", title=f"{team_a[:20]} vs {team_b[:20]}",
        height=400, legend=dict(orientation="h", y=-0.15),
    )
    st.plotly_chart(fig, use_container_width=True)

    # Show ranking comparison KPIs
    col1, col2 = st.columns(2)
    with col1:
        rank_a = int(row_a.get("rank", 0))
        st.metric(team_a[:25], f"#{rank_a}", f"{int(row_a.get('points', 0))} pts")
    with col2:
        rank_b = int(row_b.get("rank", 0))
        st.metric(team_b[:25], f"#{rank_b}", f"{int(row_b.get('points', 0))} pts")
else:
    st.info("Head-to-head data not available for the selected teams.")

# ─────────────────────────────────────────────────────────────────────────────
# 6. GOALS FOR vs GOALS AGAINST (scatter with quadrant annotations)
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("---")
section_header("Goals For vs Goals Against")

plot_df = standings[standings["team_name"].isin(selected_teams)].copy()
if not plot_df.empty and "gf" in plot_df.columns and "ga" in plot_df.columns:
    if "team_code" in plot_df.columns:
        plot_df["label"] = plot_df["team_code"]
    else:
        plot_df["label"] = plot_df["team_name"].str[:3].str.upper()

    fig = scatter_chart(
        plot_df, x="gf", y="ga", text="label",
        title="Goals Scored vs Conceded",
        add_diagonal=True,
    )
    fig.update_traces(textposition="top center", marker=dict(size=12, color=MU_RED))
    fig.update_layout(xaxis_title="Goals For", yaxis_title="Goals Against")

    # Add quadrant annotations
    fig.add_annotation(x=plot_df["gf"].max(), y=plot_df["ga"].min(),
                       text="Strong Attack<br>Solid Defense", showarrow=False,
                       font=dict(color="#4CAF50", size=10), xanchor="right")
    fig.add_annotation(x=plot_df["gf"].min(), y=plot_df["ga"].max(),
                       text="Weak Attack<br>Leaky Defense", showarrow=False,
                       font=dict(color="#F44336", size=10), xanchor="left")

    st.plotly_chart(fig, use_container_width=True)

# ─────────────────────────────────────────────────────────────────────────────
# 7. KEY STATS COMPARISON (grouped bar charts)
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("---")
section_header("Key Stats Comparison")

compare_cols = [c for c in ["team_name", "won", "drawn", "lost", "gf", "ga", "points"]
                if c in standings.columns]
compare_df = standings[standings["team_name"].isin(selected_teams)][compare_cols].copy()

if not compare_df.empty:
    compare_df = compare_df.rename(columns={
        "team_name": "Team", "won": "Wins", "drawn": "Draws",
        "lost": "Losses", "gf": "Goals For", "ga": "Goals Against",
        "points": "Points",
    })
    compare_df["Team"] = compare_df["Team"].str[:18]

    col1, col2 = st.columns(2)
    with col1:
        fig = grouped_bar_chart(
            compare_df, x="Team",
            y_cols=["Wins", "Draws", "Losses"],
            title="Results Breakdown",
        )
        fig.update_layout(height=400)
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        fig = grouped_bar_chart(
            compare_df, x="Team",
            y_cols=["Goals For", "Goals Against"],
            colors=[MU_RED, "#42A5F5"],
            title="Goal Comparison",
        )
        fig.update_layout(height=400)
        st.plotly_chart(fig, use_container_width=True)

# ─────────────────────────────────────────────────────────────────────────────
# 8. FULL LEAGUE RANKINGS
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("---")
section_header("Full League Rankings")

highlight = MU_TEAM_NAME if MU_TEAM_NAME in standings["team_name"].values else ""
styled_league_table(standings, highlight_team=highlight)
