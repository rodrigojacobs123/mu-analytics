"""Home — Season KPI dashboard, league table, match results, cross-season trends."""

import streamlit as st
import pandas as pd
from components.sidebar import render_sidebar
from viz.kpi_cards import kpi_row, section_header, form_badges
from viz.tables import styled_league_table
from viz.charts import line_chart, multi_line_chart
from data.loader import load_standings, load_mu_match_list, load_all_season_results
from processing.team_stats import compute_points_by_matchday
from processing.poisson import _resolve_team_in_results
from data.paths import list_seasons
from config import (
    MU_TEAM_NAME, MU_TEAM_ID, MU_RED, DEFAULT_LEAGUE,
    COMPETITIONS, MU_LEAGUES,
)

league, season = render_sidebar()

comp_display = COMPETITIONS.get(league, league)
st.title("Manchester United · Season Dashboard")
st.caption(f"{season} · {comp_display}")

# ── KPI Cards (computed from actual match results) ──────────────────────────
standings = load_standings(league, season)
is_mu_league = league in MU_LEAGUES
mu_matches = load_mu_match_list(league, season) if is_mu_league else pd.DataFrame()

if not mu_matches.empty:
    wins = int((mu_matches["result"] == "W").sum())
    draws = int((mu_matches["result"] == "D").sum())
    losses = int((mu_matches["result"] == "L").sum())
    gf = int(mu_matches["mu_score"].sum())
    ga = int(mu_matches["opp_score"].sum())
    gd = gf - ga
    played = len(mu_matches)
    points = wins * 3 + draws

    # Compute rank from all match results
    rank = "–"
    all_results = load_all_season_results(league, season)
    if not all_results.empty:
        team_points = {}
        for _, r in all_results.iterrows():
            hs, as_ = r["home_score"], r["away_score"]
            ht, at = r["home_team"], r["away_team"]
            if hs > as_:
                team_points[ht] = team_points.get(ht, 0) + 3
                team_points[at] = team_points.get(at, 0)
            elif hs == as_:
                team_points[ht] = team_points.get(ht, 0) + 1
                team_points[at] = team_points.get(at, 0) + 1
            else:
                team_points[at] = team_points.get(at, 0) + 3
                team_points[ht] = team_points.get(ht, 0)
        mu_resolved = _resolve_team_in_results(all_results, MU_TEAM_NAME, MU_TEAM_ID)
        sorted_teams = sorted(team_points.items(), key=lambda x: -x[1])
        for i, (t, _) in enumerate(sorted_teams, 1):
            if t == mu_resolved:
                rank = f"#{i}"
                break

    kpi_row([
        {"label": "League Position", "value": rank},
        {"label": "Points", "value": points},
        {"label": "Record (W-D-L)", "value": f"{wins}-{draws}-{losses}"},
        {"label": "Goal Difference", "value": f"{gd:+d}", "delta": gd},
    ])

    st.markdown("")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Matches", played)
    col2.metric("Goals For", gf)
    col3.metric("Goals Against", ga)
    col4.metric("Points/Match", round(points / max(played, 1), 2))

    form_list = list(mu_matches["result"].tail(6))
    if form_list:
        st.markdown("**Recent Form:** " + form_badges(form_list), unsafe_allow_html=True)

elif not standings.empty and MU_TEAM_NAME in standings["team_name"].values:
    mu_row = standings[standings["team_name"] == MU_TEAM_NAME].iloc[0]
    kpi_row([
        {"label": "League Position", "value": f"#{int(mu_row['rank'])}"},
        {"label": "Points", "value": int(mu_row["points"])},
        {"label": "Record (W-D-L)", "value": f"{int(mu_row['won'])}-{int(mu_row['drawn'])}-{int(mu_row['lost'])}"},
        {"label": "Goal Difference", "value": f"{int(mu_row['gd']):+d}", "delta": int(mu_row["gd"])},
    ])
    st.markdown("")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Matches", int(mu_row["played"]))
    col2.metric("Goals For", int(mu_row["gf"]))
    col3.metric("Goals Against", int(mu_row["ga"]))
    col4.metric("Points/Match", round(mu_row["points"] / max(mu_row["played"], 1), 2))
    last_six = mu_row.get("last_six", "")
    if last_six:
        form_list = list(last_six.replace(",", ""))
        st.markdown("**Recent Form:** " + form_badges(form_list), unsafe_allow_html=True)
else:
    st.warning("Manchester United not found in standings for this season.")

# ── Season Results ─────────────────────────────────────────────────────────
st.markdown("---")
section_header("Season Results")

results = load_all_season_results(league, season)

if is_mu_league and not results.empty:
    if not mu_matches.empty:
        display_df = mu_matches[["matchday", "date", "opponent", "is_home",
                                  "mu_score", "opp_score", "result"]].copy()
        display_df["date"] = pd.to_datetime(display_df["date"], errors="coerce").dt.strftime("%Y-%m-%d")
        display_df["Venue"] = display_df["is_home"].map({True: "Home", False: "Away"})
        display_df["Score"] = display_df.apply(
            lambda r: f"{int(r['mu_score'])}-{int(r['opp_score'])}", axis=1
        )
        display_df["Result"] = display_df["result"]
        display_df = display_df.rename(columns={
            "matchday": "MD", "date": "Date", "opponent": "Opponent",
        })
        st.dataframe(
            display_df[["MD", "Date", "Venue", "Opponent", "Score", "Result"]],
            hide_index=True, use_container_width=True,
            column_config={
                "MD": st.column_config.NumberColumn("MD", width="small"),
                "Result": st.column_config.TextColumn("Result", width="small"),
            },
        )
        st.caption(f"{len(mu_matches)} matches played")
    else:
        st.info("No match results available for Manchester United in this competition.")
elif not results.empty:
    display_df = results[["matchday", "date", "home_team", "away_team",
                           "home_score", "away_score"]].copy()
    display_df["date"] = pd.to_datetime(display_df["date"], errors="coerce").dt.strftime("%Y-%m-%d")
    display_df["Score"] = display_df.apply(
        lambda r: f"{int(r['home_score'])}-{int(r['away_score'])}", axis=1
    )
    display_df = display_df.rename(columns={
        "matchday": "MD", "date": "Date",
        "home_team": "Home", "away_team": "Away",
    })
    st.dataframe(
        display_df[["MD", "Date", "Home", "Score", "Away"]],
        hide_index=True, use_container_width=True,
    )
    st.caption(f"{len(display_df)} matches played")
else:
    st.info("No results available for this season.")

# ── Layout: League Table + Points Trend ─────────────────────────────────────
st.markdown("---")
col_table, col_chart = st.columns([1, 1])

with col_table:
    section_header("League Table")
    styled_league_table(standings)

with col_chart:
    section_header("Points Progression")
    pts_df = compute_points_by_matchday(league, season, MU_TEAM_NAME, team_id=MU_TEAM_ID)
    if not pts_df.empty:
        fig = line_chart(pts_df, x="matchday", y="cumulative_points",
                         title="Cumulative Points", y_label="Points",
                         markers=True)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No matchday data available.")

    section_header("Historical Points by Season")
    season_points = []
    for s in list_seasons(league):
        st_df = load_standings(league, s)
        if not st_df.empty and MU_TEAM_NAME in st_df["team_name"].values:
            row = st_df[st_df["team_name"] == MU_TEAM_NAME].iloc[0]
            season_points.append({"season": s, "points": int(row["points"]),
                                  "position": int(row["rank"])})

    if season_points:
        sp_df = pd.DataFrame(season_points)
        fig = line_chart(sp_df, x="season", y="points",
                         title="MU Points by Season", y_label="Total Points",
                         markers=True)
        st.plotly_chart(fig, use_container_width=True)
