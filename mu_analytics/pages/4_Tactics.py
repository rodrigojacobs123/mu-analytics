"""Season Tactics — Deep tactical profile for any team over the season."""

import json
import streamlit as st
import pandas as pd
from components.sidebar import render_sidebar
from components.team_selector import team_selector
from viz.kpi_cards import section_header, kpi_card, kpi_row
from viz.charts import (
    tactical_progression_chart, formation_donut, multi_line_chart,
    grouped_bar_chart, bar_chart,
    ppda_trend_chart, dual_axis_trend_chart,
    donut_chart, histogram,
)
from viz.radar import team_radar
from viz.pitch import plot_shot_map
from viz.tables import styled_dataframe
from data.loader import load_standings, load_team_season_stats, build_player_name_map
from data.event_parser import extract_shots, parse_match_info
from data.paths import list_team_folders, partidos_dir
from processing.season_tactics import (
    compute_season_tactical_progression, load_team_season_agg,
    compute_rolling_averages,
)
from processing.team_stats import (
    compute_team_radar_data, RADAR_CATEGORIES, get_team_folder_map,
    build_team_name_lookup,
)
from processing.manager_stats import (
    compute_formation_usage, compute_home_away_split,
    compute_goals_timeline, compute_recent_form,
)
from config import MU_TEAM_NAME, MU_RED, MU_GOLD, MU_DARK_BG

league, season = render_sidebar()

st.title("Season Tactics")

# ── Team Selector ──────────────────────────────────────────────────────────
selected = team_selector(league, season, key="season_tactics_sel",
                         multi=False, label="Select Team")
team_name = selected[0] if selected else MU_TEAM_NAME

# Resolve team_id and folder
standings = load_standings(league, season)
team_row = standings[standings["team_name"] == team_name]
team_id = team_row.iloc[0]["team_id"] if not team_row.empty else ""

# folder mapping
folder_map = get_team_folder_map(league, season)
team_folder = folder_map.get(team_name, "")

if not team_id:
    st.warning(f"Could not find team ID for {team_name}.")
    st.stop()

# ── Load data tiers ────────────────────────────────────────────────────────
# Fast tier: aggregate season stats
agg = load_team_season_agg(league, season, team_folder) if team_folder else {}

# Deep tier: per-match progression (cached)
progression = compute_season_tactical_progression(league, season, team_id)
has_progression = not progression.empty


# ═══════════════════════════════════════════════════════════════════════════
# § 1  TACTICAL IDENTITY
# ═══════════════════════════════════════════════════════════════════════════
section_header("Tactical Identity")

# Season KPI cards (from aggregate stats)
if agg:
    k1, k2, k3, k4 = st.columns(4)
    with k1:
        kpi_card("Possession", f"{agg.get('possession_pct', '–')}%")
    with k2:
        kpi_card("Pass Accuracy", f"{agg.get('pass_accuracy', '–')}%")
    with k3:
        kpi_card("Goals/Match", f"{agg.get('goals_per_match', '–')}")
    with k4:
        kpi_card("Clean Sheets", agg.get("clean_sheets", "–"))

    k5, k6, k7, k8 = st.columns(4)
    with k5:
        kpi_card("Shots/Match", agg.get("shots_per_match", "–"))
    with k6:
        kpi_card("Tackles Won", agg.get("tackles_won", "–"))
    with k7:
        kpi_card("Interceptions", agg.get("interceptions", "–"))
    with k8:
        kpi_card("Set-Piece Goals", agg.get("set_piece_goals", "–"))

# Style label (derived from progression averages if available)
if has_progression:
    avg_ppda = progression["ppda"].mean()
    avg_poss = progression["possession"].mean()
    if avg_ppda < 9 and avg_poss > 55:
        style = "High Press / Possession"
        style_icon = "🔥"
    elif avg_ppda < 9:
        style = "Aggressive Press"
        style_icon = "⚡"
    elif avg_poss > 55:
        style = "Possession-Based"
        style_icon = "🎯"
    elif avg_ppda > 13:
        style = "Low Block / Counter"
        style_icon = "🛡️"
    else:
        style = "Balanced / Transitional"
        style_icon = "⚖️"

    st.markdown(f"""
    <div style="text-align:center;padding:0.6rem;margin:0.5rem 0 1rem;
         background:#1A1A2E;border-radius:8px;border-left:4px solid {MU_RED};">
        <span style="font-size:1.6rem;">{style_icon}</span>
        <span style="color:#ccc;font-size:1.1rem;font-weight:600;margin-left:0.5rem;">
            Tactical Style: {style}
        </span>
        <span style="color:#888;font-size:0.8rem;margin-left:1rem;">
            (Avg PPDA: {avg_ppda:.1f} | Avg Possession: {avg_poss:.1f}%)
        </span>
    </div>
    """, unsafe_allow_html=True)

# Radar: team vs league average
st.markdown("#### Team Radar vs League")
all_folders = list_team_folders(league, season)
all_radar = compute_team_radar_data(league, season, all_folders)

if all_radar and team_name in all_radar:
    # Compute league average
    all_values = list(all_radar.values())
    n_cats = len(RADAR_CATEGORIES)
    league_avg = [
        round(sum(v[i] for v in all_values) / len(all_values), 1)
        for i in range(n_cats)
    ]
    radar_data = {
        team_name: all_radar[team_name],
        "League Average": league_avg,
    }
    fig = team_radar(radar_data, RADAR_CATEGORIES, title=f"{team_name} vs League")
    st.plotly_chart(fig, width="stretch")
else:
    st.info("Radar data not available for this team.")


# Recent form
form = compute_recent_form(league, season, team_id, n=5)
if form:
    form_colors = {"W": "#4CAF50", "D": "#FFC107", "L": "#F44336"}
    chips = ""
    for res in form:
        c = form_colors.get(res, "#888")
        chips += (
            f'<span style="display:inline-block;width:32px;height:32px;line-height:32px;'
            f'text-align:center;border-radius:6px;background:{c};color:white;'
            f'font-weight:700;margin:0 3px;">{res}</span>'
        )
    st.markdown(
        f'<div style="margin:0.5rem 0;"><span style="color:#888;font-size:0.85rem;'
        f'margin-right:0.5rem;">Last 5:</span>{chips}</div>',
        unsafe_allow_html=True,
    )


# ═══════════════════════════════════════════════════════════════════════════
# § 2  FORMATION PROFILE
# ═══════════════════════════════════════════════════════════════════════════
st.markdown("---")
section_header("Formation Profile")

formations = compute_formation_usage(league, season, team_id)

if formations:
    fc1, fc2 = st.columns([1, 2])
    with fc1:
        fig = formation_donut(formations, title="Formation Usage")
        st.plotly_chart(fig, width="stretch")
    with fc2:
        # Formation results table
        if has_progression:
            form_results = progression[["match_num", "opponent", "venue", "formation",
                                         "result", "score"]].copy()
            form_results.columns = ["#", "Opponent", "H/A", "Formation", "Result", "Score"]
            st.dataframe(
                form_results.style.applymap(
                    lambda v: (
                        "color: #4CAF50; font-weight: bold" if v == "W"
                        else ("color: #FFC107" if v == "D"
                              else ("color: #F44336" if v == "L" else ""))
                    ),
                    subset=["Result"],
                ),
                use_container_width=True,
                height=350,
            )
        else:
            # Fallback: just show formation frequency table
            form_df = pd.DataFrame(formations)
            form_df.columns = ["Formation", "Matches", "Usage %"]
            st.dataframe(form_df, use_container_width=True)
else:
    st.info("No formation data found. Ensure match files exist in partidos/.")


# ═══════════════════════════════════════════════════════════════════════════
# § 3  TACTICAL PROGRESSION
# ═══════════════════════════════════════════════════════════════════════════
st.markdown("---")
section_header("Tactical Progression")

if has_progression:
    st.caption("5-match rolling averages. Bottom markers: 🟩 Win  🟨 Draw  🟥 Loss")

    # Compute rolling averages for all metrics
    all_metrics = ["possession", "ppda", "field_tilt", "pass_accuracy", "progressive_passes"]
    prog_with_rolling = compute_rolling_averages(progression, all_metrics, window=5)

    # ── Chart 1: Pressing Intensity (PPDA with tactical bands) ────────────
    fig_ppda = ppda_trend_chart(
        prog_with_rolling,
        title=f"{team_name} — Pressing Intensity",
    )
    st.plotly_chart(fig_ppda, use_container_width=True)

    # ── Chart 2: Possession & Territory (both % scale) ────────────────────
    fig_poss = dual_axis_trend_chart(
        prog_with_rolling,
        left_metric="possession",
        right_metric="field_tilt",
        left_rolling="possession_rolling",
        right_rolling="field_tilt_rolling",
        left_color=MU_RED,
        right_color="#42A5F5",
        left_label="Possession %",
        right_label="Field Tilt %",
        title=f"{team_name} — Possession & Territorial Control",
    )
    st.plotly_chart(fig_poss, use_container_width=True)

    # ── Chart 3: Passing Quality (dual axis — % vs count) ────────────────
    fig_pass = dual_axis_trend_chart(
        prog_with_rolling,
        left_metric="pass_accuracy",
        right_metric="progressive_passes",
        left_rolling="pass_accuracy_rolling",
        right_rolling="progressive_passes_rolling",
        left_color=MU_GOLD,
        right_color="#42A5F5",
        left_label="Pass Accuracy %",
        right_label="Progressive Passes",
        title=f"{team_name} — Passing Quality",
    )
    st.plotly_chart(fig_pass, use_container_width=True)

    # Insight callout
    if len(progression) >= 10:
        first5 = progression.head(5)
        last5 = progression.tail(5)
        ppda_start = first5["ppda"].mean()
        ppda_end = last5["ppda"].mean()
        poss_start = first5["possession"].mean()
        poss_end = last5["possession"].mean()
        prog_start = first5["progressive_passes"].mean()
        prog_end = last5["progressive_passes"].mean()

        press_desc = "pressing more intensely" if ppda_end < ppda_start else "pressing less"
        prog_dir = "increasing" if prog_end > prog_start else "decreasing"

        st.markdown(f"""
        <div style="padding:0.8rem;background:#1A1A2E;border-radius:8px;border-left:4px solid {MU_GOLD};
             margin:0.5rem 0;">
            <span style="color:#ccc;font-size:0.9rem;">
                <b>📊 Trend Analysis:</b><br>
                • <b>Pressing:</b> PPDA {ppda_start:.1f} → {ppda_end:.1f} — {press_desc}<br>
                • <b>Possession:</b> {poss_start:.1f}% → {poss_end:.1f}%<br>
                • <b>Progressive Passes:</b> {prog_start:.0f} → {prog_end:.0f}/game — {prog_dir}
            </span>
        </div>
        """, unsafe_allow_html=True)
else:
    st.info("Per-match tactical progression requires match files in partidos/.")


# ═══════════════════════════════════════════════════════════════════════════
# § 4  ATTACKING & DEFENSIVE PROFILE
# ═══════════════════════════════════════════════════════════════════════════
st.markdown("---")
section_header("Attacking & Defensive Profile")

if agg:
    # Attacking stats
    st.markdown("#### Attacking")
    ac1, ac2, ac3, ac4 = st.columns(4)
    games = agg.get("games_played", 38)
    with ac1:
        kpi_card("Goals", int(agg.get("goals", 0)))
    with ac2:
        kpi_card("Shots/Match", agg.get("shots_per_match", "–"))
    with ac3:
        sot = agg.get("shots_on_target", 0)
        ts = agg.get("total_shots", 1) or 1
        kpi_card("SOT %", f"{round(sot / ts * 100, 1)}%")
    with ac4:
        kpi_card("Key Passes", int(agg.get("key_passes", 0)))

    # Defensive stats
    st.markdown("#### Defending")
    dc1, dc2, dc3, dc4 = st.columns(4)
    with dc1:
        kpi_card("Goals Conceded", int(agg.get("goals_conceded", 0)))
    with dc2:
        kpi_card("Tackles Won", int(agg.get("tackles_won", 0)))
    with dc3:
        kpi_card("Tackle Success", f"{agg.get('tackle_success', 0)}%")
    with dc4:
        kpi_card("Clearances", int(agg.get("total_clearances", 0)))

# Home vs Away split
st.markdown("#### Home vs Away Performance")
ha_split = compute_home_away_split(league, season, team_id)

ha_df = pd.DataFrame({
    "Metric": ["Wins", "Draws", "Losses", "Goals For", "Goals Against"],
    "Home": [
        ha_split["home_w"], ha_split["home_d"], ha_split["home_l"],
        ha_split["home_gf"], ha_split["home_ga"],
    ],
    "Away": [
        ha_split["away_w"], ha_split["away_d"], ha_split["away_l"],
        ha_split["away_gf"], ha_split["away_ga"],
    ],
})

fig = grouped_bar_chart(ha_df, x="Metric", y_cols=["Home", "Away"],
                        colors=[MU_RED, "#42A5F5"],
                        title=f"{team_name} — Home vs Away",
                        bar_names=["Home", "Away"])
st.plotly_chart(fig, width="stretch")


# ═══════════════════════════════════════════════════════════════════════════
# § 5  SET-PIECE SEASON SUMMARY
# ═══════════════════════════════════════════════════════════════════════════
st.markdown("---")
section_header("Set-Piece Season Summary")

if agg:
    sp1, sp2, sp3, sp4 = st.columns(4)
    with sp1:
        kpi_card("Corners Taken", int(agg.get("corners_taken", 0)))
    with sp2:
        ca = agg.get("corners_accurate", 0)
        ct = agg.get("corners_taken", 1) or 1
        kpi_card("Corner Accuracy", f"{round(ca / ct * 100, 1)}%")
    with sp3:
        kpi_card("Set-Piece Goals", int(agg.get("set_piece_goals", 0)))
    with sp4:
        kpi_card("Penalty Goals", int(agg.get("penalty_goals", 0)))

# Per-match SP trend from progression data
if has_progression and "sp_shots" in progression.columns:
    sp_trend = compute_rolling_averages(progression, ["sp_shots", "corners_won"], window=5)

    fig = tactical_progression_chart(
        sp_trend,
        metrics=["sp_shots", "corners_won"],
        title=f"{team_name} — Set-Piece Threat Over Season",
        colors=["#4CAF50", MU_GOLD],
        y_label="Count",
    )
    st.plotly_chart(fig, width="stretch")


# ═══════════════════════════════════════════════════════════════════════════
# § 6  PASSING PROFILE
# ═══════════════════════════════════════════════════════════════════════════
st.markdown("---")
section_header("Passing Profile")

if agg:
    games = agg.get("games_played", 38) or 38

    pp1, pp2, pp3, pp4 = st.columns(4)
    with pp1:
        kpi_card("Total Passes", int(agg.get("total_passes", 0)))
    with pp2:
        kpi_card("Pass Accuracy", f"{agg.get('pass_accuracy', 0)}%")
    with pp3:
        kpi_card("Crossing Accuracy", f"{agg.get('crossing_accuracy', 0)}%")
    with pp4:
        kpi_card("Passes/Match", round(agg.get("total_passes", 0) / games, 0))

    # Pass type distribution
    short = agg.get("successful_short_passes", 0)
    long = agg.get("successful_long_passes", 0)
    crosses = agg.get("successful_crosses", 0)

    if short + long + crosses > 0:
        pass_dist = pd.DataFrame({
            "Type": ["Short Passes", "Long Passes", "Crosses"],
            "Count": [short, long, crosses],
        })
        fig = bar_chart(pass_dist, x="Type", y="Count",
                        title=f"{team_name} — Pass Type Distribution",
                        color=MU_RED)
        st.plotly_chart(fig, width="stretch")

    # Possession stats
    pp5, pp6, pp7, pp8 = st.columns(4)
    with pp5:
        kpi_card("Recoveries", int(agg.get("recoveries", 0)))
    with pp6:
        kpi_card("Successful Dribbles", int(agg.get("successful_dribbles", 0)))
    with pp7:
        kpi_card("Losses of Possession", int(agg.get("total_losses", 0)))
    with pp8:
        kpi_card("Fouls Won", int(agg.get("fouls_won", 0)))
else:
    st.info("Aggregate season stats not available for this team.")


# ═══════════════════════════════════════════════════════════════════════════
# § 7  GOALS TIMELINE
# ═══════════════════════════════════════════════════════════════════════════
st.markdown("---")
section_header("Goal Difference Trend")

goals_df = compute_goals_timeline(league, season, team_id)
if not goals_df.empty:
    fig = multi_line_chart(
        goals_df, x="match_num",
        y_cols=["gd_cumulative"],
        colors=[MU_RED],
        title=f"{team_name} — Cumulative Goal Difference",
        y_label="Goal Difference",
    )
    # Add zero line
    fig.add_hline(y=0, line_dash="dash", line_color="#555", opacity=0.5)
    st.plotly_chart(fig, width="stretch")


# ═══════════════════════════════════════════════════════════════════════════
# § 8  xG EXPLORER
# ═══════════════════════════════════════════════════════════════════════════
st.markdown("---")
section_header("xG Explorer")
st.caption("Interactive shot analysis across the season")


# ── Shot data loader (scans partidos/ for the selected team) ──────────────
@st.cache_data(ttl=3600)
def _load_team_season_shots(_league: str, _season: str, _team_id: str) -> pd.DataFrame:
    """Load all shots from matches involving a given team."""
    pdir = partidos_dir(_league, _season)
    if not pdir.exists():
        return pd.DataFrame()

    all_shots = []
    for fpath in sorted(pdir.iterdir()):
        if fpath.suffix != ".json":
            continue
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                raw = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue

        info = parse_match_info(raw)
        home_id = info["home_id"]
        away_id = info["away_id"]

        if _team_id not in (home_id, away_id):
            continue

        events = raw.get("liveData", {}).get("event", [])
        shots = extract_shots(events)
        if shots.empty:
            continue

        shots["match_id"] = info.get("match_id", fpath.stem)
        shots["matchday"] = info["matchday"]
        shots["home_team"] = info["home_team"]
        shots["away_team"] = info["away_team"]
        shots["date"] = info["date"]
        all_shots.append(shots)

    return pd.concat(all_shots, ignore_index=True) if all_shots else pd.DataFrame()


with st.spinner("Loading season shot data..."):
    season_shots = _load_team_season_shots(league, season, team_id)

if not season_shots.empty:
    # Resolve player names
    _name_map = build_player_name_map(league, season)
    season_shots["player_display"] = season_shots.apply(
        lambda r: _name_map.get(r["player_id"], r["player_name"]), axis=1
    )

    # ── Filters ────────────────────────────────────────────────────────────
    xf1, xf2, xf3, xf4 = st.columns(4)
    with xf1:
        xg_team_filter = st.selectbox(
            "Team", ["All", team_name, "Opponents"], key="xg_team_t"
        )
    with xf2:
        xg_outcomes = season_shots["outcome"].unique().tolist()
        xg_outcome_filter = st.multiselect(
            "Outcome", xg_outcomes, default=xg_outcomes, key="xg_outcome_t"
        )
    with xf3:
        xg_body_parts = season_shots["body_part"].dropna().unique().tolist()
        xg_body_filter = st.multiselect(
            "Body Part", xg_body_parts, default=xg_body_parts, key="xg_body_t"
        )
    with xf4:
        xg_minute_range = st.slider(
            "Minute Range", 0, 95, (0, 95), key="xg_minute_t"
        )

    # Apply filters
    xg_filtered = season_shots.copy()
    if xg_team_filter == team_name:
        xg_filtered = xg_filtered[xg_filtered["team_id"] == team_id]
    elif xg_team_filter == "Opponents":
        xg_filtered = xg_filtered[xg_filtered["team_id"] != team_id]
    xg_filtered = xg_filtered[xg_filtered["outcome"].isin(xg_outcome_filter)]
    xg_filtered = xg_filtered[xg_filtered["body_part"].isin(xg_body_filter)]
    xg_filtered = xg_filtered[
        (xg_filtered["minute"] >= xg_minute_range[0])
        & (xg_filtered["minute"] <= xg_minute_range[1])
    ]

    # ── KPIs ───────────────────────────────────────────────────────────────
    xg_goals = xg_filtered[xg_filtered["outcome"] == "Goal"]
    xg_total = xg_filtered["xg"].sum()
    xg_conv = (len(xg_goals) / len(xg_filtered) * 100) if len(xg_filtered) > 0 else 0
    xg_diff = len(xg_goals) - xg_total

    kpi_row([
        {"label": "Total Shots", "value": len(xg_filtered)},
        {"label": "Goals", "value": len(xg_goals)},
        {"label": "Total xG", "value": f"{xg_total:.2f}"},
        {"label": "Conversion %", "value": f"{xg_conv:.1f}%"},
    ])
    st.markdown("")
    xk1, xk2 = st.columns(2)
    xk1.metric("Goals − xG", f"{xg_diff:+.2f}")
    xk2.metric(
        "Avg xG/Shot",
        f"{(xg_total / len(xg_filtered)):.3f}" if len(xg_filtered) > 0 else "0",
    )

    # ── Shot Map ───────────────────────────────────────────────────────────
    st.markdown("---")
    plot_shot_map(xg_filtered, title=f"Shots ({xg_team_filter})")

    # ── Distributions ──────────────────────────────────────────────────────
    xd1, xd2 = st.columns(2)
    with xd1:
        outcome_counts = xg_filtered["outcome"].value_counts()
        fig = donut_chart(
            outcome_counts.index.tolist(),
            outcome_counts.values.tolist(),
            title="Shot Outcomes",
            colors=[MU_RED, MU_GOLD, "#888888", "#FF9800", "#42A5F5"],
        )
        st.plotly_chart(fig, width="stretch")
    with xd2:
        body_counts = xg_filtered["body_part"].value_counts()
        fig = donut_chart(
            body_counts.index.tolist(),
            body_counts.values.tolist(),
            title="Shot Type",
        )
        st.plotly_chart(fig, width="stretch")

    # ── xG Distribution ───────────────────────────────────────────────────
    fig = histogram(
        xg_filtered["xg"], title="Distribution of xG Values",
        x_label="xG", nbins=25,
    )
    st.plotly_chart(fig, width="stretch")

    # ── Player xG Leaderboard ─────────────────────────────────────────────
    st.markdown("---")
    st.markdown("#### Player xG Leaderboard")
    player_xg = xg_filtered.groupby("player_display").agg(
        shots=("xg", "count"),
        total_xg=("xg", "sum"),
        goals=("outcome", lambda x: (x == "Goal").sum()),
    ).reset_index()
    player_xg["xg_diff"] = player_xg["goals"] - player_xg["total_xg"]
    player_xg = player_xg.sort_values("total_xg", ascending=False)
    player_xg.columns = ["Player", "Shots", "Total xG", "Goals", "Goals − xG"]
    player_xg["Total xG"] = player_xg["Total xG"].round(2)
    player_xg["Goals − xG"] = player_xg["Goals − xG"].round(2)
    styled_dataframe(player_xg.head(20), height=500)

    # ── Player Drill-Down ─────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("#### Player Drill-Down")
    xg_players = xg_filtered["player_display"].dropna().unique().tolist()
    if xg_players:
        xg_sel_player = st.selectbox(
            "Select Player", sorted(xg_players), key="xg_player_t"
        )
        player_shots = xg_filtered[xg_filtered["player_display"] == xg_sel_player]

        pd1, pd2 = st.columns([2, 1])
        with pd1:
            plot_shot_map(player_shots, title=f"{xg_sel_player} Shot Map")
        with pd2:
            st.metric("Shots", len(player_shots))
            st.metric("Goals", len(player_shots[player_shots["outcome"] == "Goal"]))
            st.metric("xG", f"{player_shots['xg'].sum():.2f}")

        log = player_shots[["minute", "outcome", "xg", "body_part", "matchday"]].copy()
        log.columns = ["Minute", "Outcome", "xG", "Body Part", "Matchday"]
        log["xG"] = log["xG"].round(3)
        styled_dataframe(log.sort_values("Minute"), height=300)
else:
    st.info("No shot data available. Ensure match files exist in partidos/.")
