"""Pre-Match Analysis — Enhanced multi-factor Poisson model + Monte Carlo simulation.

Uses xG regression, Elo ratings, recent form, tactical dominance,
Dixon-Coles correction, and cross-competition blending for UEFA matches.
"""

import streamlit as st
import numpy as np
import pandas as pd
from components.sidebar import render_sidebar
from components.team_selector import two_team_selector
from viz.kpi_cards import section_header, kpi_row, metric_highlight, form_badges
from viz.charts import (
    heatmap_grid, probability_bars, monte_carlo_histogram, donut_chart,
)
from viz.radar import team_radar
from viz.pitch import (
    plot_formation, plot_ball_win_height, plot_dominant_actions_by_zone,
    plot_set_piece_map, plot_corner_shot_panels, ZONE_ACTION_COLORS,
)
from data.loader import (
    load_all_season_results, load_match_raw, build_player_name_map,
)
from data.event_parser import (
    extract_formation, parse_match_info, extract_tackles, extract_interceptions,
    extract_ball_recoveries, extract_passes, extract_shots,
    extract_take_ons, extract_aerials, extract_clearances,
    extract_corners, extract_fouls,
)
from processing.set_pieces import compute_corner_breakdown, compute_corner_shot_detail
from processing.poisson import compute_enhanced_prediction
from config import MU_RED, MU_GOLD

league, season = render_sidebar()

st.title("Pre-Match Analysis")

# ══════════════════════════════════════════════════════════════════════════════
# §1 — Team Selection & Quick Prediction
# ══════════════════════════════════════════════════════════════════════════════

home_team, away_team = two_team_selector(league, season, key="prematch_teams")

sim_options = [10_000, 50_000, 100_000, 500_000]
n_sims = st.select_slider(
    "Simulation count",
    options=sim_options,
    value=100_000,
    format_func=lambda x: f"{x:,}",
    key="prematch_sims",
)

with st.spinner("Computing enhanced prediction…"):
    result = compute_enhanced_prediction(league, season, home_team, away_team, n_sims)

pred = result["prediction"]
mc = result["monte_carlo"]
ctx = result["context"]
quality = result["data_quality"]

if pred is None:
    st.warning("Insufficient data for prediction. Need at least 3 matches per team.")
    st.stop()

# ── KPI Cards ─────────────────────────────────────────────────────────────
kpi_row([
    {"label": f"{home_team} Win", "value": f"{pred['home_win_prob']:.0%}"},
    {"label": "Draw", "value": f"{pred['draw_prob']:.0%}"},
    {"label": f"{away_team} Win", "value": f"{pred['away_win_prob']:.0%}"},
    {"label": "Most Likely Score",
     "value": f"{pred['most_likely_score'][0]}-{pred['most_likely_score'][1]}"},
])

# ── Probability Bar ───────────────────────────────────────────────────────
fig = probability_bars(pred["home_win_prob"], pred["draw_prob"],
                       pred["away_win_prob"], home_team, away_team)
st.plotly_chart(fig, use_container_width=True)

# ── Data Quality Badge ────────────────────────────────────────────────────
factors = ctx.get("factors_applied", [])
n_factors = len(set(factors))
badge_map = {
    "full": ("🟢", "FULL", "#4CAF50"),
    "partial": ("🟡", "PARTIAL", "#FFC107"),
    "minimal": ("🔴", "MINIMAL", "#F44336"),
}
emoji, label, color = badge_map.get(quality, badge_map["minimal"])
is_uefa_text = " · UEFA cross-competition blending active" if ctx.get("is_uefa") else ""
st.markdown(
    f'<div style="text-align:center; padding:6px; margin-bottom:16px;">'
    f'<span style="color:{color}; font-weight:bold;">{emoji} {label}</span> '
    f'— {n_factors} prediction factor{"s" if n_factors != 1 else ""} active '
    f'({", ".join(set(factors)) if factors else "base model only"})'
    f'{is_uefa_text}</div>',
    unsafe_allow_html=True,
)


# ══════════════════════════════════════════════════════════════════════════════
# §2 — Prediction Factors (rich insight section)
# ══════════════════════════════════════════════════════════════════════════════

st.markdown("---")
section_header("Prediction Factors")

# ── Elo Comparison ────────────────────────────────────────────────────────
st.subheader("Elo Ratings")
col1, col2, col3 = st.columns([1, 1, 1])
home_elo = ctx.get("home_elo", 1500)
away_elo = ctx.get("away_elo", 1500)
with col1:
    metric_highlight(home_team, f"{home_elo:.0f}", MU_RED)
with col2:
    diff = home_elo - away_elo
    adv_color = "#4CAF50" if diff > 0 else ("#F44336" if diff < 0 else "#888888")
    metric_highlight("Elo Advantage", f"{diff:+.0f}", adv_color)
with col3:
    metric_highlight(away_team, f"{away_elo:.0f}", "#42A5F5")

# ── Recent Form ───────────────────────────────────────────────────────────
st.subheader("Recent Form (Last 5)")
col1, col2 = st.columns(2)
with col1:
    home_form = ctx.get("home_form", [])
    if home_form:
        st.markdown(form_badges(home_form), unsafe_allow_html=True)
    else:
        st.info("No recent form data")
with col2:
    away_form = ctx.get("away_form", [])
    if away_form:
        st.markdown(form_badges(away_form), unsafe_allow_html=True)
    else:
        st.info("No recent form data")

# ── Head-to-Head ──────────────────────────────────────────────────────────
h2h = ctx.get("h2h", {"wins": 0, "draws": 0, "losses": 0})
total_h2h = h2h["wins"] + h2h["draws"] + h2h["losses"]

if total_h2h > 0:
    st.subheader("Head-to-Head Record (All Seasons)")
    col1, col2 = st.columns([1, 2])
    with col1:
        st.metric(f"{home_team} Wins", h2h["wins"])
        st.metric("Draws", h2h["draws"])
        st.metric(f"{away_team} Wins", h2h["losses"])
    with col2:
        fig = donut_chart(
            [f"{home_team} Win", "Draw", f"{away_team} Win"],
            [h2h["wins"], h2h["draws"], h2h["losses"]],
            title="H2H Distribution",
            colors=[MU_RED, "#888888", "#42A5F5"],
        )
        st.plotly_chart(fig, use_container_width=True)

# ── Key Metrics Comparison ────────────────────────────────────────────────
home_stats = ctx.get("home_stats", {})
away_stats = ctx.get("away_stats", {})

if home_stats and away_stats:
    st.subheader("Key Metrics Comparison")
    metrics_display = [
        ("Goals / Match", "goals_per_match", ".2f"),
        ("Possession %", "possession_pct", ".1f"),
        ("Pass Accuracy %", "pass_accuracy", ".1f"),
        ("Shots / Match", "shots_per_match", ".1f"),
        ("Clean Sheets", "clean_sheets", ".0f"),
        ("Tackles Won", "tackles_won", ".0f"),
        ("Interceptions", "interceptions", ".0f"),
    ]

    rows = []
    for label, key, fmt in metrics_display:
        h_val = home_stats.get(key, "—")
        a_val = away_stats.get(key, "—")
        try:
            h_str = f"{float(h_val):{fmt}}"
        except (TypeError, ValueError):
            h_str = str(h_val)
        try:
            a_str = f"{float(a_val):{fmt}}"
        except (TypeError, ValueError):
            a_str = str(a_val)
        rows.append({home_team: h_str, "Metric": label, away_team: a_str})

    st.dataframe(
        pd.DataFrame(rows),
        hide_index=True,
        use_container_width=True,
    )

# ── Radar Overlay ─────────────────────────────────────────────────────────
radar_data = ctx.get("radar", {})
radar_cats = ctx.get("radar_categories", [])
if radar_data and len(radar_data) >= 2:
    st.subheader("Team Radar Comparison")
    fig = team_radar(radar_data, radar_cats, title=f"{home_team} vs {away_team}")
    st.plotly_chart(fig, use_container_width=True)

# ── Factor Breakdown ──────────────────────────────────────────────────────
with st.expander("🔍 Factor Breakdown (Advanced)"):
    factor_info = pred.get("factors", {})
    st.markdown("Each factor adjusts the base Poisson lambda. Values near **1.0** = neutral.")

    factor_rows = []
    for name, vals in factor_info.items():
        if name == "dixon_coles":
            factor_rows.append({
                "Factor": "Dixon-Coles Correction",
                "Home Adj.": "Active" if vals else "Off",
                "Away Adj.": "Active" if vals else "Off",
            })
        else:
            nice_name = name.replace("_", " ").title()
            factor_rows.append({
                "Factor": nice_name,
                "Home Adj.": f"{vals[0]:.3f}",
                "Away Adj.": f"{vals[1]:.3f}",
            })

    st.dataframe(pd.DataFrame(factor_rows), hide_index=True, use_container_width=True)

    st.caption(
        f"Base λ: {home_team} = {pred['base_home_lambda']:.3f} → "
        f"Adjusted = {pred['home_lambda']:.3f} · "
        f"{away_team} = {pred['base_away_lambda']:.3f} → "
        f"Adjusted = {pred['away_lambda']:.3f}"
    )


# ══════════════════════════════════════════════════════════════════════════════
# §3 — Scoreline Probability Matrix
# ══════════════════════════════════════════════════════════════════════════════

st.markdown("---")
section_header("Scoreline Probability Matrix")
st.caption("Dixon-Coles corrected · low-score outcomes adjusted for realism")

labels = [str(i) for i in range(pred["score_matrix"].shape[0])]
fig = heatmap_grid(
    pred["score_matrix"], labels, labels,
    title="Scoreline Probabilities",
    x_title=f"{away_team} Goals",
    y_title=f"{home_team} Goals",
)
st.plotly_chart(fig, use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════
# §4 — Monte Carlo Simulation (enhanced)
# ══════════════════════════════════════════════════════════════════════════════

st.markdown("---")
section_header(f"Monte Carlo Simulation ({n_sims:,} Matches)")

# Win/Draw/Loss
col1, col2, col3 = st.columns(3)
col1.metric(f"{home_team} Win %", f"{mc['home_win_pct']:.1%}")
col2.metric("Draw %", f"{mc['draw_pct']:.1%}")
col3.metric(f"{away_team} Win %", f"{mc['away_win_pct']:.1%}")

# Goal difference histogram
fig = monte_carlo_histogram(mc["goal_diff"], home_team, away_team,
                            title=f"Goal Difference Distribution ({n_sims:,} sims)")
st.plotly_chart(fig, use_container_width=True)

# Top scorelines
section_header("Most Likely Scorelines")
top_scores = mc["score_freq"].head(10).copy()
top_scores["scoreline"] = top_scores.apply(
    lambda r: f"{int(r['home'])}-{int(r['away'])}", axis=1
)
st.dataframe(
    top_scores[["scoreline", "count", "pct"]].rename(
        columns={"scoreline": "Score", "count": "Occurrences", "pct": "Probability (%)"}
    ),
    hide_index=True,
    use_container_width=True,
)

# Expected Goals
section_header("Expected Goals")
col1, col2 = st.columns(2)
col1.metric(f"{home_team} avg goals", f"{mc['avg_home_goals']:.2f}")
col2.metric(f"{away_team} avg goals", f"{mc['avg_away_goals']:.2f}")

# ── Match Props ───────────────────────────────────────────────────────────
st.subheader("Match Props")
col1, col2, col3, col4 = st.columns(4)
col1.metric("BTTS", f"{mc['btts_prob']:.0%}")
col2.metric("Over 2.5", f"{mc['over_2_5_prob']:.0%}")
col3.metric(f"{home_team} CS", f"{mc['home_clean_sheet_prob']:.0%}")
col4.metric(f"{away_team} CS", f"{mc['away_clean_sheet_prob']:.0%}")

# ── Goal Confidence Bands ─────────────────────────────────────────────────
st.subheader("Goal Confidence Bands")
col1, col2 = st.columns(2)

for col, team, dist in [(col1, home_team, mc["home_goal_dist"]),
                         (col2, away_team, mc["away_goal_dist"])]:
    with col:
        st.markdown(f"**{team}**")
        band_rows = []
        for g in range(4):
            count = dist.get(g, 0)
            pct = count / mc["n_sims"] * 100
            band_rows.append({"Goals": str(g), "Probability": f"{pct:.1f}%"})
        # 3+ goals
        count_3p = dist.get("3+", 0)
        pct_3p = count_3p / mc["n_sims"] * 100
        band_rows.append({"Goals": "3+", "Probability": f"{pct_3p:.1f}%"})
        st.dataframe(pd.DataFrame(band_rows), hide_index=True, use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════
# §5 — Probable Starting XI
# ══════════════════════════════════════════════════════════════════════════════

st.markdown("---")
section_header("Probable Starting XI")
st.caption("Based on most recent match formation for each team")

results_df = load_all_season_results(league, season)
name_map = build_player_name_map(league, season)

# Resolve team names for results lookup (standings may use "FC" suffix)
from processing.poisson import _resolve_team_in_results, _get_team_id
from data.loader import load_standings as _load_standings
_standings = _load_standings(league, season)
_home_resolved = _resolve_team_in_results(
    results_df, home_team, _get_team_id(results_df, _standings, home_team)
)
_away_resolved = _resolve_team_in_results(
    results_df, away_team, _get_team_id(results_df, _standings, away_team)
)


def _get_last_formation(team_name: str, resolved_name: str) -> dict | None:
    """Find the most recent match for a team and extract its formation."""
    if results_df.empty:
        return None
    team_matches = results_df[
        (results_df["home_team"] == resolved_name) | (results_df["away_team"] == resolved_name)
    ]
    if team_matches.empty:
        return None
    last = team_matches.iloc[-1]

    from data.loader import _find_match_id_for_row
    mid = _find_match_id_for_row(league, season, last)
    if not mid:
        return None

    raw = load_match_raw(league, season, mid)
    if not raw:
        return None

    info = parse_match_info(raw)
    events = raw.get("liveData", {}).get("event", [])
    # Match by resolved name (what appears in match data)
    team_id = info["home_id"] if info["home_team"] == resolved_name else info["away_id"]
    return extract_formation(events, team_id)


col1, col2 = st.columns(2)
with col1:
    home_formation = _get_last_formation(home_team, _home_resolved)
    if home_formation:
        plot_formation(home_formation, name_map, title=f"{home_team}")
    else:
        st.info(f"No formation data for {home_team}.")

with col2:
    away_formation = _get_last_formation(away_team, _away_resolved)
    if away_formation:
        plot_formation(away_formation, name_map, title=f"{away_team}",
                       primary_color="#42A5F5")
    else:
        st.info(f"No formation data for {away_team}.")


# ══════════════════════════════════════════════════════════════════════════════
# §6 — Tactical Heatmaps (Last 5 Games)
# ══════════════════════════════════════════════════════════════════════════════

st.markdown("---")
section_header("Tactical Heatmaps (Last 5 Games)")
st.caption("Aggregated from each team's last 5 matches this season")


def _load_last_n_events(resolved_name, n=5):
    """Load and merge events from the last N matches for a team.

    Returns (events_list, team_id, match_count).
    """
    if results_df.empty:
        return [], None, 0
    team_matches = results_df[
        (results_df["home_team"] == resolved_name)
        | (results_df["away_team"] == resolved_name)
    ]
    if team_matches.empty:
        return [], None, 0

    last_n = team_matches.tail(n)
    all_events = []
    team_id = None
    match_count = 0

    for _, row in last_n.iterrows():
        from data.loader import _find_match_id_for_row
        mid = _find_match_id_for_row(league, season, row)
        if not mid:
            continue
        match_raw = load_match_raw(league, season, mid)
        if not match_raw:
            continue
        match_info = parse_match_info(match_raw)
        match_events = match_raw.get("liveData", {}).get("event", [])
        if team_id is None:
            team_id = (
                match_info["home_id"]
                if match_info["home_team"] == resolved_name
                else match_info["away_id"]
            )
        all_events.extend(match_events)
        match_count += 1

    return all_events, team_id, match_count


# ── Helper functions for enhanced zone analysis ────────────────────────────

def _build_zone_actions_prematch(events, tid):
    """Assemble a unified actions DataFrame from all event extractors (last N games)."""
    frames = []

    # Passes → split into Progressive Passes and Crosses
    passes = extract_passes(events, team_id=tid)
    if not passes.empty and "end_x" in passes.columns:
        clean = passes.dropna(subset=["end_x"]).copy()
        prog_mask = (clean["end_x"] - clean["x"]) > 25
        prog = clean[prog_mask].copy()
        if not prog.empty:
            prog["action"] = "Prog. Pass"
            frames.append(prog[["x", "y", "action", "player_id", "player_name"]])
        cross_mask = (
            (clean["end_x"] > 83) & (clean["end_y"] > 21) & (clean["end_y"] < 79)
            & ~prog_mask
        )
        crosses = clean[cross_mask].copy()
        if not crosses.empty:
            crosses["action"] = "Cross"
            frames.append(crosses[["x", "y", "action", "player_id", "player_name"]])

    # Shots
    shots = extract_shots(events, tid)
    if not shots.empty:
        s = shots[["x", "y", "player_id", "player_name"]].copy()
        s["action"] = "Shot"
        frames.append(s)

    # Tackles (won only)
    tackles = extract_tackles(events, tid)
    if not tackles.empty:
        t = tackles[tackles["outcome"] == 1][["x", "y", "player_id", "player_name"]].copy()
        if not t.empty:
            t["action"] = "Tackle"
            frames.append(t)

    # Interceptions
    intc = extract_interceptions(events, tid)
    if not intc.empty:
        i = intc[["x", "y", "player_id", "player_name"]].copy()
        i["action"] = "Interception"
        frames.append(i)

    # Ball recoveries
    recs = extract_ball_recoveries(events, tid)
    if not recs.empty:
        r = recs[["x", "y", "player_id", "player_name"]].copy()
        r["action"] = "Recovery"
        frames.append(r)

    # Take-ons (successful)
    tos = extract_take_ons(events, tid)
    if not tos.empty:
        to_won = tos[tos["outcome"] == 1][["x", "y", "player_id", "player_name"]].copy()
        if not to_won.empty:
            to_won["action"] = "Take-on"
            frames.append(to_won)

    # Aerials (won)
    aer = extract_aerials(events, tid)
    if not aer.empty:
        a_won = aer[aer["outcome"] == 1][["x", "y", "player_id", "player_name"]].copy()
        if not a_won.empty:
            a_won["action"] = "Aerial"
            frames.append(a_won)

    # Clearances
    clr = extract_clearances(events, tid)
    if not clr.empty:
        c = clr[["x", "y", "player_id", "player_name"]].copy()
        c["action"] = "Clearance"
        frames.append(c)

    # Fouls
    fls = extract_fouls(events, tid)
    if not fls.empty:
        fo = fls[["x", "y", "player_id", "player_name"]].copy()
        fo["action"] = "Foul"
        frames.append(fo)

    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def _resolve_player_name(pid, dfs):
    """Resolve player name from the first non-empty DataFrame that contains it."""
    for df in dfs:
        if df.empty or "player_id" not in df.columns:
            continue
        match = df[df["player_id"] == pid]
        if not match.empty and "player_name" in match.columns:
            name = match.iloc[0]["player_name"]
            if name:
                return name
    return f"Unknown ({pid[:8]})"


def _count_fk_taken(events, tid, pid):
    """Count how many free kicks a player took (first action after opponent foul)."""
    count = 0
    for i, e in enumerate(events):
        if e.get("typeId") != 4:  # EVENT_FOUL
            continue
        if e.get("contestantId") == tid:
            continue  # our foul, not our FK to take
        foul_time = int(e.get("timeMin", 0)) * 60 + int(e.get("timeSec", 0))
        for j in range(i + 1, min(i + 10, len(events))):
            nxt = events[j]
            if nxt.get("contestantId") != tid:
                continue
            nxt_time = int(nxt.get("timeMin", 0)) * 60 + int(nxt.get("timeSec", 0))
            if nxt_time - foul_time > 30:
                break
            if nxt.get("playerId") == pid:
                count += 1
            break
    return count


def _build_player_stats_table(events, tid, n_matches=5):
    """Build per-player stats aggregated across N matches for display."""
    if n_matches < 1:
        n_matches = 1

    passes = extract_passes(events, team_id=tid)
    shots = extract_shots(events, tid)
    tackles = extract_tackles(events, tid)
    interceptions = extract_interceptions(events, tid)
    recoveries = extract_ball_recoveries(events, tid)
    clearances = extract_clearances(events, tid)
    corners = extract_corners(events, tid)
    take_ons = extract_take_ons(events, tid)

    # Collect all player IDs
    all_pids = set()
    for df in [passes, shots, tackles, interceptions, recoveries,
               clearances, corners, take_ons]:
        if not df.empty and "player_id" in df.columns:
            all_pids.update(df["player_id"].unique())

    rows = []
    for pid in all_pids:
        if not pid:
            continue

        name = _resolve_player_name(pid, [passes, shots, tackles,
                                          interceptions, corners])

        # Shots
        p_shots = shots[shots["player_id"] == pid] if not shots.empty else pd.DataFrame()
        n_shots = len(p_shots)
        shots_on = 0
        n_goals = 0
        total_xg = 0.0
        if not p_shots.empty:
            shots_on = int(p_shots["outcome"].isin(["Goal", "Saved"]).sum())
            n_goals = int((p_shots["outcome"] == "Goal").sum())
            if "xg" in p_shots.columns:
                total_xg = float(p_shots["xg"].sum())

        # Passes
        p_passes = passes[passes["player_id"] == pid] if not passes.empty else pd.DataFrame()
        total_passes = len(p_passes)
        succ_passes = int((p_passes["outcome"] == 1).sum()) if not p_passes.empty else 0
        pass_pct = round(succ_passes / total_passes * 100, 1) if total_passes > 0 else 0

        # Key passes (into opponent box)
        key_passes = 0
        if not p_passes.empty and "end_x" in p_passes.columns:
            kp = p_passes.dropna(subset=["end_x", "end_y"])
            key_passes = int(((kp["end_x"] > 83) & (kp["end_y"] > 21)
                              & (kp["end_y"] < 79) & (kp["outcome"] == 1)).sum())

        # Defensive actions
        n_tackles = len(tackles[tackles["player_id"] == pid]) if not tackles.empty else 0
        n_ints = len(interceptions[interceptions["player_id"] == pid]) if not interceptions.empty else 0
        n_recs = len(recoveries[recoveries["player_id"] == pid]) if not recoveries.empty else 0
        n_clears = len(clearances[clearances["player_id"] == pid]) if not clearances.empty else 0
        def_actions = n_tackles + n_ints + n_recs + n_clears

        # Set-piece roles
        n_corners = len(corners[corners["player_id"] == pid]) if not corners.empty else 0
        n_fks = _count_fk_taken(events, tid, pid)

        # Take-ons
        p_tos = take_ons[take_ons["player_id"] == pid] if not take_ons.empty else pd.DataFrame()
        tos_won = int((p_tos["outcome"] == 1).sum()) if not p_tos.empty else 0

        rows.append({
            "Player": name,
            "Crn Tkn": n_corners,
            "FK Tkn": n_fks,
            "Shots/G": round(n_shots / n_matches, 1),
            "SoT/G": round(shots_on / n_matches, 1),
            "Goals": n_goals,
            "xG": round(total_xg, 2),
            "Key Pass": key_passes,
            "Def/G": round(def_actions / n_matches, 1),
            "Pass %": pass_pct,
            "Drb Won": tos_won,
        })

    df = pd.DataFrame(rows)
    if df.empty:
        return df
    return df.sort_values(
        ["Crn Tkn", "Shots/G", "Def/G"],
        ascending=[False, False, False],
    ).reset_index(drop=True)


with st.spinner("Loading last 5 matches for each team…"):
    home_events_5, home_tid, home_n = _load_last_n_events(_home_resolved, n=5)
    away_events_5, away_tid, away_n = _load_last_n_events(_away_resolved, n=5)

if home_events_5 and away_events_5 and home_tid and away_tid:
    # ── Ball Win Height ──────────────────────────────────────────────────
    st.subheader("Ball Win Height")
    bw1, bw2 = st.columns(2)
    with bw1:
        h_tackles = extract_tackles(home_events_5, home_tid)
        h_ints = extract_interceptions(home_events_5, home_tid)
        h_recs = extract_ball_recoveries(home_events_5, home_tid)
        plot_ball_win_height(h_tackles, h_ints, h_recs,
                             title=f"{home_team} (Last 5)")
    with bw2:
        a_tackles = extract_tackles(away_events_5, away_tid)
        a_ints = extract_interceptions(away_events_5, away_tid)
        a_recs = extract_ball_recoveries(away_events_5, away_tid)
        plot_ball_win_height(a_tackles, a_ints, a_recs,
                             title=f"{away_team} (Last 5)")

    # ── Dominant Actions by Zone (enhanced with filters) ─────────────────
    st.subheader("Dominant Actions by Zone")
    st.caption("Filter by action type and player to explore each team's pitch dominance")

    # Build full actions for both teams
    h_all_actions = _build_zone_actions_prematch(home_events_5, home_tid)
    a_all_actions = _build_zone_actions_prematch(away_events_5, away_tid)

    # Shared action type filter
    all_action_types = list(ZONE_ACTION_COLORS.keys())
    dz_action_filter = st.multiselect(
        "Action Types", all_action_types, default=all_action_types,
        key="prematch_dz_actions",
    )

    # Two columns with per-team player filter + zone chart
    dz1, dz2 = st.columns(2)

    with dz1:
        h_player_choices = ["All Players"]
        if not h_all_actions.empty and "player_name" in h_all_actions.columns:
            unique = (
                h_all_actions[h_all_actions["player_name"].notna()
                              & (h_all_actions["player_name"] != "")]
                .drop_duplicates(subset=["player_id"])
                .sort_values("player_name")
            )
            for _, p in unique.iterrows():
                h_player_choices.append(f"{p['player_name']}|{p['player_id']}")

        h_sel = st.selectbox(
            f"{home_team} — Player",
            h_player_choices,
            format_func=lambda x: x.split("|")[0] if "|" in x else x,
            key="prematch_dz_h_player",
        )
        filtered_h = h_all_actions.copy()
        if h_sel != "All Players" and "|" in h_sel:
            filtered_h = filtered_h[filtered_h["player_id"] == h_sel.split("|")[1]]
        if dz_action_filter:
            filtered_h = filtered_h[filtered_h["action"].isin(dz_action_filter)]

        h_label = h_sel.split("|")[0] if "|" in h_sel else f"{home_team} (Last 5)"
        plot_dominant_actions_by_zone(filtered_h, title=h_label)

    with dz2:
        a_player_choices = ["All Players"]
        if not a_all_actions.empty and "player_name" in a_all_actions.columns:
            unique = (
                a_all_actions[a_all_actions["player_name"].notna()
                              & (a_all_actions["player_name"] != "")]
                .drop_duplicates(subset=["player_id"])
                .sort_values("player_name")
            )
            for _, p in unique.iterrows():
                a_player_choices.append(f"{p['player_name']}|{p['player_id']}")

        a_sel = st.selectbox(
            f"{away_team} — Player",
            a_player_choices,
            format_func=lambda x: x.split("|")[0] if "|" in x else x,
            key="prematch_dz_a_player",
        )
        filtered_a = a_all_actions.copy()
        if a_sel != "All Players" and "|" in a_sel:
            filtered_a = filtered_a[filtered_a["player_id"] == a_sel.split("|")[1]]
        if dz_action_filter:
            filtered_a = filtered_a[filtered_a["action"].isin(dz_action_filter)]

        a_label = a_sel.split("|")[0] if "|" in a_sel else f"{away_team} (Last 5)"
        plot_dominant_actions_by_zone(filtered_a, title=a_label)

    # ── Player Roles & Stats (Last 5 Games) ───────────────────────────────
    st.subheader("Player Roles & Stats (Last 5 Games)")
    st.caption("Per-player aggregates · Crn Tkn / FK Tkn = total corners & free kicks taken · /G = per game")

    pr1, pr2 = st.columns(2)
    with pr1:
        h_stats = _build_player_stats_table(home_events_5, home_tid, home_n)
        if not h_stats.empty:
            st.markdown(f"**{home_team}**")
            st.dataframe(h_stats, hide_index=True, use_container_width=True, height=420)
        else:
            st.info(f"No player data for {home_team}.")
    with pr2:
        a_stats = _build_player_stats_table(away_events_5, away_tid, away_n)
        if not a_stats.empty:
            st.markdown(f"**{away_team}**")
            st.dataframe(a_stats, hide_index=True, use_container_width=True, height=420)
        else:
            st.info(f"No player data for {away_team}.")

    # ── Corner Analysis ──────────────────────────────────────────────────
    st.subheader("Corner Analysis (Last 5 Games)")

    # Compute corner-to-shot detail for both teams
    h_all_shots = extract_shots(home_events_5)
    h_corners_det, h_corner_shots = compute_corner_shot_detail(
        home_events_5, home_tid, h_all_shots,
    )
    a_all_shots = extract_shots(away_events_5)
    a_corners_det, a_corner_shots = compute_corner_shot_detail(
        away_events_5, away_tid, a_all_shots,
    )

    # Funnel badges
    def _render_funnel(corners_df, shots_df, primary_color):
        n_c = len(corners_df)
        n_s = len(shots_df)
        n_g = int((shots_df["outcome"] == "Goal").sum()) if not shots_df.empty else 0
        total_xg = float(shots_df["xg"].sum()) if not shots_df.empty else 0.0
        st.markdown(
            f'<div style="text-align:center;padding:0.5rem;'
            f'background:#1A1A2E;border-radius:8px;">'
            f'<span style="color:{primary_color};font-size:1.4rem;'
            f'font-weight:700;">{n_c}</span>'
            f'<span style="color:#888;font-size:0.8rem;"> corners &rarr; </span>'
            f'<span style="color:{MU_GOLD};font-size:1.4rem;'
            f'font-weight:700;">{n_s}</span>'
            f'<span style="color:#888;font-size:0.8rem;"> shots &rarr; </span>'
            f'<span style="color:#4CAF50;font-size:1.4rem;'
            f'font-weight:700;">{n_g}</span>'
            f'<span style="color:#888;font-size:0.8rem;"> goals</span>'
            f'<span style="color:#888;font-size:0.8rem;"> · </span>'
            f'<span style="color:#FF9800;font-size:1.1rem;'
            f'font-weight:600;">{total_xg:.2f}</span>'
            f'<span style="color:#888;font-size:0.8rem;"> xG</span></div>',
            unsafe_allow_html=True,
        )

    fc1, fc2 = st.columns(2)
    with fc1:
        if not h_corners_det.empty:
            _render_funnel(h_corners_det, h_corner_shots, MU_RED)
        else:
            st.info(f"No corner data for {home_team}.")
    with fc2:
        if not a_corners_det.empty:
            _render_funnel(a_corners_det, a_corner_shots, "#42A5F5")
        else:
            st.info(f"No corner data for {away_team}.")

    # Shot location panels (Left Corner | Right Corner)
    cp1, cp2 = st.columns(2)
    with cp1:
        plot_corner_shot_panels(
            h_corners_det, h_corner_shots,
            team_name=home_team, team_color=MU_RED,
            n_matches=home_n,
        )
    with cp2:
        plot_corner_shot_panels(
            a_corners_det, a_corner_shots,
            team_name=away_team, team_color="#42A5F5",
            n_matches=away_n,
        )
else:
    st.info("Insufficient match data for tactical heatmaps.")
