"""Independently reviewable evidence packages of one release.

`build_package` selects evidence by IDs and manifests, never by file names alone: the
release's eligible nominal estimation, the COMPLETE frozen benchmark (every protocol
campaign, validated for completeness), the frozen hold-out (predicate set, execution
protocol, campaign), the frozen sensitivity study (manifest and every persisted variant
campaign) and the reports derived from them. Every campaign must match the package's release
(sensitivity variants: the release derived from the package release by their recorded
overrides and policy) and the current runtime, have intact data and the right protocol ID,
and in a final package be final evidence. Every artifact must carry the ID it belongs to
(data hash, protocol ID, release ID) or it is refused, so stale files cannot enter.

Layout:
  MANIFEST.json              every file with its SHA-256, the components and the package hash
  release_manifest.json      release ID, policy/code/config hashes, parsed configurations
  config/*.yaml, policy.json, policy_meta.json, source/ (avval/*.py, scripts/*.py)
  runtime.json, requirements-lock.txt
  campaigns.json, runs/<campaign>.parquet
  estimation/ benchmark/ holdout/ sensitivity/ other/   artifacts per component

`verify_package` re-hashes every file, recomputes the release ID and the code hash from the
packaged sources, reloads every campaign from Parquet and checks its data hash and release,
and recomputes the acceptance results, the benchmark completeness and analysis, every agent
evidence bundle (on the packaged rows), the hold-out scores and the sensitivity statuses,
comparing each with the packaged result.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pandas as pd

from . import CONFIG_DIR, RESULTS_DIR, ROOT
from .frozen import canonical_json, content_hash, freeze
from .provenance import LOCK_PATH, runtime_fingerprint, runtime_id, sha256_file

COMPONENTS = ("estimation", "benchmark", "holdout", "sensitivity")


def _json(path: Path, obj) -> None:
    from .benchmark import _json_default
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=1, default=_json_default), encoding="utf-8")


def _roundtrip(obj):
    from .benchmark import _json_default
    return json.loads(json.dumps(obj, default=_json_default))


class _Plan:
    def __init__(self):
        self.campaigns: dict[str, str] = {}      # campaign -> component
        self.files: list[tuple[Path, str]] = []  # (source, packaged path)
        self.components: dict[str, dict] = {}
        self.problems: list[str] = []

    def artifact(self, src: Path, dest: str, must_contain: str | None = None,
                 required: bool = True) -> None:
        if not src.exists():
            if required:
                self.problems.append(f"missing artifact {src.name}")
            return
        if must_contain is not None and src.suffix in (".md", ".json", ".csv") and \
                must_contain not in src.read_text(encoding="utf-8"):
            self.problems.append(f"{src.name} does not carry the ID {must_contain[:16]}… it "
                                 "must belong to (stale or foreign artifact)")
            return
        self.files.append((src, dest))


def _variant_release(base, rec):
    from .config import Release
    rel = Release(base.configs, rec["provenance"]["policy_sha256"], base.code_sha256)
    return rel.with_overrides(rec["overrides"]) if rec["overrides"] else rel


def collect(store, release, final: bool) -> _Plan:
    """Select and validate everything that belongs in the package (see module docstring)."""
    from .benchmark import MANIFEST_PATH as BM, load_manifest, validate_protocol
    from .estimation import campaign_problems, find_estimation
    from .evidence import verify_bundle
    from .holdout import FROZEN_PATH, PROTOCOL_PATH, check_holdout, load_frozen, \
        load_holdout_protocol
    from .sensitivity import MANIFEST_PATH as SM, load_manifest as load_sens
    plan = _Plan()
    rd = RESULTS_DIR

    # nominal estimation
    est = find_estimation(store, release=release, final=final)
    if est is None:
        plan.problems.append("estimation: no eligible nominal estimation")
    else:
        rec = store.get_campaign(est)
        plan.campaigns[est] = "estimation"
        plan.components["estimation"] = {"campaign": est, "data_sha256": rec["data_sha256"]}
        plan.artifact(rd / f"report_{est}.md", f"estimation/report_{est}.md", rec["data_sha256"])

    # benchmark
    if not BM.exists():
        plan.problems.append("benchmark: no frozen manifest")
    else:
        try:
            m = load_manifest(release)
            if final and m["evidence_mode"] != "final":
                raise ValueError("the frozen protocol is not final evidence")
            chosen, probs = validate_protocol(store, m)
            if probs:
                raise ValueError("protocol incomplete: " + "; ".join(probs[:5]))
            pid = m["protocol_id"]
            plan.components["benchmark"] = {"protocol_id": pid,
                                            "campaigns": sum(len(v) for v in chosen.values())}
            for name in [c for names in chosen.values() for c in names] + [
                    r["campaign_id"] for r in store.list_campaigns(protocol_id=pid)
                    if r["status"] == "FAILED"]:  # retained failed infrastructure attempts
                plan.campaigns[name] = "benchmark"
            plan.artifact(BM, "benchmark/benchmark_manifest.json")
            plan.artifact(rd / "benchmark_analysis.json", "benchmark/benchmark_analysis.json", pid)
            plan.artifact(rd / "benchmark.md", "benchmark/benchmark.md", pid)
            plan.artifact(rd / "discovery_curves.png", "benchmark/discovery_curves.png")
            for name in chosen.get("agent", []):
                rec = store.get_campaign(name)
                bpath = rd / f"evidence_{name}.json"
                if bpath.exists():
                    bad = verify_bundle(json.loads(bpath.read_text(encoding="utf-8")), rec, store)
                    if bad:
                        plan.problems.append(f"{name} evidence bundle: " + "; ".join(bad))
                    plan.artifact(bpath, f"benchmark/evidence_{name}.json")
                    plan.artifact(rd / f"report_{name}.md", f"benchmark/report_{name}.md",
                                  rec["data_sha256"])
                plan.artifact(rd / f"transcript_{name}.json", f"benchmark/transcript_{name}.json")
                plan.artifact(rd / f"usage_{name}.json", f"benchmark/usage_{name}.json")
        except (ValueError, KeyError) as e:
            plan.problems.append(f"benchmark: {e}")

    # hold-out
    if not (FROZEN_PATH.exists() and PROTOCOL_PATH.exists()):
        plan.problems.append("holdout: no frozen predicate set and execution protocol")
    else:
        try:
            frozen = load_frozen()
            hp = load_holdout_protocol(frozen, release)
            if final and hp["evidence_mode"] != "final":
                raise ValueError("the hold-out protocol is not final evidence")
            check_holdout(store, frozen, hp, hp["campaign"])
            plan.campaigns[hp["campaign"]] = "holdout"
            plan.components["holdout"] = {"protocol_id": hp["protocol_id"],
                                          "frozen_set_sha256": frozen["set_sha256"],
                                          "campaign": hp["campaign"], "seed": hp["seed"],
                                          "planned_runs": hp["planned_runs"],
                                          "source_bundles": frozen["derived_from"]}
            plan.artifact(FROZEN_PATH, "holdout/frozen_predicates.json")
            plan.artifact(PROTOCOL_PATH, "holdout/holdout_protocol.json")
            plan.artifact(rd / "reference_predicates.json", "holdout/reference_predicates.json",
                          release.release_id, required=False)
            plan.artifact(rd / "holdout_predicates.json", "holdout/holdout_predicates.json",
                          hp["protocol_id"])
            plan.artifact(rd / "holdout_predicates.md", "holdout/holdout_predicates.md",
                          hp["protocol_id"][:16])
        except (ValueError, LookupError, KeyError) as e:
            plan.problems.append(f"holdout: {e}")

    # sensitivity
    if not SM.exists():
        plan.problems.append("sensitivity: no frozen manifest")
    else:
        try:
            sm = load_sens(release)
            if final and sm["evidence_mode"] != "final":
                raise ValueError("the sensitivity protocol is not final evidence")
            pid = sm["protocol_id"]
            variants = [r for r in store.list_campaigns(protocol_id=pid)]
            want = {f"sens_{d}_{i:03d}" for d, vs in sm["designs"].items()
                    for i in range(len(vs))}
            have = {r["campaign_id"] for r in variants}
            if have != want:
                raise ValueError(f"{len(want - have)} variant campaigns missing, "
                                 f"{len(have - want)} unexpected")
            for r in variants:
                bad = campaign_problems(store, r, _variant_release(release, r),
                                        kind="sensitivity", protocol_id=pid, final=final)
                if bad:
                    plan.problems.append(f"{r['campaign_id']}: " + "; ".join(bad))
                plan.campaigns[r["campaign_id"]] = "sensitivity"
            plan.components["sensitivity"] = {"protocol_id": pid, "variants": len(want)}
            plan.artifact(SM, "sensitivity/sensitivity_manifest.json")
            for d in sm["designs"]:
                plan.artifact(rd / f"sensitivity_{d}.csv", f"sensitivity/sensitivity_{d}.csv", pid)
                plan.artifact(rd / f"sensitivity_{d}.md", f"sensitivity/sensitivity_{d}.md", pid)
            plan.artifact(rd / "sensitivity_oat.png", "sensitivity/sensitivity_oat.png")
        except (ValueError, KeyError) as e:
            plan.problems.append(f"sensitivity: {e}")

    # every packaged campaign: release, runtime, lifecycle, data
    for name, comp in plan.campaigns.items():
        rec = store.get_campaign(name)
        if comp == "sensitivity":
            continue  # checked above against its variant release
        if rec["status"] == "FAILED":
            if rec["release_id"] != release.release_id or rec["runtime_id"] != runtime_id():
                plan.problems.append(f"{name}: failed attempt from another release/runtime")
            continue
        bad = campaign_problems(store, rec, release, final=final,
                                full_plan=comp != "benchmark" or not name.startswith("agent"))
        if bad:
            plan.problems.append(f"{name}: " + "; ".join(bad))

    # other published artifacts: must carry this release's ID
    short = release.release_id[:16]
    plan.artifact(rd / "findings.md", "other/findings.md", short, required=False)
    plan.artifact(rd / "ac01_clusters.md", "other/ac01_clusters.md", short, required=False)
    plan.artifact(rd / "failure_boundary.json", "other/failure_boundary.json", release.release_id,
                  required=False)
    if (rd / "failure_boundary.json").exists():
        plan.artifact(rd / "failure_boundary.png", "other/failure_boundary.png")
    for p in sorted(rd.glob("handback_diagnostics_*.md")):
        plan.artifact(p, f"other/{p.name}", short)
    return plan


def build_package(store, release, out: Path, final: bool = True,
                  require: tuple = COMPONENTS) -> dict:
    """Write the package; refuse on any problem, or if a required component is missing."""
    from .estimation import release_verdict
    from .policy import POLICY_META_PATH, POLICY_PATH
    plan = collect(store, release, final)
    problems = [p for p in plan.problems
                if any(p.startswith(c) for c in require) or not p.split(":")[0] in COMPONENTS]
    if problems:
        raise ValueError("package refused:\n  " + "\n  ".join(problems))
    out = Path(out)
    if out.exists() and any(out.iterdir()):
        raise ValueError(f"{out} is not empty")
    (out / "runs").mkdir(parents=True, exist_ok=True)
    _json(out / "release_manifest.json", release.manifest())
    for p in sorted(CONFIG_DIR.glob("*.yaml")):
        (out / "config").mkdir(exist_ok=True)
        shutil.copy2(p, out / "config" / p.name)
    for sub in ("avval", "scripts"):
        for p in sorted((ROOT / sub).glob("*.py")):
            (out / "source" / sub).mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, out / "source" / sub / p.name)
    for src in (POLICY_PATH, POLICY_META_PATH, LOCK_PATH):
        if src.exists():
            shutil.copy2(src, out / src.name)
    fp = runtime_fingerprint()
    _json(out / "runtime.json", {"fingerprint": fp, "runtime_id": runtime_id(fp)})
    records = []
    for name, comp in plan.campaigns.items():
        rec = store.get_campaign(name)
        records.append({**rec, "component": comp})
        store.campaign_df(name).to_parquet(out / "runs" / f"{name}.parquet", index=False)
    _json(out / "campaigns.json", records)
    if "estimation" in plan.components:
        v = release_verdict(store, release=release, final=final)
        _json(out / "estimation" / "acceptance.json",
              {"campaign": v["estimation_campaign"], "decision": v["decision"],
               "criteria": v["criteria"]})
    for src, dest in plan.files:
        (out / dest).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, out / dest)
    files = {str(p.relative_to(out)).replace("\\", "/"): sha256_file(p)
             for p in sorted(out.rglob("*")) if p.is_file()}
    manifest = {"schema": "package/v4", "release_id": release.release_id, "final": final,
                "components": plan.components, "files": files}
    manifest["package_sha256"] = content_hash(manifest)
    _json(out / "MANIFEST.json", manifest)
    return manifest


# ---------------------------------------------------------------- verification
def _load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def verify_package(out: Path) -> list[str]:
    """Problems found (empty = the package verifies). Must run with the packaged code."""
    from .config import Release
    from .evaluation import evaluate_acceptance
    from .evidence import verify_bundle
    from .provenance import code_hash
    from .store import Store
    out = Path(out)
    problems: list[str] = []
    m = _load_json(out / "MANIFEST.json")
    if content_hash({k: v for k, v in m.items() if k != "package_sha256"}) != m["package_sha256"]:
        problems.append("MANIFEST.json does not match its package hash")
    listed = set(m["files"])
    actual = {str(p.relative_to(out)).replace("\\", "/") for p in out.rglob("*")
              if p.is_file() and p.name != "MANIFEST.json"}
    problems += [f"unlisted file {f}" for f in sorted(actual - listed)]
    for rel, h in m["files"].items():
        if sha256_file(out / rel) != h:
            problems.append(f"{rel}: hash mismatch")

    # release, code, policy, runtime
    rm = _load_json(out / "release_manifest.json")
    configs = freeze(rm["configs"])
    release = Release(configs, rm["policy_sha256"], rm["code_sha256"])
    if release.release_id != rm["release_id"] or rm["release_id"] != m["release_id"]:
        problems.append("release_manifest.json: configurations do not hash to the release ID")
    if sha256_file(out / "policy.json") != rm["policy_sha256"]:
        problems.append("policy.json does not match the release's policy hash")
    import hashlib
    h = hashlib.sha256()
    for p in sorted((out / "source" / "avval").glob("*.py")):
        h.update(f"{p.name}:{sha256_file(p, text=True)};".encode())
    if h.hexdigest() != rm["code_sha256"]:
        problems.append("packaged source does not hash to the release's code hash")
    if code_hash() != rm["code_sha256"]:
        problems.append("verification is not running with the packaged code")
    rt = _load_json(out / "runtime.json")
    if runtime_id(rt["fingerprint"]) != rt["runtime_id"]:
        problems.append("runtime.json: fingerprint does not hash to its runtime ID")

    # campaigns: reload from Parquet
    store = Store(":memory:")
    records = {r["campaign_id"]: r for r in _load_json(out / "campaigns.json")}
    for name, rec in records.items():
        df = pd.read_parquet(out / "runs" / f"{name}.parquet")
        store.create_campaign({k: rec[k] for k in (
            "campaign_id", "kind", "method", "seed", "planned_runs", "release_id",
            "runtime_id", "exposure_model_id", "protocol_id", "case_source", "overrides",
            "provenance", "evidence_mode")})
        store.insert(df.astype(object).where(df.notna(), None).to_dict("records"))
        store.update_campaign(name, status=rec["status"], completed_runs=rec["completed_runs"],
                              stop_reason=rec["stop_reason"], data_sha256=rec["data_sha256"])
        if rec["status"] == "COMPLETE" and store.data_hash(name) != rec["data_sha256"]:
            problems.append(f"{name}: data does not reproduce its recorded data hash")
        want = (_variant_release(release, rec).release_id if rec["component"] == "sensitivity"
                else release.release_id)
        if rec["release_id"] != want:
            problems.append(f"{name}: recorded under release {rec['release_id'][:12]}, the "
                            f"package release is {want[:12]}")
        if rec["runtime_id"] != rt["runtime_id"]:
            problems.append(f"{name}: recorded under another runtime than the package")
        if m["final"] and rec["evidence_mode"] != "final":
            problems.append(f"{name}: development run inside a final package")
    comps = m["components"]

    if "estimation" in comps:
        est = comps["estimation"]["campaign"]
        acc = _load_json(out / "estimation" / "acceptance.json")
        again = evaluate_acceptance(store, est, configs["acceptance"], configs["reference"])
        if canonical_json(_roundtrip(again)) != canonical_json(acc["criteria"]):
            problems.append("estimation: recomputed acceptance results differ from the package")

    if "benchmark" in comps:
        from .benchmark import analyse, validate_protocol
        bm = _load_json(out / "benchmark" / "benchmark_manifest.json")
        body = {k: bm[k] for k in ("schema", "protocol", "protocol_config_sha256",
                                   "agent_interface_id", "discovery_sha256", "baselines",
                                   "analysis_version", "priors", "release_id", "runtime_id",
                                   "evidence_mode")}
        if content_hash(body) != bm["protocol_id"] or bm["protocol_id"] != \
                comps["benchmark"]["protocol_id"]:
            problems.append("benchmark: manifest does not match its protocol ID")
        if bm["release_id"] != release.release_id or bm["runtime_id"] != rt["runtime_id"]:
            problems.append("benchmark: frozen for another release or runtime")
        chosen, probs = validate_protocol(store, bm, usage_dir=out / "benchmark")
        problems += [f"benchmark: {p}" for p in probs]
        packaged = _load_json(out / "benchmark" / "benchmark_analysis.json")
        again = analyse(store, bm, chosen)
        for key in ("summary", "matched"):
            if canonical_json(_roundtrip(again[key])) != canonical_json(packaged[key]):
                problems.append(f"benchmark: recomputed {key} differs from the package")
        for name in chosen.get("agent", []):
            bpath = out / "benchmark" / f"evidence_{name}.json"
            if bpath.exists():
                problems += [f"{name} evidence bundle: {p}" for p in
                             verify_bundle(_load_json(bpath), store.get_campaign(name), store)]

    if "holdout" in comps:
        from .holdout import load_frozen, load_holdout_protocol, score
        try:
            frozen = load_frozen(out / "holdout" / "frozen_predicates.json")
            hp = load_holdout_protocol(frozen, None, out / "holdout" / "holdout_protocol.json")
            rec = records.get(hp["campaign"])
            if rec is None or rec["protocol_id"] != hp["protocol_id"] or \
                    rec["seed"] != hp["seed"] or rec["planned_runs"] != hp["planned_runs"]:
                problems.append("holdout: the campaign is not the frozen hold-out")
            if hp["release_id"] != release.release_id:
                problems.append("holdout: protocol frozen for another release")
            packaged = _load_json(out / "holdout" / "holdout_predicates.json")
            again = score(store, frozen, hp, hp["campaign"], release)
            if canonical_json(_roundtrip(again)) != canonical_json(packaged["rows"]):
                problems.append("holdout: recomputed scores differ from the package")
        except (ValueError, KeyError) as e:
            problems.append(f"holdout: {e}")

    if "sensitivity" in comps:
        sm = _load_json(out / "sensitivity" / "sensitivity_manifest.json")
        body = {k: v for k, v in sm.items() if k not in ("protocol_id", "frozen_at", "git_commit")}
        if content_hash(body) != sm["protocol_id"]:
            problems.append("sensitivity: manifest does not match its protocol ID")
        for d in sm["designs"]:
            csv = pd.read_csv(out / "sensitivity" / f"sensitivity_{d}.csv")
            for _, r in csv.iterrows():
                rec = records.get(r["campaign"])
                if rec is None or rec["data_sha256"] != r["data_sha256"] or \
                        rec["protocol_id"] != sm["protocol_id"]:
                    problems.append(f"sensitivity {d}: row {r['campaign']} does not match its "
                                    "packaged campaign")
                    continue
                acc = evaluate_acceptance(store, r["campaign"], configs["acceptance"],
                                          configs["reference"])
                if any(str(r[f"{a['id']}_status"]) != a["status"] for a in acc):
                    problems.append(f"sensitivity {d}: recomputed statuses of {r['campaign']} "
                                    "differ from the package")
    return problems
