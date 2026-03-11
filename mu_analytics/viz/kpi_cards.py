"""Dashboard KPI card components rendered as HTML."""

import streamlit as st
import pandas as pd
from config import MU_RED, MU_GOLD
from processing.match_stats import crest_url


def kpi_card(label: str, value, delta=None, delta_suffix: str = "",
             positive_is_good: bool = True):
    """Render a styled KPI card using custom HTML."""
    delta_html = ""
    if delta is not None:
        is_positive = delta > 0 if isinstance(delta, (int, float)) else False
        delta_class = "positive" if (is_positive == positive_is_good) else "negative"
        sign = "+" if isinstance(delta, (int, float)) and delta > 0 else ""
        delta_html = f'<p class="kpi-delta {delta_class}">{sign}{delta}{delta_suffix}</p>'

    html = f"""
    <div class="kpi-card">
        <p class="kpi-label">{label}</p>
        <p class="kpi-value">{value}</p>
        {delta_html}
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)


def kpi_row(metrics: list[dict], cols: int = 4):
    """Render a row of KPI cards.

    Each metric dict should have: label, value, and optionally delta, delta_suffix.
    """
    columns = st.columns(cols)
    for i, m in enumerate(metrics):
        with columns[i % cols]:
            kpi_card(
                label=m["label"],
                value=m["value"],
                delta=m.get("delta"),
                delta_suffix=m.get("delta_suffix", ""),
                positive_is_good=m.get("positive_is_good", True),
            )


def form_badges(results: list[str]) -> str:
    """Generate HTML for W/D/L form badges.

    Args:
        results: list of "W", "D", or "L" strings (most recent first)
    """
    badges = ""
    for r in results:
        badges += f'<span class="form-badge {r}">{r}</span>'
    return f'<div style="display:flex;gap:4px;align-items:center;">{badges}</div>'


def section_header(text: str):
    """Render a styled section header."""
    st.markdown(f'<h3 class="section-header">{text}</h3>', unsafe_allow_html=True)


def metric_highlight(label: str, value, color: str = MU_RED):
    """Render a single large highlighted metric."""
    html = f"""
    <div style="text-align:center;padding:1rem;">
        <p style="color:#999;font-size:0.85rem;text-transform:uppercase;margin:0;">{label}</p>
        <p style="color:{color};font-size:3rem;font-weight:700;margin:0;">{value}</p>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)


# ── Professional Match Dashboard Components ──────────────────────────────────

def match_header_card(
    home_team: str, away_team: str,
    home_score: int, away_score: int,
    home_id: str, away_id: str,
    matchday: int, date: str, venue: str,
    ht_home: int = 0, ht_away: int = 0,
    competition: str = "Premier League",
) -> None:
    """Render professional match header with team crests flanking the score."""
    home_crest = crest_url(home_id)
    away_crest = crest_url(away_id)
    date_str = str(date)[:10]
    html = (
        f'<div class="match-header">'
        f'<div class="match-meta">{competition} &middot; Matchday {matchday} &middot; {date_str} &middot; {venue}</div>'
        f'<div class="score-row">'
        f'<div class="team-block"><img src="{home_crest}" alt="{home_team}"><span class="team-name">{home_team}</span></div>'
        f'<div class="score-display"><span class="home-score">{home_score}</span><span class="score-sep">-</span><span class="away-score">{away_score}</span></div>'
        f'<div class="team-block"><img src="{away_crest}" alt="{away_team}"><span class="team-name">{away_team}</span></div>'
        f'</div>'
        f'<div class="ht-score">HT: {ht_home} - {ht_away}</div>'
        f'</div>'
    )
    st.markdown(html, unsafe_allow_html=True)


def stats_comparison_table(stats: list[dict]) -> None:
    """Render side-by-side stat comparison bars.

    Args:
        stats: list from compute_match_stats(), each dict has
               label, home_value, away_value, home_pct, away_pct, format
    """
    rows = []
    for s in stats:
        fmt = s.get("format", "int")
        hv = s["home_value"]
        av = s["away_value"]
        if fmt == "pct":
            h_display = f"{hv:.0f}%"
            a_display = f"{av:.0f}%"
        elif fmt == "float1":
            h_display = f"{hv:.1f}"
            a_display = f"{av:.1f}"
        else:
            h_display = str(int(hv))
            a_display = str(int(av))
        hp = s["home_pct"]
        ap = s["away_pct"]
        label = s["label"]
        # Compact single-line HTML to avoid Streamlit markdown parser issues
        row = (
            f'<div class="stat-row">'
            f'<span class="stat-val home">{h_display}</span>'
            f'<div class="bar-container"><div class="bar-fill-home" style="width:{hp}%"></div></div>'
            f'<span class="stat-label">{label}</span>'
            f'<div class="bar-container"><div class="bar-fill-away" style="width:{ap}%"></div></div>'
            f'<span class="stat-val away">{a_display}</span>'
            f'</div>'
        )
        rows.append(row)

    html = '<div class="stat-comparison">' + "".join(rows) + '</div>'
    st.markdown(html, unsafe_allow_html=True)


def content_card(title: str) -> None:
    """Render a content card section title."""
    html = f'<div class="content-card" style="padding:0.8rem 1.2rem;"><div class="card-title">{title}</div></div>'
    st.markdown(html, unsafe_allow_html=True)


def key_events_timeline(
    events_df: pd.DataFrame,
    home_team: str, away_team: str,
    home_id: str, away_id: str,
) -> None:
    """Render a styled vertical timeline of key match events."""
    if events_df.empty:
        st.info("No key events recorded.")
        return

    icon_map = {
        "Goal": "&#9917;",       # ⚽
        "Card": "&#128995;",     # 🟨
        "Sub On": "&#9650;",     # ▲
        "Sub Off": "&#9660;",    # ▼
    }

    items = []
    for _, ev in events_df.sort_values("minute").iterrows():
        is_home = ev["team_id"] == home_id
        color = MU_RED if is_home else "#42A5F5"
        team = home_team if is_home else away_team
        icon = icon_map.get(ev["event_type"], "&#8226;")
        player = ev.get("player_name", "")
        # Compact single-line HTML to avoid Streamlit markdown parser issues
        item = (
            f'<div class="event-item">'
            f'<span class="event-minute">{ev["minute"]}\'</span>'
            f'<span class="event-dot" style="background:{color};"></span>'
            f'<span class="event-icon">{icon}</span>'
            f'<span class="event-detail">'
            f'<span class="player-name">{player}</span>'
            f'<span style="color:#888;"> ({team})</span>'
            f'</span></div>'
        )
        items.append(item)

    html = '<div class="event-timeline">' + "".join(items) + '</div>'
    st.markdown(html, unsafe_allow_html=True)
