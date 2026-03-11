"""xG Explorer — Interactive shot explorer with filters, pitch visualization."""

import streamlit as st
import pandas as pd
from components.sidebar import render_sidebar
from viz.kpi_cards import section_header, kpi_row
from viz.pitch import plot_shot_map
from viz.charts import bar_chart, donut_chart, histogram
from viz.tables import styled_dataframe
from data.loader import load_mu_match_list, load_match_raw, build_player_name_map
from data.event_parser import extract_shots, parse_match_info
from config import MU_TEAM_ID, MU_TEAM_NAME, MU_RED, MU_GOLD

league, season = render_sidebar()

st.title("xG Explorer")
st.caption("Interactive shot analysis across the season")

# ── Load all MU shots for the season ────────────────────────────────────────
@st.cache_data(ttl=3600)
def load_season_shots(_league: str, _season: str) -> pd.DataFrame:
    """Load all shots from MU matches for the season."""
    matches = load_mu_match_list(_league, _season)
    if matches.empty:
        return pd.DataFrame()

    all_shots = []
    for _, match in matches.iterrows():
        mid = match.get("match_id", "")
        if not mid:
            continue
        raw = load_match_raw(_league, _season, mid)
        if not raw:
            continue
        info = parse_match_info(raw)
        events = raw.get("liveData", {}).get("event", [])
        shots = extract_shots(events)
        if not shots.empty:
            shots["match_id"] = mid
            shots["matchday"] = info["matchday"]
            shots["home_team"] = info["home_team"]
            shots["away_team"] = info["away_team"]
            shots["date"] = info["date"]
            all_shots.append(shots)

    return pd.concat(all_shots, ignore_index=True) if all_shots else pd.DataFrame()


with st.spinner("Loading season shot data..."):
    season_shots = load_season_shots(league, season)

if season_shots.empty:
    st.warning("No shot data available for this season.")
    st.stop()

name_map = build_player_name_map(league, season)
season_shots["player_display"] = season_shots.apply(
    lambda r: name_map.get(r["player_id"], r["player_name"]), axis=1
)

# ── Filters ─────────────────────────────────────────────────────────────────
section_header("Filters")
col1, col2, col3, col4 = st.columns(4)

with col1:
    team_filter = st.selectbox("Team", ["All", MU_TEAM_NAME, "Opponents"], key="xg_team")
with col2:
    outcomes = season_shots["outcome"].unique().tolist()
    outcome_filter = st.multiselect("Outcome", outcomes, default=outcomes, key="xg_outcome")
with col3:
    body_parts = season_shots["body_part"].dropna().unique().tolist()
    body_filter = st.multiselect("Body Part", body_parts, default=body_parts, key="xg_body")
with col4:
    min_range = st.slider("Minute Range", 0, 95,
                          (0, 95), key="xg_minute")

# Apply filters
filtered = season_shots.copy()
if team_filter == MU_TEAM_NAME:
    filtered = filtered[filtered["team_id"] == MU_TEAM_ID]
elif team_filter == "Opponents":
    filtered = filtered[filtered["team_id"] != MU_TEAM_ID]
filtered = filtered[filtered["outcome"].isin(outcome_filter)]
filtered = filtered[filtered["body_part"].isin(body_filter)]
filtered = filtered[(filtered["minute"] >= min_range[0]) & (filtered["minute"] <= min_range[1])]

# ── KPIs ────────────────────────────────────────────────────────────────────
goals = filtered[filtered["outcome"] == "Goal"]
total_xg = filtered["xg"].sum()
conversion = (len(goals) / len(filtered) * 100) if len(filtered) > 0 else 0
xg_diff = len(goals) - total_xg

kpi_row([
    {"label": "Total Shots", "value": len(filtered)},
    {"label": "Goals", "value": len(goals)},
    {"label": "Total xG", "value": f"{total_xg:.2f}"},
    {"label": "Conversion %", "value": f"{conversion:.1f}%"},
])
st.markdown("")
col1, col2 = st.columns(2)
col1.metric("Goals - xG", f"{xg_diff:+.2f}")
col2.metric("Avg xG/Shot", f"{(total_xg / len(filtered)):.3f}" if len(filtered) > 0 else "0")

# ── Shot Map ────────────────────────────────────────────────────────────────
st.markdown("---")
section_header("Shot Map")
plot_shot_map(filtered, title=f"Shots ({team_filter})")

# ── Situation Breakdown ─────────────────────────────────────────────────────
col1, col2 = st.columns(2)

with col1:
    section_header("Outcome Distribution")
    outcome_counts = filtered["outcome"].value_counts()
    fig = donut_chart(
        outcome_counts.index.tolist(), outcome_counts.values.tolist(),
        title="Shot Outcomes",
        colors=[MU_RED, MU_GOLD, "#888888", "#FF9800", "#42A5F5"],
    )
    st.plotly_chart(fig, width="stretch")

with col2:
    section_header("Body Part Distribution")
    body_counts = filtered["body_part"].value_counts()
    fig = donut_chart(
        body_counts.index.tolist(), body_counts.values.tolist(),
        title="Shot Type",
    )
    st.plotly_chart(fig, width="stretch")

# ── xG Distribution ────────────────────────────────────────────────────────
section_header("xG Distribution")
fig = histogram(filtered["xg"], title="Distribution of xG Values",
                x_label="xG", nbins=25)
st.plotly_chart(fig, width="stretch")

# ── Player xG Leaderboard ──────────────────────────────────────────────────
st.markdown("---")
section_header("Player xG Leaderboard")
player_xg = filtered.groupby("player_display").agg(
    shots=("xg", "count"),
    total_xg=("xg", "sum"),
    goals=("outcome", lambda x: (x == "Goal").sum()),
).reset_index()
player_xg["xg_diff"] = player_xg["goals"] - player_xg["total_xg"]
player_xg = player_xg.sort_values("total_xg", ascending=False)
player_xg.columns = ["Player", "Shots", "Total xG", "Goals", "Goals - xG"]
player_xg["Total xG"] = player_xg["Total xG"].round(2)
player_xg["Goals - xG"] = player_xg["Goals - xG"].round(2)
styled_dataframe(player_xg.head(20), height=500)

# ── Player Drill-Down ───────────────────────────────────────────────────────
st.markdown("---")
section_header("Player Drill-Down")
players = filtered["player_display"].dropna().unique().tolist()
if players:
    selected_player = st.selectbox("Select Player", sorted(players), key="xg_player")
    player_shots = filtered[filtered["player_display"] == selected_player]

    col1, col2 = st.columns([2, 1])
    with col1:
        plot_shot_map(player_shots, title=f"{selected_player} Shot Map")
    with col2:
        st.metric("Shots", len(player_shots))
        st.metric("Goals", len(player_shots[player_shots["outcome"] == "Goal"]))
        st.metric("xG", f"{player_shots['xg'].sum():.2f}")

    # Shot log
    log = player_shots[["minute", "outcome", "xg", "body_part", "matchday"]].copy()
    log.columns = ["Minute", "Outcome", "xG", "Body Part", "Matchday"]
    log["xG"] = log["xG"].round(3)
    styled_dataframe(log.sort_values("Minute"), height=300)
