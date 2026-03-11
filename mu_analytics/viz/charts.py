"""Plotly chart builders — bar, line, scatter, histogram, heatmap, xG race."""

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from config import MU_RED, MU_GOLD, MU_WHITE, MU_DARK_BG, MU_GRID


def line_chart(df: pd.DataFrame, x: str, y: str, title: str = "",
               color: str = MU_RED, y_label: str = "", markers: bool = False) -> go.Figure:
    """Simple line chart with MU theme."""
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df[x], y=df[y],
        mode="lines+markers" if markers else "lines",
        line=dict(color=color, width=2.5),
        marker=dict(size=6) if markers else None,
        name=y_label or y,
    ))
    fig.update_layout(title=title, xaxis_title=x, yaxis_title=y_label or y)
    return fig


def multi_line_chart(df: pd.DataFrame, x: str, y_cols: list[str],
                     colors: list[str] | None = None, title: str = "",
                     y_label: str = "") -> go.Figure:
    """Multiple line series on the same chart."""
    if colors is None:
        colors = [MU_RED, MU_GOLD, MU_WHITE, "#888888", "#4CAF50", "#2196F3"]
    fig = go.Figure()
    for i, col in enumerate(y_cols):
        fig.add_trace(go.Scatter(
            x=df[x], y=df[col],
            mode="lines",
            line=dict(color=colors[i % len(colors)], width=2.5),
            name=col,
        ))
    fig.update_layout(title=title, yaxis_title=y_label)
    return fig


def bar_chart(df: pd.DataFrame, x: str, y: str, title: str = "",
              color: str = MU_RED, horizontal: bool = False) -> go.Figure:
    """Single-series bar chart."""
    if horizontal:
        fig = go.Figure(go.Bar(x=df[y], y=df[x], orientation="h",
                               marker_color=color))
        fig.update_layout(title=title, xaxis_title=y, yaxis_title=x)
    else:
        fig = go.Figure(go.Bar(x=df[x], y=df[y], marker_color=color))
        fig.update_layout(title=title, xaxis_title=x, yaxis_title=y)
    return fig


def grouped_bar_chart(df: pd.DataFrame, x: str, y_cols: list[str],
                      colors: list[str] | None = None, title: str = "",
                      bar_names: list[str] | None = None) -> go.Figure:
    """Grouped bar chart with multiple series."""
    if colors is None:
        colors = [MU_RED, MU_GOLD, MU_WHITE, "#888"]
    if bar_names is None:
        bar_names = y_cols
    fig = go.Figure()
    for i, col in enumerate(y_cols):
        fig.add_trace(go.Bar(
            x=df[x], y=df[col],
            name=bar_names[i],
            marker_color=colors[i % len(colors)],
        ))
    fig.update_layout(title=title, barmode="group")
    return fig


def scatter_chart(df: pd.DataFrame, x: str, y: str, title: str = "",
                  size: str | None = None, color: str | None = None,
                  text: str | None = None, add_diagonal: bool = False) -> go.Figure:
    """Scatter plot with optional size, color, and text."""
    fig = px.scatter(
        df, x=x, y=y, size=size, color=color, text=text,
        title=title, template="mu_dark",
    )
    if add_diagonal:
        min_val = min(df[x].min(), df[y].min())
        max_val = max(df[x].max(), df[y].max())
        fig.add_trace(go.Scatter(
            x=[min_val, max_val], y=[min_val, max_val],
            mode="lines", line=dict(color="#666", dash="dash", width=1),
            showlegend=False,
        ))
    return fig


def histogram(values: pd.Series | np.ndarray, title: str = "",
              x_label: str = "", color: str = MU_RED, nbins: int = 30) -> go.Figure:
    """Histogram chart."""
    fig = go.Figure(go.Histogram(x=values, nbinsx=nbins, marker_color=color))
    fig.update_layout(title=title, xaxis_title=x_label, yaxis_title="Frequency")
    return fig


def donut_chart(labels: list[str], values: list[float], title: str = "",
                colors: list[str] | None = None) -> go.Figure:
    """Donut / pie chart."""
    if colors is None:
        colors = [MU_RED, MU_GOLD, "#888888", "#4CAF50", "#2196F3"]
    fig = go.Figure(go.Pie(
        labels=labels, values=values,
        hole=0.5,
        marker_colors=colors[:len(labels)],
        textinfo="label+percent",
        textfont=dict(size=12),
    ))
    fig.update_layout(title=title, showlegend=True)
    return fig


def heatmap_grid(matrix: np.ndarray, x_labels: list[str], y_labels: list[str],
                 title: str = "", x_title: str = "", y_title: str = "",
                 annotate: bool = True, fmt: str = ".1%") -> go.Figure:
    """Heatmap grid (e.g., for Poisson scoreline probabilities)."""
    text_matrix = None
    if annotate:
        text_matrix = [[f"{v:{fmt}}" if v >= 0.005 else "" for v in row] for row in matrix]

    fig = go.Figure(go.Heatmap(
        z=matrix,
        x=x_labels,
        y=y_labels,
        colorscale=[[0, MU_DARK_BG], [0.3, "#3D0A0A"], [0.6, MU_RED], [1.0, MU_GOLD]],
        text=text_matrix,
        texttemplate="%{text}",
        textfont=dict(size=11),
        showscale=False,
    ))
    fig.update_layout(
        title=title,
        xaxis_title=x_title,
        yaxis_title=y_title,
        xaxis=dict(dtick=1),
        yaxis=dict(dtick=1, autorange="reversed"),
    )
    return fig


def xg_race_chart(xg_timeline: pd.DataFrame, home_team: str, away_team: str,
                  goals: pd.DataFrame | None = None) -> go.Figure:
    """Stepped xG race chart with goal annotations."""
    fig = go.Figure()

    # Home team xG line
    fig.add_trace(go.Scatter(
        x=xg_timeline["minute"], y=xg_timeline["home_xg"],
        mode="lines", line=dict(color=MU_RED, width=2.5, shape="hv"),
        name=f"{home_team} xG", fill="tozeroy",
        fillcolor="rgba(218,41,28,0.08)",
    ))

    # Away team xG line
    fig.add_trace(go.Scatter(
        x=xg_timeline["minute"], y=xg_timeline["away_xg"],
        mode="lines", line=dict(color="#42A5F5", width=2.5, shape="hv"),
        name=f"{away_team} xG", fill="tozeroy",
        fillcolor="rgba(66,165,245,0.08)",
    ))

    # Half-time marker
    fig.add_vline(x=45, line_dash="dash", line_color="#555555",
                  line_width=1, opacity=0.7)
    fig.add_annotation(
        x=45, y=1.0, yref="paper", yanchor="top",
        text="HT", showarrow=False,
        font=dict(size=10, color="#888"),
    )

    # Goal markers
    if goals is not None and not goals.empty:
        for _, g in goals.iterrows():
            is_home = g.get("team_id") == xg_timeline.attrs.get("home_id", "")
            team_color = MU_RED if is_home else "#42A5F5"
            fig.add_vline(
                x=g["minute"], line_dash="dot",
                line_color=team_color, opacity=0.5,
            )
            y_val = xg_timeline.loc[
                xg_timeline["minute"] <= g["minute"],
                "home_xg" if is_home else "away_xg"
            ].iloc[-1] if len(xg_timeline) > 0 else 0
            fig.add_annotation(
                x=g["minute"], y=y_val,
                text=f"⚽ {g.get('player_name', '')}",
                showarrow=True, arrowhead=2, arrowcolor=team_color,
                font=dict(size=10, color="#FAFAFA"),
                bgcolor="rgba(30,30,30,0.85)", bordercolor=team_color,
            )

    fig.update_layout(
        title="xG Race",
        xaxis_title="Minute",
        yaxis_title="Cumulative xG",
        xaxis=dict(range=[0, 95]),
        hovermode="x unified",
    )
    return fig


def probability_bars(home_prob: float, draw_prob: float, away_prob: float,
                     home_team: str, away_team: str) -> go.Figure:
    """Horizontal stacked bar showing win/draw/loss probabilities."""
    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=["Outcome"], x=[home_prob * 100], orientation="h",
        marker_color=MU_RED, name=f"{home_team} Win",
        text=f"{home_prob:.0%}", textposition="inside",
    ))
    fig.add_trace(go.Bar(
        y=["Outcome"], x=[draw_prob * 100], orientation="h",
        marker_color="#888", name="Draw",
        text=f"{draw_prob:.0%}", textposition="inside",
    ))
    fig.add_trace(go.Bar(
        y=["Outcome"], x=[away_prob * 100], orientation="h",
        marker_color="#42A5F5", name=f"{away_team} Win",
        text=f"{away_prob:.0%}", textposition="inside",
    ))
    fig.update_layout(
        barmode="stack", showlegend=True,
        height=120, margin=dict(l=10, r=10, t=10, b=10),
        xaxis=dict(visible=False), yaxis=dict(visible=False),
    )
    return fig


def goals_by_matchday(df: pd.DataFrame, title: str = "Goals by Matchday") -> go.Figure:
    """Bar chart of goals scored vs conceded per matchday."""
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=df["matchday"], y=df["mu_score"],
        name="Scored", marker_color="#4CAF50",
    ))
    fig.add_trace(go.Bar(
        x=df["matchday"], y=df["opp_score"],
        name="Conceded", marker_color=MU_RED,
    ))
    fig.update_layout(title=title, barmode="group",
                      xaxis_title="Matchday", yaxis_title="Goals")
    return fig


def monte_carlo_histogram(simulations: np.ndarray, home_team: str, away_team: str,
                          title: str = "Monte Carlo Simulation (10,000 matches)") -> go.Figure:
    """Histogram of goal difference from Monte Carlo simulations."""
    fig = go.Figure()

    # Split into win/draw/loss
    home_wins = simulations[simulations > 0]
    draws = simulations[simulations == 0]
    away_wins = simulations[simulations < 0]

    bins_range = dict(start=simulations.min() - 0.5, end=simulations.max() + 0.5, size=1)

    fig.add_trace(go.Histogram(
        x=home_wins, name=f"{home_team} Win",
        marker_color=MU_RED, xbins=bins_range,
    ))
    fig.add_trace(go.Histogram(
        x=draws, name="Draw",
        marker_color="#888888", xbins=bins_range,
    ))
    fig.add_trace(go.Histogram(
        x=away_wins, name=f"{away_team} Win",
        marker_color="#42A5F5", xbins=bins_range,
    ))

    fig.update_layout(
        title=title,
        xaxis_title="Goal Difference (Home - Away)",
        yaxis_title="Frequency",
        barmode="stack",
    )
    return fig


def tactical_progression_chart(
    df: pd.DataFrame,
    metrics: list[str],
    rolling_cols: list[str] | None = None,
    result_col: str = "result",
    matchday_col: str = "match_num",
    title: str = "Tactical Progression",
    colors: list[str] | None = None,
    y_label: str = "",
) -> go.Figure:
    """Multi-metric line chart with rolling averages and W/D/L result markers.

    Parameters
    ----------
    df : DataFrame with matchday data
    metrics : column names to plot (raw per-match values shown as faint dots)
    rolling_cols : column names for rolling averages (shown as bold lines).
                   If None, looks for '{metric}_rolling' columns.
    result_col : column with W/D/L values for marker coloring
    matchday_col : column for x-axis
    """
    if colors is None:
        colors = [MU_RED, MU_GOLD, "#42A5F5", "#4CAF50", "#FF9800"]

    RESULT_COLORS = {"W": "#4CAF50", "D": "#FFC107", "L": "#F44336"}

    fig = go.Figure()

    for i, metric in enumerate(metrics):
        color = colors[i % len(colors)]

        # Faint dots for raw per-match values
        fig.add_trace(go.Scatter(
            x=df[matchday_col], y=df[metric],
            mode="markers",
            marker=dict(size=6, color=color, opacity=0.3),
            name=f"{metric} (per match)",
            showlegend=False,
        ))

        # Bold rolling average line
        r_col = (rolling_cols[i] if rolling_cols else f"{metric}_rolling")
        if r_col in df.columns:
            fig.add_trace(go.Scatter(
                x=df[matchday_col], y=df[r_col],
                mode="lines",
                line=dict(color=color, width=3),
                name=metric.replace("_", " ").title(),
            ))

    # W/D/L markers along bottom
    if result_col in df.columns:
        for _, row in df.iterrows():
            res = row[result_col]
            fig.add_trace(go.Scatter(
                x=[row[matchday_col]], y=[0],
                mode="markers",
                marker=dict(
                    size=10, color=RESULT_COLORS.get(res, "#888"),
                    symbol="square",
                ),
                showlegend=False,
                hoverinfo="text",
                hovertext=f"MD {row[matchday_col]}: {res} ({row.get('score', '')} vs {row.get('opponent', '')})",
            ))

    fig.update_layout(
        title=title,
        xaxis_title="Match",
        yaxis_title=y_label,
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )
    return fig


def ppda_trend_chart(
    df: pd.DataFrame,
    matchday_col: str = "match_num",
    result_col: str = "result",
    title: str = "Pressing Intensity (PPDA)",
) -> go.Figure:
    """PPDA trend chart with tactical reference bands.

    Background bands show pressing intensity zones:
      < 9  = High press (green)
      9-13 = Mid-block (amber)
      > 13 = Low block (red)
    """
    RESULT_COLORS = {"W": "#4CAF50", "D": "#FFC107", "L": "#F44336"}

    fig = go.Figure()

    # Reference bands
    fig.add_hrect(y0=0, y1=9, fillcolor="#4CAF50", opacity=0.08,
                  line_width=0, annotation_text="High Press",
                  annotation_position="top left",
                  annotation=dict(font_size=10, font_color="#4CAF50"))
    fig.add_hrect(y0=9, y1=13, fillcolor="#FFC107", opacity=0.08,
                  line_width=0, annotation_text="Mid-Block",
                  annotation_position="top left",
                  annotation=dict(font_size=10, font_color="#FFC107"))
    fig.add_hrect(y0=13, y1=40, fillcolor="#F44336", opacity=0.06,
                  line_width=0, annotation_text="Low Block",
                  annotation_position="top left",
                  annotation=dict(font_size=10, font_color="#F44336"))

    # Per-match dots
    fig.add_trace(go.Scatter(
        x=df[matchday_col], y=df["ppda"],
        mode="markers",
        marker=dict(size=7, color=MU_GOLD, opacity=0.35),
        name="Per Match",
        showlegend=False,
    ))

    # Rolling average
    r_col = "ppda_rolling"
    if r_col in df.columns:
        fig.add_trace(go.Scatter(
            x=df[matchday_col], y=df[r_col],
            mode="lines",
            line=dict(color=MU_GOLD, width=3),
            name="5-Match Avg",
        ))

    # W/D/L markers
    if result_col in df.columns:
        y_base = max(df["ppda"].max() + 2, 20)
        for _, row in df.iterrows():
            res = row.get(result_col, "")
            fig.add_trace(go.Scatter(
                x=[row[matchday_col]], y=[y_base],
                mode="markers",
                marker=dict(size=9, color=RESULT_COLORS.get(res, "#888"),
                            symbol="square"),
                showlegend=False,
                hoverinfo="text",
                hovertext=f"MD {row[matchday_col]}: {res} ({row.get('score', '')} vs {row.get('opponent', '')})",
            ))

    fig.update_layout(
        title=title,
        xaxis_title="Match",
        yaxis_title="PPDA (lower = more pressing)",
        yaxis=dict(range=[0, max(df["ppda"].max() + 5, 25)]),
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )
    return fig


def dual_axis_trend_chart(
    df: pd.DataFrame,
    matchday_col: str = "match_num",
    left_metric: str = "",
    right_metric: str = "",
    left_rolling: str = "",
    right_rolling: str = "",
    left_color: str = MU_GOLD,
    right_color: str = "#42A5F5",
    left_label: str = "",
    right_label: str = "",
    title: str = "",
    result_col: str = "result",
) -> go.Figure:
    """Dual y-axis trend chart — left axis for one metric, right for another."""
    from plotly.subplots import make_subplots

    RESULT_COLORS = {"W": "#4CAF50", "D": "#FFC107", "L": "#F44336"}

    fig = make_subplots(specs=[[{"secondary_y": True}]])

    # Left metric (dots + line)
    if left_metric in df.columns:
        fig.add_trace(go.Scatter(
            x=df[matchday_col], y=df[left_metric],
            mode="markers", marker=dict(size=6, color=left_color, opacity=0.3),
            name=left_label + " (per match)", showlegend=False,
        ), secondary_y=False)
        if left_rolling in df.columns:
            fig.add_trace(go.Scatter(
                x=df[matchday_col], y=df[left_rolling],
                mode="lines", line=dict(color=left_color, width=3),
                name=left_label,
            ), secondary_y=False)

    # Right metric (dots + line)
    if right_metric in df.columns:
        fig.add_trace(go.Scatter(
            x=df[matchday_col], y=df[right_metric],
            mode="markers", marker=dict(size=6, color=right_color, opacity=0.3),
            name=right_label + " (per match)", showlegend=False,
        ), secondary_y=True)
        if right_rolling in df.columns:
            fig.add_trace(go.Scatter(
                x=df[matchday_col], y=df[right_rolling],
                mode="lines", line=dict(color=right_color, width=3),
                name=right_label,
            ), secondary_y=True)

    # W/D/L markers
    if result_col in df.columns:
        for _, row in df.iterrows():
            res = row.get(result_col, "")
            fig.add_trace(go.Scatter(
                x=[row[matchday_col]], y=[0],
                mode="markers",
                marker=dict(size=9, color=RESULT_COLORS.get(res, "#888"),
                            symbol="square"),
                showlegend=False,
                hoverinfo="text",
                hovertext=f"MD {row[matchday_col]}: {res} ({row.get('score', '')} vs {row.get('opponent', '')})",
            ), secondary_y=False)

    fig.update_layout(
        title=title,
        xaxis_title="Match",
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )
    fig.update_yaxes(title_text=left_label, secondary_y=False,
                     title_font=dict(color=left_color),
                     tickfont=dict(color=left_color))
    fig.update_yaxes(title_text=right_label, secondary_y=True,
                     title_font=dict(color=right_color),
                     tickfont=dict(color=right_color))
    return fig


def formation_donut(formations: list[dict], title: str = "Formation Usage") -> go.Figure:
    """Donut chart of formation frequency from compute_formation_usage() output.

    formations: list of dicts with 'formation', 'count', 'pct' keys.
    """
    if not formations:
        return go.Figure()

    labels = [f["formation"] for f in formations]
    values = [f["count"] for f in formations]

    top_colors = [MU_RED, MU_GOLD, "#42A5F5", "#4CAF50", "#FF9800", "#9C27B0", "#888"]
    chart_colors = top_colors[:len(labels)]

    fig = go.Figure(go.Pie(
        labels=labels, values=values,
        hole=0.55,
        marker_colors=chart_colors,
        textinfo="label+percent",
        textfont=dict(size=12),
        hovertemplate="%{label}: %{value} matches (%{percent})<extra></extra>",
    ))
    fig.update_layout(title=title, showlegend=True)
    return fig
