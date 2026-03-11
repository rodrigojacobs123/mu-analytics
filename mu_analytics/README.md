# Manchester United Sports Analytics Platform

**TFM — Master's Thesis in Big Data & Sports Analytics**

A full-featured, 11-module Streamlit analytics platform for Manchester United, built on Opta-format event data covering 17 Premier League seasons (2008–2025).

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run the platform
streamlit run app.py
```

The app will launch at `http://localhost:8501`.

## Modules

| # | Module | Description |
|---|--------|-------------|
| 1 | **Home** | Season KPI dashboard, league table, cross-season trends |
| 2 | **Pre-Match Analysis** | Recent form, Elo rating, H2H, radar chart, Poisson prediction |
| 3 | **Post-Match Analysis** | xG race, shot maps, pass networks, heatmaps, key events |
| 4 | **Tactics** | Formation display, pass networks by half, defensive actions, progressive passes |
| 5 | **Team Analysis** | Season trend, league table, Elo historical, team radar |
| 6 | **Player Scouting** | FC-style ratings (PAC/SHO/PAS/DRI/DEF/PHY), play-style detection, leaderboard |
| 7 | **Predictions** | Poisson model + Monte Carlo (10,000 simulations), probable XI |
| 8 | **Rivals & Rankings** | Multi-team radar, comparative table, stat comparison |
| 9 | **xG Explorer** | Interactive shot explorer with filters, pitch visualization |
| 10 | **Injury Tracker** | Synthetic injury intelligence with timeline and analysis |
| 11 | **Data Sources** | Dataset diagnostics, file counts, schema documentation |

## Data Configuration

The platform reads from a local Opta-format data repository. Update the data path in `config.py`:

```python
DATA_ROOT = Path("/path/to/your/europa/data")
```

The expected directory structure is:
```
europa/
├── England_Premier_League/
│   ├── 2024-2025/
│   │   ├── jsons/
│   │   │   ├── matches.json
│   │   │   ├── standings.json
│   │   │   ├── rankings.json
│   │   │   └── squads.json
│   │   ├── partidos/*.json (individual match events)
│   │   └── equipos/*/  (team folders with player stats)
│   └── ... (more seasons)
└── ... (more leagues)
```

## Tech Stack

- **Streamlit** — UI framework with multi-page navigation
- **Pandas / NumPy** — Data manipulation
- **Plotly** — Interactive charts (dark theme)
- **mplsoccer** — Football pitch visualizations
- **SciPy** — Poisson distribution for predictions
- **Matplotlib** — Static complementary charts
