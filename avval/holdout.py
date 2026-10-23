"""Held-out evaluation of triggering conditions, with a real discovery / evaluation split.

1. Discovery: agent campaigns submit evidence-backed predicates (results/evidence_*.json);
   reference predicates may be derived from discovery data (scripts/ac01_clusters.py writes
   results/reference_predicates.json, naming the campaign they were derived from).
2. Freeze: `freeze_predicates` writes results/frozen_predicates.json with every predicate,
   its source, the release ID and a set hash. A frozen set is never edited; a different set
   needs a new file.
3. Freeze the execution: `freeze_holdout_protocol` writes results/holdout_protocol.json with
   the predicate-set hash, release, runtime, exposure model, seed, planned size, region,
   target, analysis version and exposure-mass Monte-Carlo settings; its hash is the hold-out
   protocol ID.
4. Evaluate: `run_holdout` runs exactly that seed and size as a fresh campaign of kind
   `holdout_evaluation` recording the protocol ID; `evaluate` refuses any campaign, release
   or runtime that does not match the frozen protocol, so no predicate is ever scored on
   the data it was derived from (the estimation campaign included) or under another
   exposure model. Exploratory hold-outs are a separate kind (`holdout_exploratory`) and
   can never be scored as the frozen one.

Support classification (exposure model, release configuration):
- `exact-point description`: the predicate pins a continuous parameter with "=", so its
  exposure measure is zero by construction;
- `unsupported`: zero estimated exposure measure (or, for predicates on outputs, no
  hold-out run inside); a positive measure with no hold-out run inside is reported as
  "not observed" (the hold-out is too small to judge it);
- `neighbourhood`: exposure measure below MIN_MASS (a small region around sampled points);
- `exposure-supported`: measure at least MIN_MASS and hold-out runs inside.
Only exposure-supported conditions are presented as generalising triggering conditions.
"""
from __future__ import annotations

import json
import re
from datetime import datetime

import numpy as np

from . import RESULTS_DIR
from .config import CONTINUOUS, SCENARIO_PARAMS, Release
from .evaluation import columns_used, default_target, predicate_stats
from .evidence import norm_sql
from .frozen import canonical_json, content_hash, sha256_text

FROZEN_PATH = RESULTS_DIR / "frozen_predicates.json"
PROTOCOL_PATH = RESULTS_DIR / "holdout_protocol.json"
ANALYSIS_VERSION = "holdout-analysis/v4"
REFERENCE_PATH = RESULTS_DIR / "reference_predicates.json"
KIND = "holdout_evaluation"
MIN_MASS = 1e-3
MASS_SAMPLES, MASS_SEED = 200_000, 12345
INPUT_COLUMNS = {"scenario", "ego_speed", "headway", "initial_gap_m", "lead_decel",
                 "closing_speed", "friction", "driver_state", "driver_category"}
_CONT = (*CONTINUOUS, *SCENARIO_PARAMS.values(), "initial_gap_m")


def _bundle_predicates(campaign: str) -> list[dict]:
    path = RESULTS_DIR / f"evidence_{campaign}.json"
    if not path.exists():
        return []
    b = json.loads(path.read_text(encoding="utf-8"))
    body = {k: v for k, v in b.items() if k != "bundle_sha256"}
    if sha256_text(canonical_json(body)) != b["bundle_sha256"]:
        raise ValueError(f"{path}: evidence bundle hash does not match its content")
    return [{"source": campaign, "condition": f"TC-{i:02d}", "predicate": c["predicate"],
             "condition_sha256": c["condition_sha256"], "derived_from": [campaign],
             "release_id": b["release_id"]}
            for i, c in enumerate(b["conditions"], 1)]


def freeze_predicates(store, campaigns: list[str], release: Release,
                      reference_path=None, path=None) -> dict:
    reference_path, path = reference_path or REFERENCE_PATH, path or FROZEN_PATH
    items = []
    for c in campaigns:
        items += _bundle_predicates(c)
    if reference_path and reference_path.exists():
        ref = json.loads(reference_path.read_text(encoding="utf-8"))
        items += [{**r, "source": "reference"} for r in ref["predicates"]]
    for it in items:
        if it["release_id"] != release.release_id:
            raise ValueError(f"{it['source']} {it['condition']}: derived under another release")
        it["predicate_sha256"] = sha256_text(norm_sql(it["predicate"]))
    sources = sorted({c for it in items for c in it["derived_from"]})
    seeds = sorted({store.get_campaign(c)["seed"] for c in sources if store.get_campaign(c)})
    body = {"schema": "frozen-predicates/v3", "release_id": release.release_id,
            "predicates": items, "derived_from": sources, "source_seeds": seeds}
    set_id = content_hash(body)
    frozen = {**body, "set_sha256": set_id,
              "frozen_at": datetime.now().isoformat(timespec="microseconds")}
    if path.exists():
        old = json.loads(path.read_text(encoding="utf-8"))
        if old["set_sha256"] != set_id:
            raise ValueError(f"{path} holds a different frozen set ({old['set_sha256'][:12]}); a "
                             "frozen set is never edited - move it away explicitly first")
        return old
    path.write_text(json.dumps(frozen, indent=1), encoding="utf-8")
    return frozen


def load_frozen(path=None) -> dict:
    path = path or FROZEN_PATH
    f = json.loads(path.read_text(encoding="utf-8"))
    body = {k: f[k] for k in ("schema", "release_id", "predicates", "derived_from",
                              "source_seeds")}
    if content_hash(body) != f["set_sha256"]:
        raise ValueError(f"{path}: content does not match its set hash (edited after freezing?)")
    return f


def freeze_holdout_protocol(store, frozen: dict, release: Release, n: int, seed: int,
                            evidence_mode: str = "development", path=None) -> dict:
    """Freeze the hold-out EXECUTION before it runs: the frozen predicate set, release,
    runtime, exposure model, seed, planned size, region, target and the analysis settings
    (method version and exposure-mass Monte-Carlo settings). `holdout-run` then takes its
    seed and size from this file only."""
    from .provenance import final_evidence_problems, git_commit, runtime_id
    from .benchmark import load_protocol
    path = path or PROTOCOL_PATH
    if release.release_id != frozen["release_id"]:
        raise ValueError("the frozen predicates belong to another release")
    if seed in frozen["source_seeds"]:
        raise ValueError(f"seed {seed} was used by a source campaign; choose a fresh seed")
    if n <= 0:
        raise ValueError("the hold-out needs a positive size")
    if evidence_mode == "final":
        problems = final_evidence_problems()
        if problems:
            raise RuntimeError("final hold-out freeze refused: " + "; ".join(problems))
    bp = load_protocol()
    body = {"schema": "holdout-protocol/v4", "frozen_set_sha256": frozen["set_sha256"],
            "release_id": release.release_id, "runtime_id": runtime_id(),
            "exposure_model_id": release.exposure_model_id, "seed": int(seed),
            "planned_runs": int(n), "campaign": "holdout", "evidence_mode": evidence_mode,
            "analysis_version": ANALYSIS_VERSION,
            "mass": {"samples": MASS_SAMPLES, "seed": MASS_SEED, "min_mass": MIN_MASS},
            "region": bp["regions"][bp["primary"]["region"]], "target": default_target()}
    pid = content_hash(body)
    proto = {**body, "protocol_id": pid,
             "frozen_at": datetime.now().isoformat(timespec="microseconds"),
             "git_commit": git_commit()}
    if path.exists():
        old = json.loads(path.read_text(encoding="utf-8"))
        if old["protocol_id"] != pid:
            raise ValueError(f"{path} holds a different hold-out protocol "
                             f"({old['protocol_id'][:12]}); move it away explicitly first")
        return old
    path.write_text(json.dumps(proto, indent=1), encoding="utf-8")
    return proto


def load_holdout_protocol(frozen: dict, release: Release | None = None, path=None) -> dict:
    """The frozen hold-out protocol, re-verified (hash, predicate set, analysis version) and,
    given the current release, bound to the current release and runtime."""
    from .provenance import runtime_id
    path = path or PROTOCOL_PATH
    p = json.loads(path.read_text(encoding="utf-8"))
    body = {k: v for k, v in p.items() if k not in ("protocol_id", "frozen_at", "git_commit")}
    if content_hash(body) != p["protocol_id"]:
        raise ValueError(f"{path}: content does not match its protocol ID")
    if p["frozen_set_sha256"] != frozen["set_sha256"]:
        raise ValueError("the hold-out protocol belongs to another frozen predicate set")
    if p["analysis_version"] != ANALYSIS_VERSION:
        raise ValueError("the hold-out analysis changed after the protocol was frozen")
    if release is not None:
        if release.release_id != p["release_id"] or release.release_id != frozen["release_id"]:
            raise ValueError("the current release differs from the frozen hold-out release")
        if runtime_id() != p["runtime_id"]:
            raise ValueError("the current runtime differs from the frozen hold-out runtime")
    return p


def run_holdout(store, policy, frozen: dict, protocol: dict):
    """Run the frozen hold-out exactly as specified (seed, size, name, evidence mode)."""
    from .estimation import run_estimation
    release = Release.build(policy)
    load_holdout_protocol(frozen, release)  # binds to the current release and runtime
    if protocol["campaign"] in frozen["derived_from"]:
        raise ValueError("the hold-out campaign cannot be a source of the frozen predicates")
    return run_estimation(store, policy, protocol["planned_runs"], seed=protocol["seed"],
                          name=protocol["campaign"], kind=KIND,
                          protocol_id=protocol["protocol_id"],
                          evidence_mode=protocol["evidence_mode"])


def run_exploratory_holdout(store, policy, frozen: dict, n: int, seed: int,
                            name: str = "holdout_exploratory"):
    """An exploratory hold-out of any size and seed (kind `holdout_exploratory`). It can
    never be scored as the frozen hold-out."""
    from .estimation import run_estimation
    if seed in frozen["source_seeds"] or name in frozen["derived_from"]:
        raise ValueError("an exploratory hold-out may not share a seed or campaign with sources")
    return run_estimation(store, policy, n, seed=seed, name=name, kind="holdout_exploratory",
                          protocol_id=frozen["set_sha256"])


def check_holdout(store, frozen: dict, protocol: dict, holdout: str) -> None:
    from .provenance import runtime_id
    rec = store.get_campaign(holdout)
    problems = []
    if rec is None:
        raise LookupError(f"no campaign {holdout!r}")
    expect = {"kind": KIND, "status": "COMPLETE", "protocol_id": protocol["protocol_id"],
              "seed": protocol["seed"], "planned_runs": protocol["planned_runs"],
              "release_id": protocol["release_id"], "runtime_id": protocol["runtime_id"],
              "evidence_mode": protocol["evidence_mode"],
              "exposure_model_id": protocol["exposure_model_id"]}
    problems += [f"{k} is {rec[k]!r}, frozen {v!r}" for k, v in expect.items() if rec[k] != v]
    if rec["runtime_id"] != runtime_id():
        problems.append("recorded under a different runtime than the current one")
    if rec["created"].to_pydatetime() <= datetime.fromisoformat(protocol["frozen_at"]):
        problems.append("it was created before the hold-out protocol was frozen")
    if rec["created"].to_pydatetime() <= datetime.fromisoformat(frozen["frozen_at"]):
        problems.append("it was created before the predicates were frozen")
    if holdout in frozen["derived_from"] or rec["seed"] in frozen["source_seeds"]:
        problems.append("it shares a campaign or seed with the discovery data")
    n = store.n_runs(holdout)
    if n != protocol["planned_runs"] or rec["completed_runs"] != n:
        problems.append(f"{n} stored runs, frozen {protocol['planned_runs']}")
    if store.data_hash(holdout) != rec["data_sha256"]:
        problems.append("its rows do not match the recorded data hash")
    if problems:
        raise ValueError(f"{holdout!r} is not the frozen hold-out: " + "; ".join(problems))


def exposure_mass(predicate: str, release: Release, n: int = MASS_SAMPLES,
                  seed: int = MASS_SEED) -> float | None:
    """Monte-Carlo exposure measure of an input-only predicate (None if it uses outputs)."""
    import duckdb
    if columns_used(predicate) - INPUT_COLUMNS or not columns_used(predicate):
        return None
    df = release.exposure_model.sample_frame(n, np.random.default_rng(seed))  # noqa: F841
    con = duckdb.connect()
    try:
        return float(con.execute(f"SELECT avg(CAST(coalesce(({predicate}), false) AS DOUBLE)) "
                                 "FROM df").fetchone()[0])
    finally:
        con.close()


def is_point_description(predicate: str) -> bool:
    cols = "|".join(_CONT)
    return bool(re.search(rf"\b({cols})\s*=\s*-?\d", predicate))


def support_class(predicate: str, mass: float | None, runs_inside: int,
                  min_mass: float = MIN_MASS) -> str:
    if is_point_description(predicate):
        return "exact-point description"
    if mass is not None and mass == 0.0:
        return "unsupported (zero exposure measure)"
    if runs_inside == 0:
        return ("not observed in the hold-out (too few hold-out runs to judge)"
                if mass else "unsupported (no hold-out run inside)")
    if mass is not None and mass < min_mass:
        return "neighbourhood (low exposure measure)"
    return "exposure-supported"


def evaluate(store, frozen: dict, protocol: dict, holdout: str, release: Release
             ) -> list[dict]:
    """Score every frozen predicate on the frozen hold-out, under the frozen settings. The
    current release and runtime must be the frozen ones, so old hold-out rows are never
    combined with a newer exposure model or code."""
    load_holdout_protocol(frozen, release)
    check_holdout(store, frozen, protocol, holdout)
    return score(store, frozen, protocol, holdout, release)


def score(store, frozen: dict, protocol: dict, holdout: str, release: Release) -> list[dict]:
    """The scoring itself, without the identity checks (used by `evaluate` after its checks,
    and by package verification to recompute packaged results)."""
    region, target, mass_cfg = protocol["region"], protocol["target"], protocol["mass"]
    total = int(store.query(f"SELECT count(*) FILTER (WHERE {region}) AS k FROM runs",
                            holdout).iloc[0]["k"])
    rows = []
    for it in frozen["predicates"]:
        s = predicate_stats(store, holdout, it["predicate"], target)
        k = int(store.query(f"SELECT count(*) FILTER (WHERE coalesce(({it['predicate']}), false) "
                            f"AND ({region})) AS k FROM runs", holdout).iloc[0]["k"])
        mass = exposure_mass(it["predicate"], release, mass_cfg["samples"], mass_cfg["seed"])
        rows.append({**it, **s, "exposure_mass": mass, "region_events_inside": k,
                     "region_events_total": total,
                     "support": support_class(it["predicate"], mass, s["runs_inside"],
                                              mass_cfg["min_mass"])})
    return rows


def _pct(x, digits=1) -> str:
    return "-" if x is None else f"{100 * x:.{digits}f}%"


def write_holdout(store, frozen: dict, protocol: dict, holdout: str, release: Release) -> str:
    rows = evaluate(store, frozen, protocol, holdout, release)
    n = store.n_runs(holdout)
    lines = ["# Held-out evaluation of frozen triggering conditions", "",
             f"Hold-out protocol `{protocol['protocol_id'][:16]}…` (seed {protocol['seed']}, "
             f"{protocol['planned_runs']:,} planned runs, {protocol['evidence_mode']} evidence). "
             f"Frozen set `{frozen['set_sha256'][:16]}…` ({len(rows)} predicates, frozen "
             f"{frozen['frozen_at']}, derived from {', '.join(frozen['derived_from']) or '-'}). "
             f"Hold-out campaign `{holdout}`: {n:,} fresh exposure-weighted runs, created after "
             "the freeze, sharing no campaign or seed with the discovery data. Rates are "
             "conditional on the exposure model; intervals are two-sided 95% Clopper-Pearson.", "",
             "| source | TC | predicate | support | exposure measure | runs inside "
             "| target rate inside [95% CI] | lift | region events inside |",
             "|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        lo, hi = r["inside_rate_ci95"]
        ci = "-" if lo is None else f"{_pct(r['target_rate_inside'])} [{_pct(lo)}, {_pct(hi)}]"
        lift = "-" if r["lift"] is None else f"{r['lift']:.1f}"
        lines.append(f"| {r['source']} | {r['condition']} | `{r['predicate']}` | {r['support']} "
                     f"| {_pct(r['exposure_mass'], 3)} | {r['runs_inside']:,} | {ci} | {lift} "
                     f"| {r['region_events_inside']} / {r['region_events_total']} |")
    lines += ["", "Only `exposure-supported` conditions generalise under the exposure model. "
              "Exact-point descriptions and unsupported conditions describe sampled points, "
              "not triggering conditions, and are not evidence of a generalising failure mode.", ""]
    out = {"holdout_protocol_id": protocol["protocol_id"],
           "frozen_set_sha256": frozen["set_sha256"], "campaign": holdout,
           "analysis_version": ANALYSIS_VERSION, "rows": rows}
    (RESULTS_DIR / "holdout_predicates.json").write_text(json.dumps(out, indent=1, default=str),
                                                         encoding="utf-8")
    path = RESULTS_DIR / "holdout_predicates.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return str(path)
