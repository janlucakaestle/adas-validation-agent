# Evaluation: campaigns, validation status and findings

**Terminology.** The validation status is the overall result: GO, NO-GO or INSUFFICIENT
EVIDENCE. It is a validation recommendation to a release decision that is taken across
Product, Safety and Engineering. The code and the generated reports still call it the
`verdict`.

## Search vs. estimation

**Search campaigns** (random, grid, agent) report discovery metrics and failing coverage
cells, never a validation status. Over 100 seeds of 300 runs (`results/benchmark.md`):

| | random | grid |
| --- | --- | --- |
| P(contains a preventable attentive collision) | 67% (57–76%) | 64% (54–73%) |
| Distinct failing cells | 20.5 ± 2.5 | 21.1 ± 2.8 |
| Run of first failure | 8.8 ± 8.9 | 9.1 ± 8.9 |

Every seed of both found misuse hand-back collisions and comfort exceedances; 99% found
silent margin erosion. Before these evidence rules existed, a single 300-run campaign that
missed the pocket produced a false PASS on AC-01.

**The estimation campaign** (`estimate`, 100,000 runs) samples from the exposure model in
`config/exposure.yaml`. Acceptance criteria and the validation status are computed only from
it, so the status is the same whichever search campaign ran. Besides AC-01 to AC-04 (see the
README), AC-06 (information only) found 1 unpreventable collision in 100,000 runs.

## Status rules

Each criterion in `config/acceptance.yaml` declares a `kind`:

- `rate`: share of runs with an event, with a 95% Clopper–Pearson interval;
- `quantile`: a metric quantile, with a 95% percentile-bootstrap interval (fixed seed).

Each also has a `min_n` (placeholder 100, `TODO(data)`). Statuses:

- **PASS:** the point estimate *and* the conservative end of the interval meet the target,
  on at least `min_n` runs.
- **INSUFFICIENT EVIDENCE:** no data, fewer than `min_n` runs, or a point estimate that
  passes while the interval doesn't.
- **FAIL:** the point estimate misses the target, at any n.
- **NO FAILURES OBSERVED:** for zero-rate targets like AC-01, which testing can falsify but
  never prove. With no events in ≥ `min_n` runs the report states the 95% upper bound
  (≈ 3.7/n). Counts as passing.

NO-GO if any criterion fails; GO only if all pass; otherwise INSUFFICIENT EVIDENCE. INFO
criteria (AC-06) don't count. Thresholds are illustrative; a real programme would agree
them with Product and Safety.

## Provenance

A validation status holds only for the release it was computed on. Each campaign writes a
row to the `campaigns` table (name, creation time, method, budget, seed) with a provenance
record: SHA-256 of `results/policy.json`, of every file in `config/`, and over `avval/*.py`;
the git commit; and the Python, numpy, scikit-learn and duckdb versions. Text is hashed with
normalised line endings. Every report opens with this record.

An estimation counts as the current release when policy, config, code hashes and package
versions all match. The git commit is recorded but not compared, so a docs-only commit
doesn't invalidate results. It reads `uncommitted` when there's no repository or tracked
files outside `results/` have changes.

**Reproducibility.** Seeds are fixed, so re-running `estimate --n 100000 --seed 0` under the
release code reproduced the earlier estimation report exactly: every criterion value,
interval, sample size, the preventability table and coverage. Only the provenance lines
changed. The post-hoc and findings files regenerated from the new runs were byte-identical.
The two complete 100,000-run estimations took 22 and 36 minutes on a 4-core laptop.

## Sensitivity

`python -m avval.cli sensitivity` varies one assumption at a time, re-running the *same*
2,000-run exposure-weighted sample with identical cases and seeds:

- attentive mean takeover time 1.0–1.8 s, SD 0.4–0.6 s;
- ACC braking authority 3.0–4.5 m/s²;
- TOR required-deceleration threshold 2.5–3.5 m/s².

At 2,000 runs the baseline is NO-GO on AC-01 alone (AC-03 and AC-04 are INSUFFICIENT
EVIDENCE; the 100,000-run estimation settles both as FAIL). Results
(`results/sensitivity.md`, `.csv`, `.png`):

- **The attentive takeover time barely matters.** AC-01 stays FAIL throughout; only a 1.8 s
  mean adds a second collision (2 of 1,631).
- **The function's own parameters matter more.** Authority of 3.0 m/s² makes AC-03 FAIL
  (11.1%, n = 108), as does a TOR threshold of 3.5 m/s² (10.7%, n = 84), which also drops
  AC-02 to INSUFFICIENT EVIDENCE (1.58 s). AC-04 moves between PASS, INSUFFICIENT EVIDENCE
  and FAIL (4.42–5.05 m/s³).
- NO-GO in every variant.

## Findings

1. **Coverage is not confidence.** Every 300-run grid campaign covers all 108 cells, yet 36%
   contain no preventable attentive collision. Rare-event criteria need a minimum sample
   count within the relevant population (close, fast cut-ins with an attentive driver).
2. **Silent margin erosion.** The monitor's constant-speed TTC can't fall below 2 s without
   a hand-back, which held in all 60,000 benchmark runs. Acceleration-aware TTC can: it
   dropped below 2 s with no hand-back and no collision in 822 runs, all lead braking, to
   as low as 1.65 s. Friction makes no difference (409 runs below μ = 0.75, 413 above).
3. **Comfort exceedances come from cut-ins, and the metric matters.** The policy steps its
   braking without jerk limiting. Raw 20 Hz differencing gives a 95th-percentile jerk of
   7.32 m/s³, partly measuring the step size; 0.5 s smoothing gives 5.04 m/s³. All 4,338
   exceedances are cut-ins; the largest is 5.70 m/s³. A rate limiter on the policy output
   would remove them.
4. **Most attentive collisions are close, fast cut-ins.** 63 of the 67 AC-01 collisions are
   cut-ins, all with a headway of at most 0.74 s and a closing speed of at least 6.0 m/s:
   a box holding 2.5% of attentive cut-ins, with a collision rate of 8.0% inside
   (`results/ac01_clusters.md`). Rounded to 0.73 s and 6.1 m/s, as in the held-out check,
   the box holds 919 of the 100,000 runs and 61 of the collisions
   (`results/posthoc_predicates.md`). In every one of the 63 the takeover request fires at the
   moment of the cut-in, and an ordinary attentive reaction (median 1.31 s) comes too late.
   The other 4 are hard lead braking (7.5–8.5 m/s²) met by unusually slow attentive
   reactions (3.0–3.7 s). An attentive driver who reacts at hazard onset, and a careful and
   competent human reference, could reclassify many of them. The 3.5 m/s² authority and
   absent AEB are what leave the driver to cope.

Numbers behind these: `results/findings.md` and `results/ac01_clusters.md`.

## SOTIF mapping

| SOTIF concept | In this project |
| --- | --- |
| Specification and ODD | `config/odd.yaml`. `validate_case` rejects anything outside it, including a parameter from the wrong scenario. |
| Performance insufficiencies | Higher policy error on out-of-distribution states; 3.5 m/s² braking authority; no jerk limiting. |
| Specification insufficiencies | Monitor uses constant-speed TTC (finding 2); reliance on a distracted driver recovering within a published takeover time; no AEB. |
| Triggering conditions | Agent must evidence each claim with SQL (`submit_report`). Search reports list failing cells. `avval/benchmark.py::REGIONS` names four regions and measures detection probability per strategy. |
| Reasonably foreseeable misuse | The `distracted` state, covered by AC-03. |
| Acceptance criteria | Written before testing; rate or quantile with 95% interval and `min_n`; measured only on the estimation campaign. Thresholds, `min_n` and exposure are placeholders. |
| Four scenario areas | The attentive pocket sat in area 3 (unknown unsafe) when a single campaign missed it. The estimation measured it and all three agent seeds described it, moving it to area 2 (known unsafe). AC-06 keeps unpreventable collisions out of area 2. |
| Modify and re-validate | Provenance blocks stale validation statuses until `estimate` re-runs. `benchmark` and `compare` aren't blocked; re-running them is up to the engineer. The *modification* half isn't implemented: candidate fixes (rate limiter, acceleration-aware monitor, AEB, urgent-takeover data) are untested. |

## Commands

```bash
pip install -r requirements.txt
python -m avval.cli train                                   # train the system under test (~5 s)
python -m avval.cli characterise                            # dense sweep -> failure_boundary.png
python -m avval.cli estimate --n 100000 --seed 0            # exposure-weighted -> validation status, 20–40 min
python -m avval.cli baseline --method random --budget 300
python -m avval.cli baseline --method grid   --budget 300
python -m avval.cli benchmark --method random --seeds 100 --budget 300  # ~10 min
python -m avval.cli benchmark --method grid   --seeds 100 --budget 300
python -m avval.cli sensitivity                             # one-at-a-time assumptions, ~4 min
export ANTHROPIC_API_KEY=...                                 # model via --model or AVVAL_MODEL
python -m avval.cli agent --budget 300 --first-seed 0 --max-cost-usd 2.5  # one seed per call
python -m avval.cli compare random grid agent               # benchmark.md + discovery_curves.png
python -m avval.cli posthoc                                 # agent predicates on the estimation
python -m avval.cli findings                                # numbers behind the findings
pytest -q
```

Each campaign writes `results/report_<campaign>.md`. Agent campaigns also write
`results/usage_agent_s<k>.json` (tokens, cache hit rate, cost) and
`results/transcript_agent_s<k>.json`, a log of every tool call with its input and output.
The transcripts of the three agent seeds are in the repository. The results database is a
local output and is not.
