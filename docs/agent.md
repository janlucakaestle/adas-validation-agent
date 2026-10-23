# The search agent and the discovery benchmark

## Search interface and secret boundary

Every strategy obtains its information through `SearchInterface` (`avval/search.py`). The
agent uses these tools:

| Tool | Gives the agent |
| --- | --- |
| `get_system_spec` | ODD parameters and ranges, driver-state definitions, the public discovery targets (`config/discovery.yaml`), the meaning of every visible column, coverage definition, budget |
| `run_scenarios` | Key outcomes of each case, and target hits per discovery target in the batch |
| `query_results` | Read-only SQL over its own campaign, restricted to the visible columns; returns a `query_id` |
| `check_coverage` | Covered cells (scenario × driver state × bins) and uncovered examples |
| `test_predicate` | Rates inside/outside a WHERE clause, lift, 95% interval; returns a `test_id` |
| `submit_report` | Submission, accepted only if the evidence protocol holds |

**Never visible:** acceptance criteria, thresholds, populations, quantiles, `min_n`; the
verdict and any other campaign; the reference responses' parameters; driver-model numbers
and sources; monitor and actuator design values; exposure weights; how the policy was
built; and the columns `seed`, `hazard_onset_s`, `handback_required`,
`ccd_avoidable_by_reference`, `max_jerk_automated`, `max_required_decel`, `tor_reason`.

**What changed.** v0.2 leaked the AC-02 boundary (the failure predicate was
`collision OR min_ttc < 1.5`, and a batch key was `min_ttc_below_1.5`) and the reference
level (the SQL help said the reference brakes at `0.9*mu*g`). Discovery objectives are now a
separate public config whose numbers may not coincide with acceptance values, and the
`avoidable_by_reference` column is described without parameters.

**How it is tested** (`tests/test_agent_isolation.py`). `avval/protected.py` derives the
protected set from the actual release configuration (every acceptance number, formula,
identifier and name; reference, driver, monitor, actuator and exposure values; driver
sources) plus a list of protected terms. The test builds the complete agent-visible payload
(prompt, tool schemas, first message, system spec, and the keys and messages of every tool
result, including validation, SQL and submission errors) and checks that no protected term,
formula or non-public number appears. Canary tests inject leaks (a threshold, 0.9·μg, a
driver mean, a monitor threshold, a criterion ID, the training method, a generated tool
description) and require the checker to catch each. Numbers that are legitimately public
(ODD ranges, bins, budgets) cannot be hidden by omission; the term check prevents labelling
them as the protected quantity.

## Evidence protocol (`avval/evidence.py`)

Every `test_predicate` and `query_results` call is recorded in a content-addressed ledger
(full input and machine-readable result, SHA-256). A triggering condition is accepted only
if it has a description and a non-empty predicate; its `predicate_test_id` names a
successful test of exactly that predicate on the final data; its `evidence_query_id` names a
successful query of exactly its `evidence_sql`, on the final data, with at least one row;
the evidence SQL contains the predicate; and re-executing both at submission reproduces the
logged hashes. One failing condition rejects the whole submission, and the agent is told
what is missing. Accepted submissions are written as an evidence bundle
(`results/evidence_<campaign>.json`) with every hash and the full ledger; the report is
rendered from it. Transcripts keep complete tool outputs with their hashes (v0.2 cut them at
2,000 characters).

## SQL sandbox (`avval/store.py`)

- A keyword filter accepts a single `SELECT`/`WITH` statement; string literals, quoted
  identifiers and comments are stripped first, so `'set'` or `"load"` are not false
  positives.
- The statement runs in a fresh in-memory DuckDB whose only table is a view over a snapshot
  of the campaign's rows (restricted to the visible columns for the agent); external access
  and extension auto-loading are disabled, the configuration is locked, memory is capped,
  queries time out after 10 s and results are row-limited.
- Tests bypass the filter and try writes, attaches, file and network reads, globbing and
  setting changes; each is refused by the sandbox itself.

This is defence in depth for a local tool, not a hardened multi-tenant boundary.

## Benchmark methodology

Protocol in `config/benchmark.yaml`, analysis in `avval/benchmark.py`.

- **Controlled comparison**, not evidence of general LLM superiority. Strategies: the agent,
  random, grid, cross-entropy method, evolutionary search, boundary-seeking bisection and
  Gaussian-process Bayesian optimisation (expected improvement on a robustness score).
- **Information fairness, stated precisely.** All strategies have the same ODD variables,
  ranges, coverage bins, visible run columns and simulation budget; baselines read them in
  programmatic form from `SearchInterface.domain()` (derived only from the agent's spec) and
  never touch the release configuration. The LLM additionally reads natural-language
  descriptions and can reason semantically. Visible columns include derived labels such as
  `avoidable_by_reference`, which is part of the primary benchmark region
  (`collision AND avoidable_by_reference AND driver_state = 'attentive'`): the region
  predicate itself is hidden, but one of its labels is not. Every strategy can read that
  label; the numerical baselines' robustness score uses only `collision`, `end_state` and
  `min_ttc` and does not exploit it. The benchmark therefore compares complete search
  strategies, including semantic reasoning, not optimisation efficiency on one identical
  objective; a target-agnostic ablation is on the roadmap.
- **Frozen protocol.** `benchmark-freeze` writes `results/benchmark_manifest.json` with the
  protocol, the agent interface hash (prompt, tools, discovery), the full baseline
  specification (`BASELINE_SPEC`: batch size, initial batches, CEM elite fraction, smoothing
  and minimum SD, evolutionary tournament, sigma and categorical mutation, boundary local
  sigma and bisection share, BO candidates, kernel, noise, acquisition and diversity rule,
  the robustness definition), the analysis version, the priors, release ID, runtime ID and
  evidence mode; its hash is the protocol ID every benchmark campaign records. Editing any
  of these after freezing, or running/reporting under another release or runtime, is refused.
  The agent CLI enforces the protocol's seeds, budget, model, turn limit, cost caps and the
  single infrastructure retry (`<name>_s<k>_retry1`, only for a failure before any run).
- **Completeness.** A confirmatory report needs, for every strategy, exactly one valid
  campaign per frozen seed (protocol, release, runtime, seed, strategy, lifecycle, runs,
  data hash, evidence mode), no extra protocol campaigns, protocol-defined agent endings,
  and one API-returned model ID across agent seeds. Otherwise the report is refused;
  `benchmark-report --partial` writes a labelled exploratory report without conclusions.
- **Analysis.** Detection shares with Clopper–Pearson intervals. At matched per-seed budgets:
  the posterior-predictive tail probability that a baseline detects the region in at least as
  many seeds as the agent, with its 95% upper credible bound (not a frequentist p-value).
  Model: a baseline campaign is a draw of its first-hit run T; the posterior over its
  distribution is a Bayesian bootstrap over the campaigns plus two pseudo-trajectories (hit
  immediately / never), with Dirichlet weights (1, …, 1, ½, ½). One weight vector is shared
  across all budgets, so detection probabilities stay nested in the budget; each single-budget
  marginal is exactly the Jeffreys posterior Beta(k + ½, m − k + ½) (tested). The implied
  prior is a Dirichlet process whose base mass sits only on the two extremes. A
  prior-sensitivity check (uniform prior, no prior) is reported, and the plug-in value only
  for comparison.
- **Time to first target.** The number of runs until a campaign's first run in the curve
  target (`curve_target: collision`) is estimated by Kaplan–Meier, with campaigns that never
  hit it censored at their length, and summarised as the restricted mean up to the budget.
  Differences in target cells found carry bootstrap intervals.
- **Conclusions** are generated in the form "under this simulator, information interface,
  target region and run budget, the evaluated agent … relative to `<baseline>`", followed by
  an explicit statement that they do not generalise.

## Results (v1.0)

The confirmatory benchmark of the final release (ten Sonnet 5 seeds against 100 campaigns of
each of six baselines, frozen protocol) is in [`results/benchmark.md`](../results/benchmark.md),
the held-out evaluation of the agents' conditions in
[`results/holdout_predicates.md`](../results/holdout_predicates.md). The v0.2 agent results
(random and grid baselines only, plug-in p-values, seeds 0–2 run before a written protocol)
are withdrawn; see [`corrections.md`](corrections.md). Agent transcripts, usage,
reports and evidence bundles of the ten seeds are in [`results/agent/`](../results/agent/).
