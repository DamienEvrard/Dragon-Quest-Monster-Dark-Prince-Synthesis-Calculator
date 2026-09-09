# DQM3 Local AI Planner

This is a deterministic optimisation engine added on top of the existing
DQM3 synthesis calculator.

## Install

The current project only needs Flask:

```bash
pip install -r requirements.txt
```

No cloud API and no API key are required.

## CLI

From the project root:

```bash
python ai_cli.py --monster "Uberkilling Machine" --talent "Attack Booster IV"
```

Or let the planner choose a final species from the database:

```bash
python ai_cli.py --goal physical_dps --talent "Attack Booster IV" --top 5
```

Useful options:

* `--zone "..."` limits wild captures to the last explored location.
* `--owned MonsterId` tells the scorer that a monster is already owned.
* `--exclude MonsterId` forbids direct wild capture of that species.
* `--no-eggs` ignores egg-only fallback sources.
* `--max-calls 100000` gives the deterministic solver more search budget.

## Architecture

`solver.py` remains the authority for legal monster/talent synthesis.
`ai/` explores candidate final species and ranks legal trees.

The score is intentionally explainable:

* fewer syntheses = better;
* fewer wild captures = better;
* fewer unique wild species = better;
* shallower tree = slightly better;
* using already-owned monsters = better.

The result contains the full tree in JSON, so it can be rendered by the
existing Flask interface or another frontend.

## Important limitation

The "physical DPS", "mage", etc. profiles rank candidates using the stats
stored in `Monster.csv`. They do not pretend to know undocumented combat
formulas. Combat-specific intelligence can be added later as another scoring
layer without changing the legal synthesis engine.
