"""Command-line entry point: python -m avval.cli <command>."""
from __future__ import annotations

import argparse
import json
import sys

from . import RESULTS_DIR


def main(argv=None):
    # Agent text can contain characters the Windows console code page lacks (e.g. U+2208);
    # escape them rather than crash a paid run mid-campaign.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="backslashreplace")
    ap = argparse.ArgumentParser(prog="avval", description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("train", help="Train the learned ACC policy (system under test).")
    sub.add_parser("characterise", help="Dense sweep -> failure-boundary figure.")
    b = sub.add_parser("baseline", help="Run a non-agentic campaign.")
    b.add_argument("--method", choices=["random", "grid"], default="random")
    b.add_argument("--budget", type=int, default=300)
    b.add_argument("--seed", type=int, default=0)
    e = sub.add_parser("estimate", help="Exposure-weighted estimation campaign -> release verdict.")
    e.add_argument("--n", type=int, default=2000)
    e.add_argument("--seed", type=int, default=0)
    e.add_argument("--name", default="estimate")
    k = sub.add_parser("benchmark", help="Run a baseline over many seeds -> table + figure.")
    k.add_argument("--method", choices=["random", "grid"], default="random")
    k.add_argument("--seeds", type=int, default=20)
    k.add_argument("--budget", type=int, default=300)
    t = sub.add_parser("sensitivity", help="One-at-a-time sensitivity -> sensitivity.md/.png.")
    t.add_argument("--n", type=int, default=2000, help="Size of the fixed estimation sample.")
    t.add_argument("--seed", type=int, default=0)
    t.add_argument("--workers", type=int, default=None, help="Parallel processes (default: all).")
    a = sub.add_parser("agent", help="Run the LLM validation agent (needs ANTHROPIC_API_KEY).")
    a.add_argument("--budget", type=int, default=300)
    a.add_argument("--model", default=None)
    a.add_argument("--max-turns", type=int, default=40)
    a.add_argument("--name", default="agent")
    a.add_argument("--no-cache", action="store_true", help="Disable prompt caching (for comparison).")
    a.add_argument("--seeds", type=int, default=1,
                   help="Independent agent campaigns <name>_s<k> (default 1). Each costs a full "
                        "agent run of API tokens (see usage_*.json), so raise it deliberately.")
    a.add_argument("--first-seed", type=int, default=0,
                   help="Seed of the first campaign, so seeds can be run one at a time.")
    a.add_argument("--max-cost-usd", type=float, default=None,
                   help="Stop a campaign once its estimated API cost reaches this (USD).")
    h = sub.add_parser("posthoc", help="Re-evaluate the agent's submitted predicates on the "
                                          "held-out estimation campaign.")
    h.add_argument("campaigns", nargs="*", default=["agent_s0", "agent_s1", "agent_s2"])
    h.add_argument("--holdout", default="estimate")
    sub.add_parser("findings", help="Recompute the README findings' numbers -> findings.md.")
    c = sub.add_parser("compare", help="Multi-seed benchmark table + discovery-curve figure.")
    c.add_argument("strategies", nargs="*", default=["random", "grid", "agent"])
    args = ap.parse_args(argv)

    if args.cmd == "train":
        from .policy import train_policy
        policy, info = train_policy()
        policy.save()
        print(json.dumps(info, indent=2))
        return

    from .campaign import Campaign
    from .policy import LearnedACC
    from .store import Store
    policy = LearnedACC.load()

    if args.cmd == "characterise":
        from .plots import failure_boundary
        print(failure_boundary(policy))
    elif args.cmd == "estimate":
        from .estimation import run_estimation
        from .evaluation import evaluate_acceptance, overall_verdict
        from .report import write_estimation_report
        store = Store()
        camp = run_estimation(store, policy, args.n, seed=args.seed, name=args.name)
        print(write_estimation_report(store, camp.name))
        print("verdict:", overall_verdict(evaluate_acceptance(store, camp.name)))
    elif args.cmd == "baseline":
        from .baselines import auto_report, coverage_grid, random_search
        camp = Campaign(args.method, Store(), policy, args.budget, seed=args.seed,
                        method=args.method)
        (random_search if args.method == "random" else coverage_grid)(camp)
        print(auto_report(camp, args.method))
    elif args.cmd == "benchmark":
        from .baselines import coverage_grid, random_search
        store = Store()
        search = random_search if args.method == "random" else coverage_grid
        for k in range(args.seeds):
            search(Campaign(f"{args.method}_s{k}", store, policy, args.budget, seed=k,
                            method=args.method))
        _print_benchmark(store, ["random", "grid", "agent"])
    elif args.cmd == "agent":
        from .agent import DEFAULT_MODEL, ValidationAgent
        store = Store()
        print(f"Running {args.seeds} agent campaign(s); each costs a full agent run of API tokens.")
        for k in range(args.first_seed, args.first_seed + args.seeds):
            name = f"{args.name}_s{k}"
            camp = Campaign(name, store, policy, args.budget, seed=k, method="agent")
            agent = ValidationAgent(camp, model=args.model or DEFAULT_MODEL,
                                    max_turns=args.max_turns, cache=not args.no_cache,
                                    max_cost_usd=args.max_cost_usd)
            try:
                result = agent.run()
            finally:  # record what was spent even if the run crashes
                (RESULTS_DIR / f"transcript_{name}.json").write_text(
                    json.dumps(agent.transcript, indent=1, default=str))
                (RESULTS_DIR / f"usage_{name}.json").write_text(
                    json.dumps(agent.usage.summary(), indent=2))
            print(f"\n[{name}] finished={result.finished} stop={result.stop_reason} "
                  f"turns={result.turns} report={result.report_path}")
            print("usage:", json.dumps(result.usage, indent=2))
        _print_benchmark(store, [args.name])
    elif args.cmd == "sensitivity":
        from .sensitivity import run_sensitivity, write_sensitivity
        df = run_sensitivity(policy, n=args.n, seed=args.seed, workers=args.workers)
        for path in write_sensitivity(df, args.n, args.seed):
            print(path)
    elif args.cmd == "posthoc":
        from .posthoc import write_posthoc
        print(write_posthoc(Store(), args.campaigns, args.holdout))
    elif args.cmd == "findings":
        from .findings import write_findings
        print(write_findings(Store()))
    elif args.cmd == "compare":
        _print_benchmark(Store(), args.strategies)


def _print_benchmark(store, strategies):
    from .benchmark import summary_table, write_benchmark
    path, summaries = write_benchmark(store, strategies)
    print(summary_table(summaries).set_index("strategy").T.to_string())
    print(path)


if __name__ == "__main__":
    main()
