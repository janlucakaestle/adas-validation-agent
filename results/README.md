# results/

Final outputs of release `fe59625d…`. This index is documentation, not evidence, and is not
listed in `EVIDENCE_MANIFEST.json`.

## Reports to read

- **Estimation:** [`report_estimate.md`](report_estimate.md) (verdict, acceptance criteria,
  strata), [`ac01_clusters.md`](ac01_clusters.md) (where the AC-01 events are),
  [`handback_diagnostics_estimate.md`](handback_diagnostics_estimate.md) (hazardous runs
  without a takeover request).
- **Benchmark:** [`benchmark.md`](benchmark.md) (seven strategies, matched-budget
  comparison, scoped conclusions).
- **Hold-out:** [`holdout_predicates.md`](holdout_predicates.md) (frozen conditions scored
  on 100,000 fresh runs).
- **Sensitivity:** [`sensitivity_oat.md`](sensitivity_oat.md),
  [`sensitivity_factorial2.md`](sensitivity_factorial2.md),
  [`sensitivity_lhs.md`](sensitivity_lhs.md).
- **Findings:** [`findings.md`](findings.md) (margin erosion, comfort and the jerk
  definition).
- **Figures:** [`failure_boundary.png`](failure_boundary.png),
  [`discovery_curves.png`](discovery_curves.png), [`sensitivity_oat.png`](sensitivity_oat.png).

## Machine-readable files

Byte-identical copies of files inside the evidence package, which `verify-package` re-hashes
and, where noted, recomputes.

- `benchmark_manifest.json`: the frozen benchmark protocol (strategies, seeds, budget,
  baseline hyper-parameters, priors, release and runtime IDs).
- `benchmark_analysis.json`: the benchmark analysis per campaign and the matched-budget
  comparison; recomputed by `verify-package`.
- `frozen_predicates.json`: the agent and reference predicates frozen before the hold-out,
  with the set hash.
- `reference_predicates.json`: the AC-01 event boxes derived from the estimation.
- `holdout_protocol.json`: the frozen hold-out execution (seed, size, region, target,
  exposure-mass settings).
- `holdout_predicates.json`: hold-out scores and support class per predicate; recomputed by
  `verify-package`.
- `sensitivity_manifest.json`: the frozen sensitivity protocol (factors, ranges, designs).
- `sensitivity_oat.csv`, `sensitivity_factorial2.csv`, `sensitivity_lhs.csv`: one row per
  variant with factor values and criterion statuses; statuses recomputed by `verify-package`.
- `failure_boundary.json`: the grid behind `failure_boundary.png` (collision probability by
  headway and lead deceleration).

## Inputs

- `policy.json`, `policy_meta.json`: the frozen release policy and its training record,
  loaded by the code (`results/policy.json` is part of the release ID).

## agent/

For each of the ten agent seeds (`s0`–`s9`): the full transcript (`transcript_agent_s*.json`),
API usage and cost (`usage_agent_s*.json`), the search report (`report_agent_s*.md`) and the
content-addressed evidence bundle behind each submitted condition (`evidence_agent_s*.json`).

## Identity

- `RELEASE_ID`: the release ID these results belong to.
- `EVIDENCE_MANIFEST.json`: SHA-256, release ID and evidence commit of every file above
  (except this index), the evidence-package archive hash, the raw data left out of git, and
  the commands to regenerate everything.
