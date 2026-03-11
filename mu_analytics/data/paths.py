"""Path builder for the europa/ directory structure."""

from pathlib import Path
from config import DATA_ROOT


def league_dir(league: str) -> Path:
    return DATA_ROOT / league


def season_dir(league: str, season: str) -> Path:
    return DATA_ROOT / league / season


def jsons_dir(league: str, season: str) -> Path:
    return DATA_ROOT / league / season / "jsons"


def partidos_dir(league: str, season: str) -> Path:
    return DATA_ROOT / league / season / "partidos"


def equipos_dir(league: str, season: str) -> Path:
    return DATA_ROOT / league / season / "equipos"


def team_dir(league: str, season: str, team_folder: str) -> Path:
    return DATA_ROOT / league / season / "equipos" / team_folder


def team_jsons_dir(league: str, season: str, team_folder: str) -> Path:
    return DATA_ROOT / league / season / "equipos" / team_folder / "jsons"


def seasons_csv(league: str) -> Path:
    return DATA_ROOT / league / f"{league}_seasons.csv"


def equipos_csv(league: str, season: str) -> Path:
    return DATA_ROOT / league / season / f"{league}_{season}_equipos.csv"


def matches_ids_csv(league: str, season: str) -> Path:
    return DATA_ROOT / league / season / "matches_ids.csv"


def jugadores_csv(league: str, season: str, team_folder: str) -> Path:
    return team_dir(league, season, team_folder) / f"{team_folder}_jugadores.csv"


def jugadores_seasonstats_csv(league: str, season: str, team_folder: str) -> Path:
    return team_dir(league, season, team_folder) / f"{team_folder}_jugadores_seasonstats.csv"


def find_match_file(league: str, season: str, match_id: str) -> Path | None:
    """Find a match JSON file by its match ID in the partidos directory."""
    pdir = partidos_dir(league, season)
    if not pdir.exists():
        return None
    for f in pdir.iterdir():
        if f.suffix == ".json" and match_id in f.name:
            return f
    return None


def list_match_files(league: str, season: str) -> list[Path]:
    """List all match JSON files in partidos directory."""
    pdir = partidos_dir(league, season)
    if not pdir.exists():
        return []
    return sorted(f for f in pdir.iterdir() if f.suffix == ".json")


def list_team_folders(league: str, season: str) -> list[str]:
    """List all team folder names in equipos directory."""
    edir = equipos_dir(league, season)
    if not edir.exists():
        return []
    return sorted(d.name for d in edir.iterdir() if d.is_dir())


def list_seasons(league: str) -> list[str]:
    """List available season folders for a league, newest first."""
    ldir = league_dir(league)
    if not ldir.exists():
        return []
    seasons = []
    for d in ldir.iterdir():
        if d.is_dir() and "-" in d.name and d.name[0].isdigit():
            seasons.append(d.name)
    return sorted(seasons, reverse=True)
