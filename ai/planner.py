"""High-level DQM3 synthesis planner.

The planner is an optimisation layer over the project's real synthesis
engine. It can:
  * solve a specified monster + talent set;
  * if no monster is specified, rank plausible final species by stats;
  * return several non-dominated solutions when possible;
  * account for owned monsters and wild exclusions;
  * produce an explainable score.
"""
from dataclasses import asdict
from .constraints import PlannerRequest
from .goals import PROFILES, normalize_goal
from .search import solve_candidate
from .scorer import score_tree, tree_metrics, tree_to_json

def _request_json(request):
    d = asdict(request)
    d["excluded_wild_ids"] = sorted(d["excluded_wild_ids"])
    d["owned_monster_ids"] = sorted(d["owned_monster_ids"])
    return d
from synthese_core import is_family_placeholder

class PlannerResult:
    def __init__(self, candidates, goal, request):
        self.candidates = candidates
        self.goal = goal
        self.request = request

    def to_dict(self):
        return {
            "goal": self.goal,
            "request": _request_json(self.request),
            "candidates": self.candidates,
        }

class DQM3Planner:
    def __init__(self, db):
        self.db = db

    def _candidate_species(self, goal, limit=30):
        weights = PROFILES[normalize_goal(goal)]
        monsters = [m for m in self.db.monsters if not is_family_placeholder(m)]
        # Score relative to dataset maxima, avoiding an arbitrary stat scale.
        maxima = {k: max([float(m.get(k) or 0) for m in monsters] or [1]) for k in weights}
        ranked = []
        for m in monsters:
            score = sum((float(m.get(k) or 0) / maxima[k]) * w for k,w in weights.items())
            ranked.append((score, m))
        ranked.sort(key=lambda x: x[0], reverse=True)
        return [m for _,m in ranked[:limit]]

    def plan(self, request: PlannerRequest):
        goal = normalize_goal(request.objective)
        reachable = __import__("synthese_core").get_reachable_location_ids(self.db, request.last_zone)
        excluded = set(request.excluded_wild_ids)
        candidates = []

        if request.target_monster:
            m = self.db.monster_by_name.get(request.target_monster.strip().lower())
            if not m:
                # allow exact ID as a convenience
                m = self.db.monster_by_id.get(request.target_monster.strip())
            species = [m] if m else []
        else:
            species = self._candidate_species(goal, limit=max(request.top_k * 8, 20))

        for monster in species:
            if not monster:
                continue
            root, final_ids, unknown, exhausted = solve_candidate(
                self.db, monster["MonsterId"], request.talents, reachable, request, excluded
            )
            if not root:
                continue
            score, metrics = score_tree(
                self.db, root,
                weights=self._weights_for(request, goal),
                owned_ids=frozenset(request.owned_monster_ids),
            )
            # For open-ended searches, the goal profile also matters.
            # We subtract a normalized combat-stat score so a powerful
            # candidate can beat an equally cheap but weak one.
            if not request.target_monster:
                score -= self._goal_power(monster, goal) * 5.0
            candidates.append({
                "monster_id": monster["MonsterId"],
                "monster": monster["FrenchName"] or monster["Name"],
                "score": round(score, 4),
                "metrics": metrics,
                "unknown_talents": unknown,
                "budget_exhausted": exhausted,
                "talents": [
                    self.db.talent_by_id[t]["Name"] for t in sorted(final_ids)
                    if t in self.db.talent_by_id
                ],
                "tree": tree_to_json(self.db, root),
            })

        candidates.sort(key=lambda x: x["score"])
        # Deduplicate equivalent metric solutions.
        seen = set()
        unique = []
        for c in candidates:
            key = (c["monster_id"], tuple(c["talents"]), c["metrics"]["syntheses"], c["metrics"]["wild_captures"])
            if key in seen:
                continue
            seen.add(key)
            unique.append(c)
        return PlannerResult(unique[:request.top_k], goal, request)

    def _goal_power(self, monster, goal):
        weights = PROFILES[normalize_goal(goal)]
        all_monsters = [m for m in self.db.monsters if not is_family_placeholder(m)]
        maxima = {k: max([float(m.get(k) or 0) for m in all_monsters] or [1.0]) for k in weights}
        return sum((float(monster.get(k) or 0) / maxima[k]) * w for k, w in weights.items())

    @staticmethod
    def _weights_for(request, goal):
        # User's explicit priorities can override the default profile.
        # Values are costs: higher means "care more".
        defaults = {
            "syntheses": 1.0,
            "wild_captures": 0.35,
            "unique_wild_species": 0.20,
            "deep_tree": 0.10,
            "owned_bonus": 1.50,
        }
        obj = normalize_goal(goal)
        if obj == "physical_dps":
            defaults.update({"syntheses": 1.0, "wild_captures": 0.25})
        elif obj == "mage":
            defaults.update({"syntheses": 1.0, "wild_captures": 0.25})
        defaults.update(request.stat_weights or {})
        return defaults
