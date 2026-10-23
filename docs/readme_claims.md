# Claims and their sources

## Results

Final evidence of release `fe59625d…`, files in [`results/`](../results/). Every number is
conditional on the placeholder exposure weights and driver parameters. v0.2 numbers quoted in
`docs/corrections.md` come from the v0.2 result files (`git show v0.2:results/<file>`).

| Where | Claim | Source |
| --- | --- | --- |
| README figure | lead braking at 30 m/s, μ = 0.7 | `results/failure_boundary.png` (title), `results/failure_boundary.json` |
| README finding 1, corrections 1 | 0 margin-erosion runs without hand-back in 180,000 baseline runs | `results/findings.md` |
| README finding 1, corrections 1 | no hazardous run without a takeover request in `estimate` | `results/handback_diagnostics_estimate.md` |
| README finding 2, corrections 2 | agent 10/10; detection shares 1.00/0.61/0.58/0.81/0.75/0.18/1.00; runs to first collision 42.5/20.9/19.9/17.4/22.9/23.5/19.1; upper bounds 0.007, 0.002, 0.156, 0.043, 9.6e-07, 0.996; BO 100/100 | `results/benchmark.md` (strategy table, matched-budget table) |
| README finding 3, corrections 6 | 8/10 cut-in conditions zero exposure measure; distracted lead-braking condition exposure-supported in 8/10 seeds, collision rate 22.2–69.8% | `results/holdout_predicates.md` (support column, TC-01 rows) |
| README finding 4, corrections 3 | AC-07 0 of 2,647; AC-03 hand-back-required stratum 47.7% (n = 537); AC-03 1.88% overall | `results/report_estimate.md` (AC-07, AC-03 by stratum) |
| README finding 5 | indicative, single 2,000-run OAT variants (AC-07 n = 55, AC-08 n = 1,945): nominal (threshold 3.0 m/s², TTC 2 s) AC-07 0 of 55, AC-08 381 of 1,945 (19.6%); threshold 3.5 m/s² → AC-07 4 of 55, AC-08 355 of 1,945; threshold 2.5 m/s² → AC-07 0 of 55, AC-08 588 of 1,945 (30.2%); TTC 1.5 s → AC-08 305 of 1,945 (15.7%); TTC 3 s → AC-08 1,065 of 1,945 (54.8%); AC-07 0 of 55 in both TTC variants | `results/sensitivity_oat.csv` (rows `sens_oat_000`, `_027`, `_028`, `_029`, `_031`; columns `factor:tor_required_decel_mps2`, `factor:tor_ttc_s`, `AC-07_value`/`_n`, `AC-08_value`/`_n`) |
| README finding 5 | 3.5 m/s² is the braking authority and the hand-back oracle level | `config/sim.yaml` (`accel_min_mps2: -3.5`), `config/reference.yaml` |
| README finding 5, corrections 5 | 171 variants; AC-07 FAIL in 33/33 at threshold 3.5 m/s²; AC-08 FAIL in 33/33 at 2.5 m/s²; AC-03 FAIL in 171/171; 16 factors | `results/sensitivity_{oat,factorial2,lhs}.csv` (status and `factor:` columns), factor list in `results/sensitivity_oat.md` |
| README acceptance table | NO-GO; every value, bound, target and verdict of AC-01–AC-10; 69 events; cut-in stratum 5.17; AC-03 and AC-04 decided by their failing strata | `results/report_estimate.md` (verdict, acceptance table, strata) |
| README acceptance table | 61 of 69 AC-01 events are cut-ins | `results/ac01_clusters.md` |
| corrections 4 | 4,554 runs above 5 m/s³, 4,499 cut-ins; 4.95 m/s³ | `results/findings.md` |
| README reproduce | release ID `fe59625d…` | `results/RELEASE_ID` |
| README reproduce | evidence runtime CPython 3.11.9, Windows AMD64; runtime ID covers Python, OS and machine | `runtime.json` in the evidence package; provenance lines of `results/report_estimate.md`; `avval/provenance.py::runtime_id` |
| README reproduce | release ID recomputes from the public files; evidence commit | `python -m avval.cli release` in this repository; `results/EVIDENCE_MANIFEST.json` (`evidence_commit`) |
| README reproduce | package ≈ 98 MB, SHA-256 | `results/EVIDENCE_MANIFEST.json` (`package`) |
| README reproduce | agent cost ≈ $7.40 for ten seeds | sum of `est_cost_usd` in `results/agent/usage_agent_s*.json` ($7.39) |
| README reproduce | runtimes (≈ 16 min, 50 min, 2 h 45 min, 50 min, 20 min) | campaign `created`/`updated` times in the evidence package (`campaigns.json`); frozen-at times in `results/benchmark_manifest.json`, `results/sensitivity_manifest.json`, `results/holdout_protocol.json` |
| README reproduce | tests ≈ 11 min, `verify-package` ≈ 8 min, package step ≈ 10 min | measured on the author's machine while preparing v1.0 (not a result file) |
| evaluation | AC-03 and AC-10 both 1.88% (bound 2.04%), n = 20,031 each; 3 of 100,000 runs not avoided by the reference, all attentive (AC-09 n 79,969 vs AC-01 n 79,966) | `results/report_estimate.md` (acceptance table, AC-06, reference outcomes) |
| roadmap | AC-04 cut-in stratum 5.17 m/s³ (lower bound 5.167), overall 4.95 m/s³; 55 hand-back-required runs per 2,000-run variant | `results/report_estimate.md` (AC-04 by stratum); `results/sensitivity_oat.csv` (`AC-07_n`) |
| system | convergence: 0 flips, collision time ≤ 0.015 s, impact ≤ 0.23 m/s, median ΔTTC 0.0003 s | bounds asserted in `tests/test_sim_verification.py` |

## Model parameters (not results)

| Claim | Source |
| --- | --- |
| ODD ranges; 216 coverage cells (2 scenarios × 2 driver states × 54 bins) | `config/odd.yaml` |
| Authority, monitor thresholds, margins, horizon, step, delays | `config/sim.yaml` |
| Reference levels (0.9 μg ideal, status illustrative; hand-back oracle fixed at the nominal design authority 3.5 m/s², status provisional) | `config/reference.yaml` |
| Acceptance targets (1e-4, 1.5 s, 5%, 5 m/s³, 1% with 0.5 s latency, 25%; AC-09/AC-10 none), all `illustrative`; `min_n`, confidence 0.95 | `config/acceptance.yaml` |
| Sensitivity: 16 factors; 41 / 65 / 65 variants (OAT / 2⁶ factorial / 64-point LHS) of 2,000 runs | `config/sensitivity.yaml`, `avval/sensitivity.py::design` |
| Driver reaction times and response parameters, standstill hold 2.0 m/s² | `config/driver.yaml` and cited sources |
| Discovery targets (collision; near miss below 1.0 s) | `config/discovery.yaml` |
| Benchmark budget, seeds, strategies, analysis plan | `config/benchmark.yaml` |
| Sensitivity factors and ranges | `config/sensitivity.yaml` |
| Minimum n for a 5th/95th-percentile bound (59) | `avval/evaluation.py::quantile_n_needed`, `tests/test_acceptance.py` |
| SQL sandbox: 10 s timeout, 1 GB memory | `avval/store.py` |
| Author note (programme, 126 drivers) | the author's own statement, not a result of this repository |
