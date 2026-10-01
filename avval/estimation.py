"""Estimation campaigns: measure failure rates on an exposure-weighted sample of the ODD.

Search campaigns (random, grid, agent) choose where to look, so their failure rates reflect
the search strategy, not the real world: an agent that concentrates near failure boundaries
looks worse precisely because it searched well. They therefore report discovery metrics and
triggering conditions only. Acceptance criteria and release verdicts are computed on an
estimation campaign sampled from `config/exposure.yaml`, and only on one whose provenance
(policy, config, code) matches the release being judged.
"""
from __future__ import annotations

import numpy as np

from .campaign import Campaign
from .config import (CATEGORICAL, CONTINUOUS, SCENARIO_PARAMS, load_exposure, load_odd,
                     param_range, scenario_param)
from .evaluation import evaluate_acceptance, overall_verdict
from .provenance import provenance, same_release

METHOD = "estimate"


def check_exposure(exp: dict, odd: dict) -> None:
    params = odd["parameters"]
    for key in CATEGORICAL:
        if set(exp[key]) != set(params[key]["values"]):
            raise ValueError(f"exposure.yaml: {key} weights must cover exactly "
                             f"{params[key]['values']}")
        if not np.isclose(sum(exp[key].values()), 1.0):
            raise ValueError(f"exposure.yaml: {key} weights must sum to 1")
    for key, scen, hist in _histograms(exp):
        bins, weights = hist["bins"], hist["weights"]
        lo, hi = param_range(key, scen)
        name = f"{key}.{scen}" if "ranges" in params[key] else key
        if len(weights) != len(bins) - 1 or not np.isclose(sum(weights), 1.0):
            raise ValueError(f"exposure.yaml: {name} needs one weight per bin, summing to 1")
        if bins[0] < lo or bins[-1] > hi or any(np.diff(bins) <= 0):
            raise ValueError(f"exposure.yaml: {name} bins must be increasing and inside "
                             f"[{lo}, {hi}]")


def _histograms(exp: dict):
    """(parameter, scenario, histogram) for every continuous parameter in exposure.yaml."""
    for scen, own in SCENARIO_PARAMS.items():
        for key in (*CONTINUOUS, own):
            hist = exp[key]
            yield key, scen, (hist[scen] if scen in hist else hist)


def _hist(exp: dict, key: str, scenario: str) -> dict:
    return exp[key][scenario] if scenario in exp[key] else exp[key]


def sample_case(rng: np.random.Generator) -> dict:
    """One case drawn from the exposure distribution."""
    exp = load_exposure()
    case = {k: str(rng.choice(list(exp[k]), p=list(exp[k].values()))) for k in CATEGORICAL}
    for key in ("ego_speed", "headway", scenario_param(case["scenario"]), "friction"):
        hist = _hist(exp, key, case["scenario"])
        bins, weights = hist["bins"], hist["weights"]
        i = rng.choice(len(weights), p=weights)
        case[key] = float(rng.uniform(bins[i], bins[i + 1]))
    return case


def run_estimation(store, policy, n: int, seed: int = 0, name: str = METHOD,
                   sim_kwargs: dict | None = None, method: str = METHOD) -> Campaign:
    """Sample n cases from the exposure model and run them. The same (n, seed) always gives
    the same cases and per-run seeds, so variants with different `sim_kwargs` are paired."""
    check_exposure(load_exposure(), load_odd())
    camp = Campaign(name, store, policy, n, seed=seed, method=method, sim_kwargs=sim_kwargs)
    camp.run([sample_case(camp.rng) for _ in range(n)])
    return camp


def find_estimation(store, policy) -> str | None:
    """Most recent estimation campaign recorded for the same release as now (same policy
    weights, config files, source code and package versions; see `same_release`), or None."""
    current = provenance(policy)
    rows = store.con.execute("SELECT name FROM campaigns WHERE method = ? "
                             "ORDER BY created DESC", [METHOD]).fetchall()
    for (name,) in rows:
        regs = store.campaign_info(name)
        if (store.n_runs(name) > 0
                and all(same_release(r["provenance"], current) for r in regs)):
            return name
    return None


MISSING_HELP = ("No estimation campaign matches the current policy, config and code "
                "(provenance). Run `python -m avval.cli estimate --n 2000 --seed 0` first. "
                "Acceptance criteria are evaluated only on an exposure-weighted estimation "
                "campaign, never on a search campaign.")


def release_verdict(store, policy) -> dict:
    """The release verdict for the current release, from its estimation campaign.

    Used by code and reports only; the search agent never sees it (TASKS4:T37).
    """
    est = find_estimation(store, policy)
    if est is None:
        raise LookupError(MISSING_HELP)
    acc = evaluate_acceptance(store, est)
    return {"estimation_campaign": est, "estimation_runs": store.n_runs(est),
            "verdict": overall_verdict(acc), "criteria": acc}
