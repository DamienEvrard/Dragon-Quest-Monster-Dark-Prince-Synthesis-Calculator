"""User-facing constraints for the planner."""
from dataclasses import dataclass, field

@dataclass
class PlannerRequest:
    target_monster: str = ""
    talents: list[str] = field(default_factory=list)
    last_zone: str = ""
    excluded_wild_ids: set[str] = field(default_factory=set)
    owned_monster_ids: set[str] = field(default_factory=set)
    include_eggs: bool = True
    max_calls: int = 30000
    top_k: int = 5
    objective: str = "balanced"
    # Optional stat priorities used when target_monster is omitted.
    stat_weights: dict[str, float] = field(default_factory=dict)
