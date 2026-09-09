"""AI / optimisation layer for the DQM3 synthesis calculator.

The layer is deliberately deterministic: the existing synthesis rules remain
the source of truth. This package explores and ranks legal solutions.
"""
from .planner import DQM3Planner, PlannerRequest, PlannerResult
