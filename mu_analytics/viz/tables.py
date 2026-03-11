"""Styled DataFrame renderers for league tables and data displays."""

import pandas as pd
import streamlit as st
from config import MU_RED, MU_TEAM_NAME, MU_DARK_BG


def styled_league_table(df: pd.DataFrame, highlight_team: str = MU_TEAM_NAME) -> None:
    """Render a league table with the specified team highlighted."""
    if df.empty:
        st.warning("No standings data available.")
        return

    display_cols = ["rank", "team_name", "played", "won", "drawn", "lost",
                    "gf", "ga", "gd", "points"]
    available_cols = [c for c in display_cols if c in df.columns]
    display_df = df[available_cols].copy()

    col_names = {
        "rank": "Pos", "team_name": "Team", "played": "P", "won": "W",
        "drawn": "D", "lost": "L", "gf": "GF", "ga": "GA",
        "gd": "GD", "points": "Pts",
    }
    display_df = display_df.rename(columns=col_names)

    def highlight_row(row):
        if row.get("Team", "") == highlight_team:
            return [f"background-color: {MU_RED}33; font-weight: bold"] * len(row)
        return [""] * len(row)

    styled = display_df.style.apply(highlight_row, axis=1)
    styled = styled.set_properties(**{
        "text-align": "center",
    })
    styled = styled.set_properties(subset=["Team"] if "Team" in display_df.columns else [], **{
        "text-align": "left",
    })

    st.dataframe(styled, width="stretch", hide_index=True, height=740)


def styled_dataframe(df: pd.DataFrame, height: int = 400, **kwargs) -> None:
    """Render a generic styled DataFrame."""
    if df.empty:
        st.info("No data available.")
        return
    st.dataframe(df, width="stretch", hide_index=True, height=height, **kwargs)


def player_stats_table(df: pd.DataFrame, stat_columns: list[str] | None = None,
                       sort_by: str | None = None) -> None:
    """Render a player statistics table with key columns."""
    if df.empty:
        st.info("No player data available.")
        return

    if stat_columns is None:
        stat_columns = ["nombre", "posicion", "Games Played", "Goals", "Goal Assists",
                        "Total Passes", "Tackles Won", "Interceptions"]
    available = [c for c in stat_columns if c in df.columns]
    display = df[available].copy()

    if sort_by and sort_by in display.columns:
        display = display.sort_values(sort_by, ascending=False)

    st.dataframe(display, width="stretch", hide_index=True, height=500)
