"""Compare search strategies across many seeds, not one campaign each.

A single campaign per strategy proves little: whether a 300-run random campaign stumbles
on a rare failure pocket is itself random. `benchmark` runs K campaigns per strategy
(named `<method>_s<k>`, seed k) and reports, across seeds, how fast failures are found,
how many distinct failing cells are found, and the *detection probability* of each
triggering-condition region: the share of seeds whose campaign contains at least one run
in that region. Detection probabilities carry a 95% Clopper-Pearson interval over seeds.

Strategies that stop early (the agent submits before its budget is spent) are also compared
at a matched budget: each other strategy's campaigns cut to their first N runs, N being the
mean number of runs the reference strategy used.
"""
from __future__ import annotations

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


def matched_budget(store, reference: str = "agent") -> int | None:
    """Mean number of runs the reference strategy's campaigns used (None if it has none)."""
    names = seed_campaigns(store, reference)
    return round(float(np.mean([store.n_runs(n) for n in names]))) if names else None


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
    n_match = matched_budget(store, reference) if reference in strategies else None
    matched = []
    if n_match is not None:
        cut = [s for s in (strategy_summary(store, st, n_match) for st in strategies
                           if st != reference) if s]
        matched = ["", f"## Matched budget: first {n_match} runs", "",
                   f"`{reference}` campaigns stop early; they used {n_match} runs on average. "
                   f"Here every other strategy's campaigns are cut to their first {n_match} runs "
                   f"and compared with the `{reference}` campaigns as they ran.", "",
                   _md_table(transposed(cut + [s for s in summaries
                                                if s["strategy"] == reference]),
                             max_rows=len(full))]
    lines = [
        "# Search-strategy benchmark", "",
        "Each strategy is run once per seed with the same budget. Detection probability is the "
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
