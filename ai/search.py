"""Search helpers around the existing deterministic solver."""
from solver import solve, decompose_and_graft

def solve_candidate(db, monster_id, talents, reachable, request, excluded):
    root, final_ids, unknown, exhausted = solve(
        db,
        monster_id,
        talents,
        reachable,
        max_calls=request.max_calls,
        excluded_wild_ids=frozenset(excluded),
        include_eggs=request.include_eggs,
    )
    # The existing fallback is useful for deep multi-talent trees.
    if root is None and talents:
        root, assigned_ids, unassigned_ids = decompose_and_graft(
            db,
            monster_id,
            final_ids,
            reachable,
            frozenset(excluded),
            request.include_eggs,
        )
        if root is not None:
            final_ids = assigned_ids
            unknown = sorted(set(unknown) | set(unassigned_ids))
    return root, final_ids, unknown, exhausted
