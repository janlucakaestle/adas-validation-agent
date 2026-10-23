"""Command-line entry point: python -m avval.cli [--final] <command>.

`--rehearsal` runs the same command as a NON-EVIDENCE rehearsal of the final sequence: a
development run (allowed on a dirty tree) in results/rehearsal/, with the reduced sizes of
config/rehearsal.yaml patched onto the benchmark and sensitivity protocols and the
characterisation grid. It can never be combined with `--final`.

`--final` runs a command as FINAL EVIDENCE: it requires a clean, committed source tree and
the locked environment, writes everything into the release-addressed directory
results/final_<release-id prefix>/ (re-executing itself with AVVAL_RESULTS_DIR set to it),
and marks every campaign `evidence_mode = final`. Without `--final`, campaigns are
development runs: allowed on a dirty tree, never release or confirmatory evidence.

The approved order of the final campaigns is in REMEDIATION_SUMMARY.md, "Final rerun plan".
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from . import RESULTS_DIR, ROOT


def _progress(done: int, total: int) -> None:
    print(f"  {done}/{total}", flush=True)


def final_dir(release_id: str) -> Path:
    return ROOT / "results" / f"final_{release_id[:16]}"


REHEARSAL_DIR = ROOT / "results" / "rehearsal"
REHEARSAL_NOTICE = """# NOT EVIDENCE: rehearsal of the final command sequence

Everything in this directory was produced by `python -m avval.cli --rehearsal ...`: the
commands of the final rerun plan in development mode, at the reduced sizes of
config/rehearsal.yaml. Campaigns are `development` evidence with `rehearsal: true` in their
provenance; no file here is release, confirmatory or package evidence.
"""


def _parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="avval", description=__doc__)
    ap.add_argument("--final", action="store_true",
                    help="Final evidence: clean committed tree, lock match, release-addressed "
                         "output directory.")
    ap.add_argument("--rehearsal", action="store_true",
                    help="Non-evidence rehearsal of the final sequence: development mode, "
                         "results/rehearsal/, reduced sizes from config/rehearsal.yaml.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("train", help="Train the policy (refuses to overwrite without --overwrite).")
    t.add_argument("--overwrite", action="store_true")
    v = sub.add_parser("policy-verify", help="Re-train in memory and compare with policy.json "
                                             "(never overwrites the policy).")
    v.add_argument("--write-meta", action="store_true",
                   help="Write results/policy_meta.json (training recipe, versions, result).")
    sub.add_parser("release", help="Print the current release manifest summary.")
    sub.add_parser("env-check", help="Compare the environment with requirements-lock.txt.")
    sub.add_parser("db-info", help="Schema version and campaigns of the results database.")
    sub.add_parser("characterise", help="Dense sweep -> failure_boundary.png/.json.")
    e = sub.add_parser("estimate", help="Nominal exposure-weighted estimation -> verdict.")
    e.add_argument("--n", type=int)
    e.add_argument("--seed", type=int)
    e.add_argument("--name", default="estimate")
    e.add_argument("--resume", action="store_true", help="Continue an incomplete campaign.")
    b = sub.add_parser("baseline", help="Run one non-LLM search campaign (outside protocols).")
    b.add_argument("--method", required=True)
    b.add_argument("--budget", type=int, default=300)
    b.add_argument("--seed", type=int, default=0)
    b.add_argument("--name", default=None)
    sub.add_parser("benchmark-freeze", help="Freeze config/benchmark.yaml -> manifest.")
    k = sub.add_parser("benchmark-run", help="Run baseline campaigns under the frozen protocol.")
    k.add_argument("--strategy", required=True)
    k.add_argument("--first", type=int, default=None)
    k.add_argument("--count", type=int, default=None)
    r = sub.add_parser("benchmark-report", help="Analyse the frozen protocol -> benchmark.md.")
    r.add_argument("--partial", action="store_true",
                   help="Exploratory report of an incomplete protocol (no conclusions).")
    a = sub.add_parser("agent", help="Run LLM agent seeds (needs ANTHROPIC_API_KEY).")
    a.add_argument("--first-seed", type=int, required=True)
    a.add_argument("--seeds", type=int, default=1)
    a.add_argument("--budget", type=int, default=None)
    a.add_argument("--model", default=None)
    a.add_argument("--max-turns", type=int, default=None)
    a.add_argument("--max-cost-usd", type=float, default=None)
    a.add_argument("--no-protocol", action="store_true",
                   help="Exploratory run outside the frozen benchmark protocol.")
    a.add_argument("--name", default="agent")
    a.add_argument("--no-cache", action="store_true")
    sub.add_parser("sensitivity-freeze", help="Freeze config/sensitivity.yaml -> manifest.")
    s = sub.add_parser("sensitivity", help="Sensitivity designs -> sensitivity_<design>.md.")
    s.add_argument("--design", choices=["oat", "factorial2", "lhs"], default="oat")
    s.add_argument("--n", type=int, default=None, help="Exploratory runs only.")
    s.add_argument("--seed", type=int, default=None, help="Exploratory runs only.")
    s.add_argument("--workers", type=int, default=None)
    s.add_argument("--exploratory", action="store_true",
                   help="Run without the frozen manifest (development only).")
    rb = sub.add_parser("reference-boxes", help="AC-01 event boxes of a discovery campaign.")
    rb.add_argument("campaign")
    f = sub.add_parser("freeze-predicates", help="Freeze submitted/reference predicates.")
    f.add_argument("campaigns", nargs="*")
    f.add_argument("--from-benchmark", action="store_true",
                   help="Use the agent campaigns of the validated frozen benchmark.")
    hf = sub.add_parser("holdout-freeze", help="Freeze the hold-out execution (seed, size).")
    hf.add_argument("--n", type=int, required=True)
    hf.add_argument("--seed", type=int, required=True)
    sub.add_parser("holdout-run", help="Run the frozen hold-out exactly as frozen.")
    he = sub.add_parser("holdout-explore", help="Exploratory hold-out (never scored as final).")
    he.add_argument("--n", type=int, required=True)
    he.add_argument("--seed", type=int, required=True)
    he.add_argument("--name", default="holdout_exploratory")
    sub.add_parser("holdout-report", help="Evaluate frozen predicates on the frozen hold-out.")
    d = sub.add_parser("diagnose", help="Why hazardous runs got no hand-back.")
    d.add_argument("campaign")
    d.add_argument("--limit", type=int, default=2000)
    fi = sub.add_parser("findings", help="Recompute the README findings' numbers.")
    fi.add_argument("--estimation", default="estimate")
    fi.add_argument("campaigns", nargs="*")
    fi.add_argument("--from-benchmark", action="store_true",
                    help="Use every baseline campaign of the validated frozen benchmark.")
    vc = sub.add_parser("verify-compat", help="Replay a campaign under the current release.")
    vc.add_argument("campaign")
    rp = sub.add_parser("report", help="(Re)write the report of a stored estimation.")
    rp.add_argument("campaign")
    p = sub.add_parser("package", help="Write the evidence package of this release.")
    p.add_argument("--out", default=None)
    p.add_argument("--require", default="estimation,benchmark,holdout,sensitivity",
                   help="Comma-separated required components.")
    vp = sub.add_parser("verify-package", help="Verify an evidence package.")
    vp.add_argument("dir")
    return ap


def _enter_final(argv: list[str]) -> None:
    """Make sure this process runs in final mode in the release-addressed directory: return
    if it already does, otherwise re-execute in a child process with the directory set."""
    from .config import Release
    from .policy import LearnedACC
    from .provenance import final_evidence_problems
    problems = final_evidence_problems()
    if problems:
        sys.exit("final evidence refused:\n  " + "\n  ".join(problems))
    release = Release.build(LearnedACC.load())
    target = final_dir(release.release_id)
    if Path(os.environ.get("AVVAL_RESULTS_DIR", "")).resolve() == target.resolve():
        marker = target / "RELEASE_ID"
        if marker.exists() and marker.read_text().strip() != release.release_id:
            sys.exit(f"{target} belongs to release {marker.read_text().strip()[:16]}")
        marker.write_text(release.release_id + "\n")
        return
    target.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "AVVAL_RESULTS_DIR": str(target), "AVVAL_EVIDENCE_MODE": "final"}
    print(f"[final] release {release.release_id}; output directory {target}", flush=True)
    sys.exit(subprocess.run([sys.executable, "-m", "avval.cli", *argv], env=env).returncode)


def _enter_rehearsal(argv: list[str]) -> None:
    """Run this command in rehearsal mode in results/rehearsal/ (re-executing if needed)."""
    if Path(os.environ.get("AVVAL_RESULTS_DIR", "")).resolve() == REHEARSAL_DIR.resolve()             and os.environ.get("AVVAL_REHEARSAL") == "1":
        return
    REHEARSAL_DIR.mkdir(parents=True, exist_ok=True)
    (REHEARSAL_DIR / "NOT_EVIDENCE.md").write_text(REHEARSAL_NOTICE, encoding="utf-8")
    env = {**os.environ, "AVVAL_RESULTS_DIR": str(REHEARSAL_DIR), "AVVAL_REHEARSAL": "1",
           "AVVAL_EVIDENCE_MODE": "development"}
    print(f"[rehearsal] non-evidence run in {REHEARSAL_DIR}", flush=True)
    sys.exit(subprocess.run([sys.executable, "-m", "avval.cli", *argv], env=env).returncode)


def main(argv=None):
    # Agent text can contain characters the Windows console code page lacks; escape them.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="backslashreplace")
    argv = list(sys.argv[1:] if argv is None else argv)
    args = _parser().parse_args(argv)
    if args.final and (args.rehearsal or os.environ.get("AVVAL_REHEARSAL") == "1"):
        sys.exit("--final cannot run in rehearsal mode")
    if args.rehearsal:
        _enter_rehearsal(argv)
    if args.final:
        if args.cmd in ("train", "baseline", "holdout-explore") or getattr(args, "exploratory",
                                                                            False):
            sys.exit(f"`{args.cmd}` is a development command and cannot run with --final")
        _enter_final(argv)
    mode = "final" if args.final else "development"
    final = args.final

    if args.cmd == "train":
        from .policy import POLICY_META_PATH, POLICY_PATH, train_policy
        if POLICY_PATH.exists() and not args.overwrite:
            sys.exit(f"{POLICY_PATH} exists: training would replace a release input. Use "
                     "`policy-verify` to check reproducibility, or --overwrite deliberately.")
        policy, meta = train_policy()
        policy.save()
        POLICY_META_PATH.write_text(json.dumps(meta, indent=2), encoding="utf-8")
        print(json.dumps(meta, indent=2))
        return
    if args.cmd == "policy-verify":
        from .policy import POLICY_META_PATH, train_policy
        from .provenance import policy_hash
        policy, meta = train_policy()
        committed, again = policy_hash(), policy_hash(policy)
        meta.update(committed_policy_sha256=committed, retrained_policy_sha256=again,
                    reproduced=committed == again)
        if args.write_meta:
            POLICY_META_PATH.write_text(json.dumps(meta, indent=2), encoding="utf-8")
        print(json.dumps({k: meta[k] for k in ("committed_policy_sha256",
                                               "retrained_policy_sha256", "reproduced")}, indent=2))
        sys.exit(0 if meta["reproduced"] else 1)
    if args.cmd == "env-check":
        from .provenance import check_lock, runtime_fingerprint, runtime_id
        problems = check_lock()
        print(json.dumps({"runtime_id": runtime_id(), **runtime_fingerprint()}, indent=2))
        print("lock: OK" if not problems else "lock MISMATCH:\n  " + "\n  ".join(problems))
        sys.exit(1 if problems else 0)

    from .campaign import Campaign
    from .config import Release
    from .policy import LearnedACC
    from .store import Store
    policy = LearnedACC.load()
    release = Release.build(policy)

    if args.cmd == "release":
        m = release.manifest()
        print(json.dumps({k: m[k] for k in ("release_id", "policy_sha256", "code_sha256",
                                            "config_sha256", "exposure_model_id")}, indent=2))
    elif args.cmd == "db-info":
        store = Store()
        print(dict(store.con.execute("SELECT key, value FROM schema_meta").fetchall()))
        for rec in store.list_campaigns():
            print(f"{rec['campaign_id']:28} {rec['kind']:20} {rec['status']:9} "
                  f"{rec['evidence_mode']:11} {rec['completed_runs']:>7}/{rec['planned_runs']:<7} "
                  f"release {rec['release_id'][:12]}")
    elif args.cmd == "characterise":
        from .config import load_file, rehearsal_active
        from .plots import failure_boundary
        size = dict(load_file("rehearsal")["characterise"]) if rehearsal_active() else {}
        print(failure_boundary(policy, **size))
    elif args.cmd == "estimate":
        from .estimation import release_verdict, resume_estimation, run_estimation
        from .report import write_estimation_report
        store = Store()
        if args.resume:
            camp = resume_estimation(store, policy, args.name, _progress)
        else:
            if args.n is None or args.seed is None:
                sys.exit("estimate needs --n and --seed (or --resume)")
            camp = run_estimation(store, policy, args.n, seed=args.seed, name=args.name,
                                  progress=_progress, evidence_mode=mode)
        print(write_estimation_report(store, camp.name, release, final=final))
        v = release_verdict(store, release=release, final=final)
        print("decision:", json.dumps(v["decision"]))
    elif args.cmd == "baseline":
        from .baselines import auto_report, run_strategy
        store = Store()
        camp = Campaign(args.name or f"{args.method}_s{args.seed}", store, policy, args.budget,
                        seed=args.seed, method=args.method)
        run_strategy(args.method, camp)
        print(auto_report(camp, args.method))
    elif args.cmd == "benchmark-freeze":
        from .benchmark import freeze_protocol
        m = freeze_protocol(release, evidence_mode=mode)
        print(f"protocol {m['protocol_id']} frozen at {m['frozen_at']} ({m['evidence_mode']})")
    elif args.cmd == "benchmark-run":
        from .baselines import STRATEGIES, run_strategy
        from .benchmark import campaign_name, load_manifest, protocol_seeds
        m = load_manifest(release)  # refuses another release or runtime
        if m["evidence_mode"] != mode:
            sys.exit(f"the protocol was frozen as {m['evidence_mode']} evidence; run with the "
                     "same mode")
        proto = m["protocol"]
        if args.strategy not in proto["strategies"] or args.strategy not in STRATEGIES:
            sys.exit(f"{args.strategy!r} is not a baseline strategy of the frozen protocol")
        seeds = protocol_seeds(proto, args.strategy)
        if args.first is not None or args.count is not None:
            first = seeds[0] if args.first is None else args.first
            count = len(seeds) if args.count is None else args.count
            seeds = [x for x in range(first, first + count) if x in seeds]
        store = Store()
        for x in seeds:
            camp = Campaign(campaign_name(args.strategy, x), store, policy, proto["budget"],
                            seed=x, method=args.strategy, protocol_id=m["protocol_id"],
                            evidence_mode=mode)
            run_strategy(args.strategy, camp)
            print(camp.name, camp.used)
    elif args.cmd == "benchmark-report":
        from .benchmark import load_manifest, write_benchmark
        m = load_manifest(release)
        print(write_benchmark(Store(), m, partial=args.partial)[0])
    elif args.cmd == "agent":
        _agent(args, policy, release, mode)
    elif args.cmd == "sensitivity-freeze":
        from .sensitivity import freeze_protocol
        m = freeze_protocol(release, evidence_mode=mode)
        print(f"sensitivity protocol {m['protocol_id']} ({m['evidence_mode']}); variants: "
              + ", ".join(f"{k} {len(v)}" for k, v in m["designs"].items()))
    elif args.cmd == "sensitivity":
        from .sensitivity import load_manifest, load_protocol, run_sensitivity, write_sensitivity
        proto = load_protocol()
        if args.exploratory:
            n = args.n or proto["n"]
            seed = proto["seed"] if args.seed is None else args.seed
            df = run_sensitivity(policy, args.design, n=n, seed=seed, workers=args.workers)
            pid = None
        else:
            if args.n is not None or args.seed is not None:
                sys.exit("--n/--seed are fixed by the frozen sensitivity protocol "
                         "(use --exploratory for other values)")
            m = load_manifest(release)
            if m["evidence_mode"] != mode:
                sys.exit("run the sensitivity in the mode its protocol was frozen in")
            n, seed, pid = proto["n"], proto["seed"], m["protocol_id"]
            df = run_sensitivity(policy, args.design, workers=args.workers, manifest=m,
                                 store=Store())
        for path in write_sensitivity(df, args.design, n, seed, pid):
            if path:
                print(path)
    elif args.cmd == "reference-boxes":
        from .clusters import write_clusters
        print(write_clusters(Store(), policy, args.campaign, final=final))
    elif args.cmd == "freeze-predicates":
        from .estimation import require_campaigns
        from .holdout import freeze_predicates
        store = Store()
        names = list(args.campaigns)
        if args.from_benchmark:
            names += _benchmark_campaigns(store, release, agents=True)
        from .holdout import REFERENCE_PATH
        if not names and not REFERENCE_PATH.exists():
            sys.exit("no source campaigns given and no reference_predicates.json")
        require_campaigns(store, names, release, final=final, full_plan=False)
        f = freeze_predicates(store, names, release)
        print(f"frozen {len(f['predicates'])} predicates: {f['set_sha256']}")
    elif args.cmd == "holdout-freeze":
        from .holdout import freeze_holdout_protocol, load_frozen
        p = freeze_holdout_protocol(Store(), load_frozen(), release, args.n, args.seed, mode)
        print(f"hold-out protocol {p['protocol_id']}: seed {p['seed']}, n {p['planned_runs']}")
    elif args.cmd == "holdout-run":
        from .holdout import load_frozen, load_holdout_protocol, run_holdout
        frozen = load_frozen()
        p = load_holdout_protocol(frozen, release)
        if p["evidence_mode"] != mode:
            sys.exit("run the hold-out in the mode its protocol was frozen in")
        store = Store()
        run_holdout(store, policy, frozen, p)
        print(f"{p['campaign']}: {store.n_runs(p['campaign'])} runs")
    elif args.cmd == "holdout-explore":
        from .holdout import load_frozen, run_exploratory_holdout
        store = Store()
        run_exploratory_holdout(store, policy, load_frozen(), args.n, args.seed, args.name)
        print(f"{args.name}: {store.n_runs(args.name)} runs (exploratory)")
    elif args.cmd == "holdout-report":
        from .holdout import load_frozen, load_holdout_protocol, write_holdout
        frozen = load_frozen()
        p = load_holdout_protocol(frozen, release)
        print(write_holdout(Store(), frozen, p, p["campaign"], release))
    elif args.cmd == "diagnose":
        from .diagnostics import write_diagnostics
        print(write_diagnostics(Store(), args.campaign, policy, args.limit, final=final))
    elif args.cmd == "findings":
        from .findings import write_findings
        store = Store()
        names = list(args.campaigns)
        if args.from_benchmark:
            names += _benchmark_campaigns(store, release, agents=False)
        print(write_findings(store, args.estimation, names, release, final=final))
    elif args.cmd == "verify-compat":
        from .compat import verify_compatibility
        res = verify_compatibility(Store(), args.campaign, release, policy)
        print(json.dumps({k: v for k, v in res.items() if k != "first_mismatches"}, indent=2))
        sys.exit(0 if res["verified"] else 1)
    elif args.cmd == "report":
        from .report import write_estimation_report
        store = Store()
        rec = store.get_campaign(args.campaign)
        if rec is None or rec["kind"] != "nominal_estimation":
            sys.exit("only estimation reports are re-rendered here; search reports are written "
                     "when the campaign finishes")
        print(write_estimation_report(store, args.campaign, release, final=final))
    elif args.cmd == "package":
        from .package import build_package
        out = Path(args.out) if args.out else RESULTS_DIR / "package"
        require = tuple(x for x in args.require.split(",") if x)
        m = build_package(Store(), release, out, final=final, require=require)
        print(f"package {m['package_sha256']} ({len(m['files'])} files) at {out}")
    elif args.cmd == "verify-package":
        from .package import verify_package
        problems = verify_package(Path(args.dir))
        print("package verifies" if not problems else "\n".join(problems))
        sys.exit(1 if problems else 0)


def _benchmark_campaigns(store, release, agents: bool) -> list[str]:
    """Campaigns of the COMPLETE, validated frozen benchmark: its agent campaigns (incl. any
    `_retry1`) or all its baseline campaigns. Refuses an incomplete protocol."""
    from .benchmark import load_manifest, validate_protocol
    chosen, problems = validate_protocol(store, load_manifest(release))
    if problems:
        sys.exit("the frozen benchmark is incomplete:\n  " + "\n  ".join(problems))
    return [c for s, names in chosen.items() if (s == "agent") == agents for c in names]


def is_infrastructure_error(e: BaseException) -> bool:
    """API, network and timeout failures (not errors in this code or the agent's behaviour)."""
    mod = type(e).__module__ or ""
    return (mod.startswith(("anthropic", "httpx", "httpcore"))
            or isinstance(e, (ConnectionError, TimeoutError)))


def _save_agent_logs(name: str, agent) -> None:
    (RESULTS_DIR / f"transcript_{name}.json").write_text(
        json.dumps(agent.transcript, indent=1, default=str), encoding="utf-8")
    (RESULTS_DIR / f"usage_{name}.json").write_text(
        json.dumps(agent.usage.summary(), indent=2), encoding="utf-8")


def _agent(args, policy, release, mode: str) -> None:
    """Agent seeds. Under the frozen protocol, its seeds, budget, model, turns and cost caps
    apply, and its retry rule: a seed whose attempt fails for an infrastructure reason before
    making any simulation run is retried once as `<name>_s<k>_retry1` (the failed attempt and
    its logs are kept). Nothing else is retried: not a failure after the first run, not a
    non-infrastructure error, and never a seed that ended through max turns, its cost cap or
    no tool calls (those are normal protocol endings, not exceptions)."""
    from .agent import DEFAULT_MODEL, ValidationAgent
    from .benchmark import campaign_name, load_manifest
    from .campaign import Campaign
    from .store import Store
    store = Store()
    pid, budget = None, args.budget or 300
    model, turns = args.model or DEFAULT_MODEL, args.max_turns or 40
    proto = None
    if not args.no_protocol:
        m = load_manifest(release)  # refuses another release or runtime
        if m["evidence_mode"] != mode:
            sys.exit(f"the protocol was frozen as {m['evidence_mode']} evidence")
        proto = m["protocol"]
        pid, budget = m["protocol_id"], proto["budget"]
        model, turns = proto["agent"]["model"], proto["agent"]["max_turns"]
        if args.budget or args.model or args.max_turns:
            sys.exit("--budget/--model/--max-turns are fixed by the frozen protocol")
        wanted = set(range(args.first_seed, args.first_seed + args.seeds))
        if not wanted <= set(proto["seeds"]["agent"]):
            sys.exit(f"seeds {sorted(wanted - set(proto['seeds']['agent']))} are not in the "
                     "frozen protocol")
    elif mode == "final":
        sys.exit("final agent campaigns run only under the frozen protocol")

    def seed_cap() -> float | None:
        """Per-seed cost cap: the protocol's per-seed cap, limited by what is left of its
        total cap (recomputed before every attempt from the saved usage files)."""
        if proto is None:
            return args.max_cost_usd
        spent = 0.0  # only campaigns recorded under this protocol count
        for rec in store.list_campaigns(protocol_id=pid, method="agent"):
            p = RESULTS_DIR / f"usage_{rec['campaign_id']}.json"
            if p.exists():
                spent += json.loads(p.read_text(encoding="utf-8")).get("est_cost_usd") or 0.0
        cap = min(proto["agent"]["cost_cap_usd_per_seed"],
                  proto["agent"]["total_cost_cap_usd"] - spent)
        if cap <= 0:
            sys.exit(f"the protocol's total cost cap is reached (${spent:.2f} spent)")
        return cap if args.max_cost_usd is None else min(args.max_cost_usd, cap)

    print(f"Running {args.seeds} agent campaign(s); each costs a full agent run of API tokens.")
    for k in range(args.first_seed, args.first_seed + args.seeds):
        base = campaign_name(args.name, k)
        for attempt, name in enumerate((base, f"{base}_retry1")):
            cap = seed_cap()  # checked before the campaign is created
            camp = Campaign(name, store, policy, budget, seed=k, method="agent", protocol_id=pid,
                            evidence_mode=mode)
            agent = ValidationAgent(camp, model=model, max_turns=turns, cache=not args.no_cache,
                                    max_cost_usd=cap)
            try:
                result = agent.run()
            except Exception as e:  # noqa: BLE001 - classified, recorded and re-raised below
                infra = is_infrastructure_error(e) and camp.used == 0
                agent.record_client_provenance()
                camp.fail(("infrastructure: " if infra else "error: ")
                          + f"{type(e).__name__}: {e}")
                _save_agent_logs(name, agent)
                if infra and attempt == 0:
                    print(f"[{name}] infrastructure failure before any run ({e}); retrying once")
                    continue
                raise
            _save_agent_logs(name, agent)
            print(f"\n[{name}] finished={result.finished} stop={result.stop_reason} "
                  f"turns={result.turns} report={result.report_path}")
            print("usage:", json.dumps(result.usage, indent=2))
            break


if __name__ == "__main__":
    main()
