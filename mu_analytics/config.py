"""Central configuration for the Manchester United Sports Analytics Platform."""

import os
from pathlib import Path

# ── Data paths ──────────────────────────────────────────────────────────────
# On Streamlit Cloud the data lives in <repo>/data/ next to mu_analytics/.
# Locally you can override with the MU_DATA_ROOT env var.
_DEFAULT_DATA = Path(__file__).resolve().parent.parent / "data"
DATA_ROOT = Path(os.environ.get("MU_DATA_ROOT", str(_DEFAULT_DATA)))
DEFAULT_LEAGUE = "England_Premier_League"
DEFAULT_SEASON = "2025-2026"

# ── Manchester United identifiers ───────────────────────────────────────────
MU_TEAM_ID = "6eqit8ye8aomdsrrq0hk3v7gh"
MU_TEAM_CODE = "MUN"
MU_TEAM_NAME = "Manchester United FC"
MU_TEAM_FOLDER = "Manchester_United_FC"
MU_VENUE = "Old Trafford"
MU_VENUE_ID = "4zn9oeubcog5ol4cb9zm635ni"
MU_CREST_URL = (
    "https://omo.akamai.opta.net/image.php?h=www.scoresway.com"
    "&sport=football&entity=team&description=badges&dimensions=150"
    f"&id={MU_TEAM_ID}"
)

# ── Visual identity ────────────────────────────────────────────────────────
MU_RED = "#DA291C"
MU_BLACK = "#000000"
MU_GOLD = "#FBE122"
MU_WHITE = "#FFFFFF"
MU_DARK_BG = "#0E1117"
MU_CARD_BG = "#1A1A2E"
MU_GRID = "#333333"

# ── Opta event type IDs ────────────────────────────────────────────────────
EVENT_PASS = 1
EVENT_OFFSIDE_PASS = 2
EVENT_TAKE_ON = 3
EVENT_FOUL = 4
EVENT_OUT = 5
EVENT_CORNER = 6
EVENT_TACKLE = 7
EVENT_INTERCEPTION = 8
EVENT_TURNOVER = 9
EVENT_SAVE = 10
EVENT_CLAIM = 11
EVENT_CLEARANCE = 12
EVENT_MISS = 13
EVENT_POST = 14
EVENT_ATTEMPT_SAVED = 15
EVENT_GOAL = 16
EVENT_CARD = 17
EVENT_PLAYER_OFF = 18
EVENT_PLAYER_ON = 19
EVENT_PLAYER_RETIRED = 20
EVENT_BALL_RECOVERY = 49
EVENT_DISPOSSESSED = 50
EVENT_KEEPER_PICKUP = 52
EVENT_CHANCE_MISSED = 60
EVENT_BALL_TOUCH = 61
EVENT_BLOCKED_PASS = 74
EVENT_SHIELD_BALL = 83
EVENT_END = 30
EVENT_START = 32
EVENT_TEAM_SETUP = 34
EVENT_FORMATION_CHANGE = 40
EVENT_AERIAL = 44

# Shot-related type IDs (for filtering)
SHOT_TYPE_IDS = {EVENT_MISS, EVENT_POST, EVENT_ATTEMPT_SAVED, EVENT_GOAL}

# ── Opta qualifier IDs ─────────────────────────────────────────────────────
QUAL_XG = 395
QUAL_XG_TEAM = 396
QUAL_BODY_PART = 72
QUAL_INVOLVED_PLAYER = 140
QUAL_PASS_END_X = 140
QUAL_PASS_END_Y = 141
QUAL_SHOT_DISTANCE = 230
QUAL_SHOT_ANGLE = 231
QUAL_FORMATION = 44
QUAL_FORMATION_TYPE = 130
QUAL_PLAYER_IDS = 30
QUAL_SHIRT_NUMBERS = 59
QUAL_PLAYER_POSITION = 131
QUAL_ASSIST = 76
QUAL_PENALTY = 22
QUAL_OWN_GOAL = 28
QUAL_HEAD = 15
QUAL_RIGHT_FOOT = 72
QUAL_RELATED_EVENT = 55
QUAL_ZONE = 56

# ── Opta formation type ID → formation string (qualifier 130) ────────
# Empirically validated against 2025-26 EPL: Arsenal=4-3-3 (type 4),
# Liverpool/City=4-2-3-1 (type 8), Man United/Palace=3-4-2-1 (type 17).
OPTA_FORMATION_MAP = {
    "1": "4-4-2",
    "2": "4-4-1-1",
    "4": "4-3-3",
    "5": "4-5-1",
    "6": "4-4-2",
    "7": "4-1-4-1",
    "8": "4-2-3-1",
    "9": "4-3-2-1",
    "10": "5-3-2",
    "11": "5-4-1",
    "12": "3-5-2",
    "13": "3-4-3",
    "14": "3-4-2-1",
    "15": "4-1-2-1-2",
    "16": "3-5-1-1",
    "17": "3-4-2-1",
    "18": "3-1-4-2",
    "19": "3-4-1-2",
    "20": "4-2-4-0",
    "21": "4-2-2-2",
    "23": "4-1-3-2",
}

# ── Set-piece analysis constants ──────────────────────────────────────────
QUAL_CORNER_TYPE = 56       # qualifier for corner delivery type
CORNER_TYPE_LABELS = {
    "Center": "Inswinging",
    "Back": "Short / Back",
    "Right": "Right Side",
    "Left": "Left Side",
}
SET_PIECE_WINDOW_SECS = 45  # seconds after corner/foul to attribute shots

# ── Qualifier value constants ───────────────────────────────────────────────
BODY_PART_MAP = {"Head": "Head", "Right": "Right Foot", "Left": "Left Foot"}

# ── Shot outcome labels ─────────────────────────────────────────────────────
SHOT_OUTCOME_MAP = {
    EVENT_GOAL: "Goal",
    EVENT_ATTEMPT_SAVED: "Saved",
    EVENT_MISS: "Missed",
    EVENT_POST: "Post",
}

# ── Card type labels ────────────────────────────────────────────────────────
CARD_TYPE_MAP = {
    "YC": "Yellow Card",
    "Y2C": "Second Yellow",
    "RC": "Red Card",
}

# ── EPL Big Six team IDs (for defaults in comparison views) ────────────────
BIG_SIX = {
    "Manchester United FC": "6eqit8ye8aomdsrrq0hk3v7gh",
    "Manchester City FC": "b496gs285it6bheuikox6z9mj",
    "Liverpool FC": "c8h9bw1l82s06h77xxrelzhur",
    "Arsenal FC": "4dsgumo7d4zupm2ugsvm4zm4d",
    "Chelsea FC": "9q0arba2kbnywth8bkxlhgmdr",
    "Tottenham Hotspur FC": "22doj4sgsocqpbih45j5fyh89",
}

# ── Elo rating parameters ──────────────────────────────────────────────────
ELO_INITIAL = 1500
ELO_K_FACTOR = 20
ELO_HOME_ADVANTAGE = 50

# ── Poisson model parameters ───────────────────────────────────────────────
POISSON_MAX_GOALS = 8
MONTE_CARLO_SIMS = 100_000
HOME_FACTOR = 1.1
LEAGUE_AVG_GOALS_PER_TEAM = 1.35

# ── Enhanced prediction model constants ───────────────────────────────────
UCL_WEIGHT = 1.2                    # same-competition match weight for blending
DOMESTIC_WEIGHT = 0.8               # cross-competition domestic data weight
FORM_WINDOW = 5                     # recent matches for form calculation
FORM_DECAY = 0.85                   # exponential decay per match backward
DIXON_COLES_RHO = -0.13            # low-score correction (Dixon & Coles 1997)
XG_ADJUSTMENT_WEIGHT = 0.25        # how much xG luck shifts lambda
ELO_LAMBDA_SCALE = 0.001           # Elo diff → lambda multiplier
TACTICAL_DOMINANCE_WEIGHT = 0.10   # tactical metrics contribution
MIN_MATCHES_FOR_PREDICTION = 3     # minimum matches required for prediction

# ── Player rating parameters ───────────────────────────────────────────────
MIN_APPEARANCES_FOR_RATING = 5
MIN_MINUTES_FOR_RATING = 450  # ~5 full matches, avoids per-90 inflation
RATING_FLOOR = 40
RATING_CEILING = 99

# ── Available seasons (EPL) ─────────────────────────────────────────────────
EPL_SEASONS = [
    "2025-2026", "2024-2025", "2023-2024", "2022-2023", "2021-2022",
    "2020-2021", "2019-2020", "2018-2019", "2017-2018", "2016-2017",
    "2015-2016", "2014-2015", "2013-2014", "2012-2013", "2011-2012",
    "2010-2011", "2009-2010", "2008-2009",
]

# ── Available competitions ─────────────────────────────────────────────────
COMPETITIONS = {
    # England
    "England_Premier_League": "Premier League",
    # Top 5 European Leagues
    "Spain_Primera_Division": "La Liga",
    "Germany_Bundesliga": "Bundesliga",
    "Italy_Serie_A": "Serie A",
    "France_Ligue_1": "Ligue 1",
    # Other European Leagues
    "Netherlands_Eredivisie": "Eredivisie",
    "Portugal_Primeira_Liga": "Liga Portugal",
    "Scotland_Premiership": "Scottish Premiership",
    # UEFA Club Competitions
    "UEFA_UEFA_Champions_League": "Champions League",
    "UEFA_UEFA_Europa_League": "Europa League",
    "UEFA_UEFA_Conference_League": "Conference League",
}

# Competitions where MU participates (for page guards)
MU_LEAGUES = {
    "England_Premier_League",
    "UEFA_UEFA_Champions_League",
    "UEFA_UEFA_Europa_League",
    "UEFA_UEFA_Conference_League",
}

# ── Position-specific rating categories ───────────────────────────────────
POSITION_CATEGORIES = {
    "Goalkeeper": ["Shot Stopping", "Distribution", "Command", "Reflexes", "Clean Sheets"],
    "Defender":   ["Tackling", "Aerial", "Positioning", "Ball Playing", "Physicality"],
    "Midfielder": ["Passing", "Creativity", "Ball Carrying", "Defensive Work", "Pressing"],
    "Forward":    ["Finishing", "Movement", "Chance Creation", "Dribbling", "Aerial Threat"],
    "Attacker":   ["Finishing", "Movement", "Chance Creation", "Dribbling", "Aerial Threat"],
}

POSITION_CATEGORY_DISPLAY = {
    "GK_ShotStop": "Shot Stopping", "GK_Dist": "Distribution",
    "GK_Command": "Command", "GK_Reflex": "Reflexes", "GK_CleanSheet": "Clean Sheets",
    "DEF_Tackle": "Tackling", "DEF_Aerial": "Aerial",
    "DEF_Position": "Positioning", "DEF_BallPlay": "Ball Playing", "DEF_Physical": "Physicality",
    "MID_Pass": "Passing", "MID_Create": "Creativity",
    "MID_Carry": "Ball Carrying", "MID_DefWork": "Defensive Work", "MID_Press": "Pressing",
    "FWD_Finish": "Finishing", "FWD_Move": "Movement",
    "FWD_Chance": "Chance Creation", "FWD_Dribble": "Dribbling", "FWD_AerialThreat": "Aerial Threat",
}
