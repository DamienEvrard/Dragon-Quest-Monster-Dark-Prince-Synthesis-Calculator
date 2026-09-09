"""Scoring utilities for synthesis trees.

No generative model is involved here. A score is a transparent weighted sum
so the user can understand why one tree beats another.
"""
from collections import Counter

DEFAULT_WEIGHTS = {
    "syntheses": 1.0,
    "wild_captures": 0.35,
    "unique_wild_species": 0.20,
    "deep_tree": 0.10,
    "owned_bonus": 1.50,
    "talent_bonus": 0.0,
}

def _walk(node):
    if not node:
        return
    yield node
    yield from _walk(node.get("parent1"))
    yield from _walk(node.get("parent2"))

def tree_metrics(db, root, owned_ids=frozenset()):
    nodes = list(_walk(root))
    synth_nodes = [n for n in nodes if n.get("kind") == "synth"]
    wild_nodes = [n for n in nodes if n.get("kind") == "wild"]
    wild_ids = [n.get("monster_id") for n in wild_nodes]
    unique_wild = set(wild_ids)
    owned_used = sum(1 for x in wild_ids if x in owned_ids)

    def depth(n):
        if not n:
            return 0
        return 1 + max(depth(n.get("parent1")), depth(n.get("parent2")))

    return {
        "syntheses": len(synth_nodes),
        "wild_captures": len(wild_nodes),
        "unique_wild_species": len(unique_wild),
        "owned_used": owned_used,
        "depth": depth(root),
        "nodes": len(nodes),
    }

def score_tree(db, root, weights=None, owned_ids=frozenset()):
    w = dict(DEFAULT_WEIGHTS)
    if weights:
        w.update(weights)
    m = tree_metrics(db, root, owned_ids)
    # Lower is better.
    score = (
        w["syntheses"] * m["syntheses"]
        + w["wild_captures"] * m["wild_captures"]
        + w["unique_wild_species"] * m["unique_wild_species"]
        + w["deep_tree"] * m["depth"]
        - w["owned_bonus"] * m["owned_used"]
    )
    return score, m

def _json_safe(value):
    if isinstance(value, set) or isinstance(value, frozenset):
        return [_json_safe(v) for v in sorted(value, key=str)]
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    return value

def tree_to_json(db, node):
    if not node:
        return None
    out = {
        "kind": node.get("kind"),
        "monster_id": node.get("monster_id"),
        "name": node.get("name"),
        "cost": node.get("cost"),
        "recommended_level": node.get("recommended_level"),
        "capture_locations": node.get("capture_locations", []),
        "required_talents": [
            db.talent_by_id[t]["Name"]
            for t in sorted(node.get("required_talents", []))
            if t in db.talent_by_id
        ],
        "native_talents": [
            db.talent_by_id[t]["Name"]
            for t in sorted(node.get("native_talents", []))
            if t in db.talent_by_id
        ],
        "transitions": _json_safe(node.get("transitions", [])),
        "parent1": tree_to_json(db, node.get("parent1")),
        "parent2": tree_to_json(db, node.get("parent2")),
    }
    return out
