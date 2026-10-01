# Search report: Adaptive Cruise Control (learned policy) with driver-intervention request, SAE L2

**Campaign:** `agent_s9` · **Author:** agent (claude-sonnet-5) · **Date:** 2026-10-01

## Provenance

Recorded when the campaign was created (2026-10-01 20:03:29); method `agent`, budget 300, seed 9.

- Policy (`results/policy.json`) SHA-256: `5e14254aff132c1b2d674702e85ad3cc3d2c326c6c2440d9f3e43861ceb1a214`
- Source code (`avval/*.py`) SHA-256: `d47581e346c9e4f0ad01de5cbc2d6f1ae3264c6d3651fe8d4179b7f6981642c1`
- Git commit: `4a2c3a12faf900bcbbc9ce69d27241f06f866c6e`
- Python 3.11.9; duckdb 1.5.5, numpy 2.4.6, scikit-learn 1.9.1
- Config `acceptance.yaml` SHA-256: `5f3cedb44d86b64ad1bec906fd11ed06274c09ece5f21b100d12c261497e809f`
- Config `driver.yaml` SHA-256: `8f765277ffa14ccffeb486169c404a7dc3ac3073f19af9c187c871212ee6a2ca`
- Config `exposure.yaml` SHA-256: `7cae79c67676007b5c2164e57f2f40795e13d83646552875cb3d354e8443aa8c`
- Config `odd.yaml` SHA-256: `fb646eb5952b5af8971d63eb4dfe1ba0caa9d6b447be429f2ea08a3d3b080707`
- Config `reference.yaml` SHA-256: `43ab88cffbef2c0d8c0897fd6a0c75a205171dc5cae8cec0bc906f6cf0f6a709`

> **Re-rendered on 2026-10-01** by `scripts/rerender_agent_reports.py`, to attach the release verdict. The agent ran under source hash `d47581e346c9`; this release's is `2a9c9124724b`. The policy and the parsed configuration are identical and no simulation module changed (`docs/agent.md`). The summary, triggering conditions and hypothesis tests are the agent's own, from its logged submission; everything else is recomputed from the stored runs.

## Summary

## Campaign Summary (agent_s9, 192/300 runs used)

Full coverage achieved (108/108 ODD coverage cells). After the coverage sweep, I used the remaining budget to probe two clusters of failures found in the data and to confirm them with boundary/repeat testing and `test_predicate`.

### Finding 1 — cut-in with tight absolute gap + high closing speed (function limitation, affects BOTH attentive and distracted drivers)
Across the coverage grid, `cut_in` cases were almost always benign except when the initial absolute gap (headway × ego_speed) was small *and* closing speed was near the ODD maximum (~9 m/s). In that corner:
- 23/23 runs tested with `initial_gap_m <= 14.5` and `closing_speed >= 9` failed (collision or min_ttc<1.5), vs 18.7% outside (lift ≈5.3x, 95% CI on inside rate [0.85,1.0]).
- 17 of these were outright collisions; of those, 16 were flagged `preventable = true` (an ideal 0.9·mu·g braking response would have avoided the crash), meaning this is mostly a *policy/perception-timing deficiency*, not an unavoidable physics limit.
- This failure mode is **independent of driver_state** — attentive (intended-use) and distracted (foreseeable-misuse) drivers failed at the same rate (11/11 vs 8/8 in one matched test), and independent of friction (0.5–1.0) and ego_speed (15–36 m/s). The driving variable is the absolute gap at cut-in relative to closing speed, consistent with TTC = gap/closing_speed < ~1.5 s at the moment of the cut-in, before the system/driver can meaningfully react.
- Boundary mapping: gap ≤ ~11 m at closing_speed=9 → always collides; gap ≈13–14.5 m → TTC violation but not always a crash; gap ≥ ~19 m → safe.

### Finding 2 — lead_brake with distracted driver + severe braking (foreseeable-misuse / driver-supervision gap)
- `driver_state='distracted' AND lead_decel>=6.0 AND headway<=2.3`: 14/17 runs failed (82%) vs 21% outside over the whole table (lift ≈3.8x); when compared only against other distracted lead_brake runs outside this band, only 2/30 failed (6.7%), i.e. a much larger effective lift (~12x) once scenario/driver-state are held fixed.
- Attentive drivers under the *identical* parameter combinations (same ego_speed, friction, headway, lead_decel=7.5) never failed in repeated trials (0/9 across headway 1.17 and 1.9), with takeover times of 0.76–1.8 s, while distracted takeover times ranged ~2.5–8.8 s — the mechanism is the reaction-time delay of a distracted driver combined with a high-deceleration lead vehicle event that leaves insufficient margin.
- Headway matters: at max headway (3.0 s) even lead_decel=7.5 with a distracted driver was safe (0/3). The dangerous band is short-to-moderate headway (~0.8–2.3 s) combined with lead_decel ≥ 6 m/s². At lead_decel=3.5 no failures were observed (0/3) even with distracted drivers and short headway.
- Friction (0.5–1.0) did not show a clear monotonic effect in this band — collisions occurred at both low and high friction; the dominant driver is distraction reaction time vs. deceleration severity/headway margin, not tire-road friction per se.

### Limitations
- This is a search campaign, not a rate estimate: hit rates quoted (e.g., 82%, 100%) describe my deliberately adversarial sampling, not real-world collision probability.
- Only one scenario variable was swept finely at a time in places (e.g., lead_brake boundary probing fixed ego_speed=22, friction=0.75); interaction effects at untested corners (e.g., very low friction + near-boundary headway + moderate decel) are not fully characterized.
- cut-in corner-case boundary (gap/closing-speed threshold) was mapped with ~25 extra runs around the transition; finer resolution near gap≈12–14 m could sharpen the boundary further.
- Driver takeover time is stochastic; each parameter point was typically repeated 2–6 times — sufficient to detect large effects but not to pin down precise failure probabilities.

### Recommended next tests
1. Finer sweep of `cut_in` around gap 10–16 m at closing_speed 7–9 m/s to pin the exact preventable/non-preventable boundary, and check whether a different ACC lateral/longitudinal detection response could reduce the "preventable" collisions.
2. Sweep `lead_decel` 4.5–6.0 (the apparent threshold region) with distracted drivers at several headways to localize the exact onset more precisely than the 6.0 m/s² value used here.
3. Explore friction × distracted-driver interaction more systematically (orthogonal sweep) since this campaign's friction coverage in the risky band was opportunistic rather than exhaustive.

## Release verdict (from estimation campaign `estimate`): NO-GO

Not computed from this search campaign: criteria AC-01, AC-03, AC-04 failed. See `report_estimate.md` for the full report.

| id | name | value | 95% CI | target | n | min_n | status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| AC-01 | Collision-free with attentive supervision | 0.000837 | [0.000649, 0.00106] | <= 0.0 | 80025 | 100 | FAIL |
| AC-02 | TTC safety margin | 1.89 | [1.88, 1.89] | >= 1.5 | 99514 | 100 | PASS |
| AC-03 | Hand-back robustness under foreseeable misuse | 0.0927 | [0.0844, 0.102] | <= 0.05 | 4509 | 100 | FAIL |
| AC-04 | Longitudinal comfort | 5.04 | [5.03, 5.05] | <= 5.0 | 77863 | 100 | FAIL |
| AC-06 | Share of unpreventable runs (information only) | 1e-05 | [2.53e-07, 5.57e-05] | - | 100000 | 100 | INFO |

Rates use a 95% Clopper-Pearson interval, quantiles a 95% percentile bootstrap (fixed seed). A PASS needs the conservative end of the interval to meet the target.

## Discovery

Search campaigns choose where to look, so their failure *rates* say nothing about real-world risk and are not reported. What matters is what the search found and how fast.

- Runs executed: 178
- Failing runs (`collision OR coalesce(min_ttc < 1.5, false)`): 52
- Distinct failing coverage cells: 21
- Runs to first failure: 6

### Failing coverage cells

| scenario | ego_speed | headway | friction | scenario_param | runs | failing | preventable_collisions |
| --- | --- | --- | --- | --- | --- | --- | --- |
| cut_in | 22-29 | 0.3-0.8667 | 0.75-1 | closing_speed 6-9 | 14 | 10 | 5 |
| lead_brake | 22-29 | 0.8-1.5333 | 0.75-1 | lead_decel 6-9 | 9 | 6 | 5 |
| cut_in | 15-22 | 0.3-0.8667 | 0.5-0.75 | closing_speed 6-9 | 5 | 5 | 0 |
| cut_in | 15-22 | 0.3-0.8667 | 0.75-1 | closing_speed 6-9 | 5 | 5 | 1 |
| cut_in | 29-36 | 0.3-0.8667 | 0.75-1 | closing_speed 6-9 | 6 | 5 | 4 |
| lead_brake | 22-29 | 0.8-1.5333 | 0.5-0.75 | lead_decel 6-9 | 7 | 3 | 0 |
| cut_in | 15-22 | 0.8667-1.4333 | 0.75-1 | closing_speed 6-9 | 3 | 2 | 0 |
| cut_in | 22-29 | 0.3-0.8667 | 0.5-0.75 | closing_speed 6-9 | 3 | 2 | 0 |
| lead_brake | 22-29 | 0.8-1.5333 | 0.75-1 | lead_decel 3.5-6 | 6 | 2 | 0 |
| lead_brake | 15-22 | 1.5333-2.2667 | 0.5-0.75 | lead_decel 6-9 | 1 | 1 | 0 |
| lead_brake | 15-22 | 0.8-1.5333 | 0.75-1 | lead_decel 6-9 | 1 | 1 | 1 |
| lead_brake | 22-29 | 1.5333-2.2667 | 0.5-0.75 | lead_decel 6-9 | 1 | 1 | 0 |
| lead_brake | 22-29 | 2.2667-3 | 0.5-0.75 | lead_decel 3.5-6 | 1 | 1 | 0 |
| lead_brake | 22-29 | 1.5333-2.2667 | 0.75-1 | lead_decel 3.5-6 | 1 | 1 | 0 |
| lead_brake | 29-36 | 1.5333-2.2667 | 0.5-0.75 | lead_decel 6-9 | 1 | 1 | 1 |

## Preventability

A collision is *unpreventable* if an ideal system braking at 0.9 μg from the moment the hazard appears also collides (`config/reference.yaml`). AC-01 and AC-03 count preventable runs only.

| collisions | preventable_collisions | unpreventable_collisions | unpreventable_runs |
| --- | --- | --- | --- |
| 25 | 18 | 7 | 7 |

## Coverage

108 / 108 coverage cells (100%) meet the minimum run count.

## Triggering conditions and evidence

### TC-01: cut_in with small absolute initial gap combined with high closing speed causes near-certain failure (collision or TTC<1.5s), regardless of driver attentiveness, friction, or ego speed. Majority of collisions are 'preventable' (an ideal braking response would avoid them), indicating a genuine function/policy deficiency at this ODD corner rather than only a physics limit.

Predicate: `scenario = 'cut_in' AND initial_gap_m <= 14.5 AND closing_speed >= 9`

```sql
SELECT count(*) n, sum(case when collision or min_ttc<1.5 then 1 else 0 end) fails, sum(case when preventable then 1 else 0 end) preventable_count FROM runs WHERE scenario='cut_in' AND initial_gap_m<=14.5 AND closing_speed>=9
```

| n | fails | preventable_count |
| --- | --- | --- |
| 23 | 23 | 16 |

### TC-02: lead_brake with a distracted driver facing a severe lead-vehicle deceleration (>=6 m/s^2) at short-to-moderate headway (<=2.3s) produces a high failure rate; attentive drivers under matched parameters do not fail, isolating distraction-induced reaction delay (vs. an idealized ~1-2s attentive takeover) as the driving mechanism rather than friction or speed.

Predicate: `scenario = 'lead_brake' AND driver_state = 'distracted' AND lead_decel >= 6.0 AND headway <= 2.3`

```sql
SELECT driver_state, count(*) n, sum(case when collision or min_ttc<1.5 then 1 else 0 end) fails FROM runs WHERE scenario='lead_brake' AND lead_decel>=6.0 AND headway<=2.3 GROUP BY driver_state
```

| driver_state | n | fails |
| --- | --- | --- |
| distracted | 19 | 16 |
| attentive | 14 | 0 |

## Hypothesis tests

Every `test_predicate` call, in order, over the agent's own runs.

| # | where | target | inside | outside | rate inside | rate outside | lift |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | `driver_state = 'distracted' AND lead_decel >= 4.75` | failure | 18 | 90 | 0.444 | 0.0222 | 20 |
| 2 | `driver_state = 'attentive'` | failure | 54 | 54 | 0.0185 | 0.167 | 0.111 |
| 3 | `scenario = 'lead_brake' AND driver_state = 'distracted' AND lead_decel >= 4.75 AND headway <= 1.9` | failure | 12 | 96 | 0.583 | 0.0312 | 18.7 |
| 4 | `scenario = 'lead_brake' AND driver_state = 'distracted' AND lead_decel = 7.5 AND headway <= 1.9` | failure | 6 | 102 | 1 | 0.0392 | 25.5 |
| 5 | `scenario = 'lead_brake' AND driver_state = 'distracted' AND lead_decel >= 6.0` | failure | 20 | 120 | 0.7 | 0.133 | 5.25 |
| 6 | `scenario = 'cut_in' AND headway <= 0.3 AND closing_speed >= 9` | failure | 8 | 132 | 1 | 0.167 | 6 |
| 7 | `scenario = 'cut_in' AND headway <= 0.5 AND closing_speed >= 9` | failure | 19 | 141 | 1 | 0.191 | 5.22 |
| 8 | `scenario = 'cut_in' AND headway <= 0.65 AND closing_speed >= 7.5` | failure | 31 | 129 | 0.839 | 0.155 | 5.41 |
| 9 | `scenario = 'lead_brake' AND driver_state = 'distracted' AND lead_decel >= 6.0 AND headway <= 2.3` | failure | 17 | 143 | 0.824 | 0.224 | 3.68 |
| 10 | `scenario = 'lead_brake' AND driver_state = 'distracted' AND lead_decel >= 6.0 AND headway <= 2.3` | failure | 17 | 149 | 0.824 | 0.215 | 3.83 |
| 11 | `scenario = 'lead_brake' AND driver_state = 'distracted' AND lead_decel >= 6.0 AND headway <= 2.3 AND headway > 0` | failure | 17 | 149 | 0.824 | 0.215 | 3.83 |
| 12 | `scenario = 'cut_in' AND headway <= 0.87 AND closing_speed >= 9` | failure | 22 | 144 | 1 | 0.167 | 6 |
| 13 | `scenario = 'cut_in' AND initial_gap_m <= 14.5 AND closing_speed >= 9` | failure | 23 | 155 | 1 | 0.187 | 5.34 |

- TC-01: submitted predicate tested 1 time(s) (tests 13).
- TC-02: submitted predicate tested 2 time(s) (tests 9, 10).
