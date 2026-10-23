"""Acceptance criteria, coverage and discovery accounting - computed in SQL over a campaign.

Statistical method (acceptance/v3):
- Rates: exact ONE-SIDED Clopper-Pearson bounds at the configured confidence c: the
  upper bound is the c-quantile of Beta(k + 1, n - k), the lower bound the (1 - c)-quantile
  of Beta(k, n - k + 1). With k = 0 the upper bound is 1 - (1 - c)^(1/n) (about 3/n at 95%,
  the "rule of three").
- Quantiles: exact distribution-free order-statistic bounds. For the q-quantile, the
  one-sided lower bound is X_(r) with the largest r such that P(Binomial(n, q) >= r) >= c,
  and the upper bound X_(s) with the smallest s such that P(Binomial(n, q) <= s - 1) >= c.
  Coverage is at least c for any continuous distribution (conservative with ties), for
  every n; when no order statistic qualifies (n too small) the bound is unavailable and the
  criterion cannot PASS. No resampling, so results are exactly reproducible.
- Point estimates: the observed rate k / n; quantiles with linear interpolation (DuckDB's
  quantile_cont definition).

Status rules: see config/acceptance.yaml. Populations of gating criteria may use only
SCENARIO_COLUMNS (checked by `check_acceptance`), so the system under test cannot change a
denominator by acting differently.
"""
from __future__ import annotations

import itertools
import math
import operator
import re

import numpy as np
import pandas as pd
from scipy import stats

from .config import load_acceptance, load_discovery, load_odd, load_reference
from .store import COLUMNS, Store

_OPS = {"<=": operator.le, ">=": operator.ge}

INSUFFICIENT = "INSUFFICIENT EVIDENCE"
VERDICTS = ("GO", "NO-GO", INSUFFICIENT, "DECISION PENDING REQUIREMENTS")
STATUSES = ("PASS", "FAIL", INSUFFICIENT, "NO REQUIREMENT", "INFO")
DEFAULT_CONFIDENCE = 0.95

# Columns whose values are fixed by the scenario (inputs and reference replays), not by the
# system's behaviour in the run nor by its design parameters (the hand-back oracle uses a
# fixed capability). Gating populations and strata may use only these.
SCENARIO_COLUMNS = ("scenario", "ego_speed", "headway", "initial_gap_m", "lead_decel",
                    "closing_speed", "friction", "driver_state", "driver_category",
                    "hazard_onset_s", "avoidable_by_reference", "handback_required",
                    "ccd_avoidable_by_reference")
OUTPUT_COLUMNS = tuple(c for c in COLUMNS if c not in SCENARIO_COLUMNS
                       and c not in ("campaign", "run_idx", "seed"))
_STRIP = re.compile(r"'(?:[^']|'')*'")


def columns_used(sql: str | None) -> set[str]:
    """Stored column names referenced in an SQL expression (outside string literals)."""
    if not sql:
        return set()
    return set(re.findall(r"[A-Za-z_][A-Za-z0-9_]*", _STRIP.sub(" ", sql))) & set(COLUMNS)


# ---------------------------------------------------------------- bounds
def clopper_pearson_upper(k: int, n: int, confidence: float = DEFAULT_CONFIDENCE) -> float:
    """Exact one-sided upper confidence bound for a binomial rate."""
    if n <= 0:
        raise ValueError("n must be positive")
    return 1.0 if k >= n else float(stats.beta.ppf(confidence, k + 1, n - k))


def clopper_pearson_lower(k: int, n: int, confidence: float = DEFAULT_CONFIDENCE) -> float:
    """Exact one-sided lower confidence bound for a binomial rate."""
    if n <= 0:
        raise ValueError("n must be positive")
    return 0.0 if k <= 0 else float(stats.beta.ppf(1 - confidence, k, n - k + 1))


def clopper_pearson(k: int, n: int, confidence: float = 0.95) -> tuple[float, float]:
    """Exact TWO-SIDED interval at `confidence` (each tail (1 - confidence) / 2). Used for
    descriptive intervals (benchmark, predicates), never for acceptance decisions."""
    tail = 1 - (1 - confidence) / 2
    return clopper_pearson_lower(k, n, tail), clopper_pearson_upper(k, n, tail)


def rate_n_needed(threshold: float, confidence: float = DEFAULT_CONFIDENCE) -> int:
    """Smallest n at which zero events give a one-sided upper bound <= threshold."""
    return int(math.ceil(math.log(1 - confidence) / math.log(1 - threshold)))


def quantile_bound_indices(n: int, q: float, confidence: float = DEFAULT_CONFIDENCE
                           ) -> tuple[int | None, int | None]:
    """1-based order-statistic ranks (r, s) of the one-sided lower and upper bounds of the
    q-quantile, or None where no order statistic attains the confidence."""
    ranks = np.arange(1, n + 1)
    lower = ranks[stats.binom.sf(ranks - 1, n, q) >= confidence]   # P(B >= r) >= c
    upper = ranks[stats.binom.cdf(ranks - 1, n, q) >= confidence]  # P(B <= s - 1) >= c
    return (int(lower.max()) if len(lower) else None), (int(upper.min()) if len(upper) else None)


def quantile_n_needed(q: float, side: str, confidence: float = DEFAULT_CONFIDENCE) -> int:
    """Smallest n at which the one-sided order-statistic bound exists."""
    p = (1 - q) if side == "lower" else q
    return int(math.ceil(math.log(1 - confidence) / math.log(p)))


def quantile_bounds(x, q: float, confidence: float = DEFAULT_CONFIDENCE
                    ) -> tuple[float | None, float | None]:
    xs = np.sort(np.asarray(x, dtype=float))
    r, s = quantile_bound_indices(len(xs), q, confidence)
    return (None if r is None else float(xs[r - 1])), (None if s is None else float(xs[s - 1]))


def _quantile(x: np.ndarray, q, axis=None):
    """np.quantile (linear, the same definition as DuckDB's quantile_cont), with +inf allowed:
    interpolating between two infinite values gives nan, which here means +inf."""
    with np.errstate(invalid="ignore"):
        out = np.quantile(x, q, axis=axis)
    return np.where(np.isnan(out), np.inf, out)


# ---------------------------------------------------------------- requirement status
REQUIREMENT_STATUSES = ("approved", "provisional", "illustrative", "undefined")  # best first
NO_REQUIREMENT = "NO REQUIREMENT"
PENDING = "DECISION PENDING REQUIREMENTS"
# Scenario columns whose meaning depends on a definition with its own approval status
# (config/reference.yaml): a criterion using them is at most as approved as that definition.
DEFINITION_STATUS = {"avoidable_by_reference": ("ideal", "status"),
                     "handback_required": ("handback_oracle", "status"),
                     "ccd_avoidable_by_reference": ("careful_competent_driver", "status")}


def weakest(statuses) -> str:
    """The least mature status of a collection (unknown or missing = 'undefined')."""
    ranks = [REQUIREMENT_STATUSES.index(s) if s in REQUIREMENT_STATUSES
             else len(REQUIREMENT_STATUSES) - 1 for s in statuses]
    return REQUIREMENT_STATUSES[max(ranks)] if ranks else "undefined"


def requirement_sources(c, reference) -> dict[str, str]:
    """{source: status}: the criterion's own requirement status and that of every definition
    its population or strata depend on."""
    out = {f"{c['id']}.requirement_status": c.get("requirement_status", "undefined")}
    used = columns_used(expand(c, "where")) | set(c.get("strata") or [])
    for col in sorted(used & set(DEFINITION_STATUS)):
        block, key = DEFINITION_STATUS[col]
        out[f"reference.{block}.{key}"] = (reference.get(block) or {}).get(key, "undefined")
    return out


def expand(c, field: str) -> str | None:
    """A criterion's SQL field with its named `params` substituted ({name} -> value)."""
    sql = c.get(field)
    if not sql:
        return sql
    params = dict(c.get("params") or {})
    names = set(re.findall(r"\{([A-Za-z_][A-Za-z0-9_]*)\}", sql))
    missing = names - set(params)
    if missing:
        raise ValueError(f"{c['id']}: {field} uses undefined params {sorted(missing)}")
    for k in names:
        sql = sql.replace("{" + k + "}", repr(float(params[k])))
    if "{" in sql or "}" in sql:
        raise ValueError(f"{c['id']}: {field} has an unresolved placeholder")
    return sql


# ---------------------------------------------------------------- configuration checks
def check_acceptance(acc) -> None:
    """Fail-closed validation of acceptance.yaml (called for every release)."""
    conf = float(acc.get("confidence", DEFAULT_CONFIDENCE))
    if not 0.5 < conf < 1:
        raise ValueError("acceptance.yaml: confidence must lie in (0.5, 1)")
    ids = [c["id"] for c in acc["criteria"]]
    if len(ids) != len(set(ids)):
        raise ValueError("acceptance.yaml: criterion IDs must be unique")
    retired = {c["id"] for c in acc.get("retired_criteria", [])}
    if retired & set(ids):
        raise ValueError(f"acceptance.yaml: retired IDs reused: {sorted(retired & set(ids))}")
    for c in acc["criteria"]:
        cid, kind, op = c["id"], c["kind"], c.get("op")
        if kind not in ("rate", "quantile"):
            raise ValueError(f"{cid}: unknown kind {kind!r}")
        for name, v in dict(c.get("params") or {}).items():
            if not isinstance(v, (int, float)) or isinstance(v, bool) or not math.isfinite(v):
                raise ValueError(f"{cid}: param {name} must be a finite number")
        expr = expand(c, "event") if kind == "rate" else expand(c, "metric")
        if not expr:
            raise ValueError(f"{cid}: a {kind} criterion needs " +
                             ("`event`" if kind == "rate" else "`metric`"))
        if kind == "quantile" and not 0 < float(c["q"]) < 1:
            raise ValueError(f"{cid}: q must lie in (0, 1)")
        used = columns_used(expand(c, "where")) | set(c.get("strata") or [])
        conditional = sorted(used - set(SCENARIO_COLUMNS))
        if op is None:  # INFO
            if conditional and not c.get("conditional_on_system_output"):
                raise ValueError(f"{cid}: its population uses system outputs {conditional}; "
                                 "declare conditional_on_system_output: true")
            continue
        if op not in _OPS:
            raise ValueError(f"{cid}: op must be one of {sorted(_OPS)}")
        if conditional:
            raise ValueError(f"{cid}: a gating criterion's population and strata may use only "
                             f"scenario columns, not system outputs {conditional} (otherwise "
                             "the system's behaviour changes its own denominator)")
        if c.get("conditional_on_system_output"):
            raise ValueError(f"{cid}: a gating criterion cannot be conditional on outputs")
        status = c.get("requirement_status")
        if status not in REQUIREMENT_STATUSES:
            raise ValueError(f"{cid}: requirement_status must be one of {REQUIREMENT_STATUSES} "
                             "(approval is never inferred)")
        thr = c.get("threshold")
        if status == "undefined":
            if thr is not None or c.get("zero_goal"):
                raise ValueError(f"{cid}: an undefined requirement has no threshold or zero goal")
        else:
            if not isinstance(thr, (int, float)) or not math.isfinite(thr):
                raise ValueError(f"{cid}: threshold must be a finite number")
            if kind == "rate" and not 0 < thr < 1:
                raise ValueError(f"{cid}: a gating rate threshold must lie strictly between 0 "
                                 "and 1. A zero rate cannot be certified from a finite sample; "
                                 "use a positive tolerable rate (and `zero_goal: true`)")
        if c.get("zero_goal") and not (kind == "rate" and op == "<="):
            raise ValueError(f"{cid}: zero_goal applies only to '<=' rate criteria")
        if not isinstance(c.get("min_n"), int) or c["min_n"] < 1:
            raise ValueError(f"{cid}: min_n must be a positive integer")


# ---------------------------------------------------------------- measurement
def value_sql(c: dict) -> str:
    """The criterion's value as a SQL aggregate (for display and ad-hoc queries)."""
    if c["kind"] == "rate":
        return f"avg(CAST(({expand(c, 'event')}) AS INTEGER))"
    return f"quantile_cont({expand(c, 'metric')}, {c['q']})"


def _fetch(q, c: dict) -> pd.DataFrame:
    """Per-run values of the criterion (event 0/1 or metric) with stratum columns; `q` is a
    sandboxed query function (Store.session)."""
    strata = list(c.get("strata") or [])
    where = f"WHERE {expand(c, 'where')}" if c.get("where") else ""
    expr = (f"CAST(({expand(c, 'event')}) AS INTEGER)" if c["kind"] == "rate"
            else f"({expand(c, 'metric')})")
    cols = ", ".join([f"{expr} AS x", *strata])
    df = q(f"SELECT {cols} FROM runs {where}", max_rows=10**9)
    if df["x"].isna().any():
        raise ValueError(f"{c['id']}: its {'event' if c['kind'] == 'rate' else 'metric'} is "
                         "NULL for some runs; define it for every run (fail-closed)")
    return df


def _measure(x: np.ndarray, c: dict, conf: float) -> dict:
    n = len(x)
    if n == 0:
        return {"n": 0, "k": None, "value": None, "lower": None, "upper": None}
    if c["kind"] == "rate":
        k = int(x.sum())
        return {"n": n, "k": k, "value": k / n, "lower": clopper_pearson_lower(k, n, conf),
                "upper": clopper_pearson_upper(k, n, conf)}
    lo, hi = quantile_bounds(x, float(c["q"]), conf)
    return {"n": n, "k": None, "value": float(_quantile(x.astype(float), float(c["q"]))),
            "lower": lo, "upper": hi}


def _decide(c: dict, m: dict, conf: float) -> tuple[str, str, bool]:
    """(status, note, demonstrated) for one population: the engineering comparison."""
    op, thr, n, min_n = c.get("op"), c.get("threshold"), m["n"], c.get("min_n", 1)
    if op is None:
        return "INFO", "", False
    if thr is None:
        return NO_REQUIREMENT, "no target is defined: statistics only", False
    if n == 0:
        return INSUFFICIENT, "no data", False
    check = _OPS[op]
    pct = f"{conf:.0%}"
    if c.get("zero_goal") and m["k"]:
        return "FAIL", (f"zero goal falsified: {m['k']} event(s) observed. An observed event "
                        "cannot be erased by additional event-free runs."), True
    bound_side = "upper" if op == "<=" else "lower"
    other_side = "lower" if op == "<=" else "upper"
    if not check(m["value"], thr):
        other = m[other_side]
        demonstrated = other is not None and not check(other, thr)
        how = (f"the one-sided {pct} {other_side} bound {other:.4g} also violates it, so the "
               "exceedance is demonstrated" if demonstrated else
               f"the exceedance is not demonstrated at {pct} (one-sided {other_side} bound "
               f"{'unavailable' if other is None else f'{other:.4g}'})")
        return "FAIL", f"point estimate {m['value']:.4g} violates {op} {thr:g}; {how}", demonstrated
    if n < min_n:
        return INSUFFICIENT, f"n = {n} < min_n = {min_n}", False
    bound = m[bound_side]
    if bound is None:
        need = quantile_n_needed(float(c["q"]), bound_side, conf)
        return INSUFFICIENT, (f"no {pct} one-sided {bound_side} bound exists at n = {n} "
                              f"(needs n >= {need})"), False
    if not check(bound, thr):
        return INSUFFICIENT, (f"point estimate meets the threshold, but the one-sided {pct} "
                              f"{bound_side} bound {bound:.4g} does not"), False
    return "PASS", "", False


def _robustness(c: dict, status: str, demonstrated: bool, conf: float) -> str:
    if status != "FAIL":
        return ""
    if c.get("zero_goal") and demonstrated:
        return ("Permanent under the zero goal: observed events cannot be erased by more "
                "successful runs.")
    if demonstrated:
        return ("Existing evidence is already sufficient for this criterion under the current "
                "simulator, models and acceptance rules: additional IID sampling of the "
                "unchanged release is unlikely to reverse it (the opposite one-sided "
                f"{conf:.0%} bound already violates the threshold).")
    return ("Not yet demonstrated: further runs of the unchanged release could move the point "
            "estimate back across the threshold.")


def _combine(statuses: list[str]) -> str:
    if "FAIL" in statuses:
        return "FAIL"
    if NO_REQUIREMENT in statuses:
        return NO_REQUIREMENT
    if statuses and all(s == "PASS" for s in statuses):
        return "PASS"
    return INSUFFICIENT


def _stratum_domain(col: str):
    """All values a stratum column can take, or None if unknown."""
    params = load_odd()["parameters"]
    if "values" in params.get(col, {}):
        return list(params[col]["values"])
    if col == "driver_category":
        return sorted({st["category"] for st in params["driver_state"]["states"].values()})
    if col in ("avoidable_by_reference", "handback_required"):
        return [False, True]
    return None


def evaluate_criterion(store: Store, campaign: str, c: dict, conf: float,
                       reference=None, q=None) -> dict:
    if q is None:
        with store.session(campaign) as q2:
            return evaluate_criterion(store, campaign, c, conf, reference, q2)
    df = _fetch(q, c)
    x = df["x"].to_numpy(float)
    m = _measure(x, c, conf)
    status, note, demonstrated = _decide(c, m, conf)
    strata_rows = []
    strata = list(c.get("strata") or [])
    if strata and c.get("op") is not None:
        statuses = [status]
        for key, g in df.groupby(strata, dropna=False, sort=True):
            key = key if isinstance(key, tuple) else (key,)
            key = tuple(bool(k) if isinstance(k, (bool, np.bool_)) else k for k in key)
            sm = _measure(g["x"].to_numpy(float), c, conf)
            st, sn, sd = _decide(c, sm, conf)
            statuses.append(st)
            demonstrated = demonstrated or (st == "FAIL" and sd)
            strata_rows.append({"stratum": dict(zip(strata, key)), **sm, "status": st,
                                "note": sn})
        # a stratum with no runs at all is missing evidence, not a pass
        domains = [_stratum_domain(col) for col in strata]
        if all(d is not None for d in domains):
            seen = {tuple(r["stratum"].values()) for r in strata_rows}
            for combo in itertools.product(*domains):
                if combo not in seen:
                    st = NO_REQUIREMENT if c.get("threshold") is None else INSUFFICIENT
                    statuses.append(st)
                    strata_rows.append({"stratum": dict(zip(strata, combo)), "n": 0, "k": None,
                                        "value": None, "lower": None, "upper": None,
                                        "status": st, "note": "no data"})
        combined = _combine(statuses)
        if combined != status:
            bad = [r["stratum"] for r in strata_rows if r["status"] == combined]
            note = (note + "; " if note else "") + f"decided by stratum {bad}"
        status = combined
    need = None
    if c.get("op") is not None and c.get("threshold") is not None:
        need = (rate_n_needed(c["threshold"], conf) if c["kind"] == "rate" else
                quantile_n_needed(float(c["q"]), "upper" if c["op"] == "<=" else "lower", conf))
    gating = c.get("op") is not None
    sources = requirement_sources(c, reference if reference is not None else
                                  load_reference()) if gating else {}
    effective = weakest(sources.values()) if gating else None
    return {"id": c["id"], "name": c["name"], "kind": c["kind"], **m,
            "op": c.get("op"), "threshold": c.get("threshold"), "min_n": c.get("min_n"),
            "params": dict(c.get("params") or {}),
            "n_needed": need, "confidence": conf, "zero_goal": bool(c.get("zero_goal")),
            "conditional": bool(c.get("conditional_on_system_output")),
            "status": status, "note": note, "demonstrated": demonstrated,
            "requirement_status": c.get("requirement_status") if gating else None,
            "requirement_sources": sources, "effective_requirement_status": effective,
            "supports_formal_go": bool(gating and status == "PASS" and effective == "approved"),
            "robustness": _robustness(c, status, demonstrated, conf), "strata": strata_rows}


def evaluate_acceptance(store: Store, campaign: str, acceptance=None,
                        reference=None) -> list[dict]:
    """Evaluate every criterion on one campaign. Engineering status per criterion: PASS /
    FAIL / INSUFFICIENT EVIDENCE / NO REQUIREMENT / INFO; plus requirement maturity."""
    acc = acceptance or load_acceptance()
    check_acceptance(acc)
    conf = float(acc.get("confidence", DEFAULT_CONFIDENCE))
    ref = reference if reference is not None else load_reference()
    with store.session(campaign) as q:
        return [evaluate_criterion(store, campaign, c, conf, ref, q) for c in acc["criteria"]]


def overall_verdict(results: list[dict]) -> str:
    """Engineering verdict with requirement maturity (fail closed):

    NO-GO                          any gating criterion FAILs (also against a provisional or
                                   illustrative target: an observed violation is evidence
                                   against release);
    INSUFFICIENT EVIDENCE          otherwise, any gating criterion is insufficient;
    DECISION PENDING REQUIREMENTS  otherwise, any gating criterion has no target or an
                                   effective requirement status other than `approved` (a
                                   missing status counts as not approved);
    GO                             every gating criterion PASSes against an approved
                                   requirement.
    A formal release decision additionally needs final evidence (`release_decision`)."""
    gating = [r for r in results if r["status"] != "INFO"]
    statuses = [r["status"] for r in gating]
    if "FAIL" in statuses:
        return "NO-GO"
    if INSUFFICIENT in statuses or not gating:
        return INSUFFICIENT
    if any(r["status"] != "PASS" or r.get("effective_requirement_status") != "approved"
           for r in gating):
        return PENDING
    return "GO"


def release_decision(results: list[dict], evidence_mode: str) -> dict:
    """The three reported layers: the engineering verdict, whether the requirements allow a
    formal decision, and the formal decision (only for final evidence)."""
    verdict = overall_verdict(results)
    gating = [r for r in results if r["status"] != "INFO"]
    unapproved = [r["id"] for r in gating
                  if r.get("effective_requirement_status") != "approved"]
    formal = verdict if evidence_mode == "final" else "NONE (development run, not evidence)"
    return {"engineering_verdict": verdict, "unapproved_requirements": unapproved,
            "requirements_approved": not unapproved, "evidence_mode": evidence_mode,
            "formal_decision": formal}


# ---------------------------------------------------------------- discovery targets
def discovery_targets() -> dict:
    return {k: dict(v) for k, v in load_discovery()["targets"].items()}


TARGETS = tuple(load_discovery()["targets"])


def target_predicate(target: str) -> str:
    targets = load_discovery()["targets"]
    if target not in targets:
        raise ValueError(f"unknown target {target!r}; available: {list(targets)}")
    return targets[target]["predicate"]


def default_target() -> str:
    return load_discovery()["default_target"]


def predicate_stats(store: Store, campaign: str, where: str, target: str | None = None,
                    columns: tuple | None = None) -> dict:
    """How well a candidate triggering condition (a SQL WHERE clause over `runs`) concentrates
    a discovery target: runs and target rate inside and outside it, the lift (inside rate /
    outside rate) and a 95% two-sided Clopper-Pearson interval on the inside rate. Runs where
    the condition is NULL count as outside. Runs through the read-only guard and sandbox
    (restricted to `columns` when given)."""
    if not where or not where.strip():
        raise ValueError("the predicate is empty")
    target = target or default_target()
    cond = f"coalesce(({where}), false)"
    tgt = target_predicate(target)
    row = store.query(
        f"SELECT count(*) FILTER (WHERE {cond}) AS n_in, "
        f"count(*) FILTER (WHERE NOT {cond}) AS n_out, "
        f"count(*) FILTER (WHERE {cond} AND ({tgt})) AS k_in, "
        f"count(*) FILTER (WHERE NOT {cond} AND ({tgt})) AS k_out FROM runs", campaign,
        columns=columns).iloc[0]
    n_in, n_out, k_in, k_out = (int(row[k]) for k in ("n_in", "n_out", "k_in", "k_out"))
    rate_in = k_in / n_in if n_in else None
    rate_out = k_out / n_out if n_out else None
    lift = (rate_in / rate_out if rate_in is not None and rate_out else None)
    lo, hi = clopper_pearson(k_in, n_in) if n_in else (None, None)
    return {"where": where, "target": target, "runs_inside": n_in, "runs_outside": n_out,
            "target_rate_inside": rate_in, "target_rate_outside": rate_out, "lift": lift,
            "inside_rate_ci95": [lo, hi]}


# ---------------------------------------------------------------- coverage
def _bin_index(value: float, edges: list[float]) -> int:
    return int(np.clip(np.searchsorted(edges, value, side="right") - 1, 0, len(edges) - 2))


def _bins(scenario: str, odd=None) -> dict:
    """Bin edges for one scenario: the shared parameters plus its scenario-specific one."""
    return {k: list(v) for k, v in (odd or load_odd())["coverage"]["bins"][scenario].items()}


def coverage_dimensions(odd=None) -> list[str]:
    return list((odd or load_odd())["coverage"]["categorical_dimensions"])


def cell_of(case: dict, odd=None) -> tuple:
    dims = coverage_dimensions(odd)
    bins = _bins(case["scenario"], odd)
    return tuple(case[d] for d in dims) + tuple(_bin_index(case[k], bins[k]) for k in bins)


def all_cells(odd=None) -> list[tuple]:
    odd = odd or load_odd()
    dims = coverage_dimensions(odd)
    params = odd["parameters"]
    cells = []
    for cat in itertools.product(*(list(params[d]["values"]) for d in dims)):
        bins = _bins(cat[dims.index("scenario")], odd)
        cells += [cat + idx for idx in itertools.product(*(range(len(e) - 1)
                                                           for e in bins.values()))]
    return cells


def describe_cell(cell: tuple, odd=None) -> dict:
    dims = coverage_dimensions(odd)
    out = dict(zip(dims, cell[:len(dims)]))
    bins = _bins(out["scenario"], odd)
    for k, i in zip(bins, cell[len(dims):]):
        out[k] = [bins[k][i], bins[k][i + 1]]
    return out


def coverage(store: Store, campaign: str, odd=None) -> dict:
    odd = odd or load_odd()
    df = store.campaign_df(campaign)
    need = odd["coverage"]["min_runs_per_cell"]
    counts: dict[tuple, int] = {}
    for rec in df.to_dict("records"):
        c = cell_of(rec, odd)
        counts[c] = counts.get(c, 0) + 1
    cells = all_cells(odd)
    uncovered = [c for c in cells if counts.get(c, 0) < need]
    excluded = dict(odd["coverage"].get("excluded_dimensions", {}))
    return {"cells_total": len(cells), "cells_covered": len(cells) - len(uncovered),
            "fraction": 1 - len(uncovered) / len(cells), "uncovered": uncovered,
            "dimensions": coverage_dimensions(odd) + list(_bins("lead_brake", odd)),
            "excluded_dimensions": excluded, "complete_odd": not excluded}


def failure_curve(store: Store, campaign: str, target: str | None = None) -> pd.DataFrame:
    """Cumulative target runs and distinct target coverage cells vs. number of runs."""
    pred = target_predicate(target or default_target())
    df = store.query(f"SELECT *, ({pred}) AS failed FROM runs ORDER BY run_idx",
                     campaign, max_rows=10**9)
    seen: set = set()
    distinct, odd = [], load_odd()
    for rec in df.to_dict("records"):
        if rec["failed"]:
            seen.add(cell_of(rec, odd))
        distinct.append(len(seen))
    return pd.DataFrame({"runs": np.arange(1, len(df) + 1),
                         "failures": np.cumsum(df["failed"].astype(int)) if len(df) else [],
                         "distinct_failing_cells": distinct})
