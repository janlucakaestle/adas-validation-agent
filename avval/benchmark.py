"""Compare search strategies across many seeds, not one campaign each.

A single campaign per strategy proves little: whether a 300-run random campaign stumbles
on a rare failure pocket is itself random. `benchmark` runs K campaigns per strategy
(named `<method>_s<k>`, seed k) and reports, across seeds, how fast failures are found,
how many distinct failing cells are found, and the *detection probability* of each
triggering-condition region: the share of seeds whose campaign contains at least one run
in that region. Detection probabilities carry a 95% Clopper-Pearson interval over seeds.

Strategies that stop early (the agent submits before its budget is spent) are also compared
at a matched budget, per seed: for each reference campaign that used n runs, every baseline
campaign is cut to its first n runs. Across the reference seeds, the baselines' detection
probabilities at those budgets give the number of detections a baseline would be expected
to make, and the probability that it would make at least as many as the reference did
(Poisson-binomial, treating the baseline probabilities as known).
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from . import RESULTS_DIR
from .evaluation import clopper_pearson, failure_curve

# Triggering-condition regions, as SQL predicates over `runs`. A seed "detects" a region if
# its campaign contains at least one run matching the predicate.
REGIONS = {
    "attentive_preventable_collision":
        "collision AND preventable AND driver_state = 'attentive'",
    "misuse_handback_collision":
        "collision AND preventable AND tor_issued AND driver_category = 'foreseeable_misuse'",
    # The monitor hands back on constant-speed TTC < 2 s, so plain TTC can never erode unseen.
    # Acceleration-aware TTC can: it drops below the monitor's own 2 s with no hand-back.
    "silent_margin_erosion":
        "NOT collision AND NOT tor_issued AND min_ttc_accel < 2.0",
    "comfort_exceedance":     # filtered jerk above the AC-04 threshold without a hand-back
        "NOT tor_issued AND max_jerk > 5.0",
}


def seed_campaigns(store, strategy: str) -> list[str]:
    """Campaigns of a strategy: `<strategy>_s<k>` if any exist, else `<strategy>` itself."""
    names = [r[0] for r in store.con.execute(
        "SELECT DISTINCT campaign FROM all_runs WHERE regexp_matches(campaign, ?) "
        "ORDER BY campaign", [f"^{strategy}_s[0-9]+$"]).fetchall()]
    names.sort(key=lambda n: int(n.rsplit("_s", 1)[1]))
    if names:
        return names
    return [strategy] if store.n_runs(strategy) else []


def campaign_stats(store, campaign: str, max_runs: int | None = None) -> dict:
    """Discovery metrics of one campaign, or of its first `max_runs` runs only."""
    curve = failure_curve(store, campaign)
    if max_runs is not None:
        curve = curve.iloc[:max_runs]
    first = curve.loc[curve["failures"] > 0, "runs"].min() if len(curve) else np.nan
    limit = "" if max_runs is None else f" WHERE run_idx < {int(max_runs)}"
    found = store.query("SELECT " + ", ".join(
        f"count(*) FILTER (WHERE {pred}) > 0 AS {name}" for name, pred in REGIONS.items())
        + " FROM runs" + limit, campaign).iloc[0]
    return {"campaign": campaign, "runs": len(curve),
            "first_failure": float(first) if pd.notna(first) else np.nan,
            "distinct_failing_cells": int(curve["distinct_failing_cells"].iloc[-1])
            if len(curve) else 0,
            **{name: bool(found[name]) for name in REGIONS}}


def strategy_summary(store, strategy: str, max_runs: int | None = None) -> dict | None:
    names = seed_campaigns(store, strategy)
    if not names:
        return None
    df = pd.DataFrame([campaign_stats(store, n, max_runs) for n in names])
    ff = df["first_failure"].dropna()
    return {"strategy": strategy, "seeds": len(df), "runs_per_seed": int(df["runs"].median()),
            "first_failure_mean": ff.mean() if len(ff) else np.nan,
            "first_failure_sd": ff.std(ddof=1) if len(ff) > 1 else np.nan,
            "seeds_with_failure": len(ff),
            "distinct_cells_mean": df["distinct_failing_cells"].mean(),
            "distinct_cells_sd": df["distinct_failing_cells"].std(ddof=1) if len(df) > 1
            else np.nan,
            **{f"P({name})": df[name].mean() for name in REGIONS},
            **{f"P({name})_ci": clopper_pearson(int(df[name].sum()), len(df)) for name in REGIONS},
            "per_seed": df}


def _pm(mean, sd, digits=1) -> str:
    if pd.isna(mean):
        return "-"
    return f"{mean:.{digits}f}" + ("" if pd.isna(sd) else f" ± {sd:.{digits}f}")


def _p_ci(summary: dict, name: str) -> str:
    lo, hi = summary[f"P({name})_ci"]
    return f"{summary[f'P({name})']:.2f} [{lo:.2f}, {hi:.2f}]"


def campaign_profile(store, campaign: str) -> dict:
    """Failure curve and, per region, the index of the first run in it (inf if none), so any
    prefix of the campaign can be scored without re-querying."""
    first = store.query("SELECT " + ", ".join(
        f"min(run_idx) FILTER (WHERE {pred}) AS {name}" for name, pred in REGIONS.items())
        + " FROM runs", campaign).iloc[0]
    return {"curve": failure_curve(store, campaign),
            "first_idx": {name: float(first[name]) if pd.notna(first[name]) else np.inf
                          for name in REGIONS}}


def _cells_at(profile: dict, n: int) -> int:
    curve = profile["curve"]
    return int(curve["distinct_failing_cells"].iloc[min(n, len(curve)) - 1]) if len(curve) else 0


def at_least(probs: list[float], k: int) -> float:
    """P(at least k successes) for independent Bernoulli trials with these probabilities."""
    dist = np.zeros(len(probs) + 1)
    dist[0] = 1.0
    for p in probs:
        dist[1:] = dist[1:] * (1 - p) + dist[:-1] * p
        dist[0] *= 1 - p
    return float(dist[k:].sum())


def _usage(campaign: str) -> dict:
    path = RESULTS_DIR / f"usage_{campaign}.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def matched_per_seed(store, reference: str = "agent", baselines=("random", "grid"),
                     region: str = "attentive_preventable_collision") -> dict | None:
    """Per reference seed: its runs used, turns, cost and outcome, and each baseline's
    detection probability and failing cells at that seed's own number of runs."""
    ref = seed_campaigns(store, reference)
    base = {b: [campaign_profile(store, c) for c in seed_campaigns(store, b)] for b in baselines}
    base = {b: profs for b, profs in base.items() if profs}
    if not ref or not base:
        return None
    rows = []
    for name in ref:
        prof, n = campaign_profile(store, name), store.n_runs(name)
        use = _usage(name)
        row = {"campaign": name, "runs": n, "turns": use.get("api_calls"),
               "cost_usd": use.get("est_cost_usd"),
               "detected": bool(np.isfinite(prof["first_idx"][region])),
               "cells": _cells_at(prof, n)}
        for b, profs in base.items():
            k = sum(p["first_idx"][region] < n for p in profs)
            row[f"{b}_p"] = k / len(profs)
            row[f"{b}_ci"] = clopper_pearson(k, len(profs))
            row[f"{b}_cells"] = float(np.mean([_cells_at(p, n) for p in profs]))
        rows.append(row)
    df = pd.DataFrame(rows)
    hits = int(df["detected"].sum())
    return {"per_seed": df, "region": region, "detected": hits, "seeds": len(df),
            "ci": clopper_pearson(hits, len(df)),
            "baselines": {b: {"seeds": len(base[b]), "expected": float(df[f"{b}_p"].sum()),
                              "p_at_least": at_least(df[f"{b}_p"].tolist(), hits)}
                          for b in base}}


def _prob(p: float) -> str:
    return f"{p:.3f}" if p >= 0.001 else f"{p:.1e}"


def matched_lines(m: dict) -> list[str]:
    from .report import _md_table
    df, bases = m["per_seed"], list(m["baselines"])
    rows = [{"seed": r["campaign"], "runs used": r["runs"],
             "turns": "-" if pd.isna(r["turns"]) else int(r["turns"]),
             "cost": "-" if pd.isna(r["cost_usd"]) else f"${r['cost_usd']:.2f}",
             "found": "yes" if r["detected"] else "no",
             **{f"{b}: P(found) at same runs": f"{r[f'{b}_p']:.2f} [{r[f'{b}_ci'][0]:.2f}, "
                                               f"{r[f'{b}_ci'][1]:.2f}]" for b in bases},
             "failing cells": r["cells"],
             **{f"{b}: cells": f"{r[f'{b}_cells']:.1f}" for b in bases}}
            for r in df.to_dict("records")]
    lo, hi = m["ci"]
    lines = ["## Matched budget, per seed", "",
             f"Region: `{m['region']}`. Each agent seed is compared with every baseline campaign "
             "cut to the same number of runs the seed used. Baseline probabilities are shares "
             "of their campaigns, with 95% Clopper-Pearson intervals.", "",
             _md_table(pd.DataFrame(rows), max_rows=len(rows)), "",
             f"**Agent:** found the region in {m['detected']} of {m['seeds']} seeds "
             f"({m['detected'] / m['seeds']:.2f} [{lo:.2f}, {hi:.2f}]).",
             "Mean distinct failing cells at each seed's own budget: agent "
             f"{df['cells'].mean():.1f}, "
             + ", ".join(f"{b} {df[f'{b}_cells'].mean():.1f}" for b in bases) + ".", ""]
    for b, st in m["baselines"].items():
        lines.append(f"- **{b}** ({st['seeds']} campaigns) at the same per-seed budgets: "
                     f"{st['expected']:.2f} detections expected out of {m['seeds']}; probability "
                     f"of at least {m['detected']}: {_prob(st['p_at_least'])}.")
    return lines + [""]


def summary_table(summaries: list[dict]) -> pd.DataFrame:
    rows = []
    for s in summaries:
        rows.append({
            "strategy": s["strategy"], "seeds": s["seeds"], "runs/seed": s["runs_per_seed"],
            "runs to first failure (mean ± SD)":
                f"{_pm(s['first_failure_mean'], s['first_failure_sd'])} "
                f"({s['seeds_with_failure']}/{s['seeds']} seeds found one)",
            "distinct failing cells (mean ± SD)":
                _pm(s["distinct_cells_mean"], s["distinct_cells_sd"]),
            **{f"P(detect {name}) [95% CI]": _p_ci(s, name) for name in REGIONS}})
    return pd.DataFrame(rows)


def write_benchmark(store, strategies: list[str], reference: str = "agent"
                    ) -> tuple[str, list[dict]]:
    """Write results/benchmark.md (tables) and results/discovery_curves.png (figure)."""
    from .plots import discovery_curves
    from .report import _md_table

    def transposed(summaries):
        table = summary_table(summaries).set_index("strategy").T
        return table.reset_index().rename(columns={"index": "metric"})

    summaries = [s for s in (strategy_summary(store, st) for st in strategies) if s]
    full = transposed(summaries)
    matched = []
    if reference in strategies:
        m = matched_per_seed(store, reference, [st for st in strategies if st != reference])
        if m is not None:
            matched = ["", *matched_lines(m)]
    lines = [
        "# Search-strategy benchmark", "",
        "Each strategy is run once per seed with the same budget (the agent may stop "
        "early). Detection probability is the "
        "share of seeds whose campaign contains at least one run in the region "
        "(`avval/benchmark.py::REGIONS`). Runs to first failure is averaged over the seeds "
        "that found a failure.", "",
        _md_table(full, max_rows=len(full)), *matched, "",
        "![Discovery curves](discovery_curves.png)", "",
        "## Regions", "",
        *[f"- `{name}`: `{pred}`" for name, pred in REGIONS.items()], ""]
    (RESULTS_DIR / "benchmark.md").write_text("\n".join(lines), encoding="utf-8")
    discovery_curves(store, {s["strategy"]: seed_campaigns(store, s["strategy"])
                             for s in summaries})
    return str(RESULTS_DIR / "benchmark.md"), summaries
