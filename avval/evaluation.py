"""Acceptance criteria, coverage and failure accounting - all computed in SQL over a campaign."""
from __future__ import annotations

import itertools
import operator

import numpy as np
import pandas as pd
from scipy import stats

from .config import load_acceptance, load_odd
from .store import Store

_OPS = {"<=": operator.le, ">=": operator.ge, "<": operator.lt, ">": operator.gt,
        "==": operator.eq}


INSUFFICIENT = "INSUFFICIENT EVIDENCE"
NO_FAILURES = "NO FAILURES OBSERVED"
VERDICTS = ("GO", "NO-GO", INSUFFICIENT)
PASSING = ("PASS", NO_FAILURES)
CONFIDENCE = 0.95
BOOTSTRAP_RESAMPLES = 2000
BOOTSTRAP_SEED = 0  # fixed, so a report is reproducible from the stored runs
BOOTSTRAP_CHUNK_ELEMENTS = 5_000_000  # values per bootstrap chunk (about 40 MB)


def clopper_pearson(k: int, n: int, confidence: float = CONFIDENCE) -> tuple[float, float]:
    """Exact two-sided binomial interval for k events in n trials.

    With k = 0 the upper bound is 1 - (alpha/2)^(1/n), about 3.7/n at 95%. That is the
    two-sided version of the "rule of three" (3/n is the one-sided 95% bound).
    """
    if n <= 0:
        raise ValueError("n must be positive")
    alpha = 1 - confidence
    lo = 0.0 if k == 0 else float(stats.beta.ppf(alpha / 2, k, n - k + 1))
    hi = 1.0 if k == n else float(stats.beta.ppf(1 - alpha / 2, k + 1, n - k))
    return lo, hi


def _quantile(x: np.ndarray, q, axis=None):
    """np.quantile (linear, the same definition as DuckDB's quantile_cont), with +inf allowed:
    interpolating between two infinite values gives nan, which here means +inf."""
    with np.errstate(invalid="ignore"):
        out = np.quantile(x, q, axis=axis)
    return np.where(np.isnan(out), np.inf, out)


def bootstrap_quantile_ci(x, q: float, confidence: float = CONFIDENCE,
                          n_resamples: int = BOOTSTRAP_RESAMPLES,
                          seed: int = BOOTSTRAP_SEED) -> tuple[float, float]:
    """Percentile-bootstrap interval for the q-quantile of x, reproducible via `seed`.

    Resamples are drawn in chunks of about BOOTSTRAP_CHUNK_ELEMENTS values, so memory stays
    bounded for large campaigns. The random stream is consumed in the same order as one
    (n_resamples, n) draw, so the result doesn't depend on the chunk size.
    """
    x = np.asarray(x, dtype=float)
    rng = np.random.default_rng(seed)
    rows = max(1, BOOTSTRAP_CHUNK_ELEMENTS // max(len(x), 1))
    boot = np.concatenate([
        _quantile(x[rng.integers(0, len(x), size=(min(rows, n_resamples - start), len(x)))],
                  q, axis=1)
        for start in range(0, n_resamples, rows)])
    alpha = 1 - confidence
    return float(_quantile(boot, alpha / 2)), float(_quantile(boot, 1 - alpha / 2))


def value_sql(c: dict) -> str:
    """The criterion's value as a SQL aggregate (for display and ad-hoc queries)."""
    if c["kind"] == "rate":
        return f"avg(CAST(({c['event']}) AS INTEGER))"
    return f"quantile_cont({c['metric']}, {c['q']})"


def _measure(store: Store, campaign: str, c: dict) -> dict:
    where = f"WHERE {c['where']}" if c.get("where") else ""
    if c["kind"] == "rate":
        row = store.query(f"SELECT count(CAST(({c['event']}) AS INTEGER)) AS n, "
                          f"sum(CAST(({c['event']}) AS INTEGER)) AS k FROM runs {where}",
                          campaign).iloc[0]
        n, k = int(row["n"]), (0 if pd.isna(row["k"]) else int(row["k"]))
        if n == 0:
            return {"n": 0, "k": 0, "value": None, "ci_low": None, "ci_high": None}
        lo, hi = clopper_pearson(k, n)
        return {"n": n, "k": k, "value": k / n, "ci_low": lo, "ci_high": hi}
    if c["kind"] == "quantile":
        x = store.query(f"SELECT x FROM (SELECT ({c['metric']}) AS x FROM runs {where}) "
                        "WHERE x IS NOT NULL", campaign, max_rows=10**9)["x"].to_numpy(float)
        if len(x) == 0:
            return {"n": 0, "value": None, "ci_low": None, "ci_high": None}
        lo, hi = bootstrap_quantile_ci(x, c["q"])
        return {"n": len(x), "value": float(_quantile(x, c["q"])), "ci_low": lo, "ci_high": hi}
    raise ValueError(f"{c['id']}: unknown kind {c['kind']!r} (expected rate or quantile)")


def _status(c: dict, m: dict) -> tuple[str, str]:
    """(status, note) for one criterion given its measurement."""
    op, thr, n, min_n = c.get("op"), c.get("threshold"), m["n"], c.get("min_n", 0)
    if op is None:
        return "INFO", ""
    if n == 0:
        return INSUFFICIENT, "no data"
    check = _OPS[op]
    if not check(m["value"], thr):
        return "FAIL", ""
    if c["kind"] == "rate" and op == "<=" and thr == 0:  # zero target: k == 0 here
        note = (f"no failures observed in {n} runs; 95% upper bound = {m['ci_high']:.4g}. "
                "A zero-rate target can be falsified, not proven, by testing.")
        if n < min_n:
            return INSUFFICIENT, f"n = {n} < min_n = {min_n}; " + note
        return NO_FAILURES, note
    if n < min_n:
        return INSUFFICIENT, f"n = {n} < min_n = {min_n}"
    side, bound = ("upper", m["ci_high"]) if op in ("<=", "<") else ("lower", m["ci_low"])
    if not check(bound, thr):
        return INSUFFICIENT, (f"point estimate meets the threshold, but the 95% {side} bound "
                              f"{bound:.4g} does not")
    return "PASS", ""


def evaluate_acceptance(store: Store, campaign: str) -> list[dict]:
    """Evaluate every criterion, with a 95% interval. Status is one of:

    PASS                  the point estimate AND the conservative end of the 95% interval
                          (upper bound for "<=", lower bound for ">=") meet the threshold,
                          on at least `min_n` runs;
    NO FAILURES OBSERVED  a zero-rate target ("rate <= 0") with no events in >= min_n runs.
                          It cannot be proven by testing, so the 95% upper bound is reported
                          instead of a PASS. It counts as passing for the verdict;
    FAIL                  the point estimate misses the threshold (at any n: an observed
                          exceedance is evidence against release, and downgrading it would
                          only weaken a NO-GO);
    INSUFFICIENT EVIDENCE no data, fewer than `min_n` runs, or the point estimate passes but
                          the interval does not;
    INFO                  informational (no op/threshold), never affects the verdict.
    """
    results = []
    for c in load_acceptance()["criteria"]:
        m = _measure(store, campaign, c)
        status, note = _status(c, m)
        results.append({"id": c["id"], "name": c["name"], "kind": c["kind"],
                        "value": m["value"], "ci_low": m["ci_low"], "ci_high": m["ci_high"],
                        "op": c.get("op"), "threshold": c.get("threshold"), "n": m["n"],
                        "min_n": c.get("min_n", 0), "status": status, "note": note})
    return results


def overall_verdict(results: list[dict]) -> str:
    """NO-GO if any criterion FAILs; GO only if every gating criterion passes (PASS or NO
    FAILURES OBSERVED); otherwise INSUFFICIENT EVIDENCE. INFO criteria never count."""
    gating = [r["status"] for r in results if r["status"] != "INFO"]
    if "FAIL" in gating:
        return "NO-GO"
    if all(s in PASSING for s in gating):
        return "GO"
    return INSUFFICIENT


def failure_predicate() -> str:
    return load_acceptance()["failure_predicate"]


TARGETS = ("failure",)  # "nuisance_braking" is planned (docs/roadmap.md)


def target_predicate(target: str) -> str:
    if target == "failure":
        return failure_predicate()
    raise ValueError(f"unknown target {target!r}; available: {list(TARGETS)}")


def predicate_stats(store: Store, campaign: str, where: str, target: str = "failure") -> dict:
    """How well a candidate triggering condition (a SQL WHERE clause over `runs`) concentrates
    the target: runs and target rate inside and outside it, the lift (inside rate / outside
    rate) and a 95% Clopper-Pearson interval on the inside rate. Runs where the condition is
    NULL count as outside. The statement goes through the read-only guard and sandbox."""
    cond = f"coalesce(({where}), false)"
    tgt = target_predicate(target)
    row = store.query(
        f"SELECT count(*) FILTER (WHERE {cond}) AS n_in, "
        f"count(*) FILTER (WHERE NOT {cond}) AS n_out, "
        f"count(*) FILTER (WHERE {cond} AND ({tgt})) AS k_in, "
        f"count(*) FILTER (WHERE NOT {cond} AND ({tgt})) AS k_out FROM runs", campaign).iloc[0]
    n_in, n_out, k_in, k_out = (int(row[k]) for k in ("n_in", "n_out", "k_in", "k_out"))
    rate_in = k_in / n_in if n_in else None
    rate_out = k_out / n_out if n_out else None
    lift = (rate_in / rate_out if rate_in is not None and rate_out else None)
    lo, hi = clopper_pearson(k_in, n_in) if n_in else (None, None)
    return {"where": where, "target": target, "runs_inside": n_in, "runs_outside": n_out,
            "target_rate_inside": rate_in, "target_rate_outside": rate_out, "lift": lift,
            "inside_rate_ci95": [lo, hi]}


def _bin_index(value: float, edges: list[float]) -> int:
    return int(np.clip(np.searchsorted(edges, value, side="right") - 1, 0, len(edges) - 2))


def _bins(scenario: str) -> dict:
    """Bin edges for one scenario: the shared parameters plus its scenario-specific one."""
    return load_odd()["coverage"]["bins"][scenario]


def cell_of(case: dict) -> tuple:
    bins = _bins(case["scenario"])
    return (case["scenario"],) + tuple(_bin_index(case[k], bins[k]) for k in bins)


def all_cells() -> list[tuple]:
    cells = []
    for s in load_odd()["parameters"]["scenario"]["values"]:
        bins = _bins(s)
        cells += [(s,) + idx for idx in itertools.product(*(range(len(e) - 1) for e in bins.values()))]
    return cells


def describe_cell(cell: tuple) -> dict:
    bins = _bins(cell[0])
    out = {"scenario": cell[0]}
    for k, i in zip(bins, cell[1:]):
        out[k] = [bins[k][i], bins[k][i + 1]]
    return out


def coverage(store: Store, campaign: str) -> dict:
    df = store.campaign_df(campaign)
    need = load_odd()["coverage"]["min_runs_per_cell"]
    counts: dict[tuple, int] = {}
    for rec in df.to_dict("records"):
        counts[cell_of(rec)] = counts.get(cell_of(rec), 0) + 1
    cells = all_cells()
    uncovered = [c for c in cells if counts.get(c, 0) < need]
    return {"cells_total": len(cells), "cells_covered": len(cells) - len(uncovered),
            "fraction": 1 - len(uncovered) / len(cells), "uncovered": uncovered}


def failure_curve(store: Store, campaign: str) -> pd.DataFrame:
    """Cumulative failing runs and distinct failing coverage cells vs. number of runs."""
    df = store.query(f"SELECT *, ({failure_predicate()}) AS failed FROM runs ORDER BY run_idx",
                     campaign, max_rows=10**9)
    seen: set = set()
    distinct, fails = [], 0
    for rec in df.to_dict("records"):
        if rec["failed"]:
            fails += 1
            seen.add(cell_of(rec))
        distinct.append(len(seen))
    return pd.DataFrame({"runs": np.arange(1, len(df) + 1),
                         "failures": np.cumsum(df["failed"].astype(int)) if len(df) else [],
                         "distinct_failing_cells": distinct})
