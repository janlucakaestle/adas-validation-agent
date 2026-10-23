"""Discovery benchmark: a controlled comparison of search strategies under a frozen protocol.

Protocol. config/benchmark.yaml is frozen (`benchmark-freeze`) into
results/benchmark_manifest.json together with the agent interface hash, the discovery
objectives, the full baseline specification (`baselines.BASELINE_SPEC`), the analysis
version, the release ID, the runtime ID and the evidence mode. Its hash is the protocol ID
that every benchmark campaign records. `load_manifest` re-verifies the hash, refuses a
protocol, interface or baseline specification edited after freezing, and (given the current
release) refuses a different release or runtime: analysis code changed after the freeze
cannot silently re-analyse the benchmark.

Completeness. `validate_protocol` requires, for every strategy, exactly the frozen seeds:
one valid campaign per seed (protocol, release, runtime, seed, strategy, lifecycle, planned
and stored runs, data hash, evidence mode), no extra protocol campaigns, and for agent seeds
the protocol's stopping rules and its single retry rule (a seed whose first attempt failed
for an infrastructure reason before any run may have one `_retry1` campaign). A confirmatory
report is refused unless the protocol is complete; `--partial` produces an explicitly
labelled exploratory report without conclusions.

Statistics (see `posterior_predictive_at_least` for the probability model):
- detection share per strategy with a two-sided 95% Clopper-Pearson interval over seeds;
- matched budget: each agent seed j (n_j runs) is compared with every baseline campaign cut
  to its first n_j runs; we report the posterior-predictive tail probability that the
  baseline detects the region in at least as many seeds as the agent, and its 95% upper
  credible bound, under a Jeffreys-marginal Dirichlet model, with a prior-sensitivity check;
  the plug-in value is shown for comparison only. None of these is a frequentist p-value;
- runs to first target run: Kaplan-Meier with non-detecting campaigns right-censored at
  their length, summarised as the restricted mean (RMST) up to the budget;
- distinct target cells at matched budgets: mean difference with a bootstrap interval.
Conclusions are worded narrowly: they hold for this simulator, information interface,
target region and run budget, against the listed baselines.
"""
from __future__ import annotations

import json
from datetime import datetime

import numpy as np
import pandas as pd

from . import RESULTS_DIR
from .config import Release, load_file, protocol_id
from .evaluation import clopper_pearson, failure_curve
from .frozen import content_hash, thaw

MANIFEST_PATH = RESULTS_DIR / "benchmark_manifest.json"
ANALYSIS_VERSION = "benchmark-analysis/v5"
AGENT_STOPS = ("submitted", "max_turns", "cost_cap", "no_tool_calls")
PRIORS = {"jeffreys (primary)": 0.5, "uniform": 1.0, "none (plain Bayesian bootstrap)": 0.0}


# ---------------------------------------------------------------- protocol
def load_protocol() -> dict:
    return thaw(load_file("benchmark"))


def _manifest_body(release_id: str, runtime: str, evidence_mode: str) -> dict:
    from .agent import interface_id
    from .baselines import BASELINE_SPEC
    return {"schema": "benchmark-manifest/v4", "protocol": load_protocol(),
            "protocol_config_sha256": protocol_id("benchmark"),
            "agent_interface_id": interface_id(),
            "discovery_sha256": protocol_id("discovery"),
            "baselines": thaw(BASELINE_SPEC), "analysis_version": ANALYSIS_VERSION,
            "priors": PRIORS, "release_id": release_id, "runtime_id": runtime,
            "evidence_mode": evidence_mode}


def freeze_protocol(release: Release, path=None, evidence_mode: str = "development") -> dict:
    """Write the frozen benchmark manifest; refuse to overwrite a different frozen one.
    A final manifest needs a clean, committed tree and the locked environment."""
    from .provenance import final_evidence_problems, git_commit, runtime_id
    path = path or MANIFEST_PATH
    if evidence_mode == "final":
        problems = final_evidence_problems()
        if problems:
            raise RuntimeError("final benchmark freeze refused: " + "; ".join(problems))
    body = _manifest_body(release.release_id, runtime_id(), evidence_mode)
    pid = content_hash(body)
    manifest = {**body, "protocol_id": pid,
                "frozen_at": datetime.now().isoformat(timespec="microseconds"),
                "git_commit": git_commit()}
    if path.exists():
        old = json.loads(path.read_text(encoding="utf-8"))
        if old["protocol_id"] != pid:
            raise ValueError(f"{path} already holds a different frozen protocol "
                             f"({old['protocol_id'][:12]}); move it away explicitly first")
        return old
    path.write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    return manifest


def load_manifest(release: Release | None = None, path=None) -> dict:
    """The frozen manifest, re-verified: its hash, and that the protocol config, agent
    interface, discovery objectives and baseline specification are unchanged. With
    `release`, also that the current release and runtime are the frozen ones."""
    from .provenance import runtime_id
    path = path or MANIFEST_PATH
    m = json.loads(path.read_text(encoding="utf-8"))
    body = {k: m[k] for k in ("schema", "protocol", "protocol_config_sha256",
                              "agent_interface_id", "discovery_sha256", "baselines",
                              "analysis_version", "priors", "release_id", "runtime_id",
                              "evidence_mode")}
    if content_hash(body) != m["protocol_id"]:
        raise ValueError("benchmark manifest content does not match its protocol ID")
    current = _manifest_body(m["release_id"], m["runtime_id"], m["evidence_mode"])
    for key, what in (("protocol_config_sha256", "config/benchmark.yaml"),
                      ("agent_interface_id", "the agent interface (prompt, tools, discovery)"),
                      ("baselines", "the baseline specification"),
                      ("analysis_version", "the benchmark analysis version")):
        if current[key] != m[key]:
            raise ValueError(f"{what} changed after the protocol was frozen")
    if release is not None:
        if release.release_id != m["release_id"]:
            raise ValueError("the current release differs from the frozen protocol's release "
                             f"({release.release_id[:12]} vs {m['release_id'][:12]})")
        if runtime_id() != m["runtime_id"]:
            raise ValueError("the current runtime differs from the frozen protocol's runtime")
    return m


def campaign_name(strategy: str, seed: int) -> str:
    return f"{strategy}_s{seed}"


def protocol_seeds(proto: dict, strategy: str) -> list[int]:
    if strategy == "agent":
        return list(proto["seeds"]["agent"])
    b = proto["seeds"]["baselines"]
    return list(range(b["first"], b["first"] + b["count"]))


def _usage(campaign: str, base=None) -> dict | None:
    p = (base or RESULTS_DIR) / f"usage_{campaign}.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def _check(store, rec, manifest: dict, strategy: str, seed: int) -> list[str]:
    proto = manifest["protocol"]
    if rec is None:
        return ["missing"]
    out = []
    expect = {"method": strategy, "seed": seed, "protocol_id": manifest["protocol_id"],
              "release_id": manifest["release_id"], "runtime_id": manifest["runtime_id"],
              "evidence_mode": manifest["evidence_mode"], "kind": "search",
              "planned_runs": proto["budget"], "status": "COMPLETE"}
    out += [f"{k} is {rec[k]!r}, expected {v!r}" for k, v in expect.items() if rec[k] != v]
    n = store.n_runs(rec["campaign_id"])
    if rec["completed_runs"] != n:
        out.append(f"completed_runs {rec['completed_runs']} != stored {n}")
    if strategy == "agent":
        if rec["stop_reason"] not in AGENT_STOPS:
            out.append(f"agent stop reason {rec['stop_reason']!r} is not a protocol stop")
    elif n != proto["budget"]:
        out.append(f"{n} runs, protocol budget {proto['budget']}")
    if not out and store.data_hash(rec["campaign_id"]) != rec["data_sha256"]:
        out.append("stored rows do not match the data hash")
    return out


def validate_protocol(store, manifest: dict, usage_dir=None
                      ) -> tuple[dict[str, list[str]], list[str]]:
    """({strategy: [valid campaign per frozen seed, in seed order]}, problems). The protocol
    is complete only if `problems` is empty."""
    proto = manifest["protocol"]
    chosen: dict[str, list[str]] = {}
    problems: list[str] = []
    used: set[str] = set()
    for strategy in proto["strategies"]:
        chosen[strategy] = []
        for seed in protocol_seeds(proto, strategy):
            name = campaign_name(strategy, seed)
            rec = store.get_campaign(name)
            bad = _check(store, rec, manifest, strategy, seed)
            if bad and strategy == "agent" and rec is not None:
                infra_fail = (rec["status"] == "FAILED" and rec["completed_runs"] == 0
                              and store.n_runs(name) == 0
                              and str(rec["stop_reason"] or "").startswith("infrastructure"))
                if infra_fail:  # the protocol's single retry
                    used.add(name)
                    name = f"{name}_retry1"
                    rec = store.get_campaign(name)
                    bad = _check(store, rec, manifest, strategy, seed)
            if bad:
                problems.append(f"{strategy} seed {seed} ({name}): " + "; ".join(bad))
            else:
                chosen[strategy].append(name)
            used.add(name)
    extra = sorted(r["campaign_id"] for r in store.list_campaigns(
        protocol_id=manifest["protocol_id"]) if r["campaign_id"] not in used)
    problems += [f"unexpected campaign under the protocol: {c}" for c in extra]
    if "agent" in proto["strategies"]:
        models = set()
        for name in chosen["agent"]:
            u = _usage(name, usage_dir)
            if u is None or not u.get("models_returned"):
                problems.append(f"{name}: no usage record with the API-returned model ID")
            else:
                models |= set(u["models_returned"])
        if len(models) > 1:
            problems.append(f"agent seeds ran on different returned models: {sorted(models)}")
    return chosen, problems


# ---------------------------------------------------------------- per campaign
def campaign_profile(store, campaign: str, regions: dict, curve_target: str) -> dict:
    """First run index per region (inf if none), run count and the target-cell curve."""
    first = store.query("SELECT " + ", ".join(
        f"min(run_idx) FILTER (WHERE {pred}) AS \"{name}\"" for name, pred in regions.items())
        + " FROM runs", campaign).iloc[0]
    return {"campaign": campaign, "runs": store.n_runs(campaign),
            "curve": failure_curve(store, campaign, curve_target),
            "first_idx": {n: float(first[n]) if pd.notna(first[n]) else np.inf
                          for n in regions}}


def _cells_at(profile: dict, n: int) -> int:
    curve = profile["curve"]
    return int(curve["distinct_failing_cells"].iloc[min(n, len(curve)) - 1]) if len(curve) else 0


# ---------------------------------------------------------------- statistics
def at_least(probs, k: int) -> float:
    """P(at least k successes) for independent Bernoulli trials with these probabilities."""
    dist = np.zeros(len(probs) + 1)
    dist[0] = 1.0
    for p in probs:
        dist[1:] = dist[1:] * (1 - p) + dist[:-1] * p
        dist[0] *= 1 - p
    return float(dist[k:].sum())


def posterior_detection_probs(detect: np.ndarray, draws: int = 4000, seed: int = 0,
                              prior: float = 0.5) -> np.ndarray:
    """Posterior draws (draws x budgets) of the baseline's detection probability at each
    agent budget: one Dirichlet(1, ..., 1, prior, prior) weight vector per draw over the m
    campaigns plus the always-hit and never-hit pseudo-trajectories, shared by all budgets.
    See `posterior_predictive_at_least` for the model."""
    m_base, n_seeds = detect.shape
    aug = np.vstack([detect.astype(float), np.ones(n_seeds), np.zeros(n_seeds)])
    alpha = np.r_[np.ones(m_base), prior, prior]
    keep = alpha > 0
    rng = np.random.default_rng(seed)
    return rng.dirichlet(alpha[keep], size=draws) @ aug[keep]


def posterior_predictive_at_least(detect: np.ndarray, k: int, draws: int = 4000,
                                  seed: int = 0, prior: float = 0.5) -> dict:
    """Posterior-predictive tail probability that a baseline matches the agent.

    Data: `detect[i, j]` = 1 if baseline campaign i hits the region within agent seed j's
    budget n_j. Because a campaign that hits within n also hits within any larger budget,
    the columns are nested and must not be treated as independent.

    Model. A baseline campaign is a draw of its first-hit run T from an unknown distribution
    F. The posterior over F is a Bayesian bootstrap over the m observed campaigns augmented
    with two pseudo-trajectories: one that hits immediately (T = 0) and one that never hits
    (T = inf), with Dirichlet weights (1, ..., 1, prior, prior). One weight vector w is drawn
    per posterior sample and SHARED across all budgets, so p_j(w) = P_w(T < n_j) is
    non-decreasing in n_j and the nesting is preserved. For any single budget, aggregation of
    Dirichlet components gives p_j ~ Beta(k_j + prior, m - k_j + prior), where k_j is the
    number of hitting campaigns: with prior = 0.5 this is exactly the Jeffreys posterior for a
    binomial proportion (Beta(1/2, 1/2) prior). The implied prior dependence across budgets is
    that of a Dirichlet process whose base measure puts half its mass of `2 * prior` on
    "immediate hit" and half on "never hit": it adds no information about WHERE between
    budgets a hit happens, only about the extremes.

    Given p(w), the agent's seeds are independent Bernoulli(p_j) under the baseline, and the
    tail probability is P(at least k hits) (Poisson-binomial). We report its posterior mean
    (posterior predictive), its 95% upper credible bound, and the plug-in value with the
    empirical shares (shown only for comparison). prior = 0 is the plain Bayesian bootstrap,
    which puts all mass on 0 when no campaign hit. None of these is a frequentist p-value."""
    p = posterior_detection_probs(detect, draws, seed, prior)        # draws x seeds
    vals = np.array([at_least(row, k) for row in p])
    return {"plug_in": at_least(detect.mean(0), k), "posterior_predictive": float(vals.mean()),
            "upper95": float(np.quantile(vals, 0.95)),
            "expected_plug_in": float(detect.mean(0).sum()), "prior": prior}


def kaplan_meier(times: np.ndarray, events: np.ndarray) -> pd.DataFrame:
    """Kaplan-Meier survival of 'no target run yet' at each distinct event time."""
    order = np.argsort(times)
    t, e = times[order], events[order]
    out, s = [], 1.0
    for u in np.unique(t[e]):
        at_risk = np.sum(t >= u)
        d = np.sum((t == u) & e)
        s *= 1 - d / at_risk
        out.append((u, s))
    return pd.DataFrame(out, columns=["runs", "survival"])


def rmst(times: np.ndarray, events: np.ndarray, tau: float) -> float:
    """Restricted mean runs to first target run, up to tau (area under the KM curve)."""
    km = kaplan_meier(times, events)
    grid = np.r_[0.0, km["runs"].to_numpy(float), tau]
    surv = np.r_[1.0, km["survival"].to_numpy(float)]
    area, prev = 0.0, 0.0
    for t_next, s in zip(grid[1:], surv):
        t_next = min(t_next, tau)
        area += s * max(t_next - prev, 0.0)
        prev = t_next
        if prev >= tau:
            break
    return area


def first_target(profiles: list[dict]) -> tuple[np.ndarray, np.ndarray]:
    """(time, event): 1-based run of the first curve-target run, or censored at length."""
    times, events = [], []
    for p in profiles:
        hits = p["curve"].loc[p["curve"]["failures"] > 0, "runs"]
        if len(hits):
            times.append(float(hits.min()))
            events.append(True)
        else:
            times.append(float(p["runs"]))
            events.append(False)
    return np.asarray(times), np.asarray(events, bool)


def _boot_ci(stat, data: list[np.ndarray], draws: int, seed: int, joint: bool = False
             ) -> tuple[float, float]:
    """Percentile bootstrap 95% interval. `joint`: the arrays are columns of one sample and
    are resampled with shared indices; otherwise each is an independent sample."""
    rng = np.random.default_rng(seed)
    vals = []
    for _ in range(draws):
        if joint:
            idx = rng.integers(0, len(data[0]), len(data[0]))
            vals.append(stat(*[d[idx] for d in data]))
        else:
            vals.append(stat(*[d[rng.integers(0, len(d), len(d))] for d in data]))
    return float(np.quantile(vals, 0.025)), float(np.quantile(vals, 0.975))


def agent_model_identity(agent_campaigns: list[str], usage_dir=None) -> dict:
    """Which model served the agent seeds, as far as the API lets us know: the returned model
    IDs, whether any is a dated snapshot (`...-YYYYMMDD`), and the UTC span of the seeds' API
    calls. With only an alias returned, a model update behind the alias cannot be detected;
    the time span is then the only record of which version served the seeds."""
    import re
    ids, firsts, lasts, per_seed = set(), [], [], {}
    for name in agent_campaigns:
        u = _usage(name, usage_dir) or {}
        ids |= set(u.get("models_returned") or [])
        f, la = u.get("first_call_utc"), u.get("last_call_utc")
        per_seed[name] = {"first_call_utc": f, "last_call_utc": la}
        firsts += [f] if f else []
        lasts += [la] if la else []
    return {"models_returned": sorted(ids),
            "dated_snapshot": bool(ids) and all(re.search(r"-\d{8}$", m) for m in ids),
            "first_call_utc": min(firsts) if firsts else None,
            "last_call_utc": max(lasts) if lasts else None, "seeds": per_seed}


def model_identity_lines(ident: dict) -> list[str]:
    span = (f"{ident['first_call_utc']} to {ident['last_call_utc']} UTC"
            if ident["first_call_utc"] else "not recorded")
    lines = ["## Agent model identity", "",
             f"Model IDs returned by the API: {', '.join(f'`{m}`' for m in ident['models_returned']) or '-'}. "
             f"Agent API calls span {span}.", ""]
    if not ident["dated_snapshot"]:
        lines += ["**Limitation.** The API returned a model alias, not a dated snapshot ID (the "
                  "Models API listed no dated snapshot of this model when the protocol was "
                  "written). The protocol's check that all seeds ran on one returned model ID "
                  "therefore cannot detect a model update behind the alias. The seeds were run in "
                  "one sitting to keep that window short; the time span above is the record of "
                  "when they ran.", ""]
    return lines


# ---------------------------------------------------------------- analysis
def analyse(store, manifest: dict, campaigns: dict[str, list[str]]) -> dict:
    proto = manifest["protocol"]
    regions, primary = proto["regions"], proto["primary"]
    curve_target = proto["curve_target"]
    draws, bseed = int(primary["bootstrap_draws"]), int(primary["bootstrap_seed"])
    profiles = {s: [campaign_profile(store, c, regions, curve_target) for c in names]
                for s, names in campaigns.items() if names}
    budget = int(proto["budget"])
    summary = []
    for s, profs in profiles.items():
        t, e = first_target(profs)
        row = {"strategy": s, "campaigns": len(profs),
               "runs (median)": int(np.median([p["runs"] for p in profs])),
               "RMST runs to first target": rmst(t, e, budget),
               "RMST 95% CI": _boot_ci(lambda tt, ee: rmst(tt, ee, budget), [t, e], 500, bseed,
                                       joint=True) if len(profs) > 1 else (np.nan, np.nan),
               "censored": int((~e).sum())}
        for name in regions:
            k = sum(np.isfinite(p["first_idx"][name]) for p in profs)
            row[f"P({name})"] = (k / len(profs), clopper_pearson(k, len(profs)))
        summary.append(row)
    result = {"manifest": manifest, "campaigns": campaigns, "summary": summary,
              "matched": None}
    if "agent" in profiles:
        agent = profiles["agent"]
        reg = primary["region"]
        k = sum(np.isfinite(p["first_idx"][reg]) for p in agent)
        matched = {"region": reg, "seeds": len(agent), "detected": k,
                   "agent_ci": clopper_pearson(k, len(agent)), "baselines": {}}
        n_j = np.array([p["runs"] for p in agent])
        agent_cells = np.array([_cells_at(p, p["runs"]) for p in agent], float)
        for s, profs in profiles.items():
            if s == "agent":
                continue
            detect = np.array([[p["first_idx"][reg] < n for n in n_j] for p in profs])
            sens = {label: posterior_predictive_at_least(detect, k, draws, bseed, prior)
                    for label, prior in manifest["priors"].items()}
            pp = sens["jeffreys (primary)"]
            cells = np.array([[_cells_at(p, n) for n in n_j] for p in profs], float)
            diff = agent_cells.mean() - cells.mean()
            ci = _boot_ci(lambda a, b: a.mean() - b.mean(), [agent_cells, cells.mean(1)],
                          2000, bseed)
            matched["baselines"][s] = {**pp, "campaigns": len(profs), "prior_sensitivity": sens,
                                       "cells_diff": diff, "cells_diff_ci": ci,
                                       "credible_advantage":
                                           pp["upper95"] < float(primary["alpha"])}
        result["matched"] = matched
    return result


def _p(p: float) -> str:
    return f"{p:.3f}" if p >= 0.001 else f"{p:.1e}"


def conclusion(result: dict) -> list[str]:
    """Narrow, protocol-scoped conclusions only (never for a partial protocol)."""
    m = result["matched"]
    proto = result["manifest"]["protocol"]
    if not m:
        return ["No agent campaigns under this protocol: no comparison is made."]
    lines = []
    for s, b in m["baselines"].items():
        verdict = ("detected the region in more seeds than this baseline would be expected to "
                   "at the same per-seed budgets (95% upper credible bound of the "
                   f"posterior-predictive tail probability {_p(b['upper95'])} < "
                   f"{proto['primary']['alpha']})" if b["credible_advantage"] else
                   "did not show a detection advantage over this baseline that survives the "
                   f"uncertainty in its detection probabilities (95% upper bound {_p(b['upper95'])})")
        lines.append(f"- Under this simulator, information interface, target region "
                     f"(`{m['region']}`) and run budget ({proto['budget']}), the evaluated agent "
                     f"({proto['agent']['model']}, {m['seeds']} seeds) {verdict} relative to "
                     f"`{s}` ({b['campaigns']} campaigns).")
    lines.append("- The comparison is of complete search strategies with the same public "
                 "information: the agent reads natural-language descriptions and can reason "
                 "about visible derived labels such as `avoidable_by_reference` (part of the "
                 "primary region); the numerical baselines optimise a robustness score of "
                 "`collision`, `end_state` and `min_ttc` only. It is not a comparison of "
                 "optimisation efficiency on one identical objective.")
    lines.append("- These statements do not generalise to other simulators, systems, targets, "
                 "budgets, models or baselines.")
    return lines


def _json_default(o):
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, np.floating):
        return float(o)
    if isinstance(o, np.bool_):
        return bool(o)
    if isinstance(o, pd.DataFrame):
        return None
    return str(o)


def write_benchmark(store, manifest: dict, partial: bool = False) -> tuple[str, dict]:
    """results/benchmark.md, benchmark_analysis.json and discovery_curves.png. Refuses an
    incomplete protocol unless `partial`, which yields an exploratory report without
    conclusions."""
    from .plots import discovery_curves
    from .report import _md_table
    chosen, problems = validate_protocol(store, manifest)
    if problems and not partial:
        raise ValueError("the frozen benchmark protocol is incomplete or invalid; no "
                         "confirmatory report is produced:\n  " + "\n  ".join(problems))
    confirmatory = not problems and manifest["evidence_mode"] == "final"
    res = analyse(store, manifest, chosen)
    res["mode"] = ("confirmatory" if confirmatory else
                   "complete (development evidence, not confirmatory)" if not problems
                   else "partial (exploratory)")
    res["problems"] = problems
    rows = []
    for r in res["summary"]:
        row = {"strategy": r["strategy"], "campaigns": r["campaigns"],
               "runs (median)": r["runs (median)"],
               "RMST runs to first target [95% CI]":
                   f"{r['RMST runs to first target']:.1f} [{r['RMST 95% CI'][0]:.1f}, "
                   f"{r['RMST 95% CI'][1]:.1f}]", "censored": r["censored"]}
        for name in manifest["protocol"]["regions"]:
            p, (lo, hi) = r[f"P({name})"]
            row[f"P({name})"] = f"{p:.2f} [{lo:.2f}, {hi:.2f}]"
        rows.append(row)
    lines = [f"# Discovery benchmark ({res['mode']})", "",
             f"Protocol ID `{manifest['protocol_id']}`, frozen {manifest['frozen_at']} "
             f"({manifest['evidence_mode']} evidence); release `{manifest['release_id'][:16]}…`; "
             f"runtime `{manifest['runtime_id'][:16]}…`; agent interface "
             f"`{manifest['agent_interface_id'][:16]}…`.", ""]
    if problems:
        lines += ["**PARTIAL, EXPLORATORY.** The frozen protocol is incomplete or has invalid "
                  "campaigns; no conclusion is drawn:", "", *[f"- {p}" for p in problems], ""]
    lines += [_md_table(pd.DataFrame(rows), max_rows=len(rows)), "",
              "Detection shares carry two-sided 95% Clopper-Pearson intervals over seeds. Runs "
              "to first target run: Kaplan-Meier restricted mean up to the budget, campaigns "
              "with no target run censored at their length.", ""]
    m = res["matched"]
    if m:
        lo, hi = m["agent_ci"]
        lines += ["## Matched budget (primary analysis)", "",
                  f"Region `{m['region']}`: agent detected it in {m['detected']} of {m['seeds']} "
                  f"seeds ({m['detected'] / m['seeds']:.2f} [{lo:.2f}, {hi:.2f}]).", "",
                  "| baseline | campaigns | expected detections (plug-in) | tail prob. plug-in "
                  "| posterior-predictive tail prob. (Jeffreys) | 95% upper bound "
                  "| upper bound, uniform prior | upper bound, no prior | Δ target cells [95% CI] |",
                  "|---|---|---|---|---|---|---|---|---|"]
        for s, b in m["baselines"].items():
            ps = b["prior_sensitivity"]
            lines.append(f"| {s} | {b['campaigns']} | {b['expected_plug_in']:.2f} | "
                         f"{_p(b['plug_in'])} | {_p(b['posterior_predictive'])} | "
                         f"{_p(b['upper95'])} | {_p(ps['uniform']['upper95'])} | "
                         f"{_p(ps['none (plain Bayesian bootstrap)']['upper95'])} | "
                         f"{b['cells_diff']:+.1f} [{b['cells_diff_ci'][0]:+.1f}, "
                         f"{b['cells_diff_ci'][1]:+.1f}] |")
        lines += ["", "Tail probability: P(baseline detects in at least as many seeds as the "
                  "agent at the same per-seed budgets) under the model in "
                  "`avval/benchmark.py::posterior_predictive_at_least`. Posterior-predictive "
                  "quantities, not frequentist p-values.", ""]
    if chosen.get("agent"):
        res["agent_model_identity"] = agent_model_identity(chosen["agent"])
        lines += model_identity_lines(res["agent_model_identity"])
    lines += ["## Conclusions (scoped)", "",
              *(conclusion(res) if not problems else
                ["_None: the protocol is incomplete (partial report)._"]), "",
              "![Discovery curves](discovery_curves.png)", "", "## Regions", "",
              *[f"- `{n}`: `{p}`" for n, p in manifest["protocol"]["regions"].items()], ""]
    (RESULTS_DIR / "benchmark.md").write_text("\n".join(lines), encoding="utf-8")
    analysis = {k: v for k, v in res.items() if k != "manifest"}
    analysis["protocol_id"] = manifest["protocol_id"]
    (RESULTS_DIR / "benchmark_analysis.json").write_text(
        json.dumps(analysis, indent=1, default=_json_default), encoding="utf-8")
    discovery_curves(store, chosen, manifest["protocol"]["curve_target"])
    return str(RESULTS_DIR / "benchmark.md"), res
