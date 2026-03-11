"""Manager Profiles — coach history, tenure-aware stats, and manager comparison."""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from components.sidebar import render_sidebar
from viz.kpi_cards import section_header, kpi_row, form_badges
from viz.charts import donut_chart, bar_chart
from processing.match_stats import crest_url
from processing.manager_stats import (
    get_head_coaches, get_all_team_coaches, compute_manager_record,
    compute_formation_usage, compute_recent_form, compute_home_away_split,
    compute_goals_timeline, compare_managers,
)
from data.loader import load_standings
from config import MU_RED, MU_GOLD, MU_DARK_BG

league, season = render_sidebar()

st.title("Manager Profiles")
st.caption(f"Head coaches, tenure tracking & comparison — {season}")

# ── Team selector ────────────────────────────────────────────────────────────
standings = load_standings(league, season)
if standings.empty:
    st.warning("No standings data available for this competition/season.")
    st.stop()

team_options = {
    row["team_name"]: row["team_id"]
    for _, row in standings.sort_values("rank").iterrows()
}
selected_team = st.selectbox("Select Team", options=list(team_options.keys()),
                             key="mgr_team")
team_id = team_options[selected_team]

# ── Load ALL coaches for this team ───────────────────────────────────────────
team_coaches = get_all_team_coaches(league, season, team_id)

if not team_coaches:
    st.info("No manager data found for this team.")
    st.stop()

# ── Manager Change Timeline ──────────────────────────────────────────────────
section_header("Managerial Timeline")

timeline_html = '<div style="display:flex;gap:0;align-items:stretch;width:100%;">'
n_coaches = len(team_coaches)
for idx, c in enumerate(team_coaches):
    start = c.get("start_date", "")[:10] or "?"
    end = c.get("end_date", "")[:10] or "Present"
    is_active = c["active"]
    bg = MU_RED if is_active else "#333"
    border_left = "" if idx == 0 else "border-left:2px solid #555;"

    timeline_html += (
        f'<div style="flex:1;padding:0.8rem 0.6rem;background:{bg};'
        f'text-align:center;{border_left}'
        f'border-radius:{"8px 0 0 8px" if idx == 0 else ("0 8px 8px 0" if idx == n_coaches - 1 else "0")};">'
        f'<div style="font-weight:700;color:white;font-size:0.95rem;">{c["name"]}</div>'
        f'<div style="color:#ddd;font-size:0.75rem;margin-top:0.2rem;">'
        f'{start} → {end}</div>'
        f'</div>'
    )
timeline_html += '</div>'
st.markdown(timeline_html, unsafe_allow_html=True)

if n_coaches > 1:
    st.markdown(
        f'<p style="color:#999;font-size:0.8rem;margin-top:0.3rem;">'
        f'{n_coaches} managerial changes this season</p>',
        unsafe_allow_html=True,
    )

# ── Select a manager to view ────────────────────────────────────────────────
st.markdown("---")

coach_labels = []
for c in team_coaches:
    start = c.get("start_date", "")[:10] or "?"
    end = c.get("end_date", "")[:10] or "Present"
    status = " (current)" if c["active"] else ""
    coach_labels.append(f"{c['name']} ({start} → {end}){status}")

coach_map = dict(zip(coach_labels, team_coaches))

selected_label = st.selectbox("Select Manager", options=coach_labels,
                              index=len(coach_labels) - 1,
                              key="manager_select")
coach = coach_map[selected_label]

# ── Manager Profile Card ────────────────────────────────────────────────────
crest = crest_url(team_id)
tenure_start = coach["start_date"][:10] if coach["start_date"] else "Unknown"
tenure_end = coach["end_date"][:10] if coach["end_date"] else "Present"
status = "Active" if coach["active"] else "Inactive"
status_color = "#4CAF50" if coach["active"] else "#888"

profile_html = (
    f'<div class="match-header" style="text-align:left;display:flex;'
    f'align-items:center;gap:2rem;padding:1.5rem 2rem;">'
    f'<img src="{crest}" alt="{selected_team}" style="width:80px;height:80px;">'
    f'<div>'
    f'<h2 style="margin:0;color:#E0E0E0;font-size:1.8rem;">{coach["name"]}</h2>'
    f'<p style="margin:0.2rem 0 0;color:#999;font-size:0.95rem;">'
    f'{selected_team} &middot; Head Coach</p>'
    f'<div style="display:flex;gap:1.5rem;margin-top:0.7rem;flex-wrap:wrap;">'
    f'<span style="color:#BBB;font-size:0.85rem;">'
    f'<strong style="color:{MU_RED};">Nationality:</strong> {coach["nationality"]}</span>'
    f'<span style="color:#BBB;font-size:0.85rem;">'
    f'<strong style="color:{MU_RED};">Birthplace:</strong> {coach["place_of_birth"] or "N/A"}</span>'
    f'<span style="color:#BBB;font-size:0.85rem;">'
    f'<strong style="color:{MU_RED};">Appointed:</strong> {tenure_start}</span>'
    f'<span style="color:#BBB;font-size:0.85rem;">'
    f'<strong style="color:{status_color};">Status:</strong> {status}</span>'
    f'</div>'
    f'</div>'
    f'</div>'
)
st.markdown(profile_html, unsafe_allow_html=True)

# ── Tenure-filtered Record KPIs ─────────────────────────────────────────────
section_header(f"Record Under {coach['name']}")
record = compute_manager_record(
    league, season, team_id,
    start_date=coach.get("start_date", ""),
    end_date=coach.get("end_date", ""),
)

if record["played"] > 0:
    kpi_row([
        {"label": "Played", "value": record["played"]},
        {"label": "Won", "value": record["won"]},
        {"label": "Drawn", "value": record["drawn"]},
        {"label": "Lost", "value": record["lost"]},
    ], cols=4)

    kpi_row([
        {"label": "Win Rate", "value": f"{record['win_pct']:.0f}%"},
        {"label": "Points", "value": record["points"]},
        {"label": "PPG", "value": f"{record['ppg']:.2f}"},
        {"label": "Goal Diff", "value": f"{record['gd']:+d}"},
    ], cols=4)
else:
    st.info("No match results in this tenure window.")

# ── Recent Form ─────────────────────────────────────────────────────────────
form = compute_recent_form(
    league, season, team_id, n=5,
    start_date=coach.get("start_date", ""),
    end_date=coach.get("end_date", ""),
)
if form:
    st.markdown(
        f'<div style="margin:1rem 0;">'
        f'<span style="color:#999;font-size:0.85rem;text-transform:uppercase;'
        f'letter-spacing:0.05em;margin-right:0.8rem;">Last {len(form)}:</span>'
        f'{form_badges(form)}'
        f'</div>',
        unsafe_allow_html=True,
    )

# ── Results Donut + Goals ───────────────────────────────────────────────────
if record["played"] > 0:
    st.markdown("---")
    col1, col2 = st.columns([1, 1])

    with col1:
        section_header("Results Distribution")
        fig = donut_chart(
            ["Wins", "Draws", "Losses"],
            [record["won"], record["drawn"], record["lost"]],
            title=f"Results — {coach['name']}",
            colors=["#4CAF50", "#FFC107", MU_RED],
        )
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        section_header("Goals Overview")
        fig_goals = go.Figure()
        fig_goals.add_trace(go.Bar(
            x=["Goals For", "Goals Against"],
            y=[record["gf"], record["ga"]],
            marker_color=[MU_RED, "#42A5F5"],
            text=[record["gf"], record["ga"]],
            textposition="auto",
        ))
        fig_goals.update_layout(
            title=f"Goals — {coach['name']}",
            yaxis_title="Goals",
            showlegend=False,
            height=380,
        )
        st.plotly_chart(fig_goals, use_container_width=True)

# ── Home vs Away Split ──────────────────────────────────────────────────────
st.markdown("---")
section_header("Home vs Away Performance")

split = compute_home_away_split(
    league, season, team_id,
    start_date=coach.get("start_date", ""),
    end_date=coach.get("end_date", ""),
)
home_played = split["home_w"] + split["home_d"] + split["home_l"]
away_played = split["away_w"] + split["away_d"] + split["away_l"]

col1, col2 = st.columns(2)
with col1:
    st.markdown("**Home**")
    if home_played > 0:
        home_pct = split["home_w"] / home_played * 100
        st.metric("Record", f"{split['home_w']}W {split['home_d']}D {split['home_l']}L")
        st.metric("Win Rate", f"{home_pct:.0f}%")
        st.metric("Goals", f"{split['home_gf']} scored, {split['home_ga']} conceded")
    else:
        st.info("No home matches in this tenure.")

with col2:
    st.markdown("**Away**")
    if away_played > 0:
        away_pct = split["away_w"] / away_played * 100
        st.metric("Record", f"{split['away_w']}W {split['away_d']}D {split['away_l']}L")
        st.metric("Win Rate", f"{away_pct:.0f}%")
        st.metric("Goals", f"{split['away_gf']} scored, {split['away_ga']} conceded")
    else:
        st.info("No away matches in this tenure.")

# ── Formation Usage ─────────────────────────────────────────────────────────
st.markdown("---")
section_header("Tactical Formations")

formations = compute_formation_usage(
    league, season, team_id,
    start_date=coach.get("start_date", ""),
    end_date=coach.get("end_date", ""),
)

if formations:
    col1, col2 = st.columns([2, 1])
    with col1:
        fm_df = pd.DataFrame(formations)
        fig_fm = go.Figure()
        fig_fm.add_trace(go.Bar(
            x=fm_df["formation"],
            y=fm_df["count"],
            marker_color=MU_RED,
            text=fm_df.apply(lambda r: f"{r['count']} ({r['pct']:.0f}%)", axis=1),
            textposition="auto",
        ))
        fig_fm.update_layout(
            title=f"Formations Used — {coach['name']}",
            xaxis_title="Formation",
            yaxis_title="Matches",
            height=380,
        )
        st.plotly_chart(fig_fm, use_container_width=True)

    with col2:
        st.markdown("**Preferred Setup**")
        primary = formations[0]
        st.markdown(
            f'<div style="text-align:center;padding:1.5rem;">'
            f'<p style="font-size:3rem;font-weight:800;color:{MU_RED};margin:0;">'
            f'{primary["formation"]}</p>'
            f'<p style="color:#999;font-size:0.85rem;margin:0.3rem 0 0;">'
            f'Used in {primary["pct"]:.0f}% of matches</p>'
            f'</div>',
            unsafe_allow_html=True,
        )
        if len(formations) > 1:
            st.markdown("**Alternatives:**")
            for fm in formations[1:]:
                st.text(f"  {fm['formation']} — {fm['count']} matches ({fm['pct']:.0f}%)")
else:
    st.info("No formation data available for this tenure.")

# ── Goal Difference Timeline ────────────────────────────────────────────────
st.markdown("---")
section_header("Cumulative Goal Difference")

timeline = compute_goals_timeline(
    league, season, team_id,
    start_date=coach.get("start_date", ""),
    end_date=coach.get("end_date", ""),
)

if not timeline.empty:
    fig_gd = go.Figure()
    fig_gd.add_trace(go.Scatter(
        x=timeline["match_num"],
        y=timeline["gd_cumulative"],
        mode="lines+markers",
        line=dict(color=MU_RED, width=3),
        marker=dict(size=6, color=MU_RED),
        fill="tozeroy",
        fillcolor="rgba(218,41,28,0.15)",
        name="Cumulative GD",
    ))
    fig_gd.add_hline(y=0, line_dash="dash", line_color="#555", line_width=1)
    fig_gd.update_layout(
        title=f"GD Progression — {coach['name']}",
        xaxis_title="Match Number",
        yaxis_title="Cumulative Goal Difference",
        height=380,
    )
    st.plotly_chart(fig_gd, use_container_width=True)

# ══════════════════════════════════════════════════════════════════════════════
# ── MANAGER COMPARISON ───────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════

if n_coaches >= 2:
    st.markdown("---")
    st.markdown("---")
    section_header("Manager Comparison")
    st.caption(f"Compare all {n_coaches} managers who coached {selected_team} this season")

    # Build comparison table
    comp_df = compare_managers(league, season, team_id, team_coaches)

    if not comp_df.empty and comp_df["P"].sum() > 0:
        st.dataframe(comp_df, hide_index=True, use_container_width=True)

        # ── Side-by-side visual comparison ───────────────────────────────
        st.markdown("---")
        compare_colors = [MU_RED, "#42A5F5", MU_GOLD, "#4CAF50"]

        # PPG comparison bar chart
        fig_ppg = go.Figure()
        for i, (_, row) in enumerate(comp_df.iterrows()):
            fig_ppg.add_trace(go.Bar(
                x=[row["Manager"]],
                y=[row["PPG"]],
                marker_color=compare_colors[i % len(compare_colors)],
                text=[f"{row['PPG']:.2f}"],
                textposition="auto",
                name=row["Manager"],
                showlegend=False,
            ))
        fig_ppg.update_layout(
            title="Points Per Game",
            yaxis_title="PPG",
            height=350,
        )

        # Win % comparison
        fig_win = go.Figure()
        for i, (_, row) in enumerate(comp_df.iterrows()):
            fig_win.add_trace(go.Bar(
                x=[row["Manager"]],
                y=[row["Win %"]],
                marker_color=compare_colors[i % len(compare_colors)],
                text=[f"{row['Win %']:.0f}%"],
                textposition="auto",
                name=row["Manager"],
                showlegend=False,
            ))
        fig_win.update_layout(
            title="Win Rate",
            yaxis_title="Win %",
            height=350,
        )

        col1, col2 = st.columns(2)
        with col1:
            st.plotly_chart(fig_ppg, use_container_width=True)
        with col2:
            st.plotly_chart(fig_win, use_container_width=True)

        # ── Stacked W/D/L bar chart ─────────────────────────────────────
        fig_wdl = go.Figure()
        fig_wdl.add_trace(go.Bar(
            name="Won", x=comp_df["Manager"], y=comp_df["W"],
            marker_color="#4CAF50",
        ))
        fig_wdl.add_trace(go.Bar(
            name="Drawn", x=comp_df["Manager"], y=comp_df["D"],
            marker_color="#FFC107",
        ))
        fig_wdl.add_trace(go.Bar(
            name="Lost", x=comp_df["Manager"], y=comp_df["L"],
            marker_color=MU_RED,
        ))
        fig_wdl.update_layout(
            barmode="stack",
            title="Results Breakdown",
            yaxis_title="Matches",
            height=380,
            legend=dict(orientation="h", yanchor="bottom", y=1.02,
                        xanchor="center", x=0.5),
        )
        st.plotly_chart(fig_wdl, use_container_width=True)

        # ── GF/GA per game comparison ────────────────────────────────────
        fig_gfga = go.Figure()
        for i, (_, row) in enumerate(comp_df.iterrows()):
            color = compare_colors[i % len(compare_colors)]
            fig_gfga.add_trace(go.Bar(
                x=["GF/Game", "GA/Game"],
                y=[row["GF/G"], row["GA/G"]],
                name=row["Manager"],
                marker_color=color,
                text=[f"{row['GF/G']:.2f}", f"{row['GA/G']:.2f}"],
                textposition="auto",
            ))
        fig_gfga.update_layout(
            barmode="group",
            title="Goals Per Game",
            yaxis_title="Goals/Game",
            height=380,
            legend=dict(orientation="h", yanchor="bottom", y=1.02,
                        xanchor="center", x=0.5),
        )
        st.plotly_chart(fig_gfga, use_container_width=True)

    else:
        st.info("Not enough match data for comparison.")

# ── All Coaches in Competition ──────────────────────────────────────────────
st.markdown("---")
st.markdown("---")
section_header("All Head Coaches in Competition")

all_coaches = get_head_coaches(league, season)
all_data = []
for c in all_coaches:
    rec = compute_manager_record(league, season, c["team_id"])
    all_data.append({
        "Manager": c["name"],
        "Team": c["team"],
        "Nationality": c["nationality"],
        "P": rec["played"],
        "W": rec["won"],
        "D": rec["drawn"],
        "L": rec["lost"],
        "Win %": f"{rec['win_pct']:.0f}",
        "Pts": rec["points"],
        "PPG": f"{rec['ppg']:.2f}",
        "GD": rec["gd"],
    })

all_df = pd.DataFrame(all_data)
if not all_df.empty:
    all_df = all_df.sort_values("Pts", ascending=False).reset_index(drop=True)
    st.dataframe(all_df, hide_index=True, use_container_width=True, height=600)
