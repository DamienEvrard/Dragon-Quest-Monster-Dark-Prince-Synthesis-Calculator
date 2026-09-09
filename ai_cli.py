#!/usr/bin/env python3
"""Command line interface for the local DQM3 AI planner.

Examples:
  python ai_cli.py --monster "Uberkilling Machine" --talent "Attack Booster IV" --talent "Critical Mastery"
  python ai_cli.py --goal physical_dps --talent "Attack Booster IV" --top 5
"""
import argparse, json
from synthese_core import Database
from ai import DQM3Planner, PlannerRequest

def main():
    p = argparse.ArgumentParser(description="DQM3 local synthesis AI planner")
    p.add_argument("--monster", default="")
    p.add_argument("--goal", default="balanced", choices=["balanced","physical_dps","mage","tank","speed"])
    p.add_argument("--talent", action="append", default=[])
    p.add_argument("--zone", default="")
    p.add_argument("--exclude", action="append", default=[], help="MonsterId to exclude as a wild capture")
    p.add_argument("--owned", action="append", default=[], help="MonsterId already owned")
    p.add_argument("--top", type=int, default=5)
    p.add_argument("--max-calls", type=int, default=30000)
    p.add_argument("--no-eggs", action="store_true")
    args = p.parse_args()

    db = Database()
    result = DQM3Planner(db).plan(PlannerRequest(
        target_monster=args.monster,
        talents=args.talent,
        last_zone=args.zone,
        excluded_wild_ids=set(args.exclude),
        owned_monster_ids=set(args.owned),
        include_eggs=not args.no_eggs,
        top_k=args.top,
        max_calls=args.max_calls,
        objective=args.goal,
    ))
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
