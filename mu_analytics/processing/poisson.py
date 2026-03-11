"""Poisson model + Monte Carlo simulation for match prediction.

Enhanced multi-factor model with Dixon-Coles correction,
cross-competition blending (UCL), xG, Elo, form, and tactical adjustments.
"""

import unicodedata
import numpy as np
import pandas as pd
from scipy.stats import poisson


def _nfc(text: str) -> str:
    """Normalize to NFC — fixes macOS NFD filesystem encoding."""
    return unicodedata.normalize("NFC", text)
from config import (
    POISSON_MAX_GOALS, MONTE_CARLO_SIMS, HOME_FACTOR, LEAGUE_AVG_GOALS_PER_TEAM,
    UCL_WEIGHT, DOMESTIC_WEIGHT, FORM_WINDOW, FORM_DECAY,
    DIXON_COLES_RHO, XG_ADJUSTMENT_WEIGHT, ELO_LAMBDA_SCALE,
    TACTICAL_DOMINANCE_WEIGHT, MIN_MATCHES_FOR_PREDICTION,
    COMPETITIONS,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Existing core functions (preserved for backward compatibility)
# ═══════════════════════════════════════════════════════════════════════════════

def estimate_team_strengths(results: pd.DataFrame,
                            num_matches: int | None = None,
                            standings: pd.DataFrame | None = None) -> tuple[dict, dict]:
    """Compute attack and defense strength for each team from season results.

    Args:
        results: DataFrame with home_team, away_team, home_score, away_score
                 (and optionally home_id, away_id)
        num_matches: if set, use only the last N matches per team
        standings: optional standings DataFrame with team_name and team_id;
                   used to bridge name differences between results and standings

    Returns:
        (attack_strengths, defense_strengths) dicts keyed by team_name
    """
    if results.empty:
        return {}, {}

    # Build ID→name bridge from standings + results if available
    _id_to_standings_name = {}
    if standings is not None and not standings.empty and "team_id" in standings.columns:
        _id_to_standings_name = dict(zip(standings["team_id"], standings["team_name"]))

    _id_to_results_name = {}
    if "home_id" in results.columns:
        for _, r in results[["home_team", "home_id"]].drop_duplicates().iterrows():
            _id_to_results_name[r["home_id"]] = r["home_team"]
        for _, r in results[["away_team", "away_id"]].drop_duplicates().iterrows():
            _id_to_results_name[r["away_id"]] = r["away_team"]

    if num_matches:
        # Use last N matches per team
        teams = set(results["home_team"]) | set(results["away_team"])
        filtered = []
        for team in teams:
            team_matches = results[
                (results["home_team"] == team) | (results["away_team"] == team)
            ].tail(num_matches)
            filtered.append(team_matches)
        if filtered:
            results = pd.concat(filtered).drop_duplicates()

    league_avg_goals = results[["home_score", "away_score"]].mean().mean()
    if league_avg_goals == 0:
        league_avg_goals = LEAGUE_AVG_GOALS_PER_TEAM

    attack = {}
    defense = {}

    teams = set(results["home_team"]) | set(results["away_team"])
    for team in teams:
        home_m = results[results["home_team"] == team]
        away_m = results[results["away_team"] == team]

        goals_scored = home_m["home_score"].sum() + away_m["away_score"].sum()
        goals_conceded = home_m["away_score"].sum() + away_m["home_score"].sum()
        total_matches = len(home_m) + len(away_m)

        if total_matches > 0:
            att = (goals_scored / total_matches) / league_avg_goals
            defe = (goals_conceded / total_matches) / league_avg_goals
        else:
            att = 1.0
            defe = 1.0

        attack[team] = att
        defense[team] = defe
        # Generate name aliases for matching standings ↔ results names
        for alias in _team_name_aliases(team):
            attack[alias] = att
            defense[alias] = defe

    # Bridge from standings names to results strengths via team_id
    if _id_to_standings_name and _id_to_results_name:
        for tid, standings_name in _id_to_standings_name.items():
            results_name = _id_to_results_name.get(tid)
            if results_name and results_name in attack and standings_name not in attack:
                attack[standings_name] = attack[results_name]
                defense[standings_name] = defense[results_name]

    return attack, defense


def _team_name_aliases(name: str) -> list[str]:
    """Generate common name variants for a team (suffix/prefix permutations)."""
    aliases = []
    base = name.strip()
    # Suffixes: add and strip
    for suffix in (" FC", " CF", " SC", " SL", " AFC", " SV"):
        if not base.endswith(suffix):
            aliases.append(f"{base}{suffix}")
        else:
            aliases.append(base[:-len(suffix)].rstrip())
    # Prefixes: add and strip
    for prefix in ("FC ", "AC ", "BV ", "SL ", "SC ", "NK ", "SK "):
        if not base.startswith(prefix):
            aliases.append(f"{prefix}{base}")
        else:
            aliases.append(base[len(prefix):].lstrip())
    return aliases


# ═══════════════════════════════════════════════════════════════════════════════
# NEW: Factor adjustment functions
# ═══════════════════════════════════════════════════════════════════════════════

def compute_form_weighted_strength(results: pd.DataFrame, team: str,
                                   window: int = FORM_WINDOW,
                                   decay: float = FORM_DECAY) -> tuple[float, float]:
    """Compute recent form with exponential decay weighting.

    Looks at the last `window` matches for `team`, weighting the most
    recent match at 1.0 and each prior match by `decay` cumulatively.

    Returns:
        (weighted_gs_per_match, weighted_gc_per_match)
        Falls back to (1.35, 1.35) if no data.
    """
    team_m = results[
        (results["home_team"] == team) | (results["away_team"] == team)
    ].tail(window)

    if team_m.empty:
        return (LEAGUE_AVG_GOALS_PER_TEAM, LEAGUE_AVG_GOALS_PER_TEAM)

    n = len(team_m)
    weights = np.array([decay ** (n - 1 - i) for i in range(n)])
    total_weight = weights.sum()

    scored = []
    conceded = []
    for _, r in team_m.iterrows():
        is_home = r["home_team"] == team
        scored.append(r["home_score"] if is_home else r["away_score"])
        conceded.append(r["away_score"] if is_home else r["home_score"])

    scored = np.array(scored, dtype=float)
    conceded = np.array(conceded, dtype=float)

    w_gs = np.dot(weights, scored) / total_weight
    w_gc = np.dot(weights, conceded) / total_weight

    return (w_gs, w_gc)


def compute_form_adjustment(results: pd.DataFrame, team: str,
                            window: int = FORM_WINDOW,
                            decay: float = FORM_DECAY) -> tuple[float, float]:
    """Convert form-weighted strength into a lambda adjustment ratio.

    Compares decay-weighted goals/match to season average.
    Returns (attack_adj, defense_adj), each clamped to [0.85, 1.15].
    Values > 1.0 mean recent form is better than season average.
    """
    w_gs, w_gc = compute_form_weighted_strength(results, team, window, decay)

    # Season averages for this team
    team_m = results[
        (results["home_team"] == team) | (results["away_team"] == team)
    ]
    if len(team_m) < 2:
        return (1.0, 1.0)

    scored_all = []
    conceded_all = []
    for _, r in team_m.iterrows():
        is_home = r["home_team"] == team
        scored_all.append(r["home_score"] if is_home else r["away_score"])
        conceded_all.append(r["away_score"] if is_home else r["home_score"])

    avg_gs = np.mean(scored_all) if scored_all else LEAGUE_AVG_GOALS_PER_TEAM
    avg_gc = np.mean(conceded_all) if conceded_all else LEAGUE_AVG_GOALS_PER_TEAM

    # Attack: recent form goals scored vs season avg (higher = better)
    att_adj = w_gs / avg_gs if avg_gs > 0 else 1.0
    # Defense: recent form goals conceded vs season avg (lower = better → invert)
    def_adj = avg_gc / w_gc if w_gc > 0 else 1.0

    return (
        float(np.clip(att_adj, 0.85, 1.15)),
        float(np.clip(def_adj, 0.85, 1.15)),
    )


def compute_xg_adjustment(league: str, season: str,
                          team_folder: str, team_id: str) -> tuple[float, float]:
    """Compare actual goals to expected goals (xG) across the season.

    If a team is over-performing xG, we regress lambda downward (and vice versa).
    This captures "luck correction" — a team scoring 20 from 15 xG is likely
    to regress.

    Returns (attack_adj, defense_adj), each clamped to [0.80, 1.20].
    Falls back to (1.0, 1.0) if no xG data is available.
    """
    try:
        from data.loader import load_match_raw, load_all_season_results
        from data.event_parser import parse_match_info
        from processing.xg import compute_match_xg
        from data.paths import list_match_files
    except ImportError:
        return (1.0, 1.0)

    match_files = list_match_files(league, season)
    if not match_files:
        return (1.0, 1.0)

    total_xg_for = 0.0
    total_xg_against = 0.0
    total_goals_for = 0.0
    total_goals_against = 0.0
    match_count = 0

    for fpath in match_files:
        try:
            import json
            with open(fpath, "r", encoding="utf-8") as f:
                raw = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue

        info = parse_match_info(raw)
        events = raw.get("liveData", {}).get("event", [])

        # Check if this team played in this match
        is_home = info.get("home_id") == team_id
        is_away = info.get("away_id") == team_id
        if not is_home and not is_away:
            continue

        opp_id = info["away_id"] if is_home else info["home_id"]

        xg_for = compute_match_xg(events, team_id)
        xg_against = compute_match_xg(events, opp_id)
        goals_for = info["home_score"] if is_home else info["away_score"]
        goals_against = info["away_score"] if is_home else info["home_score"]

        if goals_for is None or goals_against is None:
            continue

        total_xg_for += xg_for
        total_xg_against += xg_against
        total_goals_for += goals_for
        total_goals_against += goals_against
        match_count += 1

    if match_count < 3 or total_xg_for < 0.5:
        return (1.0, 1.0)

    # Attack: if xG > actual goals → team is underperforming → adjust up
    att_adj = 1.0 + XG_ADJUSTMENT_WEIGHT * (total_xg_for - total_goals_for) / max(total_goals_for, 1)
    # Defense: if xG against < actual conceded → unlucky → adjust favorably
    def_adj = 1.0 + XG_ADJUSTMENT_WEIGHT * (total_goals_against - total_xg_against) / max(total_goals_against, 1)

    return (
        float(np.clip(att_adj, 0.80, 1.20)),
        float(np.clip(def_adj, 0.80, 1.20)),
    )


def compute_elo_lambda_adjustment(home_elo: float, away_elo: float) -> tuple[float, float]:
    """Convert Elo rating difference into lambda multipliers.

    A 100-point Elo advantage gives ~10% lambda boost.

    Returns (home_adj, away_adj) each clamped to [0.85, 1.15].
    """
    diff = home_elo - away_elo  # positive = home is stronger
    home_adj = 1.0 + ELO_LAMBDA_SCALE * diff
    away_adj = 1.0 - ELO_LAMBDA_SCALE * diff

    return (
        float(np.clip(home_adj, 0.85, 1.15)),
        float(np.clip(away_adj, 0.85, 1.15)),
    )


def compute_tactical_dominance(home_stats: dict, away_stats: dict) -> tuple[float, float]:
    """Compute tactical dominance adjustment from aggregated season stats.

    Uses 5 key metrics: possession, pass accuracy, shots/match,
    goals/match, and clean sheet rate.

    Args:
        home_stats: dict from load_team_season_agg() for home team
        away_stats: dict from load_team_season_agg() for away team

    Returns (home_adj, away_adj) each clamped to [0.90, 1.10].
    Falls back to (1.0, 1.0) if stats are missing.
    """
    metrics = [
        ("possession_pct", 50.0),     # default neutral
        ("pass_accuracy", 75.0),
        ("shots_per_match", 12.0),
        ("goals_per_match", 1.35),
        ("clean_sheets", 5.0),
    ]

    if not home_stats or not away_stats:
        return (1.0, 1.0)

    home_shares = []
    away_shares = []

    for metric, default in metrics:
        h_val = home_stats.get(metric, default)
        a_val = away_stats.get(metric, default)

        # Ensure numeric
        try:
            h_val = float(h_val)
            a_val = float(a_val)
        except (TypeError, ValueError):
            continue

        total = h_val + a_val
        if total > 0:
            home_shares.append(h_val / total)
            away_shares.append(a_val / total)
        else:
            home_shares.append(0.5)
            away_shares.append(0.5)

    if not home_shares:
        return (1.0, 1.0)

    # Average share across metrics (0.5 = neutral, >0.5 = dominant)
    h_avg = np.mean(home_shares)
    a_avg = np.mean(away_shares)

    # Convert share to adjustment: 0.5 → 1.0, 0.6 → 1.0 + weight*(0.6-0.5)/0.5
    home_adj = 1.0 + TACTICAL_DOMINANCE_WEIGHT * (h_avg - 0.5) / 0.5
    away_adj = 1.0 + TACTICAL_DOMINANCE_WEIGHT * (a_avg - 0.5) / 0.5

    return (
        float(np.clip(home_adj, 0.90, 1.10)),
        float(np.clip(away_adj, 0.90, 1.10)),
    )


def apply_dixon_coles_correction(score_matrix: np.ndarray,
                                 home_lambda: float, away_lambda: float,
                                 rho: float = DIXON_COLES_RHO) -> np.ndarray:
    """Apply Dixon-Coles (1997) low-score correction to probability matrix.

    Standard Poisson assumes independence between home/away goals.
    Dixon-Coles corrects this by adjusting the four low-score cells:
    (0,0), (1,0), (0,1), (1,1) using parameter rho (typically ≈ -0.13).

    This slightly inflates 0-0 and 1-1 probabilities while deflating
    1-0 and 0-1 — matching observed football data more closely.

    Returns a re-normalized copy of the score matrix.
    """
    m = score_matrix.copy()

    # Dixon-Coles tau function applied to cells (0,0), (1,0), (0,1), (1,1)
    if m.shape[0] >= 2 and m.shape[1] >= 2:
        # τ(0,0) = 1 − λ₁·λ₂·ρ
        m[0, 0] *= max(1.0 - home_lambda * away_lambda * rho, 0.001)
        # τ(1,0) = 1 + λ₂·ρ
        m[1, 0] *= max(1.0 + away_lambda * rho, 0.001)
        # τ(0,1) = 1 + λ₁·ρ
        m[0, 1] *= max(1.0 + home_lambda * rho, 0.001)
        # τ(1,1) = 1 − ρ
        m[1, 1] *= max(1.0 - rho, 0.001)

    # Re-normalize so probabilities sum to 1
    total = m.sum()
    if total > 0:
        m /= total

    return m


def compute_cross_competition_strength(team_name: str, team_id: str,
                                       ucl_results: pd.DataFrame,
                                       ucl_standings: pd.DataFrame,
                                       season: str) -> tuple[float, float] | None:
    """For UCL/Europa teams with few matches, blend with domestic league data.

    Searches all domestic leagues in COMPETITIONS for a matching team_id
    in their standings, then blends attack/defense strengths weighted by
    match count and competition weight.

    Returns (blended_attack, blended_defense) or None if no domestic data found.
    """
    from data.loader import load_all_season_results, load_standings

    # UCL strengths
    ucl_att, ucl_def = estimate_team_strengths(ucl_results, standings=ucl_standings)
    ucl_attack = ucl_att.get(team_name, 1.0)
    ucl_defense = ucl_def.get(team_name, 1.0)

    ucl_team_m = ucl_results[
        (ucl_results["home_team"] == team_name) |
        (ucl_results["away_team"] == team_name)
    ]
    ucl_n = len(ucl_team_m)

    # Search domestic leagues for matching team_id
    domestic_leagues = [k for k in COMPETITIONS if not k.startswith("UEFA")]
    dom_attack, dom_defense, dom_n = None, None, 0

    for dom_league in domestic_leagues:
        try:
            dom_standings = load_standings(dom_league, season)
            if dom_standings.empty or "team_id" not in dom_standings.columns:
                continue
            if team_id not in dom_standings["team_id"].values:
                continue

            # Found domestic league for this team
            dom_results = load_all_season_results(dom_league, season)
            if dom_results.empty:
                continue

            dom_att, dom_def = estimate_team_strengths(dom_results, standings=dom_standings)

            # Find the team's name in the domestic league
            dom_team_row = dom_standings[dom_standings["team_id"] == team_id].iloc[0]
            dom_team_name = dom_team_row["team_name"]

            if dom_team_name in dom_att:
                dom_attack = dom_att[dom_team_name]
                dom_defense = dom_def[dom_team_name]
            elif team_name in dom_att:
                dom_attack = dom_att[team_name]
                dom_defense = dom_def[team_name]

            if dom_attack is not None:
                dom_team_m = dom_results[
                    (dom_results["home_team"] == dom_team_name) |
                    (dom_results["away_team"] == dom_team_name)
                ]
                dom_n = len(dom_team_m)
                break
        except Exception:
            continue

    if dom_attack is None:
        return None  # No domestic data found

    # Weighted blend
    ucl_total_weight = ucl_n * UCL_WEIGHT
    dom_total_weight = dom_n * DOMESTIC_WEIGHT
    total_weight = ucl_total_weight + dom_total_weight

    if total_weight == 0:
        return None

    blended_att = (ucl_attack * ucl_total_weight + dom_attack * dom_total_weight) / total_weight
    blended_def = (ucl_defense * ucl_total_weight + dom_defense * dom_total_weight) / total_weight

    return (blended_att, blended_def)


# ═══════════════════════════════════════════════════════════════════════════════
# Enhanced predict_match and monte_carlo_simulation
# ═══════════════════════════════════════════════════════════════════════════════

def predict_match(home_attack: float, home_defense: float,
                  away_attack: float, away_defense: float,
                  league_avg: float = LEAGUE_AVG_GOALS_PER_TEAM, *,
                  home_xg_adj: float = 1.0, away_xg_adj: float = 1.0,
                  home_elo_adj: float = 1.0, away_elo_adj: float = 1.0,
                  home_tactical_adj: float = 1.0, away_tactical_adj: float = 1.0,
                  home_form_att_adj: float = 1.0, home_form_def_adj: float = 1.0,
                  away_form_att_adj: float = 1.0, away_form_def_adj: float = 1.0,
                  apply_dixon_coles_flag: bool = True,
                  max_goals: int = POISSON_MAX_GOALS) -> dict:
    """Predict match outcome using enhanced multi-factor Poisson model.

    All adjustment parameters default to 1.0 for full backward compatibility.
    Existing callers (Pre-Match Analysis) work unchanged.

    The enhanced lambda formula:
        home_λ = base_λ × xg_adj × elo_adj × tactical_adj × form_att_adj
        (base_λ = home_attack × away_defense × league_avg × HOME_FACTOR)

    Returns dict with score_matrix, probabilities, expected goals,
    most likely score, lambdas, and factor breakdown.
    """
    # Base lambdas (same as original)
    base_home = home_attack * away_defense * league_avg * HOME_FACTOR
    base_away = away_attack * home_defense * league_avg

    # Apply multiplicative adjustments
    home_lambda = (base_home * home_xg_adj * home_elo_adj
                   * home_tactical_adj * home_form_att_adj)
    away_lambda = (base_away * away_xg_adj * away_elo_adj
                   * away_tactical_adj * away_form_att_adj)

    # Clamp lambdas to reasonable range
    home_lambda = float(np.clip(home_lambda, 0.1, 5.5))
    away_lambda = float(np.clip(away_lambda, 0.1, 5.5))

    max_g = max_goals
    score_matrix = np.zeros((max_g, max_g))

    for i in range(max_g):
        for j in range(max_g):
            score_matrix[i][j] = poisson.pmf(i, home_lambda) * poisson.pmf(j, away_lambda)

    # Apply Dixon-Coles correction
    if apply_dixon_coles_flag:
        score_matrix = apply_dixon_coles_correction(score_matrix, home_lambda, away_lambda)

    home_win = sum(score_matrix[i][j] for i in range(max_g) for j in range(max_g) if i > j)
    draw = sum(score_matrix[i][i] for i in range(max_g))
    away_win = sum(score_matrix[i][j] for i in range(max_g) for j in range(max_g) if i < j)

    # Normalize
    total = home_win + draw + away_win
    if total > 0:
        home_win /= total
        draw /= total
        away_win /= total

    # Most likely score
    max_idx = np.unravel_index(score_matrix.argmax(), score_matrix.shape)

    return {
        "score_matrix": score_matrix,
        "home_win_prob": home_win,
        "draw_prob": draw,
        "away_win_prob": away_win,
        "most_likely_score": (int(max_idx[0]), int(max_idx[1])),
        "home_lambda": home_lambda,
        "away_lambda": away_lambda,
        "base_home_lambda": base_home,
        "base_away_lambda": base_away,
        "factors": {
            "xg": (home_xg_adj, away_xg_adj),
            "elo": (home_elo_adj, away_elo_adj),
            "tactical": (home_tactical_adj, away_tactical_adj),
            "form_attack": (home_form_att_adj, away_form_att_adj),
            "form_defense": (home_form_def_adj, away_form_def_adj),
            "dixon_coles": apply_dixon_coles_flag,
        },
    }


def monte_carlo_simulation(home_lambda: float, away_lambda: float,
                           n_sims: int = MONTE_CARLO_SIMS) -> dict:
    """Run N Monte Carlo simulated matches using Poisson distribution.

    Enhanced with market-style props: BTTS, Over/Under 2.5, clean sheet probs,
    and per-team goal distributions.
    """
    rng = np.random.default_rng(42)
    home_goals = rng.poisson(home_lambda, n_sims)
    away_goals = rng.poisson(away_lambda, n_sims)
    goal_diff = home_goals - away_goals
    total_goals = home_goals + away_goals

    home_wins = np.sum(home_goals > away_goals)
    draws = np.sum(home_goals == away_goals)
    away_wins = np.sum(home_goals < away_goals)

    # Score frequency
    scores = pd.DataFrame({"home": home_goals, "away": away_goals})
    score_counts = scores.groupby(["home", "away"]).size().reset_index(name="count")
    score_counts["pct"] = score_counts["count"] / n_sims * 100
    score_counts = score_counts.sort_values("count", ascending=False)

    # Market props
    btts = np.sum((home_goals > 0) & (away_goals > 0))
    over_2_5 = np.sum(total_goals > 2.5)
    under_2_5 = n_sims - over_2_5
    home_cs = np.sum(away_goals == 0)
    away_cs = np.sum(home_goals == 0)

    # Per-team goal distributions
    home_goal_dist = {}
    away_goal_dist = {}
    for g in range(5):
        home_goal_dist[g] = int(np.sum(home_goals == g))
        away_goal_dist[g] = int(np.sum(away_goals == g))
    home_goal_dist["3+"] = int(np.sum(home_goals >= 3))
    away_goal_dist["3+"] = int(np.sum(away_goals >= 3))

    return {
        "home_goals": home_goals,
        "away_goals": away_goals,
        "goal_diff": goal_diff,
        "home_win_pct": home_wins / n_sims,
        "draw_pct": draws / n_sims,
        "away_win_pct": away_wins / n_sims,
        "avg_home_goals": float(home_goals.mean()),
        "avg_away_goals": float(away_goals.mean()),
        "score_freq": score_counts,
        "n_sims": n_sims,
        # Enhanced props
        "btts_prob": btts / n_sims,
        "over_2_5_prob": over_2_5 / n_sims,
        "under_2_5_prob": under_2_5 / n_sims,
        "home_clean_sheet_prob": home_cs / n_sims,
        "away_clean_sheet_prob": away_cs / n_sims,
        "home_goal_dist": home_goal_dist,
        "away_goal_dist": away_goal_dist,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Orchestrator: compute_enhanced_prediction
# ═══════════════════════════════════════════════════════════════════════════════

def compute_enhanced_prediction(league: str, season: str,
                                home_team: str, away_team: str,
                                n_sims: int = MONTE_CARLO_SIMS) -> dict:
    """Orchestrate all prediction factors into a single enhanced prediction.

    Each factor is computed independently and gracefully falls back to
    neutral (1.0) if data is unavailable. This means predictions work
    with any amount of data — from UCL (5 matches) to EPL (28+ matches).

    For UEFA competitions, cross-competition blending supplements sparse
    UCL data with domestic league performance.

    Returns:
        {
            "prediction": predict_match output,
            "monte_carlo": monte_carlo_simulation output,
            "context": {elo, form, h2h, team_stats, radar, factors_applied, ...},
            "data_quality": "full" | "partial" | "minimal",
        }
    """
    from data.loader import load_all_season_results, load_standings
    from data.paths import list_seasons
    from processing.elo import compute_elo_history, get_current_elo, get_cross_league_elo
    from processing.team_stats import (
        compute_team_radar_data, RADAR_CATEGORIES, get_team_folder_map,
    )

    results = load_all_season_results(league, season)
    standings = load_standings(league, season)

    if results.empty:
        return _empty_prediction()

    # ── Base strengths ───────────────────────────────────────────────
    is_uefa = league.startswith("UEFA")
    attack, defense = estimate_team_strengths(results, standings=standings)

    # Try cross-competition blending for UEFA competitions
    home_id = _get_team_id(results, standings, home_team)
    away_id = _get_team_id(results, standings, away_team)

    if is_uefa and home_id:
        blended = compute_cross_competition_strength(
            home_team, home_id, results, standings, season
        )
        if blended:
            attack[home_team], defense[home_team] = blended

    if is_uefa and away_id:
        blended = compute_cross_competition_strength(
            away_team, away_id, results, standings, season
        )
        if blended:
            attack[away_team], defense[away_team] = blended

    if home_team not in attack or away_team not in attack:
        return _empty_prediction()

    # ── Resolve team names in results (standings vs partidos mismatch) ─
    home_in_results = _resolve_team_in_results(results, home_team, home_id)
    away_in_results = _resolve_team_in_results(results, away_team, away_id)

    # ── Factor computations (each skippable) ─────────────────────────
    factors_applied = []
    context = {}

    # 1. Form — cross-competition (last 5 games across ALL competitions)
    home_form_att, home_form_def = 1.0, 1.0
    away_form_att, away_form_def = 1.0, 1.0
    try:
        if home_id:
            home_form_att, home_form_def = compute_cross_comp_form_adjustment(home_id, season)
        if away_id:
            away_form_att, away_form_def = compute_cross_comp_form_adjustment(away_id, season)
    except Exception:
        # Fallback to single-league form
        home_form_att, home_form_def = compute_form_adjustment(results, home_in_results)
        away_form_att, away_form_def = compute_form_adjustment(results, away_in_results)
    if (home_form_att, home_form_def) != (1.0, 1.0) or (away_form_att, away_form_def) != (1.0, 1.0):
        factors_applied.append("form")

    # Compute form badges (W/D/L) — cross-competition for richer data
    try:
        home_cross_form = _get_cross_comp_form_string(home_id, season) if home_id else []
        away_cross_form = _get_cross_comp_form_string(away_id, season) if away_id else []
        context["home_form"] = home_cross_form if home_cross_form else _get_form_string(results, home_in_results)
        context["away_form"] = away_cross_form if away_cross_form else _get_form_string(results, away_in_results)
    except Exception:
        context["home_form"] = _get_form_string(results, home_in_results)
        context["away_form"] = _get_form_string(results, away_in_results)

    # 2. Elo (cross-league: if UCL team has no Elo, pull domestic league Elo)
    home_elo_adj, away_elo_adj = 1.0, 1.0
    try:
        home_elo = get_cross_league_elo(home_team, home_id, league, season)
        away_elo = get_cross_league_elo(away_team, away_id, league, season)
        home_elo_adj, away_elo_adj = compute_elo_lambda_adjustment(home_elo, away_elo)
        context["home_elo"] = home_elo
        context["away_elo"] = away_elo
        if home_elo != 1500.0 or away_elo != 1500.0:
            factors_applied.append("elo")
    except Exception:
        context["home_elo"] = 1500.0
        context["away_elo"] = 1500.0

    # 3. xG adjustment
    home_xg_adj, away_xg_adj = 1.0, 1.0
    try:
        folder_map = get_team_folder_map(league, season)
        home_folder = folder_map.get(home_team, "")
        away_folder = folder_map.get(away_team, "")

        if home_folder and home_id:
            h_xg_att, h_xg_def = compute_xg_adjustment(league, season, home_folder, home_id)
            home_xg_adj = h_xg_att
            if h_xg_att != 1.0 or h_xg_def != 1.0:
                factors_applied.append("xG")
        if away_folder and away_id:
            a_xg_att, a_xg_def = compute_xg_adjustment(league, season, away_folder, away_id)
            away_xg_adj = a_xg_att
    except Exception:
        pass

    # 4. Tactical dominance
    home_tact_adj, away_tact_adj = 1.0, 1.0
    try:
        from processing.season_tactics import load_team_season_agg
        if home_folder and away_folder:
            home_stats = load_team_season_agg(league, season, home_folder)
            away_stats = load_team_season_agg(league, season, away_folder)
            home_tact_adj, away_tact_adj = compute_tactical_dominance(home_stats, away_stats)
            context["home_stats"] = home_stats
            context["away_stats"] = away_stats
            if (home_tact_adj, away_tact_adj) != (1.0, 1.0):
                factors_applied.append("tactical")
    except Exception:
        pass

    # 5. Head-to-Head
    h2h_w, h2h_d, h2h_l = 0, 0, 0
    try:
        for s in list_seasons(league):
            sr = load_all_season_results(league, s)
            if sr.empty:
                continue
            h2h = sr[
                ((sr["home_team"] == home_team) & (sr["away_team"] == away_team)) |
                ((sr["home_team"] == away_team) & (sr["away_team"] == home_team))
            ]
            for _, r in h2h.iterrows():
                is_h = r["home_team"] == home_team
                hs, aws = r["home_score"], r["away_score"]
                my = hs if is_h else aws
                opp = aws if is_h else hs
                if my > opp:
                    h2h_w += 1
                elif my == opp:
                    h2h_d += 1
                else:
                    h2h_l += 1
        context["h2h"] = {"wins": h2h_w, "draws": h2h_d, "losses": h2h_l}
        if h2h_w + h2h_d + h2h_l > 0:
            factors_applied.append("h2h")
    except Exception:
        context["h2h"] = {"wins": 0, "draws": 0, "losses": 0}

    # 6. Radar data — normalize against ALL league teams, then filter to selected pair
    try:
        folder_map = get_team_folder_map(league, season)
        all_radar = compute_team_radar_data(league, season, None)  # full league normalization
        # Filter to just the two selected teams (match by folder display name)
        home_radar_key = _nfc(folder_map.get(home_team, "").replace("_", " "))
        away_radar_key = _nfc(folder_map.get(away_team, "").replace("_", " "))
        radar_data = {}
        for key, vals in all_radar.items():
            if key == home_radar_key or key == away_radar_key:
                radar_data[key] = vals
        context["radar"] = radar_data
        context["radar_categories"] = RADAR_CATEGORIES
    except Exception:
        context["radar"] = {}
        context["radar_categories"] = []

    # ── Prediction ───────────────────────────────────────────────────
    pred = predict_match(
        attack[home_team], defense[home_team],
        attack[away_team], defense[away_team],
        home_xg_adj=home_xg_adj,
        away_xg_adj=away_xg_adj,
        home_elo_adj=home_elo_adj,
        away_elo_adj=away_elo_adj,
        home_tactical_adj=home_tact_adj,
        away_tactical_adj=away_tact_adj,
        home_form_att_adj=home_form_att,
        home_form_def_adj=home_form_def,
        away_form_att_adj=away_form_att,
        away_form_def_adj=away_form_def,
    )

    mc = monte_carlo_simulation(pred["home_lambda"], pred["away_lambda"], n_sims)

    # ── Data quality ─────────────────────────────────────────────────
    n_factors = len(set(factors_applied))
    if n_factors >= 4:
        quality = "full"
    elif n_factors >= 2:
        quality = "partial"
    else:
        quality = "minimal"

    context["factors_applied"] = factors_applied
    context["is_uefa"] = is_uefa

    return {
        "prediction": pred,
        "monte_carlo": mc,
        "context": context,
        "data_quality": quality,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Helper utilities
# ═══════════════════════════════════════════════════════════════════════════════

def _get_team_id(results: pd.DataFrame, standings: pd.DataFrame, team_name: str) -> str | None:
    """Resolve a team_id from results or standings."""
    # Try standings first (most authoritative)
    if standings is not None and not standings.empty and "team_id" in standings.columns:
        row = standings[standings["team_name"] == team_name]
        if not row.empty:
            return row.iloc[0]["team_id"]

    # Try results
    if "home_id" in results.columns:
        home_rows = results[results["home_team"] == team_name]
        if not home_rows.empty:
            return home_rows.iloc[0]["home_id"]
        away_rows = results[results["away_team"] == team_name]
        if not away_rows.empty:
            return away_rows.iloc[0]["away_id"]

        # Try aliases (e.g., "Manchester United FC" → "Manchester United")
        for alias in _team_name_aliases(team_name):
            home_rows = results[results["home_team"] == alias]
            if not home_rows.empty:
                return home_rows.iloc[0]["home_id"]
            away_rows = results[results["away_team"] == alias]
            if not away_rows.empty:
                return away_rows.iloc[0]["away_id"]

    return None


def _resolve_team_in_results(results: pd.DataFrame, team_name: str,
                             team_id: str | None = None) -> str:
    """Find the actual name used for a team in the results DataFrame.

    The team selector uses standings names (e.g., "Manchester United FC")
    but results from partidos/ may use shorter names ("Manchester United").
    This resolves the mismatch by checking team_id or aliases.
    """
    # Direct match
    if not results.empty:
        all_teams = set(results["home_team"]) | set(results["away_team"])
        if team_name in all_teams:
            return team_name

        # Try matching via team_id
        if team_id and "home_id" in results.columns:
            row = results[results["home_id"] == team_id]
            if not row.empty:
                return row.iloc[0]["home_team"]
            row = results[results["away_id"] == team_id]
            if not row.empty:
                return row.iloc[0]["away_team"]

        # Try aliases
        for alias in _team_name_aliases(team_name):
            if alias in all_teams:
                return alias

    return team_name  # fallback to original


def _get_form_string(results: pd.DataFrame, team: str, n: int = 5) -> list[str]:
    """Get last N results as list of 'W', 'D', 'L'."""
    team_m = results[
        (results["home_team"] == team) | (results["away_team"] == team)
    ].tail(n)

    form = []
    for _, r in team_m.iterrows():
        is_home = r["home_team"] == team
        my_score = r["home_score"] if is_home else r["away_score"]
        opp_score = r["away_score"] if is_home else r["home_score"]
        if my_score > opp_score:
            form.append("W")
        elif my_score == opp_score:
            form.append("D")
        else:
            form.append("L")
    return form


def _load_cross_competition_results(team_id: str, season: str) -> pd.DataFrame:
    """Load results from ALL competitions a team plays in for the same season.

    Returns a merged DataFrame sorted by date, with team names normalized
    to their result-file names. This enables cross-competition form analysis
    (e.g., last 5 games might span EPL + Europa League).
    """
    from data.loader import load_all_season_results, load_standings

    all_frames = []
    for comp_key in COMPETITIONS:
        try:
            standings = load_standings(comp_key, season)
            if standings.empty or "team_id" not in standings.columns:
                continue
            if team_id not in standings["team_id"].values:
                continue
            results = load_all_season_results(comp_key, season)
            if results.empty:
                continue
            results = results.copy()
            results["competition"] = comp_key
            all_frames.append(results)
        except Exception:
            continue

    if not all_frames:
        return pd.DataFrame()

    merged = pd.concat(all_frames, ignore_index=True)
    if "date" in merged.columns:
        merged["date"] = pd.to_datetime(merged["date"], errors="coerce")
        merged = merged.sort_values("date").reset_index(drop=True)
    return merged


def _resolve_team_across_comps(merged_results: pd.DataFrame,
                                team_id: str) -> list[str]:
    """Find all name variants for a team_id across competitions."""
    names = set()
    if "home_id" in merged_results.columns:
        home = merged_results[merged_results["home_id"] == team_id]["home_team"].unique()
        away = merged_results[merged_results["away_id"] == team_id]["away_team"].unique()
        names.update(home)
        names.update(away)
    return list(names)


def _get_cross_comp_form_string(team_id: str, season: str, n: int = 5) -> list[str]:
    """Get last N results across ALL competitions as 'W', 'D', 'L'."""
    merged = _load_cross_competition_results(team_id, season)
    if merged.empty:
        return []

    names = _resolve_team_across_comps(merged, team_id)
    if not names:
        return []

    # Filter to matches this team played in
    mask = pd.Series(False, index=merged.index)
    for name in names:
        mask |= (merged["home_team"] == name) | (merged["away_team"] == name)
    team_m = merged[mask].tail(n)

    form = []
    for _, r in team_m.iterrows():
        is_home = r["home_team"] in names
        my_score = r["home_score"] if is_home else r["away_score"]
        opp_score = r["away_score"] if is_home else r["home_score"]
        if my_score > opp_score:
            form.append("W")
        elif my_score == opp_score:
            form.append("D")
        else:
            form.append("L")
    return form


def compute_cross_comp_form_adjustment(team_id: str, season: str,
                                        window: int = FORM_WINDOW,
                                        decay: float = FORM_DECAY) -> tuple[float, float]:
    """Compute form adjustment using last N games across ALL competitions.

    Returns (attack_adj, defense_adj), each clamped to [0.85, 1.15].
    Falls back to (1.0, 1.0) if no cross-competition data.
    """
    merged = _load_cross_competition_results(team_id, season)
    if merged.empty:
        return (1.0, 1.0)

    names = _resolve_team_across_comps(merged, team_id)
    if not names:
        return (1.0, 1.0)

    mask = pd.Series(False, index=merged.index)
    for name in names:
        mask |= (merged["home_team"] == name) | (merged["away_team"] == name)
    all_team_m = merged[mask]
    recent = all_team_m.tail(window)

    if recent.empty or len(all_team_m) < 2:
        return (1.0, 1.0)

    n = len(recent)
    weights = np.array([decay ** (n - 1 - i) for i in range(n)])
    total_weight = weights.sum()

    scored, conceded = [], []
    for _, r in recent.iterrows():
        is_home = r["home_team"] in names
        scored.append(r["home_score"] if is_home else r["away_score"])
        conceded.append(r["away_score"] if is_home else r["home_score"])

    scored = np.array(scored, dtype=float)
    conceded = np.array(conceded, dtype=float)

    w_gs = np.dot(weights, scored) / total_weight
    w_gc = np.dot(weights, conceded) / total_weight

    # Season averages across all comps
    all_scored, all_conceded = [], []
    for _, r in all_team_m.iterrows():
        is_home = r["home_team"] in names
        all_scored.append(r["home_score"] if is_home else r["away_score"])
        all_conceded.append(r["away_score"] if is_home else r["home_score"])

    avg_gs = np.mean(all_scored) if all_scored else LEAGUE_AVG_GOALS_PER_TEAM
    avg_gc = np.mean(all_conceded) if all_conceded else LEAGUE_AVG_GOALS_PER_TEAM

    att_adj = w_gs / avg_gs if avg_gs > 0 else 1.0
    def_adj = avg_gc / w_gc if w_gc > 0 else 1.0

    return (
        float(np.clip(att_adj, 0.85, 1.15)),
        float(np.clip(def_adj, 0.85, 1.15)),
    )


def _empty_prediction() -> dict:
    """Return an empty prediction structure when data is insufficient."""
    return {
        "prediction": None,
        "monte_carlo": None,
        "context": {},
        "data_quality": "minimal",
    }
