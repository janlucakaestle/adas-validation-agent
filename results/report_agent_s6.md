# Search report: Adaptive Cruise Control (learned policy) with driver-intervention request, SAE L2

**Campaign:** `agent_s6` · **Author:** agent (claude-sonnet-5) · **Date:** 2026-10-01

## Provenance

Recorded when the campaign was created (2026-10-01 19:46:55); method `agent`, budget 300, seed 6.

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

## Campaign summary (agent_s6, 220/300 runs used)

I ran a full 108-cell coverage sweep of the ODD (both scenarios, all coverage bins, alternating attentive/distracted), then spent the remaining budget hypothesis-testing two failure clusters that emerged, probing boundaries and repeating near-boundary cases to account for stochastic takeover time.

### Finding 1 — lead_brake, hard lead braking + distracted driver + not-too-long headway: ~100% failure in tested region
In the coverage sweep, **all** lead_brake failures (collision or min_ttc<1.5) occurred with a **distracted** driver; 0/27 attentive lead_brake runs failed across the full grid (incl. an extreme corner: ego=36 m/s, friction=0.5, headway=0.8s, lead_decel=9 m/s² — attentive survived, distracted collided in 3/3 repeats).
Refining the boundary: at fixed headway=1.17s/friction=0.75/ego=25.5, distracted runs were failure-free for lead_decel ≤ 4.5 m/s² (0/12) but failures appeared sharply at lead_decel ≥ 4.75 m/s². Combined with headway and speed, the condition
`driver_state=distracted AND lead_decel>=4.75 AND headway<2.6 AND ego_speed>=22`
gives **23/23 (100%) failures** in my runs, vs 0/11 for the identical window with an attentive driver. This isolates a genuine SOTIF misuse-sensitive gap: the function (plus a distracted driver's delayed takeover) cannot avoid the TTC breach when the lead brakes moderately-to-hard from a non-generous headway at highway-ish speeds. Longer headway (≥2.6s) or lower ego speed (<22 m/s) consistently avoided failure even with distracted drivers and hard braking, so the risk is specific to the short-headway/high-speed/hard-braking combination, not hard braking alone.
Note: lead_decel is capped by road friction (e.g. a requested 7.5–9 m/s² is only realized as ~4.9 m/s² at friction=0.5), which is why low-friction corners sometimes showed near-misses instead of outright collisions — but near-misses (min_ttc<1.5) still count as failures, so the triggering condition held regardless of friction.

### Finding 2 — cut_in with very short initial time-to-collision: deterministic failure, independent of driver state
A cut_in at short headway + high closing speed produces failures regardless of attentive/distracted state (both equally affected, e.g. 2/2 attentive vs 4/4 distracted in one matched set). Testing directly against the geometric quantity (initial_gap / closing_speed, i.e. the TTC at the instant of cut-in) gave a near-perfect split:
- `initial_gap_m/closing_speed < 1.5` → **13/13 (100%) failures**
- `initial_gap_m/closing_speed >= 1.5` → **0/61 (0%) failures**
All these failures are flagged `preventable=true`, meaning the simulator judges them avoidable by an ideal controller — i.e. this is a function performance gap (the policy does not instantaneously react hard enough at the moment of cut-in to keep TTC above 1.5s), not an inherent physics limit of the ODD. This condition affects attentive drivers too since it manifests before any driver reaction is even possible.

### What was NOT a strong driver
- Friction alone did not cleanly predict failure in cut_in; it mattered mainly in lead_brake by capping realized lead deceleration.
- cut_in with longer headway (>~0.7s) was failure-free across all tested closing speeds up to 9 m/s and across all driver states/frictions/speeds in both the coverage grid and follow-up probes.
- Attentive driver + lead_brake was failure-free across the entire tested grid, including extreme corners (low friction, high speed, high decel, short headway) — suggesting the intended-use configuration (supervising driver) is robust for lead_brake.

### Limitations
- Rates above are over my own non-random, hypothesis-driven samples; they are evidence of concentration, not real-world probabilities.
- The lead_brake boundary (decel 4.5→4.75, headway 2.6, speed 22) was located with a fairly coarse grid plus a handful of boundary probes; exact thresholds may shift slightly with finer sampling.
- Did not extensively explore combinations of distracted driver + cut_in beyond the short-TTC geometric regime (e.g., medium headway with very high closing speed and a distracted driver) — a plausible next probe.
- Did not test interaction of very low friction (0.5) with cut_in scenario beyond one corner (headway=0.3, closing=9) — worth more sampling to see if friction modulates the cut_in TTC-breach finding.

### Recommended next tests (if budget allowed)
1. Map the exact decel/headway/speed boundary surface for the lead_brake+distracted condition (finer grid + more repeats near the 4.5–4.75 m/s² and 2.0–2.8s headway edges).
2. Check whether the cut_in TTC<1.5-at-onset condition can be mitigated by any policy change at low closing speeds (3–5 m/s) with still-short headway, to see if the geometric predictor saturates or if there's a softer boundary.
3. Explore distracted driver + cut_in at moderate headway (0.7–1.4s) combined with high closing speed (7–9 m/s) with multiple repeats, since this region had limited sampling.

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

- Runs executed: 162
- Failing runs (`collision OR coalesce(min_ttc < 1.5, false)`): 41
- Distinct failing coverage cells: 20
- Runs to first failure: 6

### Failing coverage cells

| scenario | ego_speed | headway | friction | scenario_param | runs | failing | preventable_collisions |
| --- | --- | --- | --- | --- | --- | --- | --- |
| lead_brake | 22-29 | 0.8-1.5333 | 0.75-1 | lead_decel 6-9 | 8 | 8 | 8 |
| cut_in | 29-36 | 0.3-0.8667 | 0.5-0.75 | closing_speed 6-9 | 7 | 6 | 6 |
| cut_in | 15-22 | 0.3-0.8667 | 0.75-1 | closing_speed 6-9 | 3 | 3 | 0 |
| lead_brake | 22-29 | 0.8-1.5333 | 0.5-0.75 | lead_decel 6-9 | 4 | 3 | 0 |
| cut_in | 22-29 | 0.3-0.8667 | 0.75-1 | closing_speed 6-9 | 6 | 3 | 0 |
| lead_brake | 29-36 | 0.8-1.5333 | 0.5-0.75 | lead_decel 6-9 | 7 | 3 | 3 |
| lead_brake | 22-29 | 1.5333-2.2667 | 0.75-1 | lead_decel 6-9 | 3 | 2 | 1 |
| lead_brake | 15-22 | 1.5333-2.2667 | 0.5-0.75 | lead_decel 6-9 | 1 | 1 | 0 |
| lead_brake | 15-22 | 0.8-1.5333 | 0.75-1 | lead_decel 6-9 | 1 | 1 | 1 |
| lead_brake | 22-29 | 0.8-1.5333 | 0.5-0.75 | lead_decel 3.5-6 | 1 | 1 | 0 |
| lead_brake | 22-29 | 1.5333-2.2667 | 0.5-0.75 | lead_decel 6-9 | 1 | 1 | 0 |
| lead_brake | 22-29 | 2.2667-3 | 0.5-0.75 | lead_decel 3.5-6 | 1 | 1 | 0 |
| lead_brake | 22-29 | 1.5333-2.2667 | 0.75-1 | lead_decel 3.5-6 | 1 | 1 | 0 |
| lead_brake | 29-36 | 0.8-1.5333 | 0.5-0.75 | lead_decel 3.5-6 | 1 | 1 | 1 |
| lead_brake | 29-36 | 1.5333-2.2667 | 0.5-0.75 | lead_decel 6-9 | 1 | 1 | 1 |

## Preventability

A collision is *unpreventable* if an ideal system braking at 0.9 μg from the moment the hazard appears also collides (`config/reference.yaml`). AC-01 and AC-03 count preventable runs only.

| collisions | preventable_collisions | unpreventable_collisions | unpreventable_runs |
| --- | --- | --- | --- |
| 22 | 22 | 0 | 0 |

## Coverage

108 / 108 coverage cells (100%) meet the minimum run count.

## Triggering conditions and evidence

### TC-01: lead_brake scenario: distracted driver + moderately hard lead braking (>=4.75 m/s^2) + not-too-generous headway (<2.6s) + highway-ish ego speed (>=22 m/s) leads to near-certain failure (collision or TTC<1.5s), while the identical window with an attentive driver has zero failures.

Predicate: `scenario = 'lead_brake' AND driver_state = 'distracted' AND lead_decel >= 4.75 AND headway < 2.6 AND ego_speed >= 22`

```sql
SELECT count(*) n, sum(case when collision or min_ttc<1.5 then 1 else 0 end) failures FROM runs WHERE scenario='lead_brake' AND driver_state='distracted' AND lead_decel>=4.75 AND headway<2.6 AND ego_speed>=22
```

| n | failures |
| --- | --- |
| 23 | 23 |

### TC-02: cut_in scenario: when the initial time-to-collision at the moment of cut-in (initial_gap_m / closing_speed) is below 1.5s, the function (and driver, regardless of attentive/distracted state) cannot prevent the TTC/collision failure criterion from being breached; preventable=true on these runs indicates this is a function gap, not an unavoidable physics limit.

Predicate: `scenario = 'cut_in' AND initial_gap_m / closing_speed < 1.5`

```sql
SELECT count(*) n, sum(case when collision or min_ttc<1.5 then 1 else 0 end) failures, avg(preventable::int) avg_preventable FROM runs WHERE scenario='cut_in' AND initial_gap_m/closing_speed < 1.5
```

| n | failures | avg_preventable |
| --- | --- | --- |
| 13 | 13 | 1.0 |

### TC-03: Contrast / boundary check: attentive driver in lead_brake scenario shows zero failures across the full tested ODD grid including extreme corners (low friction, high speed, high lead_decel, short headway), indicating the misuse (distracted) condition above is the dominant risk driver for lead_brake, not the scenario parameters alone.

Predicate: `scenario = 'lead_brake' AND driver_state = 'attentive'`

```sql
SELECT count(*) n, sum(case when collision or min_ttc<1.5 then 1 else 0 end) failures FROM runs WHERE scenario='lead_brake' AND driver_state='attentive'
```

| n | failures |
| --- | --- |
| 30 | 0 |

## Hypothesis tests

Every `test_predicate` call, in order, over the agent's own runs.

| # | where | target | inside | outside | rate inside | rate outside | lift |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | `scenario = 'lead_brake' AND driver_state = 'distracted' AND lead_decel >= 4.75` | failure | 18 | 90 | 0.667 | 0.0222 | 30 |
| 2 | `scenario = 'lead_brake' AND driver_state = 'distracted'` | failure | 27 | 81 | 0.444 | 0.0247 | 18 |
| 3 | `scenario = 'lead_brake' AND driver_state = 'attentive'` | failure | 27 | 81 | 0 | 0.173 | 0 |
| 4 | `scenario = 'lead_brake' AND driver_state = 'distracted' AND lead_decel < 4.75` | failure | 9 | 99 | 0 | 0.141 | 0 |
| 5 | `scenario = 'lead_brake' AND driver_state = 'distracted' AND lead_decel >= 4.75 AND headway < 1.5` | failure | 6 | 102 | 0.833 | 0.0882 | 9.44 |
| 6 | `scenario = 'lead_brake' AND driver_state = 'distracted' AND lead_decel >= 4.75 AND headway >= 1.5` | failure | 12 | 96 | 0.583 | 0.0729 | 8 |
| 7 | `scenario = 'cut_in' AND headway < 0.5 AND closing_speed > 7` | failure | 6 | 142 | 1 | 0.211 | 4.73 |
| 8 | `scenario = 'cut_in' AND headway < 0.7 AND closing_speed > 6` | failure | 12 | 136 | 0.667 | 0.206 | 3.24 |
| 9 | `scenario = 'lead_brake' AND driver_state = 'distracted' AND lead_decel >= 4.75 AND headway < 2.8` | failure | 35 | 113 | 0.8 | 0.0708 | 11.3 |
| 10 | `scenario = 'cut_in' AND headway < 0.7 AND closing_speed > 6 AND driver_state = 'attentive'` | failure | 6 | 142 | 0.667 | 0.225 | 2.96 |
| 11 | `scenario = 'cut_in' AND headway < 0.7 AND closing_speed > 6 AND driver_state = 'distracted'` | failure | 6 | 142 | 0.667 | 0.225 | 2.96 |
| 12 | `scenario = 'cut_in' AND initial_gap_m / closing_speed < 1.5` | failure | 13 | 149 | 1 | 0.188 | 5.32 |
| 13 | `scenario = 'cut_in' AND initial_gap_m / closing_speed >= 1.5` | failure | 61 | 101 | 0 | 0.406 | 0 |
| 14 | `scenario = 'lead_brake' AND driver_state = 'distracted' AND lead_decel >= 4.75 AND headway < 2.6 AND ego_speed >= 22` | failure | 23 | 139 | 1 | 0.129 | 7.72 |
| 15 | `scenario = 'lead_brake' AND driver_state = 'distracted' AND lead_decel >= 4.75 AND headway < 2.0` | failure | 27 | 135 | 0.926 | 0.119 | 7.81 |
| 16 | `scenario = 'lead_brake' AND driver_state = 'attentive' AND lead_decel >= 4.75 AND headway < 2.6 AND ego_speed >= 22` | failure | 11 | 151 | 0 | 0.272 | 0 |

- TC-01: submitted predicate tested 1 time(s) (tests 14).
- TC-02: submitted predicate tested 1 time(s) (tests 12).
- TC-03: submitted predicate tested 1 time(s) (tests 3).
