"""Data Sources — Dataset info, file counts, connection status, schema docs."""

import streamlit as st
import pandas as pd
from datetime import datetime
from components.sidebar import render_sidebar
from viz.kpi_cards import section_header, kpi_row
from viz.tables import styled_dataframe
from data.loader import get_data_diagnostics
from data.paths import (
    list_seasons, list_team_folders, list_match_files, league_dir,
    jsons_dir, partidos_dir, equipos_dir,
)
from config import DATA_ROOT, DEFAULT_LEAGUE, COMPETITIONS

league, season = render_sidebar()

st.title("Data Sources")
st.caption("Dataset diagnostics and configuration panel")

# ── Connection Status ───────────────────────────────────────────────────────
section_header("Connection Status")

data_root_exists = DATA_ROOT.exists()
if data_root_exists:
    st.success(f"Data root connected: `{DATA_ROOT}`")
else:
    st.error(f"Data root NOT FOUND: `{DATA_ROOT}`")

# ── Current Season Diagnostics ──────────────────────────────────────────────
diag = get_data_diagnostics(league, season)

col1, col2 = st.columns(2)
with col1:
    st.metric("JSON Files", len(diag.get("json_files", [])),
              help="Core season-level JSON files")
with col2:
    st.metric("Match Files", diag.get("num_match_files", 0),
              help="Individual match event JSONs in partidos/")

# ── JSON File Details ───────────────────────────────────────────────────────
section_header(f"Season Data Files ({season})")
if diag.get("json_files"):
    files_df = pd.DataFrame(diag["json_files"])
    files_df["modified"] = pd.to_datetime(files_df["modified"], unit="s").dt.strftime("%Y-%m-%d %H:%M")
    files_df.columns = ["File", "Size (MB)", "Last Modified"]
    styled_dataframe(files_df, height=200)
else:
    st.info("No JSON files found for this season.")

# ── Team Coverage ───────────────────────────────────────────────────────────
section_header("Team Coverage")
teams = list_team_folders(league, season)
st.metric("Teams in Dataset", len(teams))
if teams:
    with st.expander("Team Folders"):
        for t in sorted(teams):
            st.text(t.replace("_", " "))

# ── Multi-League Overview ───────────────────────────────────────────────────
st.markdown("---")
section_header("Available Competitions")

league_info = []
if DATA_ROOT.exists():
    for d in sorted(DATA_ROOT.iterdir()):
        if d.is_dir() and not d.name.startswith("."):
            seasons = list_seasons(d.name)
            league_info.append({
                "Competition": d.name.replace("_", " "),
                "Seasons": len(seasons),
                "Latest": seasons[0] if seasons else "N/A",
                "Oldest": seasons[-1] if seasons else "N/A",
            })

if league_info:
    league_df = pd.DataFrame(league_info)
    league_df = league_df.sort_values("Seasons", ascending=False)
    styled_dataframe(league_df, height=600)

    total_seasons = league_df["Seasons"].sum()
    kpi_row([
        {"label": "Total Competitions", "value": len(league_info)},
        {"label": "Total Seasons", "value": int(total_seasons)},
        {"label": "Current League Seasons", "value": len(list_seasons(league))},
    ], cols=3)

# ── Schema Documentation ───────────────────────────────────────────────────
st.markdown("---")
section_header("Data Schema Reference")

with st.expander("matches.json — Match Summaries"):
    st.code("""
{
  "match": [
    {
      "matchInfo": {
        "id", "date", "time", "week" (matchday),
        "contestant": [{"name", "code", "id", "position": "home|away"}],
        "venue": {"shortName", "longName"}
      },
      "liveData": {
        "matchDetails": {"scores": {"total": {home, away}, "ht": {home, away}}},
        "event": [1000+ events with typeId, x, y, qualifiers]
      }
    }
  ]
}
    """, language="json")

with st.expander("standings.json — League Table"):
    st.code("""
{
  "stage": [{
    "division": [{
      "type": "total|home|away",
      "ranking": [{
        "rank", "contestantName", "contestantCode", "contestantId",
        "points", "matchesPlayed", "matchesWon", "matchesDrawn",
        "matchesLost", "goalsFor", "goalsAgainst", "goaldifference",
        "lastSix"
      }]
    }]
  }]
}
    """, language="json")

with st.expander("Event Types (Opta typeId)"):
    st.markdown("""
| typeId | Event |
|--------|-------|
| 1 | Pass |
| 3 | Foul |
| 7 | Tackle |
| 8 | Interception |
| 13 | Miss |
| 14 | Post |
| 15 | Attempt Saved |
| 16 | Goal |
| 17 | Card |
| 34 | Team Setup |
| 49 | Ball Recovery |
    """)

with st.expander("Key Qualifiers"):
    st.markdown("""
| qualifierId | Meaning |
|------------|---------|
| 395 | xG value (divide by 100) |
| 44 | Formation data |
| 76 | Assist flag |
| 22 | Penalty flag |
| 230 | Shot distance |
| 231 | Shot angle |
| 140/141 | Pass end x/y |
    """)

# ── Config Panel ────────────────────────────────────────────────────────────
st.markdown("---")
section_header("Configuration")
st.code(f"""
DATA_ROOT = {DATA_ROOT}
DEFAULT_LEAGUE = {DEFAULT_LEAGUE}
DEFAULT_SEASON = {season}
""", language="python")
