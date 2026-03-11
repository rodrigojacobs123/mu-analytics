"""Global sidebar: MU crest, title, season picker, competition picker."""

import streamlit as st
from config import (
    MU_CREST_URL, MU_RED, MU_GOLD, DEFAULT_LEAGUE, DEFAULT_SEASON,
    COMPETITIONS,
)
from data.paths import list_seasons


def render_sidebar():
    """Render the global sidebar with branding and selectors.

    Returns (league, season) tuple.
    """
    with st.sidebar:
        # MU Crest and title
        st.markdown(
            f"""
            <div style="text-align:center;padding:0.5rem 0 1rem 0;">
                <img src="{MU_CREST_URL}" width="80" style="margin-bottom:0.5rem;"/>
                <h2 style="color:{MU_RED};margin:0;font-size:1.2rem;">Manchester United</h2>
                <p style="color:#999;font-size:0.75rem;margin:0;">Sports Analytics Platform · TFM</p>
            </div>
            <hr style="border-color:{MU_RED}30;margin:0.5rem 0;">
            """,
            unsafe_allow_html=True,
        )

        # Competition selector (first — so season list adapts)
        comp_names = list(COMPETITIONS.values())
        comp_keys = list(COMPETITIONS.keys())
        comp_idx = comp_keys.index(DEFAULT_LEAGUE) if DEFAULT_LEAGUE in comp_keys else 0
        comp_label = st.selectbox(
            "Competition",
            options=comp_names,
            index=comp_idx,
            key="global_competition",
        )
        league = comp_keys[comp_names.index(comp_label)]

        # Season selector — dynamically list seasons available on disk
        available_seasons = list_seasons(league)
        if not available_seasons:
            available_seasons = [DEFAULT_SEASON]

        default_idx = (
            available_seasons.index(DEFAULT_SEASON)
            if DEFAULT_SEASON in available_seasons
            else 0
        )
        season = st.selectbox(
            "Season",
            options=available_seasons,
            index=default_idx,
            key="global_season",
        )

        st.markdown(
            f'<hr style="border-color:{MU_RED}30;margin:0.5rem 0;">',
            unsafe_allow_html=True,
        )

    return league, season
