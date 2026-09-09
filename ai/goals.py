"""Small deterministic goal profiles.

These profiles are intentionally conservative: they rank candidate final
monsters by their database stats, but never invent combat mechanics.
"""
PROFILES = {
    "physical_dps": {"MaxAtt": 1.0, "MaxAgi": 0.30, "MaxHP": 0.10},
    "mage": {"MaxWis": 1.0, "MaxMP": 0.35, "MaxAgi": 0.15},
    "tank": {"MaxHP": 1.0, "MaxDef": 0.80, "MaxMP": 0.10},
    "speed": {"MaxAgi": 1.0, "MaxAtt": 0.30, "MaxWis": 0.20},
    "balanced": {"MaxAtt": 0.35, "MaxWis": 0.35, "MaxHP": 0.20, "MaxDef": 0.20, "MaxAgi": 0.20},
}

def normalize_goal(goal):
    g = (goal or "balanced").strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "dps": "physical_dps",
        "physical": "physical_dps",
        "attacker": "physical_dps",
        "physique": "physical_dps",
        "mage_dps": "mage",
        "magic": "mage",
        "wisdom": "mage",
        "speed_dps": "speed",
    }
    return aliases.get(g, g if g in PROFILES else "balanced")

def stat_score(monster, weights):
    vals = {k: float(monster.get(k) or 0) for k in weights}
    # Normalize each stat by its max in the caller; this function assumes
    # normalized values when used externally.
    return sum(vals[k] * weight for k, weight in weights.items())
