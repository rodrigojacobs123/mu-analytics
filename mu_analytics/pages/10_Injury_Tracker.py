"""Injury Tracker — Synthetic injury intelligence with history and analysis."""

import streamlit as st
import pandas as pd
import plotly.express as px
from components.sidebar import render_sidebar
from viz.kpi_cards import section_header, kpi_row
from viz.charts import bar_chart, donut_chart
from viz.tables import styled_dataframe
from data.loader import load_squad_roster
from processing.injuries_synthetic import generate_synthetic_injuries
from config import MU_TEAM_NAME, MU_TEAM_ID, MU_RED, MU_GOLD

league, season = render_sidebar()

st.title("Injury Tracker")

# Disclaimer
st.warning(
    "**Note:** Injury data shown here is synthetically generated for demonstration purposes. "
    "It does not reflect actual Manchester United injury records. This module showcases the "
    "platform's injury intelligence capabilities for the TFM project."
)

# ── Generate Synthetic Injuries ─────────────────────────────────────────────
roster = load_squad_roster(league, season)
mu_roster = {pid: info for pid, info in roster.items()
             if MU_TEAM_NAME in info.get("team", "") or "Manchester United" in info.get("team", "")}

if not mu_roster:
    st.error("No roster data available.")
    st.stop()

injuries = generate_synthetic_injuries(mu_roster, season)

if injuries.empty:
    st.info("No injury data generated.")
    st.stop()

# ── KPIs ────────────────────────────────────────────────────────────────────
active = injuries[injuries["status"] == "Active"]
recovered = injuries[injuries["status"] == "Recovered"]

kpi_row([
    {"label": "Total Injury Events", "value": len(injuries)},
    {"label": "Players Affected", "value": injuries["player_name"].nunique()},
    {"label": "Currently Injured", "value": len(active)},
    {"label": "Recovered", "value": len(recovered)},
])

# ── Current Injuries ────────────────────────────────────────────────────────
st.markdown("---")
section_header("Currently Injured Players")
if not active.empty:
    display = active[["player_name", "position", "injury_type", "body_region",
                      "start_date", "expected_return", "days_out", "specialist"]].copy()
    display.columns = ["Player", "Position", "Injury", "Region",
                       "Start", "Expected Return", "Days Out", "Specialist"]
    styled_dataframe(display, height=300)
else:
    st.success("No currently active injuries!")

# ── Injury Timeline (Gantt-style) ──────────────────────────────────────────
st.markdown("---")
section_header("Injury Timeline")
if not injuries.empty:
    timeline_df = injuries.copy()
    timeline_df["start_date"] = pd.to_datetime(timeline_df["start_date"])
    timeline_df["expected_return"] = pd.to_datetime(timeline_df["expected_return"])

    fig = px.timeline(
        timeline_df, x_start="start_date", x_end="expected_return",
        y="player_name", color="injury_type",
        title="Injury History Timeline",
        template="plotly_dark",
    )
    fig.update_yaxes(categoryorder="total ascending")
    fig.update_layout(height=max(400, len(timeline_df) * 25))
    st.plotly_chart(fig, width="stretch")

# ── Body Region Breakdown ───────────────────────────────────────────────────
col1, col2 = st.columns(2)

with col1:
    section_header("Injuries by Body Region")
    region_counts = injuries["body_region"].value_counts()
    fig = donut_chart(region_counts.index.tolist(), region_counts.values.tolist(),
                      title="Body Region Distribution")
    st.plotly_chart(fig, width="stretch")

with col2:
    section_header("Top Injury Types")
    type_counts = injuries["injury_type"].value_counts().head(8)
    fig = bar_chart(
        pd.DataFrame({"type": type_counts.index, "count": type_counts.values}),
        x="type", y="count", title="Most Common Injuries",
    )
    fig.update_layout(xaxis_tickangle=-45)
    st.plotly_chart(fig, width="stretch")

# ── Injury by Position ──────────────────────────────────────────────────────
st.markdown("---")
section_header("Injuries by Position")
pos_counts = injuries.groupby("position").agg(
    total=("injury_type", "count"),
    players=("player_name", "nunique"),
    avg_days=("days_out", "mean"),
).reset_index()
pos_counts.columns = ["Position", "Total Injuries", "Players Affected", "Avg Days Out"]
pos_counts["Avg Days Out"] = pos_counts["Avg Days Out"].round(1)
styled_dataframe(pos_counts)

# ── Specialist Workload ─────────────────────────────────────────────────────
st.markdown("---")
section_header("Specialist Workload")
spec_counts = injuries["specialist"].value_counts()
fig = bar_chart(
    pd.DataFrame({"Specialist": spec_counts.index, "Cases": spec_counts.values}),
    x="Specialist", y="Cases", title="Cases per Specialist",
)
fig.update_layout(xaxis_tickangle=-30)
st.plotly_chart(fig, width="stretch")

# ── Player Lookup ───────────────────────────────────────────────────────────
st.markdown("---")
section_header("Player Injury Lookup")
player_names = sorted(injuries["player_name"].unique().tolist())
selected_player = st.selectbox("Select Player", player_names, key="injury_player")

player_injuries = injuries[injuries["player_name"] == selected_player]
if not player_injuries.empty:
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Injuries", len(player_injuries))
    col2.metric("Total Days Out", int(player_injuries["days_out"].sum()))
    most_common = player_injuries["injury_type"].mode().iloc[0] if not player_injuries.empty else "N/A"
    col3.metric("Most Common", most_common)

    styled_dataframe(
        player_injuries[["injury_type", "body_region", "start_date",
                         "expected_return", "days_out", "status", "specialist"]].rename(columns={
            "injury_type": "Injury", "body_region": "Region",
            "start_date": "Start", "expected_return": "Return",
            "days_out": "Days", "status": "Status", "specialist": "Specialist",
        }),
        height=250,
    )
