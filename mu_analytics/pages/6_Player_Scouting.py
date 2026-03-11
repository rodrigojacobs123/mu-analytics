"""Player Scouting — Position-specific ratings, versatility detection, gap analysis."""

import streamlit as st
import pandas as pd
from components.sidebar import render_sidebar
from viz.kpi_cards import section_header, kpi_card, metric_highlight
from viz.radar import fc_radar, position_radar
from viz.tables import styled_dataframe
from data.loader import load_all_player_season_stats
from processing.player_ratings import (
    compute_fc_ratings, POSITION_ATTR_KEYS, POSITION_CATEGORY_DISPLAY,
    get_position_attrs, get_position_display_names,
    SUB_POSITIONS,
)
from processing.play_style import classify_play_style, get_all_play_styles
from processing.gap_analysis import (
    compute_team_gaps, compute_position_depth,
    find_recommendations, find_players_by_role,
)
from config import (
    MU_TEAM_NAME, MU_RED, MU_GOLD, MU_DARK_BG,
    POSITION_CATEGORIES,
)

league, season = render_sidebar()

st.title("Player Scouting")

# ── Compute Ratings ─────────────────────────────────────────────────────────
with st.spinner("Computing player ratings..."):
    all_stats = load_all_player_season_stats(league, season)
    ratings_df = compute_fc_ratings(all_stats)

if ratings_df.empty:
    st.warning("No player stats available for computing ratings.")
    st.stop()

# Classify play styles for all players (uses legacy PAC/SHO/PAS/DRI/DEF/PHY)
def _add_play_styles(df):
    styles = []
    for _, row in df.iterrows():
        r = {attr: int(row.get(attr, 50)) for attr in ["PAC", "SHO", "PAS", "DRI", "DEF", "PHY"]}
        name, desc, icon = classify_play_style(r)
        styles.append(f"{icon} {name}")
    df["play_style"] = styles
    return df

ratings_df = _add_play_styles(ratings_df)

# Get unique values for filters
all_teams = sorted(ratings_df["equipo"].dropna().unique().tolist())
all_positions = sorted(ratings_df["posicion"].dropna().unique().tolist())
all_styles = sorted(set(ratings_df["play_style"].dropna().unique().tolist()))


# ═══════════════════════════════════════════════════════════════════════════
# § 1  ADVANCED FILTERS
# ═══════════════════════════════════════════════════════════════════════════

with st.expander("**Advanced Filters**", expanded=True):
    fcol1, fcol2, fcol3, fcol4 = st.columns(4)
    with fcol1:
        scope = st.radio("Scope", ["Manchester United", "Custom Team", "Entire League"],
                         horizontal=False, key="scouting_scope")
    with fcol2:
        if scope == "Custom Team":
            selected_teams = st.multiselect("Select Team(s)", all_teams, key="team_filter")
        else:
            selected_teams = []
        pos_filter = st.multiselect("Position", all_positions, key="pos_filter")
    with fcol3:
        style_filter = st.multiselect("Play Style", all_styles, key="style_filter")
    with fcol4:
        ovr_range = st.slider("OVR Range", 40, 99, (40, 99), key="ovr_filter")
        # Dynamic sort options: position-specific if single position selected
        if len(pos_filter) == 1:
            pos_attrs = get_position_display_names(pos_filter[0])
            sort_options = ["OVR"] + pos_attrs
        else:
            sort_options = ["OVR", "PAC", "SHO", "PAS", "DRI", "DEF", "PHY"]
        attr_sort = st.selectbox("Sort by", sort_options, key="sort_ratings")

# Apply filters
if scope == "Manchester United":
    display_df = ratings_df[ratings_df["equipo"] == MU_TEAM_NAME].copy()
    if display_df.empty:
        display_df = ratings_df[ratings_df["equipo"].str.contains("Manchester United", na=False)]
    focus_team = MU_TEAM_NAME
elif scope == "Custom Team":
    if selected_teams:
        display_df = ratings_df[ratings_df["equipo"].isin(selected_teams)].copy()
        focus_team = selected_teams[0] if len(selected_teams) == 1 else None
    else:
        display_df = ratings_df.copy()
        focus_team = None
else:
    display_df = ratings_df.copy()
    focus_team = None

if pos_filter:
    display_df = display_df[display_df["posicion"].isin(pos_filter)]
if style_filter:
    display_df = display_df[display_df["play_style"].isin(style_filter)]
display_df = display_df[
    (display_df["OVR"] >= ovr_range[0]) & (display_df["OVR"] <= ovr_range[1])
]


# ═══════════════════════════════════════════════════════════════════════════
# § 2  PLAYER LEADERBOARD (position-aware columns)
# ═══════════════════════════════════════════════════════════════════════════
section_header(f"Player Leaderboard ({len(display_df)} players)")

# Show position-specific columns when filtering by one position
if len(pos_filter) == 1:
    pos_keys = get_position_attrs(pos_filter[0])
    pos_display = get_position_display_names(pos_filter[0])
    show_cols = ["nombre", "posicion", "equipo", "play_style"] + pos_keys + ["OVR"]
    # Map sort display name → column key
    display_to_key = {v: k for k, v in POSITION_CATEGORY_DISPLAY.items()}
    sort_col = display_to_key.get(attr_sort, attr_sort)
else:
    show_cols = ["nombre", "posicion", "equipo", "play_style",
                 "PAC", "SHO", "PAS", "DRI", "DEF", "PHY", "OVR"]
    sort_col = attr_sort

available = [c for c in show_cols if c in display_df.columns]
if sort_col in display_df.columns:
    sorted_df = display_df[available].sort_values(sort_col, ascending=False).head(50)
else:
    sorted_df = display_df[available].sort_values("OVR", ascending=False).head(50)

# Rename position-specific columns to display names for the table
rename_map = {k: v for k, v in POSITION_CATEGORY_DISPLAY.items() if k in sorted_df.columns}
styled_dataframe(sorted_df.rename(columns=rename_map), height=420)


# ═══════════════════════════════════════════════════════════════════════════
# § 3  INDIVIDUAL PLAYER CARD (position-specific radar + versatility)
# ═══════════════════════════════════════════════════════════════════════════
st.markdown("---")
section_header("Player Card")

player_options = display_df[display_df["nombre"].notna()]["nombre"].tolist()
if not player_options:
    st.info("No rated players match your filters.")
    st.stop()

selected_name = st.selectbox("Select Player", player_options, key="player_card_sel")
player_row = display_df[display_df["nombre"] == selected_name].iloc[0]

# Get player's position and corresponding attributes
ovr = int(player_row.get("OVR", 50))
pos = player_row.get("posicion", "Midfielder")
team = player_row.get("equipo", "Unknown")
pos_keys = get_position_attrs(pos)
pos_display_names = get_position_display_names(pos)

# Build position-specific ratings dict
pos_ratings = {k: int(player_row.get(k, 50)) if pd.notna(player_row.get(k)) else 50
               for k in pos_keys}

# Legacy ratings for play-style
legacy_ratings = {attr: int(player_row.get(attr, 50))
                  for attr in ["PAC", "SHO", "PAS", "DRI", "DEF", "PHY"]}

# Player card layout
col1, col2, col3 = st.columns([1.2, 2, 1])

with col1:
    metric_highlight("OVR", ovr, MU_RED)
    st.markdown(f"**Position:** {pos}")
    st.markdown(f"**Team:** {team}")

    # Play-style badge
    style_name, style_desc, style_icon = classify_play_style(legacy_ratings)
    st.markdown(f"""
    <div style="background:#1A1A2E;border-left:3px solid {MU_GOLD};padding:0.8rem;
                border-radius:5px;margin-top:1rem;">
        <p style="margin:0;color:{MU_GOLD};font-weight:bold;font-size:1.1rem;">
            {style_icon} {style_name}
        </p>
        <p style="margin:0.3rem 0 0;color:#999;font-size:0.85rem;">{style_desc}</p>
    </div>
    """, unsafe_allow_html=True)

    # Versatility badge
    v_tags = player_row.get("versatility_tags", [])
    if isinstance(v_tags, list) and v_tags:
        for tag in v_tags:
            st.markdown(f"""
            <div style="background:#1A1A2E;border-left:3px solid #42A5F5;padding:0.6rem;
                        border-radius:5px;margin-top:0.5rem;">
                <p style="margin:0;color:#42A5F5;font-weight:bold;font-size:0.9rem;">
                    {tag}
                </p>
            </div>
            """, unsafe_allow_html=True)

    # Percentile ranking
    all_pos_players = ratings_df[ratings_df["posicion"] == pos]
    if not all_pos_players.empty:
        rank = (all_pos_players["OVR"] <= ovr).sum()
        pctile = int(rank / len(all_pos_players) * 100)
        st.markdown(f"""
        <div style="margin-top:0.8rem;padding:0.5rem;background:#1A1A2E;border-radius:5px;">
            <span style="color:#888;font-size:0.75rem;">LEAGUE PERCENTILE</span><br>
            <span style="color:{'#4CAF50' if pctile >= 75 else (MU_GOLD if pctile >= 50 else '#FF5252')};
                   font-size:1.5rem;font-weight:700;">{pctile}th</span>
            <span style="color:#666;font-size:0.75rem;"> among {len(all_pos_players)} {pos}s</span>
        </div>
        """, unsafe_allow_html=True)

with col2:
    # Position-specific radar (5 axes tailored to position)
    fig = position_radar(selected_name, pos, pos_ratings)
    st.plotly_chart(fig, use_container_width=True)

with col3:
    # Position-specific attribute bars with league percentile context
    for key, display_name in zip(pos_keys, pos_display_names):
        val = pos_ratings.get(key, 50)
        # League percentile for this attribute
        if not all_pos_players.empty and key in all_pos_players.columns:
            valid = all_pos_players[key].dropna()
            attr_pctile = int((valid <= val).sum() / len(valid) * 100) if len(valid) > 0 else 50
        else:
            attr_pctile = 50
        bar_color = MU_RED if val >= 75 else (MU_GOLD if val >= 60 else "#666")
        pctile_color = "#4CAF50" if attr_pctile >= 75 else (MU_GOLD if attr_pctile >= 50 else "#888")
        st.markdown(f"""
        <div style="margin:0.35rem 0;">
            <div style="display:flex;justify-content:space-between;align-items:center;">
                <span style="color:#999;font-size:0.72rem;width:80px;">{display_name}</span>
                <span style="color:white;font-weight:bold;font-size:1rem;">{val}</span>
                <span style="color:{pctile_color};font-size:0.7rem;">{attr_pctile}%ile</span>
            </div>
            <div style="background:#333;border-radius:3px;height:8px;width:100%;">
                <div style="background:{bar_color};border-radius:3px;height:8px;width:{val}%;"></div>
            </div>
        </div>
        """, unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════
# § 4  PLAYER COMPARISON
# ═══════════════════════════════════════════════════════════════════════════
st.markdown("---")
section_header("Player Comparison")

all_player_names = ratings_df[ratings_df["nombre"].notna()]["nombre"].tolist()
compare_names = st.multiselect(
    "Compare with (any league player)",
    [n for n in all_player_names if n != selected_name],
    max_selections=2,
    key="player_compare"
)

if compare_names:
    # Check if all compared players share the same position
    compare_rows = [ratings_df[ratings_df["nombre"] == n].iloc[0] for n in compare_names]
    all_same_pos = all(r.get("posicion") == pos for r in compare_rows)

    if all_same_pos:
        # Position-specific radar comparison
        compare_pos_ratings = {}
        for name, row in zip(compare_names, compare_rows):
            compare_pos_ratings[name] = {
                k: int(row.get(k, 50)) if pd.notna(row.get(k)) else 50
                for k in pos_keys
            }
        fig = position_radar(selected_name, pos, pos_ratings,
                             compare_to=compare_pos_ratings)
        st.plotly_chart(fig, use_container_width=True)

        # Comparison table with position attributes
        comp_data = {"Attribute": pos_display_names + ["OVR"]}
        comp_data[selected_name] = [pos_ratings.get(k, 0) for k in pos_keys] + [ovr]
        for name, row in zip(compare_names, compare_rows):
            comp_data[name] = ([int(row.get(k, 0)) if pd.notna(row.get(k)) else 0
                                for k in pos_keys]
                               + [int(row.get("OVR", 0))])
    else:
        # Mixed positions — use legacy PAC/SHO/PAS/DRI/DEF/PHY radar
        compare_legacy = {}
        for name, row in zip(compare_names, compare_rows):
            compare_legacy[name] = {attr: int(row.get(attr, 50))
                                    for attr in ["PAC", "SHO", "PAS", "DRI", "DEF", "PHY"]}
        fig = fc_radar(selected_name, legacy_ratings, compare_to=compare_legacy)
        st.plotly_chart(fig, use_container_width=True)

        # Comparison table with legacy attributes
        attrs = ["PAC", "SHO", "PAS", "DRI", "DEF", "PHY"]
        comp_data = {"Attribute": attrs + ["OVR"]}
        comp_data[selected_name] = [legacy_ratings.get(a, 0) for a in attrs] + [ovr]
        for name, row in zip(compare_names, compare_rows):
            comp_data[name] = [int(row.get(a, 0)) for a in attrs] + [int(row.get("OVR", 0))]

    comp_df = pd.DataFrame(comp_data)
    styled_dataframe(comp_df, height=300)


# ═══════════════════════════════════════════════════════════════════════════
# § 5  SQUAD DEPTH ANALYSIS
# ═══════════════════════════════════════════════════════════════════════════
st.markdown("---")
section_header("Squad Depth Analysis")

depth_team = st.selectbox(
    "Analyze Team Depth",
    all_teams,
    index=all_teams.index(MU_TEAM_NAME) if MU_TEAM_NAME in all_teams else 0,
    key="depth_team"
)

depth_df = compute_position_depth(ratings_df, depth_team)
if not depth_df.empty:
    for _, row in depth_df.iterrows():
        depth_color = {
            "Strong": "#4CAF50", "Adequate": MU_GOLD,
            "Thin": "#FF9800", "Empty": "#FF5252"
        }.get(row["depth_rating"], "#666")

        depth_icon = {
            "Strong": "++", "Adequate": "+", "Thin": "-", "Empty": "--"
        }.get(row["depth_rating"], "?")

        bar_width = min(row["count"] * 15, 100)
        st.markdown(f"""
        <div style="display:flex;align-items:center;gap:10px;margin:0.3rem 0;padding:0.5rem;
                    background:#1A1A2E;border-radius:6px;border-left:3px solid {depth_color};">
            <span style="width:100px;color:#ccc;font-size:0.85rem;font-weight:600;">{row['position']}</span>
            <div style="flex:1;">
                <div style="background:#333;border-radius:3px;height:20px;width:100%;position:relative;">
                    <div style="background:{depth_color};border-radius:3px;height:20px;width:{bar_width}%;
                         display:flex;align-items:center;padding-left:8px;">
                        <span style="color:white;font-size:0.75rem;font-weight:700;">{row['count']} players</span>
                    </div>
                </div>
            </div>
            <span style="width:60px;text-align:center;color:white;font-weight:700;font-size:0.9rem;">
                {row['avg_ovr']}
            </span>
            <span style="width:30px;text-align:center;color:{depth_color};font-weight:bold;">{depth_icon}</span>
            <span style="width:80px;color:{depth_color};font-size:0.75rem;font-weight:600;">
                {row['depth_rating']}
            </span>
        </div>
        """, unsafe_allow_html=True)

    st.caption("Bar = player count | Number = avg OVR | Rating = depth assessment")
else:
    st.info("No depth data available for this team.")


# ═══════════════════════════════════════════════════════════════════════════
# § 6  TEAM GAP ANALYSIS (position-specific attributes)
# ═══════════════════════════════════════════════════════════════════════════
st.markdown("---")
section_header("Gap Analysis vs League Average")

gap_team = depth_team  # Use same team selection

gaps_df = compute_team_gaps(ratings_df, gap_team)
if not gaps_df.empty:
    # Show OVR gaps by position
    ovr_gaps = gaps_df[gaps_df["attribute"] == "OVR"].copy()
    ovr_gaps = ovr_gaps.sort_values("gap")

    st.markdown(f"#### {gap_team} — Position OVR vs League Average")

    for _, row in ovr_gaps.iterrows():
        gap = row["gap"]
        gap_color = "#4CAF50" if gap >= 2 else (MU_GOLD if gap >= -2 else "#FF5252")
        gap_icon = "+" if gap > 0 else ("-" if gap < 0 else "=")
        bar_pos = min(max((row["team_avg"] - 40) / 60 * 100, 0), 100)

        st.markdown(f"""
        <div style="margin:0.35rem 0;padding:0.5rem 0.8rem;background:#1A1A2E;border-radius:6px;">
            <div style="display:flex;justify-content:space-between;align-items:center;">
                <span style="color:#ccc;font-size:0.85rem;font-weight:600;width:100px;">
                    {row['position']}
                </span>
                <span style="color:white;font-size:0.9rem;">
                    Team: <b>{row['team_avg']}</b>
                </span>
                <span style="color:#888;font-size:0.9rem;">
                    League: <b>{row['league_avg']}</b>
                </span>
                <span style="color:{gap_color};font-size:0.9rem;font-weight:700;">
                    {gap_icon} {abs(gap):.1f}
                </span>
            </div>
            <div style="position:relative;background:#333;border-radius:3px;height:8px;margin-top:6px;">
                <div style="background:{gap_color};border-radius:3px;height:8px;width:{bar_pos}%;"></div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    # Detailed attribute gaps (expandable, now position-specific)
    with st.expander("Detailed Attribute Breakdown"):
        detail = gaps_df[gaps_df["attribute"] != "OVR"].copy()
        if not detail.empty:
            # Show display_name instead of raw attribute key
            show = detail[["position", "display_name", "team_avg", "league_avg", "gap"]].copy()
            show.columns = ["Position", "Attribute", "Team Avg", "League Avg", "Gap"]
            styled_dataframe(show, height=350)
else:
    st.info("No gap data available.")


# ═══════════════════════════════════════════════════════════════════════════
# § 7  SCOUTING RECOMMENDATIONS (position-specific attributes)
# ═══════════════════════════════════════════════════════════════════════════
st.markdown("---")
section_header("Scouting Recommendations")

rec_team = depth_team

# ── Mode selector: auto gap analysis vs manual role browsing ──
rec_mode_col, rec_filter_col = st.columns([1, 2])
with rec_mode_col:
    rec_mode = st.radio(
        "Search mode",
        ["Auto (Gap Analysis)", "Browse by Role"],
        horizontal=True,
        key="rec_mode",
    )

recs_df = pd.DataFrame()
role_label = ""

if rec_mode == "Browse by Role":
    with rec_filter_col:
        chosen_role = st.selectbox(
            "Select a role",
            SUB_POSITIONS,
            key="rec_role",
        )
    role_label = chosen_role
    recs_df = find_players_by_role(ratings_df, rec_team, chosen_role, top_n=5)
else:
    recs_df = find_recommendations(ratings_df, rec_team, top_n=3)


def _render_rec_card(rec: pd.Series) -> None:
    """Render a single recommendation card with position-specific attribute chips."""
    rec_pos = rec["posicion"]
    rec_pos_keys = get_position_attrs(rec_pos)
    rec_pos_names = get_position_display_names(rec_pos)

    attr_chips = ""
    for key, display in zip(rec_pos_keys, rec_pos_names):
        val = rec.get(display, rec.get(key, 40))
        if pd.isna(val):
            val = 40
        val = int(val)
        attr_chips += (
            f'<div style="text-align:center;padding:4px 6px;background:#222;border-radius:4px;">'
            f'<span style="color:#888;font-size:0.6rem;">{display[:8]}</span><br>'
            f'<span style="color:white;font-size:0.8rem;font-weight:600;">{val}</span>'
            f'</div>'
        )

    key_display = rec.get("key_display", rec.get("key_attribute", ""))
    key_val = int(rec.get("key_value", 0))
    sub_pos = rec.get("sub_posicion", "")
    role_tag = f' · <span style="color:{MU_GOLD};font-size:0.7rem;">{sub_pos}</span>' if sub_pos else ""

    card_html = (
        f'<div style="display:flex;align-items:center;gap:10px;margin:0.4rem 0;padding:0.7rem 1rem;'
        f'background:#1A1A2E;border-radius:8px;border-left:3px solid {MU_RED};">'
        f'<div style="text-align:center;min-width:50px;">'
        f'<span style="color:{MU_RED};font-size:1.6rem;font-weight:700;">{rec["OVR"]}</span>'
        f'<br><span style="color:#666;font-size:0.65rem;">OVR</span></div>'
        f'<div style="flex:1;min-width:120px;">'
        f'<span style="color:white;font-size:1rem;font-weight:600;">{rec["nombre"]}</span>'
        f'<br><span style="color:#888;font-size:0.8rem;">{rec["equipo"]} | {rec_pos}{role_tag}</span></div>'
        f'<div style="display:flex;gap:6px;flex-wrap:wrap;">{attr_chips}</div>'
        f'<div style="text-align:center;padding:4px 8px;background:{MU_GOLD}22;border-radius:4px;'
        f'border:1px solid {MU_GOLD}44;min-width:70px;">'
        f'<span style="color:{MU_GOLD};font-size:0.6rem;">KEY</span><br>'
        f'<span style="color:{MU_GOLD};font-size:0.8rem;font-weight:700;">{key_display} {key_val}</span>'
        f'</div></div>'
    )
    st.markdown(card_html, unsafe_allow_html=True)


if not recs_df.empty:
    if rec_mode == "Browse by Role":
        st.markdown(f"**Top {role_label} players from other teams (excluding {rec_team}):**")
        for _, rec in recs_df.iterrows():
            _render_rec_card(rec)
        st.caption(f"Showing top players classified as **{role_label}** by attribute profile.")
    else:
        st.markdown(f"**Players from other teams who could strengthen {rec_team}:**")
        for gap_label in recs_df["fills_gap"].unique():
            gap_recs = recs_df[recs_df["fills_gap"] == gap_label]
            st.markdown(f"#### {gap_label}")
            for _, rec in gap_recs.iterrows():
                _render_rec_card(rec)
        st.caption("Recommendations based on positions where the team rates below league average.")
else:
    if rec_mode == "Browse by Role":
        st.info(f"No **{role_label}** players found in other teams.")
    else:
        st.success(f"{rec_team} is above league average in all positions! No urgent gaps detected.")


# ═══════════════════════════════════════════════════════════════════════════
# § 8  PLAY STYLE GUIDE
# ═══════════════════════════════════════════════════════════════════════════
st.markdown("---")
with st.expander("Play Style Guide"):
    all_style_defs = get_all_play_styles()
    style_cols = st.columns(2)
    for i, (name, cfg) in enumerate(all_style_defs.items()):
        with style_cols[i % 2]:
            st.markdown(f"""
            <div style="padding:0.5rem;margin:0.3rem 0;background:#1A1A2E;border-radius:5px;">
                <span style="font-size:1.1rem;">{cfg['icon']}</span>
                <span style="color:{MU_GOLD};font-weight:600;">{name}</span>
                <br><span style="color:#888;font-size:0.8rem;">{cfg['desc']}</span>
            </div>
            """, unsafe_allow_html=True)
