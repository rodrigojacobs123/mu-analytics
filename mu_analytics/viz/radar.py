"""Plotly scatterpolar radar chart builder."""

import plotly.graph_objects as go
from config import MU_RED, MU_GOLD, MU_WHITE


def _hex_to_rgba(hex_color: str, alpha: float) -> str:
    """Convert hex color to rgba string for Plotly compatibility."""
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


def radar_chart(categories: list[str], values_dict: dict[str, list[float]],
                title: str = "", max_val: float = 100,
                colors: list[str] | None = None) -> go.Figure:
    """Multi-trace radar chart.

    Args:
        categories: list of axis labels (e.g., ["PAC", "SHO", "PAS", ...])
        values_dict: {trace_name: [value_per_category]}
        title: chart title
        max_val: maximum value for the radial axis
        colors: list of colors per trace
    """
    if colors is None:
        colors = [MU_RED, MU_GOLD, "#42A5F5", "#4CAF50", MU_WHITE, "#FF9800"]

    fig = go.Figure()

    for i, (name, vals) in enumerate(values_dict.items()):
        color = colors[i % len(colors)]
        # Close the polygon
        closed_vals = list(vals) + [vals[0]]
        closed_cats = list(categories) + [categories[0]]

        fig.add_trace(go.Scatterpolar(
            r=closed_vals,
            theta=closed_cats,
            fill="toself",
            fillcolor=_hex_to_rgba(color, 0.12),
            line=dict(color=color, width=2),
            name=name,
            marker=dict(size=5),
        ))

    fig.update_layout(
        title=title,
        polar=dict(
            bgcolor="#0E1117",
            radialaxis=dict(
                visible=True, range=[0, max_val],
                gridcolor="#333333", tickfont=dict(size=10, color="#888"),
            ),
            angularaxis=dict(
                gridcolor="#333333",
                tickfont=dict(size=12, color="#CCCCCC"),
            ),
        ),
        showlegend=True,
        legend=dict(
            x=0.5, y=-0.15, xanchor="center", yanchor="top",
            orientation="h", font=dict(size=12, color="#CCCCCC"),
            bgcolor="rgba(0,0,0,0)",
        ),
        margin=dict(t=60, b=80, l=80, r=80),
    )
    return fig


def fc_radar(player_name: str, ratings: dict[str, float],
             compare_to: dict[str, dict[str, float]] | None = None) -> go.Figure:
    """FC-style hexagonal radar for player ratings (PAC/SHO/PAS/DRI/DEF/PHY).

    Args:
        player_name: primary player name
        ratings: {attribute: value} (e.g., {"PAC": 78, "SHO": 85, ...})
        compare_to: optional {player_name: {attribute: value}} for overlay
    """
    categories = ["PAC", "SHO", "PAS", "DRI", "DEF", "PHY"]
    values_dict = {player_name: [ratings.get(c, 50) for c in categories]}

    if compare_to:
        for name, vals in compare_to.items():
            values_dict[name] = [vals.get(c, 50) for c in categories]

    return radar_chart(
        categories=categories,
        values_dict=values_dict,
        title=f"Player Ratings — {player_name}",
        max_val=99,
    )


def position_radar(player_name: str, position: str, ratings: dict[str, float],
                   compare_to: dict[str, dict[str, float]] | None = None) -> go.Figure:
    """Position-specific radar with 5 axes based on the player's role.

    Args:
        player_name: primary player display name
        position: one of Goalkeeper/Defender/Midfielder/Forward
        ratings: {attr_key: value} e.g. {"GK_ShotStop": 82, "GK_Dist": 75, ...}
        compare_to: optional {name: {attr_key: value}} for overlay traces
    """
    from processing.player_ratings import POSITION_ATTR_KEYS
    from config import POSITION_CATEGORY_DISPLAY

    keys = POSITION_ATTR_KEYS.get(position, POSITION_ATTR_KEYS.get("Midfielder", []))
    categories = [POSITION_CATEGORY_DISPLAY.get(k, k) for k in keys]

    values_dict = {player_name: [ratings.get(k, 50) for k in keys]}
    if compare_to:
        for name, vals in compare_to.items():
            values_dict[name] = [vals.get(k, 50) for k in keys]

    return radar_chart(
        categories=categories,
        values_dict=values_dict,
        title=f"{position} Ratings — {player_name}",
        max_val=99,
    )


def team_radar(team_data: dict[str, list[float]], categories: list[str],
               title: str = "Team Comparison") -> go.Figure:
    """Radar chart for comparing multiple teams across metrics."""
    return radar_chart(
        categories=categories,
        values_dict=team_data,
        title=title,
        max_val=100,
    )
