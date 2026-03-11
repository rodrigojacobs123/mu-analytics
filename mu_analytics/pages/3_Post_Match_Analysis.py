"""Post-Match Analysis — full match dashboard with stats, xG, pitch viz & tactical deep dive."""

import streamlit as st
import pandas as pd
from components.sidebar import render_sidebar
from components.match_selector import match_selector
from viz.kpi_cards import (
    section_header, match_header_card, stats_comparison_table,
    key_events_timeline, kpi_card, kpi_row,
)
from viz.pitch import (
    plot_shot_map, plot_pass_network, plot_heatmap,
    plot_formation, plot_defensive_actions,
    plot_progressive_passes, plot_set_piece_map,
    plot_pass_map, plot_ball_win_height, plot_dominant_actions_by_zone,
    ZONE_ACTION_COLORS,
)
from viz.charts import xg_race_chart
from data.loader import load_match_raw, build_player_name_map
from data.event_parser import (
    parse_match_info, extract_shots, extract_goals,
    extract_all_touches, extract_key_events,
    extract_passes, extract_tackles, extract_interceptions,
    extract_ball_recoveries, extract_formation, extract_substitutions,
    extract_take_ons, extract_aerials, extract_fouls,
    extract_clearances,
)
from processing.xg import compute_xg_timeline, compute_match_xg
from processing.pass_network import build_pass_network
from processing.match_stats import compute_match_stats
from processing.set_pieces import (
    compute_set_piece_stats, compute_corner_breakdown, compute_dangerous_fk_zones,
)
from processing.formations import (
    get_match_formations, detect_formation_changes,
    compute_tactical_kpis, compute_possession_zones,
    compute_ppda, compute_field_tilt,
)
from processing.match_ratings import compute_match_ratings, rating_color
from config import MU_TEAM_ID, MU_RED, MU_GOLD, MU_DARK_BG

league, season = render_sidebar()

st.title("Post-Match Analysis")

match = match_selector(league, season, key="postmatch_sel")
if not match:
    st.info("Select a match to analyze.")
    st.stop()

match_id = match.get("match_id", "")
if not match_id:
    st.warning("Match ID not found. Select a different match.")
    st.stop()

# Load full match data
raw = load_match_raw(league, season, match_id)
if not raw:
    st.error("Could not load match data.")
    st.stop()

info = parse_match_info(raw)
events = raw.get("liveData", {}).get("event", [])
name_map = build_player_name_map(league, season)

home_team = info["home_team"]
away_team = info["away_team"]
home_id = info["home_id"]
away_id = info["away_id"]

# ── Match Header with Crests ──────────────────────────────────────────────
match_header_card(
    home_team=home_team, away_team=away_team,
    home_score=info["home_score"], away_score=info["away_score"],
    home_id=home_id, away_id=away_id,
    matchday=info["matchday"], date=info["date"], venue=info["venue"],
    ht_home=info["ht_home"], ht_away=info["ht_away"],
)

# ── Stats Comparison Bars ─────────────────────────────────────────────────
section_header("Match Statistics")
match_stats = compute_match_stats(events, home_id, away_id)
stats_comparison_table(match_stats)

# ── xG Race + Key Events (side by side) ──────────────────────────────────
section_header("xG Flow & Key Events")
col1, col2 = st.columns([3, 2])

with col1:
    timeline = compute_xg_timeline(events, home_id, away_id)
    goals = extract_goals(events)
    home_xg = compute_match_xg(events, home_id)
    away_xg = compute_match_xg(events, away_id)
    fig = xg_race_chart(timeline, home_team, away_team, goals)
    st.plotly_chart(fig, width="stretch")
    # xG summary below chart
    st.markdown(
        f'<div style="text-align:center;color:#999;font-size:0.85rem;">'
        f'<span style="color:{MU_RED};font-weight:700;">{home_team} xG: {home_xg:.2f}</span>'
        f' &nbsp;&middot;&nbsp; '
        f'<span style="color:#42A5F5;font-weight:700;">{away_team} xG: {away_xg:.2f}</span>'
        f'</div>',
        unsafe_allow_html=True,
    )

with col2:
    key_events = extract_key_events(events)
    key_events_timeline(key_events, home_team, away_team, home_id, away_id)

# ── Shot Maps ─────────────────────────────────────────────────────────────
section_header("Shot Maps")
home_shots = extract_shots(events, home_id)
away_shots = extract_shots(events, away_id)
col1, col2 = st.columns(2)
with col1:
    plot_shot_map(home_shots, title=f"{home_team} Shots")
with col2:
    plot_shot_map(away_shots, title=f"{away_team} Shots")


# ══════════════════════════════════════════════════════════════════════════
#                     TACTICAL ANALYSIS
# ══════════════════════════════════════════════════════════════════════════
st.markdown("---")

# ── Team & Period Selector ────────────────────────────────────────────────
tcol1, tcol2 = st.columns(2)
with tcol1:
    team_choice = st.radio("Team Focus", [home_team, away_team],
                           horizontal=True, key="pm_team")
with tcol2:
    half_choice = st.radio("Period", ["Full Match", "1st Half", "2nd Half"],
                           horizontal=True, key="pm_half")

team_id = home_id if team_choice == home_team else away_id
opponent_id = away_id if team_id == home_id else home_id
period = None if half_choice == "Full Match" else (1 if half_choice == "1st Half" else 2)

# ═══════════════════════════════════════════════════════════════════════════
# § 1  TACTICAL OVERVIEW KPIs
# ═══════════════════════════════════════════════════════════════════════════
section_header("Tactical Overview")

kpis = compute_tactical_kpis(events, team_id, opponent_id, period)

kpi_cols = st.columns(4)
with kpi_cols[0]:
    kpi_card("Possession", f"{kpis['possession_pct']}%")
with kpi_cols[1]:
    ppda_val = kpis["ppda"]
    ppda_label = "High" if ppda_val < 9 else ("Medium" if ppda_val < 13 else "Low")
    kpi_card("PPDA", f"{ppda_val}", delta=ppda_label, delta_suffix=" press")
with kpi_cols[2]:
    kpi_card("Field Tilt", f"{kpis['field_tilt']}%")
with kpi_cols[3]:
    kpi_card("Pass Accuracy", f"{kpis['pass_accuracy']}%")

kpi_cols2 = st.columns(4)
with kpi_cols2[0]:
    kpi_card("Total Passes", kpis["total_passes"])
with kpi_cols2[1]:
    kpi_card("Progressive Passes", kpis["progressive_passes"])
with kpi_cols2[2]:
    kpi_card("High Recoveries", kpis["high_press_recoveries"])
with kpi_cols2[3]:
    kpi_card("Avg Def. Line", f"{kpis['defensive_line_height']}m")

# ═══════════════════════════════════════════════════════════════════════════
# § 2  SIDE-BY-SIDE FORMATION COMPARISON
# ═══════════════════════════════════════════════════════════════════════════
section_header("Formation Comparison")

formations = get_match_formations(events, home_id, away_id)
home_formation = formations["home"]
away_formation = formations["away"]

fcol1, fcol2 = st.columns(2)
with fcol1:
    primary_home = MU_RED if home_id == MU_TEAM_ID else "#42A5F5"
    plot_formation(home_formation, name_map,
                   title=f"{home_team}",
                   primary_color=primary_home)
with fcol2:
    primary_away = MU_RED if away_id == MU_TEAM_ID else "#42A5F5"
    plot_formation(away_formation, name_map,
                   title=f"{away_team}",
                   primary_color=primary_away)

# Formation change detection
home_changes = detect_formation_changes(events, home_id)
away_changes = detect_formation_changes(events, away_id)

if home_changes or away_changes:
    st.markdown("#### Formation Changes During Match")
    chcol1, chcol2 = st.columns(2)
    with chcol1:
        if home_changes:
            st.markdown(f"**{home_team}**")
            start_f = home_formation["formation_str"] if home_formation else "?"
            st.markdown(f"Started: **{start_f}**")
            for ch in home_changes:
                st.markdown(f"- **{ch['minute']}'** Changed to **{ch['formation_str']}**")
        else:
            st.caption(f"{home_team}: No formation changes")
    with chcol2:
        if away_changes:
            st.markdown(f"**{away_team}**")
            start_f = away_formation["formation_str"] if away_formation else "?"
            st.markdown(f"Started: **{start_f}**")
            for ch in away_changes:
                st.markdown(f"- **{ch['minute']}'** Changed to **{ch['formation_str']}**")
        else:
            st.caption(f"{away_team}: No formation changes")

# ═══════════════════════════════════════════════════════════════════════════
# § 3  POSSESSION ZONES (Territorial Analysis)
# ═══════════════════════════════════════════════════════════════════════════
section_header("Territorial Dominance")

zones_home = compute_possession_zones(events, home_id, period)
zones_away = compute_possession_zones(events, away_id, period)


# Visual third-by-third bars
def _zone_bar(label, home_val, away_val, home_team_name, away_team_name):
    """Render a zone comparison bar."""
    h_color = MU_RED if home_id == MU_TEAM_ID else "#42A5F5"
    a_color = MU_RED if away_id == MU_TEAM_ID else "#FF9800"
    st.markdown(f"""
    <div style="margin: 0.6rem 0;">
        <div style="display:flex;justify-content:space-between;margin-bottom:4px;">
            <span style="color:#ccc;font-size:0.85rem;font-weight:600;">{home_team_name}</span>
            <span style="color:#888;font-size:0.8rem;text-transform:uppercase;letter-spacing:1px;">{label}</span>
            <span style="color:#ccc;font-size:0.85rem;font-weight:600;">{away_team_name}</span>
        </div>
        <div style="display:flex;height:24px;border-radius:4px;overflow:hidden;background:#222;">
            <div style="width:{home_val}%;background:linear-gradient(90deg,{h_color}dd,{h_color}88);
                 display:flex;align-items:center;justify-content:center;">
                <span style="color:white;font-size:0.75rem;font-weight:700;">{home_val}%</span>
            </div>
            <div style="width:{away_val}%;background:linear-gradient(90deg,{a_color}88,{a_color}dd);
                 display:flex;align-items:center;justify-content:center;">
                <span style="color:white;font-size:0.75rem;font-weight:700;">{away_val}%</span>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)


# Approximate: use total touch counts per zone
t_home = extract_all_touches(events, home_id)
t_away = extract_all_touches(events, away_id)
if period is not None:
    if not t_home.empty:
        t_home = t_home[t_home["period"] == period]
    if not t_away.empty:
        t_away = t_away[t_away["period"] == period]


def _zone_split(home_touches, away_touches, x_min, x_max):
    h = len(home_touches[(home_touches["x"] >= x_min) & (home_touches["x"] < x_max)]) if not home_touches.empty else 0
    a = len(away_touches[(away_touches["x"] >= x_min) & (away_touches["x"] < x_max)]) if not away_touches.empty else 0
    total = h + a
    if total == 0:
        return 50, 50
    return round(h / total * 100), round(a / total * 100)


h_def, a_def = _zone_split(t_home, t_away, 0, 33.33)
h_mid, a_mid = _zone_split(t_home, t_away, 33.33, 66.66)
h_att, a_att = _zone_split(t_home, t_away, 66.66, 100)

_zone_bar("Defensive Third", h_def, a_def, home_team, away_team)
_zone_bar("Middle Third", h_mid, a_mid, home_team, away_team)
_zone_bar("Attacking Third", h_att, a_att, home_team, away_team)

# Field tilt indicator
ft_home = compute_field_tilt(events, home_id, away_id, period)
ft_away = compute_field_tilt(events, away_id, home_id, period)
st.markdown(f"""
<div style="text-align:center;margin:1rem 0;padding:0.6rem;background:#1A1A2E;border-radius:8px;">
    <span style="color:#888;font-size:0.8rem;text-transform:uppercase;letter-spacing:1px;">
        Field Tilt
    </span>
    <div style="display:flex;justify-content:center;align-items:center;gap:2rem;margin-top:0.3rem;">
        <span style="color:{MU_RED if home_id == MU_TEAM_ID else '#42A5F5'};font-size:1.4rem;font-weight:700;">{ft_home}%</span>
        <span style="color:#555;font-size:0.9rem;">vs</span>
        <span style="color:{MU_RED if away_id == MU_TEAM_ID else '#FF9800'};font-size:1.4rem;font-weight:700;">{ft_away}%</span>
    </div>
</div>
""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════
# § 4  PASS NETWORKS (Side by Side, period-aware)
# ═══════════════════════════════════════════════════════════════════════════
section_header(f"Pass Networks — {half_choice}")

pn_col1, pn_col2 = st.columns(2)
with pn_col1:
    nodes_h, edges_h = build_pass_network(events, home_id, period=period)
    h_color = MU_RED if home_id == MU_TEAM_ID else "#42A5F5"
    plot_pass_network(nodes_h, edges_h,
                      title=f"{home_team}",
                      node_color=h_color)
with pn_col2:
    nodes_a, edges_a = build_pass_network(events, away_id, period=period)
    a_color = MU_RED if away_id == MU_TEAM_ID else "#FF9800"
    plot_pass_network(nodes_a, edges_a,
                      title=f"{away_team}",
                      node_color=a_color)


# ═══════════════════════════════════════════════════════════════════════════
# § 5  PRESSING ANALYSIS
# ═══════════════════════════════════════════════════════════════════════════
section_header("Pressing Analysis")

ppda_home = compute_ppda(events, home_id, away_id, period)
ppda_away = compute_ppda(events, away_id, home_id, period)

pcol1, pcol2, pcol3 = st.columns([1, 2, 1])
with pcol1:
    st.markdown(f"""
    <div style="text-align:center;padding:1rem;background:#1A1A2E;border-radius:8px;">
        <p style="color:#888;font-size:0.75rem;text-transform:uppercase;margin:0;">
            {home_team} PPDA
        </p>
        <p style="color:{MU_RED if home_id == MU_TEAM_ID else '#42A5F5'};font-size:2rem;font-weight:700;margin:0;">
            {ppda_home}
        </p>
        <p style="color:#666;font-size:0.75rem;margin:0;">
            {'High press' if ppda_home < 9 else ('Moderate' if ppda_home < 13 else 'Low block')}
        </p>
    </div>
    """, unsafe_allow_html=True)
with pcol3:
    st.markdown(f"""
    <div style="text-align:center;padding:1rem;background:#1A1A2E;border-radius:8px;">
        <p style="color:#888;font-size:0.75rem;text-transform:uppercase;margin:0;">
            {away_team} PPDA
        </p>
        <p style="color:{MU_RED if away_id == MU_TEAM_ID else '#FF9800'};font-size:2rem;font-weight:700;margin:0;">
            {ppda_away}
        </p>
        <p style="color:#666;font-size:0.75rem;margin:0;">
            {'High press' if ppda_away < 9 else ('Moderate' if ppda_away < 13 else 'Low block')}
        </p>
    </div>
    """, unsafe_allow_html=True)

with pcol2:
    st.markdown(f"""
    <div style="padding:0.8rem;background:#1A1A2E;border-radius:8px;font-size:0.8rem;color:#999;">
        <p style="margin:0 0 0.5rem;color:#ccc;font-weight:600;">PPDA Guide</p>
        <p style="margin:0.2rem 0;"><b style="color:#4CAF50;">&lt; 9</b> — Intense high press</p>
        <p style="margin:0.2rem 0;"><b style="color:{MU_GOLD};">9 – 13</b> — Moderate pressing</p>
        <p style="margin:0.2rem 0;"><b style="color:#888;">&gt; 13</b> — Low block / counter-attack</p>
        <p style="margin:0.5rem 0 0;color:#666;font-size:0.7rem;">
            PPDA = Opponent passes allowed / Defensive actions
        </p>
    </div>
    """, unsafe_allow_html=True)

# Pressing heatmap — ball recoveries + tackles in opponent half
st.markdown(f"#### High Press Zones — {team_choice}")
recoveries = extract_ball_recoveries(events, team_id)
tackles = extract_tackles(events, team_id)

if period is not None:
    if not recoveries.empty:
        recoveries = recoveries[recoveries["period"] == period]
    if not tackles.empty:
        tackles = tackles[tackles["period"] == period]

pressing_actions = pd.DataFrame()
if not recoveries.empty:
    pressing = recoveries[recoveries["x"] > 50]
    if not tackles.empty:
        high_tackles = tackles[tackles["x"] > 50]
        pressing_actions = pd.concat([pressing[["x", "y"]], high_tackles[["x", "y"]]])
    else:
        pressing_actions = pressing[["x", "y"]]

if not pressing_actions.empty:
    plot_heatmap(pressing_actions, title=f"{team_choice} High Press Zones")
else:
    st.info("No high-press actions detected.")


# ═══════════════════════════════════════════════════════════════════════════
# § 6  DEFENSIVE ACTIONS (Side by Side)
# ═══════════════════════════════════════════════════════════════════════════
section_header("Defensive Actions")

tackles_home = extract_tackles(events, home_id)
tackles_away = extract_tackles(events, away_id)
ints_home = extract_interceptions(events, home_id)
ints_away = extract_interceptions(events, away_id)

if period is not None:
    if not tackles_home.empty:
        tackles_home = tackles_home[tackles_home["period"] == period]
    if not tackles_away.empty:
        tackles_away = tackles_away[tackles_away["period"] == period]
    if not ints_home.empty:
        ints_home = ints_home[ints_home["period"] == period]
    if not ints_away.empty:
        ints_away = ints_away[ints_away["period"] == period]

# KPI summary
dcol1, dcol2, dcol3, dcol4 = st.columns(4)
with dcol1:
    t_won_h = len(tackles_home[tackles_home["outcome"] == 1]) if not tackles_home.empty else 0
    kpi_card(f"{home_team[:15]} Tackles", f"{t_won_h}/{len(tackles_home)}")
with dcol2:
    kpi_card(f"{home_team[:15]} Interceptions", len(ints_home))
with dcol3:
    t_won_a = len(tackles_away[tackles_away["outcome"] == 1]) if not tackles_away.empty else 0
    kpi_card(f"{away_team[:15]} Tackles", f"{t_won_a}/{len(tackles_away)}")
with dcol4:
    kpi_card(f"{away_team[:15]} Interceptions", len(ints_away))

# Side-by-side pitch maps
da_col1, da_col2 = st.columns(2)
with da_col1:
    plot_defensive_actions(tackles_home, ints_home,
                           title=f"{home_team} Defensive Actions")
with da_col2:
    plot_defensive_actions(tackles_away, ints_away,
                           title=f"{away_team} Defensive Actions")


# ═══════════════════════════════════════════════════════════════════════════
# § 6.5  BALL WIN HEIGHT
# ═══════════════════════════════════════════════════════════════════════════
section_header("Ball Win Height")

rec_home = extract_ball_recoveries(events, home_id)
rec_away = extract_ball_recoveries(events, away_id)
if period is not None:
    if not rec_home.empty:
        rec_home = rec_home[rec_home["period"] == period]
    if not rec_away.empty:
        rec_away = rec_away[rec_away["period"] == period]

bw_col1, bw_col2 = st.columns(2)
with bw_col1:
    plot_ball_win_height(tackles_home, ints_home, rec_home, title=f"{home_team}")
with bw_col2:
    plot_ball_win_height(tackles_away, ints_away, rec_away, title=f"{away_team}")


# ═══════════════════════════════════════════════════════════════════════════
# § 6.6  DOMINANT ACTIONS BY ZONE
# ═══════════════════════════════════════════════════════════════════════════
section_header("Dominant Actions by Zone")
st.caption("Which action type dominates each pitch zone — filter by team, player, and action category")

def _build_zone_actions(events, tid, period_filter=None):
    """Assemble a unified actions DataFrame from all event extractors."""
    frames = []

    # Passes → split into Progressive Passes and Crosses
    passes = extract_passes(events, team_id=tid)
    if period_filter is not None and not passes.empty:
        passes = passes[passes["period"] == period_filter]
    if not passes.empty and "end_x" in passes.columns:
        clean = passes.dropna(subset=["end_x"]).copy()
        # Progressive passes (Δx > 25)
        prog_mask = (clean["end_x"] - clean["x"]) > 25
        prog = clean[prog_mask].copy()
        if not prog.empty:
            prog["action"] = "Prog. Pass"
            frames.append(prog[["x", "y", "action", "player_id", "player_name"]])
        # Crosses (passes into the box)
        cross_mask = (
            (clean["end_x"] > 83) & (clean["end_y"] > 21) & (clean["end_y"] < 79)
            & ~prog_mask  # avoid double-counting
        )
        crosses = clean[cross_mask].copy()
        if not crosses.empty:
            crosses["action"] = "Cross"
            frames.append(crosses[["x", "y", "action", "player_id", "player_name"]])

    # Shots
    shots = extract_shots(events, tid)
    if period_filter is not None and not shots.empty:
        shots = shots[shots["period"] == period_filter]
    if not shots.empty:
        s = shots[["x", "y", "player_id", "player_name"]].copy()
        s["action"] = "Shot"
        frames.append(s)

    # Tackles (won only)
    tackles = extract_tackles(events, tid)
    if period_filter is not None and not tackles.empty:
        tackles = tackles[tackles["period"] == period_filter]
    if not tackles.empty:
        t = tackles[tackles["outcome"] == 1][["x", "y", "player_id", "player_name"]].copy()
        if not t.empty:
            t["action"] = "Tackle"
            frames.append(t)

    # Interceptions
    intc = extract_interceptions(events, tid)
    if period_filter is not None and not intc.empty:
        intc = intc[intc["period"] == period_filter]
    if not intc.empty:
        i = intc[["x", "y", "player_id", "player_name"]].copy()
        i["action"] = "Interception"
        frames.append(i)

    # Ball recoveries
    recs = extract_ball_recoveries(events, tid)
    if period_filter is not None and not recs.empty:
        recs = recs[recs["period"] == period_filter]
    if not recs.empty:
        r = recs[["x", "y", "player_id", "player_name"]].copy()
        r["action"] = "Recovery"
        frames.append(r)

    # Take-ons (successful)
    tos = extract_take_ons(events, tid)
    if period_filter is not None and not tos.empty:
        tos = tos[tos["period"] == period_filter]
    if not tos.empty:
        to_won = tos[tos["outcome"] == 1][["x", "y", "player_id", "player_name"]].copy()
        if not to_won.empty:
            to_won["action"] = "Take-on"
            frames.append(to_won)

    # Aerials (won)
    aer = extract_aerials(events, tid)
    if period_filter is not None and not aer.empty:
        aer = aer[aer["period"] == period_filter]
    if not aer.empty:
        a_won = aer[aer["outcome"] == 1][["x", "y", "player_id", "player_name"]].copy()
        if not a_won.empty:
            a_won["action"] = "Aerial"
            frames.append(a_won)

    # Clearances
    clr = extract_clearances(events, tid)
    if period_filter is not None and not clr.empty:
        clr = clr[clr["period"] == period_filter]
    if not clr.empty:
        c = clr[["x", "y", "player_id", "player_name"]].copy()
        c["action"] = "Clearance"
        frames.append(c)

    # Fouls
    fouls = extract_fouls(events, tid)
    if period_filter is not None and not fouls.empty:
        fouls = fouls[fouls["period"] == period_filter]
    if not fouls.empty:
        f = fouls[["x", "y", "player_id", "player_name"]].copy()
        f["action"] = "Foul"
        frames.append(f)

    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


# ── Controls ──────────────────────────────────────────────────────────────
dz_ctrl1, dz_ctrl2, dz_ctrl3 = st.columns([1, 2, 3])

with dz_ctrl1:
    dz_team = st.radio(
        "Team", [home_team, away_team], horizontal=True, key="dz_team",
    )
dz_tid = home_id if dz_team == home_team else away_id

# Build full actions DataFrame for selected team
dz_all_actions = _build_zone_actions(events, dz_tid, period)

# Player list from events
dz_player_choices = ["Entire Team"]
if not dz_all_actions.empty and "player_name" in dz_all_actions.columns:
    unique_players = (
        dz_all_actions[dz_all_actions["player_name"].notna() & (dz_all_actions["player_name"] != "")]
        .drop_duplicates(subset=["player_id"])
        .sort_values("player_name")
    )
    for _, p in unique_players.iterrows():
        dz_player_choices.append(f"{p['player_name']}|{p['player_id']}")

with dz_ctrl2:
    dz_player_sel = st.selectbox(
        "Player",
        dz_player_choices,
        format_func=lambda x: x.split("|")[0] if "|" in x else x,
        key="dz_player",
    )

with dz_ctrl3:
    all_action_types = list(ZONE_ACTION_COLORS.keys())
    dz_action_filter = st.multiselect(
        "Action Types",
        all_action_types,
        default=all_action_types,
        key="dz_actions",
    )

# ── Filter and plot ───────────────────────────────────────────────────────
if not dz_all_actions.empty:
    filtered = dz_all_actions.copy()
    # Player filter
    if dz_player_sel != "Entire Team" and "|" in dz_player_sel:
        sel_pid = dz_player_sel.split("|")[1]
        filtered = filtered[filtered["player_id"] == sel_pid]
    # Action type filter
    if dz_action_filter:
        filtered = filtered[filtered["action"].isin(dz_action_filter)]

    player_label = dz_player_sel.split("|")[0] if "|" in dz_player_sel else dz_team
    plot_dominant_actions_by_zone(
        filtered,
        title=f"{player_label} — Dominant Actions by Zone",
    )
else:
    st.info("No action data for zone analysis.")


# ═══════════════════════════════════════════════════════════════════════════
# § 7  PROGRESSIVE PASSES
# ═══════════════════════════════════════════════════════════════════════════
section_header("Progressive Passes")

passes_team = extract_passes(events, team_id=team_id)
if period is not None and not passes_team.empty:
    passes_team = passes_team[passes_team["period"] == period]

pp_col1, pp_col2 = st.columns([3, 1])
with pp_col1:
    plot_progressive_passes(passes_team, title=f"{team_choice} Progressive Passes — {half_choice}")
with pp_col2:
    if not passes_team.empty and "end_x" in passes_team.columns:
        prog = passes_team.dropna(subset=["end_x", "end_y"])
        prog_passes = prog[(prog["end_x"] - prog["x"]) > 25]
        completed = len(prog_passes[prog_passes["outcome"] == 1])
        incomplete = len(prog_passes[prog_passes["outcome"] == 0])
        total_prog = completed + incomplete
        acc = round(completed / total_prog * 100, 1) if total_prog > 0 else 0

        kpi_card("Progressive Passes", total_prog)
        kpi_card("Completed", completed)
        kpi_card("Accuracy", f"{acc}%")

        # Top progressive passers
        if not prog_passes.empty:
            top_passers = prog_passes.groupby("player_name").size().sort_values(ascending=False).head(5)
            st.markdown("**Top Progressors:**")
            for name, count in top_passers.items():
                st.markdown(f"- {name}: **{count}**")
    else:
        st.info("No progressive pass data.")


# ═══════════════════════════════════════════════════════════════════════════
# § 8  TEAM HEATMAPS (Side by Side, period-aware)
# ═══════════════════════════════════════════════════════════════════════════
section_header("Touch Heatmaps")

hm_col1, hm_col2 = st.columns(2)
with hm_col1:
    touches_h = extract_all_touches(events, home_id)
    if period is not None and not touches_h.empty:
        touches_h = touches_h[touches_h["period"] == period]
    plot_heatmap(touches_h, title=f"{home_team}")
with hm_col2:
    touches_a = extract_all_touches(events, away_id)
    if period is not None and not touches_a.empty:
        touches_a = touches_a[touches_a["period"] == period]
    plot_heatmap(touches_a, title=f"{away_team}")


# ═══════════════════════════════════════════════════════════════════════════
# § 9  SET-PIECE ANALYSIS
# ═══════════════════════════════════════════════════════════════════════════
section_header("Set-Piece Analysis")

sp_stats = compute_set_piece_stats(events, home_id, away_id, period)
sp_h = sp_stats["home"]
sp_a = sp_stats["away"]

# ── 9a: Set-Piece Overview KPIs ──────────────────────────────────────────
h_sp_color = MU_RED if home_id == MU_TEAM_ID else "#42A5F5"
a_sp_color = MU_RED if away_id == MU_TEAM_ID else "#FF9800"

st.markdown(f"""
<div style="display:grid;grid-template-columns:1fr 1fr;gap:1rem;margin:0.5rem 0 1.5rem;">
  <div style="text-align:center;padding:0.3rem 0;">
    <span style="color:{h_sp_color};font-weight:700;font-size:1rem;">{home_team}</span>
  </div>
  <div style="text-align:center;padding:0.3rem 0;">
    <span style="color:{a_sp_color};font-weight:700;font-size:1rem;">{away_team}</span>
  </div>
</div>
""", unsafe_allow_html=True)

sp_row1 = st.columns(4)
with sp_row1[0]:
    kpi_card("Corners Won", sp_h["corners_won"])
with sp_row1[1]:
    kpi_card("FK Won", sp_h["fouls_won"])
with sp_row1[2]:
    kpi_card("Corners Won", sp_a["corners_won"])
with sp_row1[3]:
    kpi_card("FK Won", sp_a["fouls_won"])

sp_row2 = st.columns(4)
with sp_row2[0]:
    kpi_card("SP Shots", sp_h["set_piece_shots"])
with sp_row2[1]:
    sp_g_h = sp_h["set_piece_goals"]
    kpi_card("SP Goals", sp_g_h,
             delta="Goal!" if sp_g_h > 0 else None)
with sp_row2[2]:
    kpi_card("SP Shots", sp_a["set_piece_shots"])
with sp_row2[3]:
    sp_g_a = sp_a["set_piece_goals"]
    kpi_card("SP Goals", sp_g_a,
             delta="Goal!" if sp_g_a > 0 else None)

# Penalty row (only if any were awarded)
if sp_h["penalties_awarded"] > 0 or sp_a["penalties_awarded"] > 0:
    pen_c1, pen_c2 = st.columns(2)
    with pen_c1:
        kpi_card("Penalties", sp_h["penalties_awarded"])
    with pen_c2:
        kpi_card("Penalties", sp_a["penalties_awarded"])


# ── 9b: Corner Analysis ──────────────────────────────────────────────────
st.markdown("#### Corner Analysis")

all_match_shots = extract_shots(events)
if period is not None and not all_match_shots.empty:
    all_match_shots = all_match_shots[all_match_shots["period"] == period]

corners_h_df = compute_corner_breakdown(events, home_id, all_match_shots, period)
corners_a_df = compute_corner_breakdown(events, away_id, all_match_shots, period)


# Conversion funnel
def _corner_funnel(corners_df, team_name, color):
    """Render a compact corner conversion funnel."""
    if corners_df.empty:
        st.caption(f"{team_name}: No corners")
        return
    n = len(corners_df)
    shots = int(corners_df["had_shot"].sum())
    goals = int(corners_df["had_goal"].sum())
    st.markdown(f"""
<div style="text-align:center;padding:0.6rem;background:#1A1A2E;border-radius:8px;margin-bottom:0.5rem;">
<span style="color:{color};font-size:1.6rem;font-weight:700;">{n}</span>
<span style="color:#888;font-size:0.8rem;"> corners &rarr; </span>
<span style="color:{MU_GOLD};font-size:1.6rem;font-weight:700;">{shots}</span>
<span style="color:#888;font-size:0.8rem;"> shots &rarr; </span>
<span style="color:#4CAF50;font-size:1.6rem;font-weight:700;">{goals}</span>
<span style="color:#888;font-size:0.8rem;"> goals</span>
</div>
""", unsafe_allow_html=True)


fc1, fc2 = st.columns(2)
with fc1:
    _corner_funnel(corners_h_df, home_team, h_sp_color)
with fc2:
    _corner_funnel(corners_a_df, away_team, a_sp_color)


# Corner delivery type breakdown
def _delivery_breakdown(corners_df, team_name, color):
    """Render corner delivery type as horizontal chips."""
    if corners_df.empty:
        return
    counts = corners_df["delivery_label"].value_counts()
    chips = ""
    for label, cnt in counts.items():
        chips += (
            f'<div style="display:inline-block;padding:4px 10px;margin:2px;'
            f'background:#222;border-radius:4px;border-left:3px solid {color};">'
            f'<span style="color:#ccc;font-size:0.8rem;">{label}</span> '
            f'<span style="color:white;font-weight:700;">{cnt}</span></div>'
        )
    st.markdown(f'<div style="margin:0.3rem 0;">{chips}</div>',
                unsafe_allow_html=True)


dc1, dc2 = st.columns(2)
with dc1:
    _delivery_breakdown(corners_h_df, home_team, h_sp_color)
with dc2:
    _delivery_breakdown(corners_a_df, away_team, a_sp_color)

# Corner pitch maps — where corners were delivered
cmap1, cmap2 = st.columns(2)
with cmap1:
    plot_set_piece_map(
        corners_h_df, title=f"{home_team} Corners",
        color=h_sp_color, highlight_col="had_shot",
        highlight_color=MU_GOLD,
        highlight_label="Shot", default_label="No shot",
    )
with cmap2:
    plot_set_piece_map(
        corners_a_df, title=f"{away_team} Corners",
        color=a_sp_color, highlight_col="had_shot",
        highlight_color=MU_GOLD,
        highlight_label="Shot", default_label="No shot",
    )


# ── 9c: Dangerous Free-Kick Zones ───────────────────────────────────────
st.markdown("#### Dangerous Free-Kick Zones")
st.caption("Where each team won free kicks (fouls by opponent). Gold = final third (dangerous area).")

fk_h = compute_dangerous_fk_zones(events, home_id, away_id, period)
fk_a = compute_dangerous_fk_zones(events, away_id, home_id, period)


# KPI: dangerous free kicks
def _dangerous_count(fk_df):
    if fk_df.empty:
        return 0, 0
    total = len(fk_df)
    danger = int(fk_df["dangerous"].sum())
    return total, danger


fk_total_h, fk_danger_h = _dangerous_count(fk_h)
fk_total_a, fk_danger_a = _dangerous_count(fk_a)

fk_kpi1, fk_kpi2 = st.columns(2)
with fk_kpi1:
    kpi_card(f"{home_team[:15]} FK Danger",
             f"{fk_danger_h}/{fk_total_h}",
             delta=f"{round(fk_danger_h/fk_total_h*100)}% in final third" if fk_total_h > 0 else None)
with fk_kpi2:
    kpi_card(f"{away_team[:15]} FK Danger",
             f"{fk_danger_a}/{fk_total_a}",
             delta=f"{round(fk_danger_a/fk_total_a*100)}% in final third" if fk_total_a > 0 else None)

fk_map1, fk_map2 = st.columns(2)
with fk_map1:
    plot_set_piece_map(
        fk_h, title=f"{home_team} FK Won",
        color=h_sp_color, highlight_col="dangerous",
        highlight_color=MU_GOLD,
        highlight_label="Final Third", default_label="Other",
    )
with fk_map2:
    plot_set_piece_map(
        fk_a, title=f"{away_team} FK Won",
        color=a_sp_color, highlight_col="dangerous",
        highlight_color=MU_GOLD,
        highlight_label="Final Third", default_label="Other",
    )

# ═══════════════════════════════════════════════════════════════════════════
# § 9.5  PLAYER MATCH RATINGS (Position-Aware)
# ═══════════════════════════════════════════════════════════════════════════
st.markdown("---")
section_header("Player Match Ratings")
st.caption("Position-aware performance scores — base 6.0, metrics weighted by role")

# ── Legend ────────────────────────────────────────────────────────────
st.markdown(
    '<div style="display:flex;gap:1.5rem;padding:0.4rem 0 0.6rem 0;'
    'font-size:0.75rem;color:#999;flex-wrap:wrap;">'
    '<span>⚽ Goals</span>'
    '<span>🅰️ Assists</span>'
    '<span>🦶 Tackles won</span>'
    '<span>✋ Interceptions</span>'
    '<span>🧤 Saves (GK)</span>'
    '<span style="color:#4CAF50;">■ 8+ Excellent</span>'
    '<span style="color:#8BC34A;">■ 7+ Good</span>'
    '<span style="color:#FFC107;">■ 6+ Average</span>'
    '<span style="color:#FF9800;">■ 5+ Below avg</span>'
    '<span style="color:#F44336;">■ &lt;5 Poor</span>'
    '</div>',
    unsafe_allow_html=True,
)

rate_col1, rate_col2 = st.columns(2)

def _render_rating_row(r):
    """Build HTML for a single player rating row."""
    color = rating_color(r["rating"])
    name = r["player_name"]
    if len(name) > 16 and " " in name:
        parts = name.split()
        name = f"{parts[0][0]}. {' '.join(parts[1:])}"
    pos = r["position"]
    rating_val = r["rating"]
    key_stats = []
    if r["goals"] > 0:
        key_stats.append(f"⚽ {r['goals']}")
    if r["assists"] > 0:
        key_stats.append(f"🅰️ {r['assists']}")
    if r["tackles_won"] > 0:
        key_stats.append(f"🦶 {r['tackles_won']}")
    if r["interceptions"] > 0:
        key_stats.append(f"✋ {r['interceptions']}")
    if r["saves"] > 0 and pos == "GK":
        key_stats.append(f"🧤 {r['saves']}")
    stats_str = " ".join(key_stats[:3]) if key_stats else ""

    return (
        f'<div style="display:flex;align-items:center;gap:0.8rem;'
        f'padding:0.3rem 0;border-bottom:1px solid #333;">'
        f'<span style="background:{color};color:white;font-weight:800;'
        f'font-size:0.95rem;padding:0.2rem 0.5rem;border-radius:4px;'
        f'min-width:2.5rem;text-align:center;">{rating_val}</span>'
        f'<span style="color:#aaa;font-size:0.75rem;min-width:2rem;">{pos}</span>'
        f'<span style="color:white;font-size:0.85rem;flex:1;">{name}</span>'
        f'<span style="color:#999;font-size:0.75rem;">{stats_str}</span>'
        f'</div>'
    )

with rate_col1:
    st.markdown(f"**{home_team}**")
    ratings_home = compute_match_ratings(events, home_id)
    if not ratings_home.empty:
        for _, r in ratings_home.iterrows():
            st.markdown(_render_rating_row(r), unsafe_allow_html=True)
    else:
        st.info("No rating data available.")

with rate_col2:
    st.markdown(f"**{away_team}**")
    ratings_away = compute_match_ratings(events, away_id)
    if not ratings_away.empty:
        for _, r in ratings_away.iterrows():
            st.markdown(_render_rating_row(r), unsafe_allow_html=True)
    else:
        st.info("No rating data available.")

# ═══════════════════════════════════════════════════════════════════════════
# § 10  INDIVIDUAL PLAYER ANALYSIS
# ═══════════════════════════════════════════════════════════════════════════
st.markdown("---")
section_header("Individual Player Analysis")

# ── Build player roster from formation + substitutions ───────────────────
home_form = extract_formation(events, home_id)
away_form = extract_formation(events, away_id)
subs_df = extract_substitutions(events)

_POS_LABELS = {1: "GK", 2: "DEF", 3: "MID", 4: "FWD"}


def _build_match_players(formation, team_id, team_name, subs_df_inner):
    """Build list of players who appeared in the match for one team."""
    players = []
    if not formation:
        return players

    for p in formation.get("starters", []):
        pid = p["player_id"]
        shirt = p.get("shirt", "")
        pos_row = p.get("position_row", 0)
        pos_label = _POS_LABELS.get(pos_row, "")
        display = name_map.get(pid, f"Player {pid[:8]}")
        players.append({
            "player_id": pid,
            "label": f"#{shirt} {display} ({pos_label})",
            "team": team_name,
            "team_id": team_id,
            "shirt": shirt,
            "position_row": pos_row,
            "is_starter": True,
        })

    # Subs who actually came on
    if not subs_df_inner.empty:
        subs_on = subs_df_inner[
            (subs_df_inner["team_id"] == team_id) & (subs_df_inner["type"] == "on")
        ]
        for _, sub_row in subs_on.iterrows():
            pid = sub_row["player_id"]
            shirt = ""
            for s in formation.get("subs", []):
                if s["player_id"] == pid:
                    shirt = s.get("shirt", "")
                    break
            display = name_map.get(pid, sub_row.get("player_name", f"Player {pid[:8]}"))
            players.append({
                "player_id": pid,
                "label": f"#{shirt} {display} (SUB)",
                "team": team_name,
                "team_id": team_id,
                "shirt": shirt,
                "position_row": 5,
                "is_starter": False,
            })

    players.sort(key=lambda p: (p["position_row"], str(p.get("shirt", "99"))))
    return players


home_players = _build_match_players(home_form, home_id, home_team, subs_df)
away_players = _build_match_players(away_form, away_id, away_team, subs_df)
all_match_players = home_players + away_players

if not all_match_players:
    st.info("No player data available for this match.")
    st.stop()

# ── Player selector ──────────────────────────────────────────────────────
player_options = {}
for p in all_match_players:
    key = f"{p['team']}: {p['label']}"
    player_options[key] = p

selected_key = st.selectbox(
    "Select Player",
    list(player_options.keys()),
    key="player_analysis_sel",
)

if not selected_key:
    st.stop()

sel = player_options[selected_key]
sel_pid = sel["player_id"]
sel_team_id = sel["team_id"]
sel_display = sel["label"]

# ── Minutes played ───────────────────────────────────────────────────────
match_length = info.get("match_length_min", 90)

if sel["is_starter"]:
    if not subs_df.empty:
        sub_off = subs_df[(subs_df["player_id"] == sel_pid) & (subs_df["type"] == "off")]
        minutes_played = int(sub_off.iloc[0]["minute"]) if not sub_off.empty else match_length
    else:
        minutes_played = match_length
else:
    if not subs_df.empty:
        sub_on = subs_df[(subs_df["player_id"] == sel_pid) & (subs_df["type"] == "on")]
        if not sub_on.empty:
            on_min = int(sub_on.iloc[0]["minute"])
            sub_off = subs_df[(subs_df["player_id"] == sel_pid) & (subs_df["type"] == "off")]
            minutes_played = (int(sub_off.iloc[0]["minute"]) - on_min) if not sub_off.empty else (match_length - on_min)
        else:
            minutes_played = 0
    else:
        minutes_played = 0

# ── Extract player-level data ────────────────────────────────────────────
p_touches = extract_all_touches(events, sel_team_id)
p_touches = p_touches[p_touches["player_id"] == sel_pid] if not p_touches.empty else p_touches

p_passes = extract_passes(events, sel_team_id)
p_passes = p_passes[p_passes["player_id"] == sel_pid] if not p_passes.empty else p_passes

p_shots = extract_shots(events, sel_team_id)
p_shots = p_shots[p_shots["player_id"] == sel_pid] if not p_shots.empty else p_shots

p_tackles = extract_tackles(events, sel_team_id)
p_tackles = p_tackles[p_tackles["player_id"] == sel_pid] if not p_tackles.empty else p_tackles

p_ints = extract_interceptions(events, sel_team_id)
p_ints = p_ints[p_ints["player_id"] == sel_pid] if not p_ints.empty else p_ints

p_recoveries = extract_ball_recoveries(events, sel_team_id)
p_recoveries = p_recoveries[p_recoveries["player_id"] == sel_pid] if not p_recoveries.empty else p_recoveries

p_take_ons = extract_take_ons(events, sel_team_id)
p_take_ons = p_take_ons[p_take_ons["player_id"] == sel_pid] if not p_take_ons.empty else p_take_ons

p_aerials = extract_aerials(events, sel_team_id)
p_aerials = p_aerials[p_aerials["player_id"] == sel_pid] if not p_aerials.empty else p_aerials

p_fouls = extract_fouls(events, sel_team_id)
p_fouls = p_fouls[p_fouls["player_id"] == sel_pid] if not p_fouls.empty else p_fouls

# ── Compute KPIs ─────────────────────────────────────────────────────────
n_touches = len(p_touches)
total_passes = len(p_passes)
completed_passes = int((p_passes["outcome"] == 1).sum()) if not p_passes.empty else 0
pass_acc = round(completed_passes / total_passes * 100, 1) if total_passes > 0 else 0

prog_passes = 0
if not p_passes.empty and "end_x" in p_passes.columns:
    prog_df = p_passes.dropna(subset=["end_x", "end_y"])
    prog_passes = int(((prog_df["end_x"] - prog_df["x"]) > 25).sum())

n_shots = len(p_shots)
n_goals = int((p_shots["outcome"] == "Goal").sum()) if not p_shots.empty else 0
total_xg = round(float(p_shots["xg"].sum()), 2) if not p_shots.empty else 0.0

total_dribbles = len(p_take_ons)
succ_dribbles = int((p_take_ons["outcome"] == 1).sum()) if not p_take_ons.empty else 0

total_tackles = len(p_tackles)
won_tackles = int((p_tackles["outcome"] == 1).sum()) if not p_tackles.empty else 0

n_ints = len(p_ints)
n_recoveries = len(p_recoveries)

total_aerials = len(p_aerials)
won_aerials = int((p_aerials["outcome"] == 1).sum()) if not p_aerials.empty else 0

n_fouls = len(p_fouls)

# ── Display KPIs ─────────────────────────────────────────────────────────
st.markdown(f"#### {sel_display}")

kpi_row([
    {"label": "Minutes", "value": minutes_played},
    {"label": "Touches", "value": n_touches},
    {"label": "Passes", "value": f"{completed_passes}/{total_passes} ({pass_acc}%)"},
    {"label": "Prog. Passes", "value": prog_passes},
])

kpi_row([
    {"label": "Shots", "value": n_shots},
    {"label": "Goals", "value": n_goals},
    {"label": "xG", "value": total_xg},
    {"label": "Dribbles", "value": f"{succ_dribbles}/{total_dribbles}"},
])

kpi_row([
    {"label": "Tackles Won", "value": f"{won_tackles}/{total_tackles}"},
    {"label": "Interceptions", "value": n_ints},
    {"label": "Recoveries", "value": n_recoveries},
    {"label": "Aerials Won", "value": f"{won_aerials}/{total_aerials}"},
])

if n_fouls > 0:
    st.markdown(f"**Fouls committed:** {n_fouls}")

# ── Pitch Visualizations ─────────────────────────────────────────────────
st.markdown("")
viz_c1, viz_c2 = st.columns(2)

with viz_c1:
    plot_heatmap(p_touches, title=f"{sel_display} — Touch Heatmap")

with viz_c2:
    plot_pass_map(p_passes, title=f"{sel_display} — Pass Map")

viz_c3, viz_c4 = st.columns(2)

with viz_c3:
    if not p_shots.empty:
        plot_shot_map(p_shots, title=f"{sel_display} — Shots", half=True)
    else:
        st.info("No shots for this player.")

with viz_c4:
    plot_defensive_actions(
        p_tackles, p_ints,
        title=f"{sel_display} — Defensive Actions",
    )
