"""mplsoccer pitch visualizations — shot maps, pass networks, heatmaps."""

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from mplsoccer import Pitch, VerticalPitch
import streamlit as st

from config import MU_RED, MU_GOLD, MU_DARK_BG
from viz.theme import PITCH_KWARGS, HALF_PITCH_KWARGS, MU_CMAP


def _draw_pitch(pitch, figsize=(12, 8)):
    """Draw pitch and set dark background on the figure."""
    fig, ax = pitch.draw(figsize=figsize)
    fig.set_facecolor(MU_DARK_BG)
    return fig, ax


def _show_fig(fig):
    """Display a matplotlib figure in Streamlit and close it."""
    st.pyplot(fig, width="stretch")
    plt.close(fig)


def plot_shot_map(shots: pd.DataFrame, title: str = "Shot Map",
                  half: bool = True) -> None:
    """Plot shots on a pitch. Color by outcome, size by xG."""
    if shots.empty:
        st.info("No shots to display.")
        return

    if half:
        pitch = VerticalPitch(**HALF_PITCH_KWARGS)
    else:
        pitch = Pitch(**PITCH_KWARGS)

    fig, ax = _draw_pitch(pitch, figsize=(10, 7))
    ax.set_title(title, color="white", fontsize=14, pad=10)

    outcome_colors = {
        "Goal": "#4CAF50",
        "Saved": MU_GOLD,
        "Missed": "#888888",
        "Post": "#FF9800",
        "Unknown": "#555555",
    }

    for outcome, group in shots.groupby("outcome"):
        color = outcome_colors.get(outcome, "#555555")
        sizes = group["xg"].clip(0.01, 1.0) * 400 + 30

        if half:
            pitch.scatter(group["x"], group["y"], s=sizes, c=color,
                          edgecolors="white", linewidth=0.5, alpha=0.8,
                          label=outcome, ax=ax, zorder=5)
        else:
            pitch.scatter(group["x"], group["y"], s=sizes, c=color,
                          edgecolors="white", linewidth=0.5, alpha=0.8,
                          label=outcome, ax=ax, zorder=5)

    ax.legend(loc="lower left", fontsize=9, facecolor=MU_DARK_BG,
              edgecolor="#444", labelcolor="white")
    _show_fig(fig)


def plot_pass_network(nodes: pd.DataFrame, edges: pd.DataFrame,
                      title: str = "Pass Network",
                      node_color: str = MU_RED) -> None:
    """Plot a pass network with directional arrows and pass count labels."""
    if nodes.empty:
        st.info("No pass network data.")
        return

    pitch = Pitch(**PITCH_KWARGS)
    fig, ax = _draw_pitch(pitch, figsize=(12, 8))
    ax.set_title(title, color="white", fontsize=14, pad=10)

    # Draw edges as arrows (shows pass direction)
    if not edges.empty:
        max_passes = edges["pass_count"].max()
        top_threshold = edges["pass_count"].quantile(0.75)

        # Ensure consistent types for player_id matching
        nodes = nodes.copy()
        edges = edges.copy()
        nodes["player_id"] = nodes["player_id"].astype(str)
        edges["from_id"] = edges["from_id"].astype(str)
        edges["to_id"] = edges["to_id"].astype(str)

        for _, edge in edges.iterrows():
            from_node = nodes[nodes["player_id"] == edge["from_id"]]
            to_node = nodes[nodes["player_id"] == edge["to_id"]]
            if from_node.empty or to_node.empty:
                continue

            fx, fy = from_node["avg_x"].values[0], from_node["avg_y"].values[0]
            tx, ty = to_node["avg_x"].values[0], to_node["avg_y"].values[0]
            ratio = edge["pass_count"] / max_passes
            width = ratio * 6 + 0.5
            alpha = min(ratio + 0.2, 0.9)

            # Directional arrows
            pitch.arrows(
                fx, fy, tx, ty,
                width=width, headwidth=4, headlength=3,
                color=MU_GOLD, alpha=alpha, ax=ax, zorder=3,
            )

            # Pass count label on top connections
            if edge["pass_count"] >= top_threshold:
                mx, my = (fx + tx) / 2, (fy + ty) / 2
                ax.annotate(
                    str(int(edge["pass_count"])),
                    xy=(mx, my), ha="center", va="center",
                    fontsize=7, fontweight="bold", color="#fff",
                    bbox=dict(facecolor="#000", alpha=0.6,
                              edgecolor=MU_GOLD, linewidth=0.8,
                              pad=1.5, boxstyle="round,pad=0.2"),
                    zorder=6,
                )

    # Draw nodes (players) with glow effect
    node_sizes = nodes["total_passes"].clip(1) / nodes["total_passes"].max() * 800 + 250
    # Glow layer
    pitch.scatter(nodes["avg_x"], nodes["avg_y"], s=node_sizes * 1.6,
                  c=node_color, alpha=0.15, ax=ax, zorder=4)
    # Main node
    pitch.scatter(nodes["avg_x"], nodes["avg_y"], s=node_sizes,
                  c=node_color, edgecolors="white", linewidth=1.5,
                  ax=ax, zorder=5)

    # Shirt numbers inside nodes + player name labels below
    has_shirt = "shirt_number" in nodes.columns
    for _, node in nodes.iterrows():
        if has_shirt and node.get("shirt_number"):
            ax.annotate(
                str(node["shirt_number"]),
                xy=(node["avg_x"], node["avg_y"]),
                ha="center", va="center", fontsize=9,
                fontweight="bold", color="white", zorder=7,
            )
        ax.annotate(
            node.get("player_name", "")[:12],
            xy=(node["avg_x"], node["avg_y"]),
            xytext=(0, -15), textcoords="offset points",
            ha="center", fontsize=8, color="white",
            bbox=dict(facecolor="#333333", alpha=0.7, edgecolor="none", pad=1),
            zorder=7,
        )

    _show_fig(fig)


def plot_heatmap(touches: pd.DataFrame, title: str = "Touch Heatmap") -> None:
    """Plot a KDE heatmap of all touch events."""
    if touches.empty:
        st.info("No touch data to display.")
        return

    pitch = Pitch(**PITCH_KWARGS)
    fig, ax = _draw_pitch(pitch, figsize=(12, 8))
    ax.set_title(title, color="white", fontsize=14, pad=10)

    pitch.kdeplot(touches["x"], touches["y"], ax=ax,
                  cmap=MU_CMAP, fill=True, levels=50, thresh=0.05,
                  alpha=0.7, zorder=2)

    _show_fig(fig)


def plot_formation(formation: dict, player_names: dict[str, str],
                   title: str = "Formation",
                   primary_color: str = MU_RED) -> None:
    """Plot starting formation with player positions on a full vertical pitch."""
    if not formation:
        st.info("No formation data available.")
        return

    # Use full pitch so all rows (GK → FWD) have proper spacing
    full_pitch_kwargs = dict(PITCH_KWARGS)
    pitch = VerticalPitch(**full_pitch_kwargs)
    fig, ax = _draw_pitch(pitch, figsize=(6, 10))
    ax.set_title(f"{title} ({formation['formation_str']})",
                 color="white", fontsize=13, pad=8)

    starters = formation.get("starters", [])
    if not starters:
        _show_fig(fig)
        return

    # Compute approximate positions based on row assignments
    from collections import Counter
    row_positions = {}

    # Full-pitch y positions — evenly spread across 0-100 Opta range
    row_y_map = {1: 8, 2: 30, 3: 55, 4: 78}
    row_label_map = {1: "GK", 2: "DEF", 3: "MID", 4: "FWD"}

    for s in starters:
        row = s["position_row"]
        if row not in row_positions:
            row_positions[row] = []
        row_positions[row].append(s)

    for row, players in row_positions.items():
        n = len(players)
        y = row_y_map.get(row, 50)
        # Wider lateral spread with comfortable padding
        x_positions = np.linspace(12, 88, n + 2)[1:-1] if n > 1 else [50]

        # Scale markers and fonts for crowded rows
        marker_outer = 500 if n >= 5 else 600
        marker_inner = 300 if n >= 5 else 380
        shirt_font = 8 if n >= 5 else 10
        name_font = 6 if n >= 5 else 7
        name_max = 10 if n >= 5 else 14

        for i, p in enumerate(players):
            x = x_positions[i] if i < len(x_positions) else 50
            name = player_names.get(p["player_id"], p.get("shirt", "?"))
            # Shorten long names: "Bruno Fernandes" → "B. Fernandes"
            if len(name) > 10 and " " in name:
                parts = name.split()
                name = f"{parts[0][0]}. {' '.join(parts[1:])}"

            # Outer decorative ring
            pitch.scatter(y, x, s=marker_outer, c="none", edgecolors=primary_color,
                          linewidth=2.5, ax=ax, zorder=4)
            # Inner filled circle
            pitch.scatter(y, x, s=marker_inner, c=primary_color, edgecolors="white",
                          linewidth=2, ax=ax, zorder=5)
            ax.annotate(
                p.get("shirt", ""),
                xy=(y, x), ha="center", va="center",
                fontsize=shirt_font, fontweight="bold", color="white", zorder=6,
            )
            ax.annotate(
                name[:name_max],
                xy=(y, x), xytext=(0, -14), textcoords="offset points",
                ha="center", fontsize=name_font, color="white",
                bbox=dict(facecolor="#222", alpha=0.8, edgecolor="none",
                          pad=1, boxstyle="round,pad=0.2"),
            )

        # Position group label on the right side of each row
        label = row_label_map.get(row, "")
        if label:
            ax.annotate(
                label, xy=(104, y), ha="left", va="center",
                fontsize=8, color="#aaa", fontstyle="italic", zorder=2,
                annotation_clip=False,
            )

    _show_fig(fig)


def plot_formation_shape(formation_str: str, title: str = "",
                         primary_color: str = MU_RED,
                         pct: float | None = None) -> None:
    """Draw the tactical shape of a formation on a half-pitch.

    Takes a formation string like '3-4-2-1' and places abstract position
    dots in the correct rows.  No player names needed — this is a
    season-level overview.
    """
    if not formation_str or formation_str == "?":
        st.info("No formation data.")
        return

    # Parse "3-4-2-1" → [3, 4, 2, 1]
    try:
        rows = [int(x) for x in formation_str.split("-")]
    except ValueError:
        st.info(f"Cannot parse formation: {formation_str}")
        return

    full_pitch_kwargs = dict(PITCH_KWARGS)
    pitch = VerticalPitch(**full_pitch_kwargs)
    fig, ax = _draw_pitch(pitch, figsize=(5, 8))

    label = formation_str
    if pct is not None:
        label += f"  ({pct:.0f}%)"
    ax.set_title(label if not title else title,
                 color="white", fontsize=14, fontweight="bold", pad=10)

    # Y positions for each row (GK at bottom → FWD at top)
    # GK is always 1 player at y=8
    n_field_rows = len(rows)
    y_positions = np.linspace(25, 82, n_field_rows)

    # Draw GK first
    pitch.scatter(8, 50, s=500, c=primary_color, edgecolors="white",
                  linewidth=2, ax=ax, zorder=5)
    pitch.scatter(8, 50, s=800, c="none", edgecolors=primary_color,
                  linewidth=2, alpha=0.5, ax=ax, zorder=4)
    ax.annotate("GK", xy=(8, 50), ha="center", va="center",
                fontsize=9, fontweight="bold", color="white", zorder=6)

    # Draw field rows
    row_labels = _get_row_labels(rows)
    for i, (n_players, y) in enumerate(zip(rows, y_positions)):
        x_positions = np.linspace(15, 85, n_players + 2)[1:-1] if n_players > 1 else [50]
        for x in x_positions:
            # Outer ring
            pitch.scatter(y, x, s=500, c=primary_color, edgecolors="white",
                          linewidth=2, ax=ax, zorder=5)
            pitch.scatter(y, x, s=800, c="none", edgecolors=primary_color,
                          linewidth=2, alpha=0.5, ax=ax, zorder=4)

        # Row label on the right side
        lbl = row_labels[i] if i < len(row_labels) else ""
        ax.annotate(lbl, xy=(y, 96), ha="center", va="bottom",
                    fontsize=8, color="#888", fontstyle="italic", zorder=2)

    # Connection lines between rows (subtle structure lines)
    all_y = [8] + list(y_positions)
    for j in range(len(all_y) - 1):
        ax.plot([all_y[j], all_y[j + 1]], [50, 50],
                color="#444", linewidth=0.8, alpha=0.4, zorder=1,
                linestyle="--")

    _show_fig(fig)


def _get_row_labels(rows: list[int]) -> list[str]:
    """Assign tactical labels to formation rows."""
    n = len(rows)
    if n == 3:
        return ["DEF", "MID", "FWD"]
    elif n == 4:
        return ["DEF", "DM", "AM", "FWD"]
    elif n == 5:
        return ["DEF", "DM", "MID", "AM", "FWD"]
    else:
        return ["DEF"] + ["MID"] * max(0, n - 2) + ["FWD"]


def plot_defensive_actions(tackles: pd.DataFrame, interceptions: pd.DataFrame,
                           title: str = "Defensive Actions") -> None:
    """Plot tackles and interceptions on the pitch."""
    pitch = Pitch(**PITCH_KWARGS)
    fig, ax = _draw_pitch(pitch, figsize=(12, 8))
    ax.set_title(title, color="white", fontsize=14, pad=10)

    if not tackles.empty:
        pitch.scatter(tackles["x"], tackles["y"], s=80,
                      c="#42A5F5", edgecolors="white", linewidth=0.5,
                      alpha=0.7, label="Tackles", ax=ax, zorder=4)

    if not interceptions.empty:
        pitch.scatter(interceptions["x"], interceptions["y"], s=80,
                      c=MU_GOLD, edgecolors="white", linewidth=0.5,
                      alpha=0.7, label="Interceptions", ax=ax, zorder=4)

    ax.legend(loc="lower left", fontsize=9, facecolor=MU_DARK_BG,
              edgecolor="#444", labelcolor="white")
    _show_fig(fig)


def plot_progressive_passes(passes: pd.DataFrame,
                            title: str = "Progressive Passes") -> None:
    """Plot forward passes with significant progression (end_x - x > 25)."""
    if passes.empty or "end_x" not in passes.columns:
        st.info("No progressive pass data.")
        return

    prog = passes.dropna(subset=["end_x", "end_y"]).copy()
    prog["progression"] = prog["end_x"] - prog["x"]
    prog = prog[prog["progression"] > 25]

    if prog.empty:
        st.info("No significant progressive passes found.")
        return

    pitch = Pitch(**PITCH_KWARGS)
    fig, ax = _draw_pitch(pitch, figsize=(12, 8))
    ax.set_title(title, color="white", fontsize=14, pad=10)

    completed = prog[prog["outcome"] == 1]
    incomplete = prog[prog["outcome"] == 0]

    if not completed.empty:
        pitch.arrows(completed["x"], completed["y"],
                     completed["end_x"], completed["end_y"],
                     color="#4CAF50", alpha=0.6, width=1.5,
                     headwidth=5, headlength=3, ax=ax, zorder=3,
                     label="Complete")

    if not incomplete.empty:
        pitch.arrows(incomplete["x"], incomplete["y"],
                     incomplete["end_x"], incomplete["end_y"],
                     color=MU_RED, alpha=0.4, width=1, headwidth=4,
                     headlength=3, ax=ax, zorder=3, label="Incomplete")

    ax.legend(loc="lower left", fontsize=9, facecolor=MU_DARK_BG,
              edgecolor="#444", labelcolor="white")
    _show_fig(fig)


def plot_pass_map(passes: pd.DataFrame,
                  title: str = "Pass Map") -> None:
    """Plot all passes on a full pitch — completed (green) and incomplete (red)."""
    if passes.empty or "end_x" not in passes.columns:
        st.info("No pass data to display.")
        return

    clean = passes.dropna(subset=["end_x", "end_y"]).copy()
    if clean.empty:
        st.info("No pass data to display.")
        return

    pitch = Pitch(**PITCH_KWARGS)
    fig, ax = _draw_pitch(pitch, figsize=(12, 8))
    ax.set_title(title, color="white", fontsize=14, pad=10)

    completed = clean[clean["outcome"] == 1]
    incomplete = clean[clean["outcome"] == 0]

    if not completed.empty:
        pitch.arrows(completed["x"], completed["y"],
                     completed["end_x"], completed["end_y"],
                     color="#4CAF50", alpha=0.5, width=1.5,
                     headwidth=5, headlength=3, ax=ax, zorder=3,
                     label="Complete")

    if not incomplete.empty:
        pitch.arrows(incomplete["x"], incomplete["y"],
                     incomplete["end_x"], incomplete["end_y"],
                     color=MU_RED, alpha=0.35, width=1, headwidth=4,
                     headlength=3, ax=ax, zorder=3, label="Incomplete")

    ax.legend(loc="lower left", fontsize=9, facecolor=MU_DARK_BG,
              edgecolor="#444", labelcolor="white")
    _show_fig(fig)


def plot_set_piece_map(
    df: pd.DataFrame,
    title: str = "Set Pieces",
    color: str = MU_RED,
    highlight_col: str | None = None,
    highlight_color: str = MU_GOLD,
    highlight_label: str = "Dangerous",
    default_label: str = "Normal",
) -> None:
    """Plot set-piece locations on a full pitch.

    Parameters
    ----------
    df : DataFrame with x, y columns (Opta 0-100 coordinate system).
    highlight_col : optional bool column to split markers into two groups
                    (e.g. ``had_shot`` for corners, ``dangerous`` for FK zones).
    """
    if df.empty:
        st.info("No set-piece data to display.")
        return

    pitch = Pitch(**PITCH_KWARGS)
    fig, ax = _draw_pitch(pitch, figsize=(12, 8))
    ax.set_title(title, color="white", fontsize=14, pad=10)

    if highlight_col and highlight_col in df.columns:
        hi = df[df[highlight_col] == True]   # noqa: E712
        lo = df[df[highlight_col] != True]   # noqa: E712

        if not lo.empty:
            pitch.scatter(lo["x"], lo["y"], s=80, c="#666",
                          edgecolors="white", linewidth=0.5, alpha=0.6,
                          label=default_label, ax=ax, zorder=4)
        if not hi.empty:
            pitch.scatter(hi["x"], hi["y"], s=140, c=highlight_color,
                          edgecolors="white", linewidth=0.8, alpha=0.9,
                          label=highlight_label, ax=ax, zorder=5)
    else:
        pitch.scatter(df["x"], df["y"], s=100, c=color,
                      edgecolors="white", linewidth=0.5, alpha=0.7,
                      ax=ax, zorder=4)

    ax.legend(loc="lower left", fontsize=9, facecolor=MU_DARK_BG,
              edgecolor="#444", labelcolor="white")
    _show_fig(fig)


def plot_ball_win_height(tackles: pd.DataFrame, interceptions: pd.DataFrame,
                         recoveries: pd.DataFrame,
                         title: str = "Ball Win Height",
                         color: str = MU_RED) -> None:
    """Plot KDE heatmap of ball wins with average height line.

    Ball wins = tackles + interceptions + ball recoveries.
    The cyan dashed line shows the average x-position (ball win height).
    """
    frames = [df[["x", "y"]] for df in [tackles, interceptions, recoveries]
              if not df.empty]
    if not frames:
        st.info("No ball win data to display.")
        return

    ball_wins = pd.concat(frames, ignore_index=True)
    if ball_wins.empty:
        st.info("No ball win data to display.")
        return

    pitch = Pitch(**PITCH_KWARGS)
    fig, ax = _draw_pitch(pitch, figsize=(12, 8))
    ax.set_title(title, color="white", fontsize=14, pad=10)

    # KDE heatmap
    pitch.kdeplot(ball_wins["x"], ball_wins["y"], ax=ax,
                  cmap=MU_CMAP, fill=True, levels=50, thresh=0.05,
                  alpha=0.7, zorder=2)

    # Average ball win height — vertical line at mean x position
    avg_x = ball_wins["x"].mean()
    ax.plot([avg_x, avg_x], [0, 100], color="#00E5FF", linestyle="--",
            linewidth=2, alpha=0.8, zorder=6)
    ax.annotate(
        f"Avg: {avg_x:.1f}",
        xy=(avg_x, 2), ha="center", va="bottom",
        fontsize=10, fontweight="bold", color="#00E5FF",
        bbox=dict(facecolor="#222", alpha=0.8, edgecolor="#00E5FF",
                  pad=2, boxstyle="round,pad=0.3"),
        zorder=7,
    )

    # Ball win count
    ax.annotate(
        f"n = {len(ball_wins)}",
        xy=(96, 97), ha="right", va="top",
        fontsize=9, color="#999", zorder=7,
    )

    _show_fig(fig)


ZONE_ACTION_COLORS = {
    "Shot":         MU_GOLD,
    "Tackle":       "#009688",   # teal
    "Interception": "#9C27B0",   # purple
    "Recovery":     "#2196F3",   # blue
    "Take-on":      "#FF9800",   # orange
    "Aerial":       "#00BCD4",   # cyan
    "Clearance":    "#E91E63",   # pink
    "Cross":        "#CDDC39",   # lime
    "Foul":         "#F44336",   # red
    "Prog. Pass":   "#4CAF50",   # green
}


def plot_dominant_actions_by_zone(actions: pd.DataFrame,
                                  title: str = "Dominant Actions by Zone",
                                  action_colors: dict | None = None) -> None:
    """Plot a 5×3 pitch grid colored by the dominant action type per zone.

    ``actions`` must have columns: x, y, action.
    Optionally accepts a custom ``action_colors`` dict (action → hex).
    """
    from matplotlib.patches import Rectangle, Patch

    if actions.empty or "action" not in actions.columns:
        st.info("No action data for zone analysis.")
        return

    colors = action_colors or ZONE_ACTION_COLORS

    pitch = Pitch(**PITCH_KWARGS)
    fig, ax = _draw_pitch(pitch, figsize=(12, 8))
    ax.set_title(title, color="white", fontsize=14, pad=10)

    # Zone grid: 5 columns (x) × 3 rows (y)
    x_edges = [0, 20, 40, 60, 80, 100]
    y_edges = [0, 33.33, 66.66, 100]

    for xi in range(len(x_edges) - 1):
        for yi in range(len(y_edges) - 1):
            x_min, x_max = x_edges[xi], x_edges[xi + 1]
            y_min, y_max = y_edges[yi], y_edges[yi + 1]

            zone = actions[
                (actions["x"] >= x_min) & (actions["x"] < x_max)
                & (actions["y"] >= y_min) & (actions["y"] < y_max)
            ]

            if zone.empty:
                continue

            counts = zone["action"].value_counts()
            dominant = counts.idxmax()
            dom_count = int(counts.iloc[0])
            total = int(counts.sum())
            zone_color = colors.get(dominant, "#444444")

            rect = Rectangle(
                (x_min, y_min), x_max - x_min, y_max - y_min,
                facecolor=zone_color, alpha=0.40, edgecolor="white",
                linewidth=1, zorder=2,
            )
            ax.add_patch(rect)

            cx = (x_min + x_max) / 2
            cy = (y_min + y_max) / 2
            ax.annotate(
                f"{dominant}\n({dom_count}/{total})",
                xy=(cx, cy), ha="center", va="center",
                fontsize=7, fontweight="bold", color="white",
                zorder=3,
            )

    # Build legend only for actions that actually appear
    present = set(actions["action"].unique())
    legend_elements = [
        Patch(facecolor=c, alpha=0.55, edgecolor="white", label=lbl)
        for lbl, c in colors.items() if lbl in present
    ]
    if legend_elements:
        ax.legend(handles=legend_elements, loc="lower left", fontsize=8,
                  facecolor=MU_DARK_BG, edgecolor="#444", labelcolor="white")

    _show_fig(fig)
