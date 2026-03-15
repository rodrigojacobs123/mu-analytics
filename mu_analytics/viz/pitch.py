"""mplsoccer pitch visualizations — shot maps, pass networks, heatmaps."""

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from mplsoccer import Pitch, VerticalPitch
import streamlit as st

from config import MU_RED, MU_GOLD, MU_DARK_BG, EVENT_PASS, EVENT_GOAL
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
    """Plot a pass network — clean Forza-Football style with connection lines."""
    if nodes.empty:
        st.info("No pass network data.")
        return

    nodes = nodes.copy()
    edges = edges.copy()
    nodes["player_id"] = nodes["player_id"].astype(str)
    if not edges.empty:
        edges["from_id"] = edges["from_id"].astype(str)
        edges["to_id"] = edges["to_id"].astype(str)

    # Map Opta coords to canvas space
    # Opta: x=0 own goal → 100 opp goal, y=0 right touchline → 100 left
    # Canvas: x-axis = horizontal width, y-axis = vertical (bottom=own goal)
    canvas_x = (100 - nodes["avg_y"].values) / 100 * 10 + 0.5   # y→horizontal, flip
    canvas_y = nodes["avg_x"].values / 100 * 13.5 + 0.5          # x→vertical
    pos = dict(zip(nodes["player_id"], zip(canvas_x, canvas_y)))

    fig, ax = plt.subplots(figsize=(6, 9))
    fig.set_facecolor(MU_DARK_BG)
    ax.set_facecolor(MU_DARK_BG)
    ax.set_xlim(-0.5, 11.5)
    ax.set_ylim(-0.8, 15)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title(title, color="white", fontsize=12, fontweight="bold", pad=10)

    # Draw connection lines — width proportional to pass count
    if not edges.empty:
        max_passes = edges["pass_count"].max()
        top_threshold = edges["pass_count"].quantile(0.75) if len(edges) > 3 else 0

        for _, edge in edges.iterrows():
            fid, tid = edge["from_id"], edge["to_id"]
            if fid not in pos or tid not in pos:
                continue
            fx, fy = pos[fid]
            tx, ty = pos[tid]
            ratio = edge["pass_count"] / max_passes
            lw = ratio * 5 + 0.5
            alpha = min(ratio * 0.6 + 0.15, 0.85)
            ax.plot([fx, tx], [fy, ty], color=MU_GOLD, linewidth=lw,
                    alpha=alpha, solid_capstyle="round", zorder=2)

            # Pass count badge on strongest connections
            if edge["pass_count"] >= top_threshold and edge["pass_count"] > 1:
                mx, my = (fx + tx) / 2, (fy + ty) / 2
                ax.text(mx, my, str(int(edge["pass_count"])),
                        ha="center", va="center", fontsize=6,
                        fontweight="bold", color="white",
                        bbox=dict(facecolor="#000", alpha=0.65,
                                  edgecolor=MU_GOLD, linewidth=0.6,
                                  pad=1.2, boxstyle="round,pad=0.15"),
                        zorder=6)

    # Draw player nodes — circles with shirt numbers + last name
    circle_r = 0.36
    has_shirt = "shirt_number" in nodes.columns
    for _, node in nodes.iterrows():
        pid = node["player_id"]
        if pid not in pos:
            continue
        x, y = pos[pid]
        shirt = str(node["shirt_number"]) if has_shirt and node.get("shirt_number") else ""
        name = node.get("player_name", "")
        last = name.split()[-1] if " " in name else (name or shirt)

        # Glow ring
        glow = plt.Circle((x, y), circle_r + 0.05, fc="none",
                           ec=node_color, linewidth=1.2, alpha=0.35, zorder=3)
        ax.add_patch(glow)
        # Filled circle
        circle = plt.Circle((x, y), circle_r, fc=node_color,
                             ec="white", linewidth=1.8, zorder=4)
        ax.add_patch(circle)
        # Shirt number
        ax.text(x, y, shirt, ha="center", va="center",
                fontsize=10, fontweight="bold", color="white", zorder=5)
        # Last name below
        ax.text(x, y - circle_r - 0.12, last,
                ha="center", va="top", fontsize=6.5, color="white",
                fontweight="bold", zorder=5)

    st.pyplot(fig, use_container_width=True)
    plt.close(fig)


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
    """Plot starting formation — clean Forza-Football style on plain canvas."""
    if not formation:
        st.info("No formation data available.")
        return

    starters = formation.get("starters", [])
    if not starters:
        st.info("No formation data available.")
        return

    # Parse formation string: "4-2-3-1" → [4, 2, 3, 1]
    form_str = formation.get("formation_str", "")
    try:
        row_sizes = [int(x) for x in form_str.split("-")]
    except (ValueError, AttributeError):
        row_sizes = []

    # Separate GK from field players
    gk_players = [s for s in starters if s["position_row"] == 1]
    field_players = [s for s in starters if s["position_row"] >= 2]
    field_players.sort(key=lambda p: p["position_row"])

    # Build display rows: GK + sub-rows from formation string
    display_rows = []
    if gk_players:
        display_rows.append(gk_players)

    if row_sizes and sum(row_sizes) == len(field_players):
        idx = 0
        for size in row_sizes:
            display_rows.append(field_players[idx:idx + size])
            idx += size
    else:
        for row_val in sorted(set(p["position_row"] for p in field_players)):
            display_rows.append([p for p in field_players if p["position_row"] == row_val])

    n_rows = len(display_rows)

    # Clean canvas — no pitch markings
    fig, ax = plt.subplots(figsize=(5, 10))
    fig.set_facecolor(MU_DARK_BG)
    ax.set_facecolor(MU_DARK_BG)
    ax.set_xlim(-0.5, 10.5)
    ax.set_ylim(-1.0, n_rows * 1.6 + 0.3)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title(f"{title} ({form_str})",
                 color="white", fontsize=12, fontweight="bold", pad=10)

    # Draw rows bottom-to-top (GK at y=0, FWD at top)
    row_spacing = 1.6
    circle_r = 0.38
    for row_idx, players in enumerate(display_rows):
        y = row_idx * row_spacing
        n = len(players)
        # Center players horizontally: spread across x=1..9
        if n == 1:
            x_positions = [5.0]
        else:
            margin = max(1.5, 5.0 - n * 0.8)
            x_positions = np.linspace(margin, 10 - margin, n)

        for i, p in enumerate(players):
            x = x_positions[i]
            shirt = p.get("shirt", "")
            name = player_names.get(p["player_id"], "")
            # Get last name only: "Bruno Fernandes" → "Fernandes"
            if " " in name:
                last = name.split()[-1]
            else:
                last = name or shirt

            # Filled circle
            circle = plt.Circle((x, y), circle_r, fc=primary_color,
                                ec="white", linewidth=2, zorder=5)
            ax.add_patch(circle)
            # Outer glow ring
            glow = plt.Circle((x, y), circle_r + 0.06, fc="none",
                              ec=primary_color, linewidth=1.5, alpha=0.4, zorder=4)
            ax.add_patch(glow)

            # Shirt number inside circle
            ax.text(x, y, shirt, ha="center", va="center",
                    fontsize=13, fontweight="bold", color="white", zorder=6)
            # Last name below
            ax.text(x, y - circle_r - 0.15, last,
                    ha="center", va="top", fontsize=9, color="white",
                    fontweight="bold", zorder=6)

    st.pyplot(fig, use_container_width=True)
    plt.close(fig)


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
    color_by: str | None = None,
    color_map: dict[str, str] | None = None,
    goal_col: str | None = None,
) -> None:
    """Plot set-piece locations on a full pitch.

    Parameters
    ----------
    df : DataFrame with x, y columns (Opta 0-100 coordinate system).
    highlight_col : optional bool column to split markers into two groups
                    (e.g. ``had_shot`` for corners, ``dangerous`` for FK zones).
    color_by : optional categorical column to color-code points (e.g.
               ``delivery_label`` for corner delivery type).
    color_map : dict mapping category values to hex colours.
    goal_col : optional bool column; True rows get a star marker (★).
    """
    if df.empty:
        st.info("No set-piece data to display.")
        return

    pitch = Pitch(**PITCH_KWARGS)
    fig, ax = _draw_pitch(pitch, figsize=(12, 8))
    ax.set_title(title, color="white", fontsize=14, pad=10)

    # ── Mode 1: color by categorical column (delivery type) ──────────
    if color_by and color_by in df.columns:
        cmap = color_map or {}
        categories = sorted(df[color_by].unique())
        for cat in categories:
            cat_df = df[df[color_by] == cat]
            c = cmap.get(cat, "#999")

            if goal_col and goal_col in cat_df.columns:
                no_goal = cat_df[cat_df[goal_col] != True]   # noqa: E712
                goals = cat_df[cat_df[goal_col] == True]     # noqa: E712
            else:
                no_goal = cat_df
                goals = pd.DataFrame()

            if not no_goal.empty:
                pitch.scatter(no_goal["x"], no_goal["y"], s=100, c=c,
                              edgecolors="white", linewidth=0.6, alpha=0.8,
                              label=cat, ax=ax, zorder=4)
            if not goals.empty:
                pitch.scatter(goals["x"], goals["y"], s=260, c=c,
                              edgecolors="white", linewidth=0.8, alpha=0.95,
                              marker="*", ax=ax, zorder=6)

        # Add a single "Goal" legend entry with a star marker
        if goal_col and goal_col in df.columns and df[goal_col].any():
            ax.scatter([], [], s=180, c="white", marker="*",
                       edgecolors="white", label="Goal ★")

    # ── Mode 2: binary highlight (original behaviour) ────────────────
    elif highlight_col and highlight_col in df.columns:
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

    # ── Mode 3: plain single colour ──────────────────────────────────
    else:
        pitch.scatter(df["x"], df["y"], s=100, c=color,
                      edgecolors="white", linewidth=0.5, alpha=0.7,
                      ax=ax, zorder=4)

    ax.legend(loc="lower left", fontsize=9, facecolor=MU_DARK_BG,
              edgecolor="#444", labelcolor="white")
    _show_fig(fig)


def plot_corner_shot_panels(
    corners_df: pd.DataFrame,
    shots_df: pd.DataFrame,
    team_name: str,
    team_color: str = MU_RED,
    n_matches: int | None = None,
) -> None:
    """Two-panel half-pitch showing shot locations after corners by side.

    Left panel = shots from Left Corners, Right panel = shots from Right Corners.
    Goals rendered as green stars, non-goals as circles sized by xG.
    """
    if corners_df.empty:
        st.info("No corner data to display.")
        return

    sides = ["Left Corner", "Right Corner"]
    fig, axes = plt.subplots(1, 2, figsize=(12, 7))
    fig.set_facecolor(MU_DARK_BG)
    fig.suptitle(f"{team_name} — Corner Analysis", color="white",
                 fontsize=14, fontweight="bold", y=0.97)

    for idx, side in enumerate(sides):
        ax = axes[idx]
        pitch = VerticalPitch(**HALF_PITCH_KWARGS)
        pitch.draw(ax=ax)
        ax.set_facecolor(MU_DARK_BG)

        side_corners = corners_df[corners_df["corner_side"] == side]
        n_corners = len(side_corners)

        side_shots = shots_df[shots_df["corner_side"] == side] if not shots_df.empty else pd.DataFrame()
        n_shots = len(side_shots)

        goals = side_shots[side_shots["outcome"] == "Goal"] if not side_shots.empty else pd.DataFrame()
        non_goals = side_shots[side_shots["outcome"] != "Goal"] if not side_shots.empty else pd.DataFrame()
        n_goals = len(goals)
        total_xg = float(side_shots["xg"].sum()) if not side_shots.empty else 0.0

        # Delivery destinations (first touch after each corner)
        if "delivery_x" in side_corners.columns:
            deliveries = side_corners.dropna(subset=["delivery_x", "delivery_y"])
        else:
            deliveries = pd.DataFrame()
        n_deliveries = len(deliveries)

        # Panel title
        ax.set_title(f"{side} ({n_corners})", color="white", fontsize=12, pad=6)

        if n_corners == 0:
            ax.text(50, 82, "No corners\nfrom this side",
                    ha="center", va="center", color="#666", fontsize=11,
                    transform=ax.transData)
        else:
            # KDE heatmap on delivery destinations (more data points)
            if n_deliveries >= 5:
                pitch.kdeplot(deliveries["delivery_x"],
                              deliveries["delivery_y"], ax=ax,
                              cmap=MU_CMAP, fill=True, levels=40,
                              thresh=0.05, alpha=0.3, zorder=2)

            # Delivery destination markers — small circles, low alpha
            if n_deliveries > 0:
                pitch.scatter(deliveries["delivery_x"],
                              deliveries["delivery_y"],
                              s=40, c=team_color, edgecolors="white",
                              linewidth=0.4, alpha=0.45, ax=ax, zorder=3)

            # Non-goal shots — bigger circles sized by xG
            if not non_goals.empty:
                sizes = non_goals["xg"].fillna(0).clip(0) * 300 + 50
                pitch.scatter(non_goals["x"], non_goals["y"],
                              s=sizes, c=team_color, edgecolors="white",
                              linewidth=0.6, alpha=0.75, ax=ax, zorder=4)

            # Goal shots — green stars
            if not goals.empty:
                pitch.scatter(goals["x"], goals["y"],
                              s=350, c="#4CAF50", edgecolors="white",
                              linewidth=0.8, alpha=0.95, marker="*",
                              ax=ax, zorder=6)

            # Fallback text only if NO deliveries AND no shots
            if n_deliveries == 0 and n_shots == 0:
                ax.text(50, 82, f"{n_corners} corners\nno delivery data",
                        ha="center", va="center", color="#888", fontsize=10,
                        transform=ax.transData)

        # Stats annotation at bottom of panel
        stats_lines = [f"{n_corners} corners · {n_shots} shots · {n_goals} goals"]
        stats_lines.append(f"xG: {total_xg:.2f}")
        if n_matches and n_matches > 0 and n_corners > 0:
            rate = round(n_shots / n_matches, 1)
            stats_lines[0] += f" · {rate} shots/G"

        ax.annotate(
            "\n".join(stats_lines),
            xy=(0.5, -0.02), xycoords="axes fraction",
            ha="center", va="top", fontsize=9, color="#ccc",
            bbox=dict(facecolor="#1A1A2E", alpha=0.9, edgecolor="#444",
                      pad=4, boxstyle="round,pad=0.4"),
        )

    # Shared legend
    legend_elements = [
        plt.Line2D([0], [0], marker="o", color="w", markerfacecolor=team_color,
                   markersize=5, alpha=0.5, linestyle="None", label="Delivery"),
        plt.Line2D([0], [0], marker="o", color="w", markerfacecolor=team_color,
                   markersize=8, linestyle="None", label="Shot"),
        plt.Line2D([0], [0], marker="*", color="w", markerfacecolor="#4CAF50",
                   markersize=12, linestyle="None", label="Goal"),
    ]
    fig.legend(handles=legend_elements, loc="lower center", ncol=3,
               fontsize=9, facecolor=MU_DARK_BG, edgecolor="#444",
               labelcolor="white", framealpha=0.9)

    fig.tight_layout(rect=[0, 0.06, 1, 0.95])
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


CORNER_SIDE_COLORS = {
    "Left Corner":  "#2196F3",   # blue
    "Right Corner": "#FF9800",   # orange
}


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


# ── Origin badge colors ─────────────────────────────────────────────────
_ORIGIN_COLORS = {
    "OPEN_PLAY":  "#4CAF50",
    "CORNER":     "#FF9800",
    "FREE_KICK":  "#9C27B0",
    "THROW_IN":   "#00BCD4",
    "PENALTY":    "#F44336",
    "OWN_GOAL":   "#888888",
}
_ORIGIN_LABELS = {
    "OPEN_PLAY":  "Open Play",
    "CORNER":     "Corner",
    "FREE_KICK":  "Free Kick",
    "THROW_IN":   "Throw-In",
    "PENALTY":    "Penalty",
    "OWN_GOAL":   "Own Goal",
}


def plot_goal_buildup(buildup: dict, team_color: str = MU_RED) -> None:
    """Plot a single goal build-up sequence on a full pitch.

    ``buildup`` is one dict from ``extract_goal_buildups()`` containing
    scorer, origin, sequence (list of event rows with x/y/end_x/end_y).
    """
    seq = buildup.get("sequence", [])
    if not seq:
        return

    pitch = Pitch(**PITCH_KWARGS)
    fig, ax = _draw_pitch(pitch, figsize=(12, 8))

    origin = buildup["origin"]
    scorer = buildup["scorer"]
    minute = buildup["goal_minute"]
    n_passes = buildup["n_passes"]

    # Title
    ax.set_title(
        f"{scorer}  {minute}'",
        color="white", fontsize=13, fontweight="bold", pad=12,
    )

    # Draw pass arrows in sequence
    for i, ev in enumerate(seq):
        ex, ey = ev["x"], ev["y"]
        is_goal = ev["typeId"] == EVENT_GOAL
        is_pass = ev["typeId"] == EVENT_PASS

        if is_pass and ev.get("end_x") is not None:
            alpha = 0.5 + 0.4 * (i / max(len(seq) - 1, 1))
            pitch.arrows(
                ex, ey, ev["end_x"], ev["end_y"],
                color=team_color, alpha=alpha, width=2,
                headwidth=6, headlength=4, ax=ax, zorder=3,
            )
            # Player name at pass origin
            name = ev.get("player_name", "")
            short = name.split()[-1] if " " in name else name
            ax.annotate(
                short, xy=(ex, ey), fontsize=7, color="white",
                ha="center", va="bottom",
                xytext=(0, 6), textcoords="offset points",
                zorder=5,
            )

        # Goal marker — large star
        if is_goal:
            pitch.scatter(
                ex, ey, s=600, marker="*",
                c=MU_GOLD, edgecolors="white", linewidth=1,
                ax=ax, zorder=6,
            )
            ax.annotate(
                "GOAL", xy=(ex, ey), fontsize=8, fontweight="bold",
                color=MU_GOLD, ha="center", va="bottom",
                xytext=(0, 12), textcoords="offset points",
                zorder=7,
            )

    # Non-pass, non-goal events — small dots showing touch positions
    for ev in seq:
        if ev["typeId"] not in (EVENT_PASS, EVENT_GOAL):
            pitch.scatter(
                ev["x"], ev["y"], s=40, c="white", alpha=0.5,
                edgecolors="none", ax=ax, zorder=2,
            )

    # Origin badge (top-right of pitch)
    badge_color = _ORIGIN_COLORS.get(origin, "#666")
    badge_label = _ORIGIN_LABELS.get(origin, origin)
    ax.annotate(
        f"  {badge_label}  ",
        xy=(98, 2), ha="right", va="top",
        fontsize=9, fontweight="bold", color="white",
        bbox=dict(facecolor=badge_color, alpha=0.85, edgecolor="white",
                  linewidth=1, pad=3, boxstyle="round,pad=0.3"),
        zorder=8,
    )

    # Pass count + duration info (bottom-left)
    dur = buildup.get("duration_secs", 0)
    info = f"{n_passes} passes"
    if dur > 0:
        info += f"  ·  {dur}s"
    ax.annotate(
        info, xy=(2, 98), ha="left", va="bottom",
        fontsize=8, color="#aaa", zorder=8,
    )

    _show_fig(fig)
