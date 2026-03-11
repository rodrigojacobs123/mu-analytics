"""Manchester United visual theme — Plotly template, mplsoccer config, CSS."""

import plotly.graph_objects as go
import plotly.io as pio
from matplotlib.colors import LinearSegmentedColormap

from config import MU_RED, MU_BLACK, MU_GOLD, MU_WHITE, MU_DARK_BG, MU_GRID

# ── Plotly dark template with MU colors ─────────────────────────────────────

MU_PLOTLY_TEMPLATE = go.layout.Template(
    layout=go.Layout(
        paper_bgcolor=MU_DARK_BG,
        plot_bgcolor=MU_DARK_BG,
        font=dict(color="#FAFAFA", family="Segoe UI, sans-serif", size=13),
        title=dict(font=dict(size=20, color="#FAFAFA")),
        xaxis=dict(gridcolor=MU_GRID, zerolinecolor=MU_GRID),
        yaxis=dict(gridcolor=MU_GRID, zerolinecolor=MU_GRID),
        colorway=[MU_RED, MU_GOLD, MU_WHITE, "#888888", "#4CAF50", "#2196F3",
                  "#FF9800", "#9C27B0", "#00BCD4", "#795548"],
        hoverlabel=dict(bgcolor="#1E1E1E", font_size=13, bordercolor=MU_RED),
        legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(size=12)),
        margin=dict(l=40, r=20, t=50, b=40),
    )
)
pio.templates["mu_dark"] = MU_PLOTLY_TEMPLATE
pio.templates.default = "mu_dark"

# ── mplsoccer pitch configuration ──────────────────────────────────────────

PITCH_COLOR = MU_DARK_BG
PITCH_LINE_COLOR = "#444444"

PITCH_KWARGS = dict(
    pitch_type="opta",
    pitch_color=PITCH_COLOR,
    line_color=PITCH_LINE_COLOR,
    linewidth=1,
    goal_type="box",
)

HALF_PITCH_KWARGS = dict(
    pitch_type="opta",
    pitch_color=PITCH_COLOR,
    line_color=PITCH_LINE_COLOR,
    linewidth=1,
    goal_type="box",
    half=True,
)

# ── Matplotlib colormaps ────────────────────────────────────────────────────

MU_CMAP = LinearSegmentedColormap.from_list(
    "mu_heat", [MU_DARK_BG, "#3D0A0A", MU_RED, MU_GOLD, MU_WHITE]
)

MU_CMAP_BLUE = LinearSegmentedColormap.from_list(
    "mu_blue", [MU_DARK_BG, "#0A1A3D", "#1565C0", "#42A5F5", MU_WHITE]
)

# ── Matplotlib figure defaults ──────────────────────────────────────────────

MPL_FIG_KWARGS = dict(facecolor=MU_DARK_BG)

# ── Global CSS for Streamlit ────────────────────────────────────────────────

GLOBAL_CSS = f"""
<style>
    /* Sidebar branding */
    [data-testid="stSidebar"] {{
        background-color: #1A1A1A;
    }}
    [data-testid="stSidebar"] .stMarkdown h1,
    [data-testid="stSidebar"] .stMarkdown h2,
    [data-testid="stSidebar"] .stMarkdown h3 {{
        color: {MU_RED};
    }}

    /* Metric cards */
    [data-testid="stMetricValue"] {{
        color: {MU_RED} !important;
        font-size: 2rem !important;
        font-weight: 700 !important;
    }}
    [data-testid="stMetricDelta"] {{
        font-size: 0.9rem !important;
    }}

    /* Headers */
    h1 {{ color: {MU_WHITE}; }}
    h2, h3 {{ color: #E0E0E0; }}

    /* DataFrames */
    .stDataFrame {{
        border: 1px solid {MU_RED}40;
        border-radius: 8px;
    }}

    /* Selectbox and inputs */
    .stSelectbox label, .stMultiSelect label, .stSlider label {{
        color: #CCCCCC !important;
    }}

    /* Tabs */
    .stTabs [data-baseweb="tab"] {{
        color: #CCCCCC;
    }}
    .stTabs [aria-selected="true"] {{
        color: {MU_RED} !important;
        border-bottom-color: {MU_RED} !important;
    }}

    /* Divider */
    hr {{
        border-color: {MU_RED}40;
    }}

    /* Custom KPI card styling */
    .kpi-card {{
        background: linear-gradient(135deg, #1A1A2E 0%, #16213E 100%);
        border-left: 4px solid {MU_RED};
        border-radius: 8px;
        padding: 1rem 1.2rem;
        margin: 0.5rem 0;
    }}
    .kpi-card .kpi-value {{
        font-size: 2.2rem;
        font-weight: 700;
        color: {MU_WHITE};
        margin: 0;
    }}
    .kpi-card .kpi-label {{
        font-size: 0.85rem;
        color: #999;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin: 0;
    }}
    .kpi-card .kpi-delta {{
        font-size: 0.85rem;
        margin-top: 0.2rem;
    }}
    .kpi-card .kpi-delta.positive {{ color: #4CAF50; }}
    .kpi-card .kpi-delta.negative {{ color: {MU_RED}; }}

    /* Form result badges */
    .form-badge {{
        display: inline-block;
        width: 28px;
        height: 28px;
        line-height: 28px;
        text-align: center;
        border-radius: 50%;
        font-weight: 700;
        font-size: 0.8rem;
        margin: 0 2px;
        color: white;
    }}
    .form-badge.W {{ background-color: #4CAF50; }}
    .form-badge.D {{ background-color: #FFC107; color: #333; }}
    .form-badge.L {{ background-color: {MU_RED}; }}

    /* Section headers */
    .section-header {{
        border-bottom: 2px solid {MU_RED};
        padding-bottom: 0.3rem;
        margin-bottom: 1rem;
        color: {MU_WHITE};
    }}

    /* ── Match Header Card ──────────────────────────────────────────── */
    .match-header {{
        background: linear-gradient(135deg, #1A1A2E 0%, #16213E 50%, #1A1A2E 100%);
        border: 1px solid rgba(218,41,28,0.2);
        border-radius: 12px;
        padding: 1.5rem 2rem;
        margin-bottom: 1.5rem;
        text-align: center;
    }}
    .match-header .match-meta {{
        color: #888;
        font-size: 0.8rem;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        margin-bottom: 0.8rem;
    }}
    .match-header .score-row {{
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 1.5rem;
    }}
    .match-header .team-block {{
        display: flex;
        flex-direction: column;
        align-items: center;
        min-width: 120px;
    }}
    .match-header .team-block img {{
        width: 60px;
        height: 60px;
        margin-bottom: 0.4rem;
    }}
    .match-header .team-block .team-name {{
        color: #E0E0E0;
        font-size: 0.95rem;
        font-weight: 600;
    }}
    .match-header .score-display {{
        font-size: 3rem;
        font-weight: 800;
        letter-spacing: 0.05em;
    }}
    .match-header .score-display .home-score {{ color: {MU_RED}; }}
    .match-header .score-display .away-score {{ color: #42A5F5; }}
    .match-header .score-display .score-sep {{ color: #555; margin: 0 0.3rem; }}
    .match-header .ht-score {{
        color: #666;
        font-size: 0.8rem;
        margin-top: 0.5rem;
    }}

    /* ── Stats Comparison Bars ──────────────────────────────────────── */
    .stat-comparison {{
        padding: 0.2rem 0;
        max-width: 700px;
        margin: 0 auto 1.5rem auto;
    }}
    .stat-row {{
        display: flex;
        align-items: center;
        margin: 0.5rem 0;
        gap: 6px;
    }}
    .stat-row .stat-val {{
        width: 45px;
        font-weight: 700;
        font-size: 0.9rem;
        color: #E0E0E0;
    }}
    .stat-row .stat-val.home {{ text-align: right; }}
    .stat-row .stat-val.away {{ text-align: left; }}
    .stat-row .stat-label {{
        width: 100px;
        text-align: center;
        font-size: 0.72rem;
        color: #999;
        text-transform: uppercase;
        letter-spacing: 0.04em;
        flex-shrink: 0;
    }}
    .stat-row .bar-container {{
        flex: 1;
        height: 8px;
        background: #2A2A3E;
        border-radius: 4px;
        overflow: hidden;
    }}
    .stat-row .bar-fill-home {{
        height: 100%;
        background: linear-gradient(90deg, transparent, {MU_RED});
        border-radius: 4px;
        float: right;
        transition: width 0.5s ease;
    }}
    .stat-row .bar-fill-away {{
        height: 100%;
        background: linear-gradient(90deg, #42A5F5, transparent);
        border-radius: 4px;
        float: left;
        transition: width 0.5s ease;
    }}

    /* ── Content Card ───────────────────────────────────────────────── */
    .content-card {{
        background: #1A1A2E;
        border: 1px solid #2A2A3E;
        border-radius: 10px;
        padding: 1.2rem;
        margin-bottom: 1rem;
    }}
    .content-card .card-title {{
        color: #E0E0E0;
        font-size: 1rem;
        font-weight: 600;
        border-bottom: 2px solid {MU_RED};
        padding-bottom: 0.4rem;
        margin-bottom: 1rem;
    }}

    /* ── Key Events Timeline ────────────────────────────────────────── */
    .event-timeline {{
        position: relative;
        padding: 0.5rem 0 0.5rem 40px;
    }}
    .event-timeline::before {{
        content: '';
        position: absolute;
        left: 30px;
        top: 0;
        bottom: 0;
        width: 2px;
        background: #2A2A3E;
    }}
    .event-item {{
        display: flex;
        align-items: center;
        padding: 0.35rem 0;
        position: relative;
    }}
    .event-item .event-minute {{
        position: absolute;
        left: -38px;
        width: 30px;
        text-align: right;
        font-size: 0.78rem;
        font-weight: 700;
        color: #777;
    }}
    .event-item .event-dot {{
        width: 10px;
        height: 10px;
        border-radius: 50%;
        flex-shrink: 0;
        margin-right: 10px;
        position: relative;
        left: -9px;
        z-index: 1;
    }}
    .event-item .event-icon {{
        font-size: 0.9rem;
        margin-right: 6px;
    }}
    .event-item .event-detail {{
        font-size: 0.82rem;
        color: #CCC;
    }}
    .event-item .event-detail .player-name {{
        font-weight: 600;
        color: #E0E0E0;
    }}
</style>
"""


def apply_theme():
    """Inject global CSS into the Streamlit app."""
    import streamlit as st
    st.markdown(GLOBAL_CSS, unsafe_allow_html=True)
