"""Pass network graph computation from successful passes."""

import pandas as pd
from data.event_parser import extract_passes


def build_pass_network(events: list[dict], team_id: str,
                       period: int | None = None,
                       min_passes: int = 3,
                       squad_roster: dict | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Build pass network nodes and edges from match events.

    Args:
        events: raw event list from match JSON
        team_id: team to analyze
        period: 1=first half, 2=second half, None=all
        min_passes: minimum passes for an edge to be included
        squad_roster: optional dict[player_id: {shirt_number, ...}] for shirt numbers

    Returns:
        (nodes_df, edges_df):
        nodes_df columns: player_id, player_name, avg_x, avg_y, total_passes[, shirt_number]
        edges_df columns: from_id, to_id, from_name, to_name, pass_count
    """
    passes = extract_passes(events, team_id=team_id, successful_only=True)
    if passes.empty:
        return pd.DataFrame(), pd.DataFrame()

    if period is not None:
        passes = passes[passes["period"] == period]

    if passes.empty:
        return pd.DataFrame(), pd.DataFrame()

    # Nodes: average position of each passer
    nodes = passes.groupby(["player_id", "player_name"]).agg(
        avg_x=("x", "mean"),
        avg_y=("y", "mean"),
        total_passes=("event_id", "count"),
    ).reset_index()

    # Add shirt numbers if roster provided
    if squad_roster:
        nodes["shirt_number"] = nodes["player_id"].map(
            lambda pid: squad_roster.get(pid, {}).get("shirt_number", "")
        )

    # Edges: passer -> receiver frequency
    pass_pairs = passes[passes["receiver_id"].notna()].copy()
    if pass_pairs.empty:
        return nodes, pd.DataFrame()

    edges = pass_pairs.groupby(["player_id", "receiver_id"]).agg(
        pass_count=("event_id", "count"),
    ).reset_index()
    edges = edges.rename(columns={"player_id": "from_id", "receiver_id": "to_id"})

    # Filter by minimum passes
    edges = edges[edges["pass_count"] >= min_passes]

    # Add player names to edges
    name_map = dict(zip(nodes["player_id"], nodes["player_name"]))
    edges["from_name"] = edges["from_id"].map(name_map).fillna("")
    edges["to_name"] = edges["to_id"].map(name_map).fillna("")

    return nodes, edges
