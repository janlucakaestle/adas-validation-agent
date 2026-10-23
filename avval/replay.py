"""Replay stored runs: re-simulate a stored row from its case and per-run seed.

Used for hand-back diagnostics (traces are not stored) and for the machine-verified
compatibility check (avval/compat.py): a stored campaign is compatible with a release only
if re-simulating every run under that release reproduces every stored column exactly.
"""
from __future__ import annotations

import math

from .config import SCENARIO_PARAMS, Release, driver_attributes
from .reference import References
from .sim import simulate

CASE_KEYS = ("scenario", "ego_speed", "headway", "friction", "driver_state")


def case_of(row: dict) -> dict:
    case = {k: row[k] for k in CASE_KEYS}
    own = SCENARIO_PARAMS[row["scenario"]]
    case[own] = float(row[own])
    for k in SCENARIO_PARAMS.values():
        case.setdefault(k, None)
    return case


def replay(row: dict, policy, release: Release, refs: References | None = None
           ) -> tuple[dict, object]:
    """(re-simulated stored row, trace) for a stored row under `release`."""
    case = case_of(row)
    metrics, trace = simulate(case, policy, int(row["seed"]), release.sim_params)
    refs = refs or References(release)
    out = {"campaign": row["campaign"], "run_idx": int(row["run_idx"]), "seed": int(row["seed"]),
           **case, "initial_gap_m": case["headway"] * case["ego_speed"],
           **driver_attributes(case["driver_state"], release.odd), **refs.evaluate(case),
           **metrics}
    return out, trace


def same_value(a, b) -> bool:
    none_a = a is None or (isinstance(a, float) and math.isnan(a))
    none_b = b is None or (isinstance(b, float) and math.isnan(b))
    if none_a or none_b:
        return none_a and none_b
    if isinstance(a, (bool,)) or isinstance(b, (bool,)):
        return bool(a) == bool(b)
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return float(a) == float(b)
    return a == b
