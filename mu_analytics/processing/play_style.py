"""Rule-based play-style classification from player percentile stats."""

PLAY_STYLES = {
    "Playmaker": {
        "check": lambda r: r.get("PAS", 0) >= 75 and r.get("DRI", 0) >= 60,
        "desc": "Creative hub who dictates tempo and unlocks defenses",
        "icon": "🎯",
    },
    "Ball Winner": {
        "check": lambda r: r.get("DEF", 0) >= 75 and r.get("PHY", 0) >= 70,
        "desc": "Aggressive in winning possession and disrupting play",
        "icon": "🛡️",
    },
    "Target Man": {
        "check": lambda r: r.get("PHY", 0) >= 78 and r.get("SHO", 0) >= 60,
        "desc": "Dominant aerial presence and focal point of attacks",
        "icon": "🏋️",
    },
    "Box-to-Box": {
        "check": lambda r: r.get("DEF", 0) >= 55 and r.get("SHO", 0) >= 50 and r.get("PAS", 0) >= 55,
        "desc": "Covers every blade of grass, contributing at both ends",
        "icon": "🔄",
    },
    "Inverted Winger": {
        "check": lambda r: r.get("DRI", 0) >= 72 and r.get("SHO", 0) >= 65 and r.get("PAC", 0) >= 65,
        "desc": "Cuts inside from the wing to shoot or create",
        "icon": "↩️",
    },
    "Deep-Lying Playmaker": {
        "check": lambda r: r.get("PAS", 0) >= 78 and r.get("DEF", 0) >= 50,
        "desc": "Builds play from deep with vision and range",
        "icon": "📐",
    },
    "Poacher": {
        "check": lambda r: r.get("SHO", 0) >= 78 and r.get("PAC", 0) >= 60,
        "desc": "Lethal inside the box with clinical finishing",
        "icon": "⚡",
    },
    "Anchor": {
        "check": lambda r: r.get("DEF", 0) >= 72 and r.get("PAS", 0) >= 55 and r.get("PHY", 0) >= 65,
        "desc": "Shields the back line and recycles possession",
        "icon": "⚓",
    },
    "Speed Merchant": {
        "check": lambda r: r.get("PAC", 0) >= 80 and r.get("DRI", 0) >= 65,
        "desc": "Uses raw pace to stretch defenses and create space",
        "icon": "💨",
    },
    "Sweeper Keeper": {
        "check": lambda r: r.get("PAS", 0) >= 65 and r.get("PHY", 0) >= 70,
        "desc": "Commands the box and distributes effectively",
        "icon": "🧤",
    },
}


def classify_play_style(ratings: dict[str, float]) -> tuple[str, str, str]:
    """Classify a player's play style based on FC ratings.

    Args:
        ratings: dict with PAC, SHO, PAS, DRI, DEF, PHY values

    Returns:
        (style_name, description, icon)
    """
    for style, cfg in PLAY_STYLES.items():
        if cfg["check"](ratings):
            return style, cfg["desc"], cfg["icon"]

    return "Versatile", "Well-rounded player who contributes across multiple areas", "⭐"


def get_all_play_styles() -> dict:
    """Return all defined play style rules (for documentation)."""
    return {name: {"desc": cfg["desc"], "icon": cfg["icon"]}
            for name, cfg in PLAY_STYLES.items()}
