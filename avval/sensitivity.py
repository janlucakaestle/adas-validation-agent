"""Sensitivity of acceptance results to modelling and design assumptions.

The protocol is config/sensitivity.yaml: a list of factors (paths into the release
configuration, with ranges) and three designs:

- `oat`: one factor at a time, at evenly spaced points over its range;
- `factorial2`: a full two-level factorial over selected factors, analysed for main effects
  and two-way interactions (least squares on the +/-1 coded design);
- `lhs`: a Latin hypercube over all factors, analysed with standardised regression
  coefficients (SRC) and the regression R^2 (a global, linear screening method).

Every variant re-runs the SAME exposure-weighted sample (identical cases and per-run seeds,
which are derived from the campaign seed and run index), so differences come from the
assumptions, not from resampling (common random numbers). Each variant is a release of its
own (overrides recorded, distinct release ID) run as a `sensitivity` campaign in a
throw-away in-memory store: it can never become release evidence.

Responses. PRIMARY responses are continuous or high-frequency (`primary_responses`:
effective-TTC percentiles, required-deceleration exceedance, near misses at a fixed margin).
Each is reported as a PAIRED difference from the nominal variant of the same design (run by
run, thanks to the common random numbers) with a paired-bootstrap Monte Carlo interval and
the realised minimum detectable effect. Collision rates and acceptance statuses are
SECONDARY (rare events at the per-variant n) and labelled so.

Conclusions may only mention the factors and ranges in the protocol; reports say so.
"""
from __future__ import annotations

import itertools
import json
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime

import numpy as np
import pandas as pd

from . import RESULTS_DIR
from .config import Release, load_file, protocol_id
from .evaluation import clopper_pearson, evaluate_acceptance, overall_verdict
from .frozen import content_hash, thaw

MANIFEST_PATH = RESULTS_DIR / "sensitivity_manifest.json"
ANALYSIS_VERSION = "sensitivity-analysis/v5"
Z_MDE = 2.80  # z(0.975) + z(0.80): two-sided 5%, power 80%
DESIGNS = ("oat", "factorial2", "lhs")


def load_protocol() -> dict:
    return thaw(load_file("sensitivity"))


def _get(cfgs: dict, path: list):
    node = cfgs
    for k in path:
        node = node[k]
    return node


def nominal_values(release: Release, proto: dict | None = None) -> dict[str, float]:
    proto = proto or load_protocol()
    cfgs = {k: thaw(v) for k, v in release.configs.items()}
    out = {}
    for name, f in proto["factors"].items():
        path = [("attentive" if p == "*" else p) for p in f["path"]]
        v = float(_get(cfgs, path))
        out[name] = -v if f.get("negate") else v
    return out


def overrides_for(values: dict[str, float], release: Release, proto: dict | None = None) -> dict:
    """A nested override patch setting each factor in `values` (others stay nominal)."""
    proto = proto or load_protocol()
    patch: dict = {}

    def put(path, val):
        node = patch
        for k in path[:-1]:
            node = node.setdefault(k, {})
        node[path[-1]] = val

    states = list(release.driver["states"])
    for name, val in values.items():
        f = proto["factors"][name]
        v = -float(val) if f.get("negate") else float(val)
        paths = ([[s if p == "*" else p for p in f["path"]] for s in states]
                 if "*" in f["path"] else [list(f["path"])])
        for p in paths:
            put(p, v)
        if f.get("complement"):
            put(list(f["complement"]), 1.0 - v)
    return patch


# ---------------------------------------------------------------- designs
def _snap(f: dict, v: float) -> float:
    """Round a factor value to its grid (delays must lie on the simulator step grid)."""
    g = f.get("grid")
    return round(round(v / g) * g, 6) if g else round(float(v), 6)


def design(kind: str, release: Release, proto: dict | None = None) -> list[dict]:
    """Variants as {factor: value} (empty dict = the nominal baseline, always first)."""
    proto = proto or load_protocol()
    nom = nominal_values(release, proto)
    factors = proto["factors"]
    out: list[dict] = [{}]
    if kind == "oat":
        pts = int(proto["designs"]["oat"]["points"])
        for name, f in factors.items():
            for v in np.linspace(*f["range"], pts):
                v = _snap(f, v)
                if not np.isclose(v, nom[name]):
                    out.append({name: v})
    elif kind == "factorial2":
        names = list(proto["designs"]["factorial2"]["factors"])
        for levels in itertools.product((0, 1), repeat=len(names)):
            out.append({n: _snap(factors[n], factors[n]["range"][lv])
                        for n, lv in zip(names, levels)})
    elif kind == "lhs":
        spec = proto["designs"]["lhs"]
        m, names = int(spec["samples"]), list(factors)
        rng = np.random.default_rng(int(spec["seed"]))
        u = (np.stack([rng.permutation(m) for _ in names], 1) + rng.uniform(size=(m, len(names)))) / m
        for row in u:
            out.append({n: _snap(factors[n], factors[n]["range"][0] + x * (
                factors[n]["range"][1] - factors[n]["range"][0])) for n, x in zip(names, row)})
    else:
        raise ValueError(f"unknown design {kind!r}")
    return out


# ---------------------------------------------------------------- frozen protocol
def _manifest_body(release: Release, evidence_mode: str) -> dict:
    from .provenance import runtime_id
    proto = load_protocol()
    return {"schema": "sensitivity-manifest/v4", "config": proto,
            "config_sha256": protocol_id("sensitivity"),
            "designs": {k: design(k, release, proto) for k in DESIGNS},
            "release_id": release.release_id, "runtime_id": runtime_id(),
            "analysis_version": ANALYSIS_VERSION, "evidence_mode": evidence_mode}


def freeze_protocol(release: Release, evidence_mode: str = "development", path=None) -> dict:
    """Write results/sensitivity_manifest.json (config, concrete variant lists of all three
    designs, release, runtime, analysis version); refuse to overwrite a different one."""
    from .provenance import final_evidence_problems, git_commit
    path = path or MANIFEST_PATH
    if evidence_mode == "final":
        problems = final_evidence_problems()
        if problems:
            raise RuntimeError("final sensitivity freeze refused: " + "; ".join(problems))
    body = _manifest_body(release, evidence_mode)
    pid = content_hash(body)
    m = {**body, "protocol_id": pid,
         "frozen_at": datetime.now().isoformat(timespec="microseconds"),
         "git_commit": git_commit()}
    if path.exists():
        old = json.loads(path.read_text(encoding="utf-8"))
        if old["protocol_id"] != pid:
            raise ValueError(f"{path} holds a different sensitivity protocol "
                             f"({old['protocol_id'][:12]}); move it away explicitly first")
        return old
    path.write_text(json.dumps(m, indent=1), encoding="utf-8")
    return m


def load_manifest(release: Release, path=None) -> dict:
    """The frozen manifest, re-verified against its hash, the current config, the current
    design expansion, release and runtime."""
    path = path or MANIFEST_PATH
    m = json.loads(path.read_text(encoding="utf-8"))
    body = {k: v for k, v in m.items() if k not in ("protocol_id", "frozen_at", "git_commit")}
    if content_hash(body) != m["protocol_id"]:
        raise ValueError(f"{path}: content does not match its protocol ID")
    now = _manifest_body(release, m["evidence_mode"])
    for key in ("config", "designs", "release_id", "runtime_id", "analysis_version"):
        if now[key] != m[key]:
            raise ValueError(f"sensitivity protocol mismatch: {key} differs from the frozen one")
    return m


# ---------------------------------------------------------------- execution
def _policy_for(values: dict, nominal_policy, nom: dict, mode: str):
    """(policy, note) for a variant, handling ACC authority above the training authority."""
    from .policy import TRAIN_ACCEL_MIN, train_policy
    auth = values.get("acc_authority_mps2")
    if auth is None or auth <= -TRAIN_ACCEL_MIN + 1e-9:
        return nominal_policy, ""
    if mode == "retrain":
        pol, _ = train_policy(accel_min=-auth)
        return pol, f"policy re-trained for authority {auth:g}"
    if mode == "saturate":
        return nominal_policy, "CONFOUNDED: authority above training authority, policy extrapolates"
    raise ValueError("variant excluded (authority above nominal, mode exclude_above_nominal)")


def run_variant(nominal_policy, values: dict, n: int, seed: int, mode: str,
                name: str = "sensitivity", protocol: str | None = None,
                evidence_mode: str = "development", keep_data: bool = False):
    """Run one variant in a throw-away store. Returns the result row, and with `keep_data`
    also (campaign record, run rows) so the caller can persist the variant's evidence."""
    from .estimation import run_estimation
    from .store import Store
    base = Release.build(nominal_policy)
    proto = load_protocol()
    policy, note = _policy_for(values, nominal_policy, nominal_values(base, proto), mode)
    rel = base.with_policy(policy) if policy is not nominal_policy else base
    store = Store(":memory:")
    camp = run_estimation(store, policy, n, seed=seed, name=name, kind="sensitivity",
                          release=rel, overrides=overrides_for(values, rel, proto) or None,
                          protocol_id=protocol, evidence_mode=evidence_mode)
    acc = evaluate_acceptance(store, camp.name, camp.release.acceptance,
                              camp.release.reference)
    row = store.query("SELECT count(*) AS n, count(*) FILTER (WHERE collision) AS k FROM runs "
                      "WHERE driver_state = 'attentive' AND avoidable_by_reference",
                      camp.name).iloc[0]
    k, m = int(row["k"]), int(row["n"])
    lo, hi = clopper_pearson(k, m) if m else (np.nan, np.nan)
    out = {"campaign": name, "protocol_id": protocol,
           **{f"factor:{f}": v for f, v in values.items()}, "note": note,
           "release_id": camp.release.release_id, "data_sha256": camp.record["data_sha256"],
           "attentive_runs": m, "attentive_collisions": k,
           "attentive_rate": k / m if m else np.nan, "attentive_ci_low": lo,
           "attentive_ci_high": hi, "verdict": overall_verdict(acc),
           **{f"{a['id']}_status": a["status"] for a in acc},
           **{f"{a['id']}_value": a["value"] for a in acc},
           **{f"{a['id']}_n": a["n"] for a in acc}}
    out["_per_run"] = primary_frame(store, name, proto)
    if keep_data:
        return out, store.get_campaign(name), store.campaign_df(name)
    return out


def run_sensitivity(policy, kind: str = "oat", n: int | None = None, seed: int | None = None,
                    workers: int | None = None, manifest: dict | None = None,
                    store=None) -> pd.DataFrame:
    """Run one design. With a frozen `manifest`, n, seed and the variant list come from it,
    every variant campaign records its protocol ID, and with `store` every variant's
    campaign record and runs are persisted there (verified against their data hashes)."""
    proto = load_protocol()
    base = Release.build(policy)
    if manifest is not None:
        load_manifest(base)  # refuses a changed config, design, release or runtime
        n, seed = int(proto["n"]), int(proto["seed"])
        variants = manifest["designs"][kind]
        pid, mode_ev = manifest["protocol_id"], manifest["evidence_mode"]
    else:
        n = int(n or proto["n"])
        seed = int(proto["seed"] if seed is None else seed)
        variants = design(kind, base, proto)
        pid, mode_ev = None, "development"
    mode = proto["authority_mode"]
    if mode == "exclude_above_nominal":
        lim = nominal_values(base, proto)["acc_authority_mps2"]
        variants = [v for v in variants if v.get("acc_authority_mps2", 0) <= lim + 1e-9]
    names = [f"sens_{kind}_{i:03d}" for i in range(len(variants))]
    keep = store is not None
    args = [(policy, v, n, seed, mode, nm, pid, mode_ev, keep) for v, nm in zip(variants, names)]
    if workers == 1:
        results = [run_variant(*a) for a in args]
    else:
        with ProcessPoolExecutor(max_workers=workers) as ex:
            results = list(ex.map(run_variant, *zip(*args)))
    if keep:
        for _, rec, df in results:
            store.import_campaign(rec, df)
        rows = [r for r, _, _ in results]
    else:
        rows = results
    if variants[0] != {}:
        raise ValueError("variant 0 of every design must be the nominal configuration")
    per_run = [r.pop("_per_run") for r in rows]
    for r, pr in zip(rows, per_run):
        r.update(paired_effects(per_run[0], pr, proto))
    df = pd.DataFrame(rows)
    df.insert(0, "design", kind)
    nom = nominal_values(base, proto)
    for f in proto["factors"]:
        col = f"factor:{f}"
        df[col] = df[col].fillna(nom[f]) if col in df else nom[f]
    return df


# ---------------------------------------------------------------- primary responses
def primary_frame(store, campaign: str, proto: dict) -> pd.DataFrame:
    """Per-run values of the primary responses, ordered by run index: the metric for
    quantile responses, the event indicator for rate responses."""
    cols = []
    for name, r in proto["primary_responses"].items():
        expr = r["metric"] if r["kind"] == "quantile" else f"CASE WHEN {r['event']} THEN 1.0 ELSE 0.0 END"
        cols.append(f'({expr}) AS "{name}"')
    return store.query(f"SELECT run_idx, {', '.join(cols)} FROM runs ORDER BY run_idx",
                       campaign, max_rows=10**9)


def _stat(x: np.ndarray, r: dict, axis=None):
    if r["kind"] == "quantile":  # an order statistic: defined with +inf values, no interpolation
        return np.quantile(x, float(r["q"]), axis=axis, method="inverted_cdf")
    return np.mean(x, axis=axis)


def _diff(a, b):
    """a - b, with equal values (also equal infinities) giving exactly 0."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    with np.errstate(invalid="ignore"):
        return np.where(a == b, 0.0, a - b)


def paired_effects(nominal: pd.DataFrame, variant: pd.DataFrame, proto: dict) -> dict:
    """Primary responses of a variant and their PAIRED differences from the nominal variant:
    point difference, paired percentile-bootstrap interval (the same resampled run indices
    for both), bootstrap standard error and the realised minimum detectable effect
    (Z_MDE x SE). Requires the same runs in the same order (common random numbers)."""
    if not np.array_equal(nominal["run_idx"].to_numpy(), variant["run_idx"].to_numpy()):
        raise ValueError("paired effects need the same run indices in nominal and variant")
    u = proto["uncertainty"]
    conf, draws = float(u["confidence"]), int(u["draws"])
    n = len(nominal)
    idx = np.random.default_rng(int(u["seed"])).integers(0, n, size=(draws, n))
    out = {}
    for name, r in proto["primary_responses"].items():
        x0, x1 = nominal[name].to_numpy(float), variant[name].to_numpy(float)
        d = float(_diff(_stat(x1, r), _stat(x0, r)))
        boot = _diff(_stat(x1[idx], r, axis=1), _stat(x0[idx], r, axis=1))
        finite = np.isfinite(boot).all()
        lo, hi = (np.quantile(boot, [(1 - conf) / 2, (1 + conf) / 2]) if finite
                  else (np.nan, np.nan))
        se = float(np.std(boot, ddof=1)) if finite else np.nan
        out.update({name: float(_stat(x1, r)), f"{name}_diff": d, f"{name}_diff_lo": float(lo),
                    f"{name}_diff_hi": float(hi), f"{name}_diff_se": se,
                    f"{name}_mde80": Z_MDE * se})
    return out


# ---------------------------------------------------------------- analysis
def effects(df: pd.DataFrame, response: str, factors: list[str]) -> pd.DataFrame:
    """Main effects and two-way interactions from a two-level factorial (coded +/-1)."""
    sub = df.replace([np.inf, -np.inf], np.nan).dropna(subset=[response])
    if len(sub) < len(factors) + 2:
        return pd.DataFrame({"term": ["(not estimable: too few variants with a defined "
                                      f"{response})"], "effect (high - low)": [np.nan]})
    X = []
    for f in factors:
        col = sub[f"factor:{f}"].to_numpy(float)
        X.append(np.where(col >= np.median(col), 1.0, -1.0) if col.min() < col.max()
                 else np.zeros(len(col)))
    terms = list(factors) + [f"{a} x {b}" for a, b in itertools.combinations(factors, 2)]
    cols = X + [X[i] * X[j] for i, j in itertools.combinations(range(len(factors)), 2)]
    A = np.column_stack([np.ones(len(sub)), *cols])
    coef, *_ = np.linalg.lstsq(A, sub[response].to_numpy(float), rcond=None)
    return pd.DataFrame({"term": terms, "effect (high - low)": 2 * coef[1:]}).sort_values(
        "effect (high - low)", key=np.abs, ascending=False)


def src(df: pd.DataFrame, response: str, factors: list[str]) -> tuple[pd.DataFrame, float]:
    """Standardised regression coefficients and R^2 (linear global screening)."""
    sub = df.replace([np.inf, -np.inf], np.nan).dropna(subset=[response])
    if len(sub) < 3:
        return pd.DataFrame({"factor": ["(not estimable)"], "SRC": [np.nan]}), float("nan")
    X = np.column_stack([sub[f"factor:{f}"].to_numpy(float) for f in factors])
    y = sub[response].to_numpy(float)
    keep = X.std(0) > 0
    Xs = (X[:, keep] - X[:, keep].mean(0)) / X[:, keep].std(0)
    ys = (y - y.mean()) / (y.std() or 1.0)
    coef, *_ = np.linalg.lstsq(np.column_stack([np.ones(len(ys)), Xs]), ys, rcond=None)
    pred = np.column_stack([np.ones(len(ys)), Xs]) @ coef
    r2 = 1 - np.sum((ys - pred) ** 2) / max(np.sum(ys ** 2), 1e-12)
    names = [f for f, k in zip(factors, keep) if k]
    return (pd.DataFrame({"factor": names, "SRC": coef[1:]}).sort_values(
        "SRC", key=np.abs, ascending=False), float(r2))


def _effect_cell(row, name: str, r: dict) -> str:
    v, d = row[name], row[f"{name}_diff"]
    lo, hi, mde = row[f"{name}_diff_lo"], row[f"{name}_diff_hi"], row[f"{name}_mde80"]
    if row.name != 0 and mde == 0:  # no run changed: no precision statement possible
        m = "MDE n/a: no run differs"
    else:
        m = f"MDE {100 * mde:.2f}" if r["kind"] == "rate" else f"MDE {mde:.3f}"
    if r["kind"] == "rate":
        return (f"{100 * v:.2f}%; Δ {100 * d:+.2f} pp [{100 * lo:+.2f}, {100 * hi:+.2f}] ({m})")
    return f"{v:.3f}; Δ {d:+.3f} [{lo:+.3f}, {hi:+.3f}] ({m})"


def write_sensitivity(df: pd.DataFrame, kind: str, n: int, seed: int,
                      protocol: str | None = None) -> tuple[str, str | None]:
    """results/sensitivity_<design>.md/.csv (and a figure for OAT). Primary responses are
    paired differences from the nominal variant with Monte Carlo intervals; acceptance
    statuses and collision rates are reported as secondary."""
    from .report import _md_table
    proto = load_protocol()
    factors = list(proto["factors"])
    primary = proto["primary_responses"]
    secondary = [f"{r}_value" for r in proto["secondary_responses"]]
    u = proto["uncertainty"]
    df = df.copy()
    df["protocol_id"] = protocol
    df.to_csv(RESULTS_DIR / f"sensitivity_{kind}.csv", index=False)
    lines = [f"# Sensitivity ({kind})", "",
             (f"Frozen sensitivity protocol `{protocol}`." if protocol else
              "**Exploratory: not run under a frozen sensitivity protocol.**"), "",
             f"{len(df)} variants, each re-running the same exposure-weighted sample "
             f"({n} runs, seed {seed}; common random numbers: identical cases and per-run "
             "seeds, only the varied factor changes). "
             "Only these factors were varied, over these ranges; nothing here supports a "
             "conclusion about any other assumption (for example the correlation of "
             "reaction time with speed, or the exposure structure):", "",
             *[f"- `{n}`: {f['range'][0]:g}-{f['range'][1]:g} (`{'.'.join(map(str, f['path']))}`)"
               for n, f in proto["factors"].items()], ""]
    show = [c for c in df.columns if c.startswith("factor:") and df[c].nunique() > 1]
    ren = {c: c.replace("factor:", "") for c in show}
    prim = df[["campaign", *show]].rename(columns=ren)
    for name, r in primary.items():
        prim[name + (" [s]" if r["kind"] == "quantile" else "")] = [
            _effect_cell(row, name, r) for _, row in df.iterrows()]
    lines += ["## Primary responses (paired differences from the nominal variant)", "",
              "Each cell: the variant's value; Δ = variant − nominal (row 0), computed run by "
              f"run on the common sample; [{float(u['confidence']):.0%} paired percentile "
              f"bootstrap interval, {int(u['draws'])} draws over run indices]; MDE = realised "
              f"minimum detectable difference ({Z_MDE:.2f} × bootstrap SE: two-sided 5%, power "
              "80%). These intervals are the Monte Carlo uncertainty of the finite sample, "
              "given the frozen model. A paired MDE rests on the runs whose outcome changed; "
              "\"MDE n/a\" means no run changed, so a zero interval is not a precision claim "
              "(the protocol's conservative unpaired MDEs below then apply). Definitions:", "",
              *[f"- `{name}`: " + (f"{float(r['q']):.0%} quantile of `{r['metric']}`"
                                   if r["kind"] == "quantile" else f"share of runs with `{r['event']}`")
                for name, r in primary.items()], "",
              _md_table(prim, max_rows=len(prim)), "",
              "Detectable effects declared in the protocol (conservative, unpaired, n = "
              f"{proto['power']['n']}): " + "; ".join(
                  f"`{k}` {v['mde_unpaired']}" for k, v in proto["power"].items()
                  if isinstance(v, dict)) + ".", ""]
    if kind == "factorial2":
        names = list(proto["designs"]["factorial2"]["factors"])
        for r in primary:
            lines += [f"## Factorial effects on {r} (primary)", "",
                      _md_table(effects(df.iloc[1:], r, names), max_rows=40), ""]
    if kind == "lhs":
        for r in primary:
            tab, r2 = src(df.iloc[1:], r, factors)
            lines += [f"## Standardised regression coefficients for {r} (primary; R² = {r2:.2f})",
                      "", "A linear screen: a low R² means interactions or non-linearity "
                      "dominate, and the SRC ranking is not reliable.", "",
                      _md_table(tab, max_rows=40), ""]
    table = df[["campaign", *show, "note", "attentive_collisions", "attentive_runs",
                *[c for c in df.columns if c.endswith("_status")], "verdict"]]
    lines += ["## Secondary responses: collision counts and acceptance statuses", "",
              f"Rare-event results at {n} runs per variant: most acceptance statuses are "
              "INSUFFICIENT EVIDENCE or decided by a handful of events, so they are not "
              "informative on their own and are not the basis of any sensitivity conclusion.", "",
              _md_table(table.rename(columns=ren), max_rows=len(table)), ""]
    if kind == "factorial2":
        names = list(proto["designs"]["factorial2"]["factors"])
        for r in secondary:
            lines += [f"### Factorial effects on {r[:-6]} (secondary)", "",
                      _md_table(effects(df.iloc[1:], r, names), max_rows=40), ""]
    if kind == "lhs":
        for r in secondary:
            tab, r2 = src(df.iloc[1:], r, factors)
            lines += [f"### SRC for {r[:-6]} (secondary; R² = {r2:.2f})", "",
                      _md_table(tab, max_rows=40), ""]
    path = RESULTS_DIR / f"sensitivity_{kind}.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    fig = None
    if kind == "oat":
        from .plots import sensitivity_figure
        fig = str(sensitivity_figure(df, proto))
    return str(path), fig
