"""Run batches of scenario cases and log them - the shared execution layer for every campaign."""
from __future__ import annotations

import numpy as np

from .config import driver_attributes, load_odd, param_range, scenario_param, validate_case
from .policy import LearnedACC
from .provenance import provenance
from .reference import ccd_preventable, ideal_preventable
from .sim import simulate
from .store import Store


class Campaign:
    def __init__(self, name: str, store: Store, policy: LearnedACC, budget: int,
                 seed: int = 0, fresh: bool = True, method: str = "manual",
                 sim_kwargs: dict | None = None):
        """`sim_kwargs` override modelling assumptions in `simulate()` (sensitivity analysis).
        They are not part of the provenance record, so use them only for throw-away stores."""
        self.name, self.store, self.policy, self.budget = name, store, policy, budget
        self.rng = np.random.default_rng(seed)
        self.sim_kwargs = sim_kwargs or {}
        if fresh:
            store.reset_campaign(name)
        store.register_campaign(name, method, budget, seed, provenance(policy))

    @property
    def used(self) -> int:
        return self.store.n_runs(self.name)

    @property
    def remaining(self) -> int:
        return self.budget - self.used

    def run(self, cases: list[dict]) -> list[dict]:
        """Validate, simulate and store cases. Stops silently when the budget is exhausted."""
        rows, start = [], self.used
        for case in cases:
            if start + len(rows) >= self.budget:
                break
            clean = validate_case(case)
            seed = int(self.rng.integers(2**31))
            metrics, _ = simulate(clean, self.policy, seed, **self.sim_kwargs)
            # A run the system avoided was, by definition, preventable. Only collisions are
            # replayed with the references (see avval/reference.py).
            avoided = not metrics["collision"]
            clean["initial_gap_m"] = clean["headway"] * clean["ego_speed"]
            rows.append({"campaign": self.name, "run_idx": start + len(rows), "seed": seed,
                         **clean, **driver_attributes(clean["driver_state"]), **metrics,
                         "preventable": avoided or ideal_preventable(clean),
                         "ccd_preventable": ccd_preventable(clean, avoided)})
        self.store.insert(rows)
        return rows


def random_case(rng: np.random.Generator) -> dict:
    p = load_odd()["parameters"]
    case = {k: str(rng.choice(p[k]["values"])) for k in ("scenario", "driver_state")}
    # Draw order is fixed (the scenario-specific parameter third) so a seed keeps giving the same cases.
    for k in ("ego_speed", "headway", scenario_param(case["scenario"]), "friction"):
        lo, hi = param_range(k, case["scenario"])
        case[k] = float(rng.uniform(lo, hi))
    return case
