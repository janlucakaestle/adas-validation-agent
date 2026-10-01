# Search report: Adaptive Cruise Control (learned policy) with driver-intervention request, SAE L2

**Campaign:** `agent_s2` · **Author:** agent (claude-sonnet-5) · **Date:** 2026-10-01

## Provenance

Recorded when the campaign was created (2026-09-30 22:28:18); method `agent`, budget 300, seed 2.

- Policy (`results/policy.json`) SHA-256: `5e14254aff132c1b2d674702e85ad3cc3d2c326c6c2440d9f3e43861ceb1a214`
- Source code (`avval/*.py`) SHA-256: `3be861a1d234ca069f86f2635425d52d1df7ba9d93f14db0fabea0f265664a89`
- Git commit: `uncommitted`
- Python 3.11.9; duckdb 1.5.5, numpy 2.4.6, scikit-learn 1.9.1
- Config `acceptance.yaml` SHA-256: `a7b59b09f1f62392bb43c562f6123b44e8cbedfbf105906dd7e4a72883254876`
- Config `driver.yaml` SHA-256: `b9dfc342b59084813b0e7d0125e655fae1996b254fce1bfc08f577cac84953b8`
- Config `exposure.yaml` SHA-256: `2b95ea73f490f4dfa3626f4cccbf31d5279d936a469e45a7da5eb1945750d3fe`
- Config `odd.yaml` SHA-256: `6551f07c7bb57a5a19f98a4fba07fc6951fc1980e38caf3aff22faadaf06147e`
- Config `reference.yaml` SHA-256: `5d96ab3655542260859e4c3f03c777413f20c97adc59f47deff4f3e8e0fefc06`

> **Re-rendered on 2026-10-01** by `scripts/rerender_agent_reports.py`, to attach the release verdict. The agent ran under source hash `3be861a1d234`; this release's is `330d6d3bcb9a`. The policy and the parsed configuration are identical and no simulation module changed (`docs/agent.md`). The summary, triggering conditions and hypothesis tests are the agent's own, from its logged submission; everything else is recomputed from the stored runs.

## Summary

## Campaign summary
Budget used: 219/300 runs (100% of the 108 coverage cells populated; remainder spent on hypothesis testing/confirmation).

Two distinct, well-evidenced triggering conditions for failure (`collision OR min_ttc < 1.5`) were found and confirmed. All collision rows inspected had `preventable = true`, i.e. an ideal 0.9·mu·g braking response would have avoided them — these are function deficiencies, not just physics limits of the scenario.

### 1. lead_brake + distracted driver + hard lead braking (lead_decel ≳ 5 m/s²)
- Systematic sweep of headway (0.8–2.8 s) × lead_decel (3–9 m/s²) at fixed ego_speed=25.5, friction=0.75 shows: with a **distracted** driver, failure rate is 77% (24/31) for lead_decel≥5, essentially independent of headway across the tested 0.8–2.8s range — the driver's re-engagement delay after the TOR consumes the margin that headway provides.
- The identical sweep with an **attentive** driver, same headway×decel grid (24 runs) plus 33 more attentive lead_brake coverage/friction-variation runs (57 total), produced only 1 failure (1.75%) — i.e. lift of ~6x for distracted vs attentive, and attentive is robust almost everywhere tested.
- Low friction (0.5) did not add extra failures on top of the decel/headway effect in the small probe done (12 runs, 0 collisions), so friction was not the dominant driver here (lead_decel and driver distraction dominate); this deserves more sampling if further budget is available.
- Repeated-seed runs (same nominal case, random takeover time) at decel=6, headway=1.5 show the failure is stochastic and takeover-time-dependent: 2/3 distracted repeats failed (min_ttc 1.22, 0.81, borderline 1.53) vs 0/3 attentive repeats failed (min_ttc 1.77–1.98), consistent with the driver-state effect being causal rather than incidental.

### 2. cut_in with short headway (≤0.4 s) and moderate-high closing speed (≥6 m/s)
- At headway ≤0.4s and closing_speed ≥6 m/s, the failure rate is 100% (15/15) regardless of driver state, vs 16.5% outside this region (lift ≈6x).
- Critically, this condition fails at the **same rate for attentive and distracted drivers** (8/8 attentive, 7/7 distracted both 100%; collision counts 2/8 and 2/7 respectively, near-identical min_ttc regardless of driver state/takeover time in repeated-seed tests, e.g. min_ttc=0.95 identical across 4 repeats with varying takeover times). This indicates the system itself (ACC control + TOR timing) cannot recover from aggressive close cut-ins even with a perfectly attentive supervisor — a genuine SOTIF gap in the intended-use ODD, not just foreseeable misuse.

### Limitations
- My own runs were selected to find and confirm failure clusters; the rates quoted (e.g. 77%, 100%) reflect a targeted search, not real-world exposure frequencies. The release verdict/failure rate will be computed separately.
- Friction's role in the lead_brake condition was only lightly probed (12 runs at friction=0.5); a fuller friction sweep at high decel would sharpen the boundary.
- The exact lead_decel/headway threshold for the distracted lead_brake condition was bracketed (failures appear from decel≈5 up, more severe at 7-9) but not finely resolved below decel=5; cut_in boundary was resolved to headway≈0.3-0.4s / closing_speed≈6-7 m/s but not swept at other ego speeds/frictions.

### Recommended next tests
1. Finer sweep of friction (0.5–1.0) crossed with lead_decel (5–9) under distracted state to check if low friction shifts the failure threshold to lower decelerations.
2. Sweep cut_in headway/closing_speed boundary at other ego speeds (15, 36 m/s) to confirm the ~0.4s/6 m/s threshold generalizes.
3. Larger repeat counts (10+) at the two boundary conditions to tighten confidence intervals on the failure rate given stochastic takeover time.

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

- Runs executed: 219
- Failing runs (`collision OR coalesce(min_ttc < 1.5, false)`): 53
- Distinct failing coverage cells: 16
- Runs to first failure: 6

### Failing coverage cells

| scenario | ego_speed | headway | friction | scenario_param | runs | failing | preventable_collisions |
| --- | --- | --- | --- | --- | --- | --- | --- |
| cut_in | 22-29 | 0.3-0.8667 | 0.75-1 | closing_speed 6-9 | 32 | 23 | 4 |
| lead_brake | 22-29 | 0.8-1.5333 | 0.75-1 | lead_decel 6-9 | 15 | 8 | 5 |
| lead_brake | 22-29 | 2.2667-3 | 0.75-1 | lead_decel 6-9 | 9 | 5 | 0 |
| lead_brake | 22-29 | 1.5333-2.2667 | 0.75-1 | lead_decel 6-9 | 9 | 3 | 1 |
| lead_brake | 22-29 | 0.8-1.5333 | 0.5-0.75 | lead_decel 3.5-6 | 3 | 2 | 0 |
| lead_brake | 22-29 | 0.8-1.5333 | 0.75-1 | lead_decel 3.5-6 | 5 | 2 | 0 |
| lead_brake | 15-22 | 1.5333-2.2667 | 0.5-0.75 | lead_decel 6-9 | 1 | 1 | 0 |
| lead_brake | 15-22 | 0.8-1.5333 | 0.75-1 | lead_decel 6-9 | 1 | 1 | 1 |
| lead_brake | 29-36 | 1.5333-2.2667 | 0.5-0.75 | lead_decel 6-9 | 1 | 1 | 1 |
| lead_brake | 29-36 | 0.8-1.5333 | 0.75-1 | lead_decel 6-9 | 1 | 1 | 1 |
| cut_in | 15-22 | 0.3-0.8667 | 0.5-0.75 | closing_speed 6-9 | 1 | 1 | 0 |
| cut_in | 15-22 | 0.3-0.8667 | 0.75-1 | closing_speed 6-9 | 1 | 1 | 0 |
| lead_brake | 22-29 | 0.8-1.5333 | 0.5-0.75 | lead_decel 6-9 | 3 | 1 | 0 |
| lead_brake | 22-29 | 1.5333-2.2667 | 0.5-0.75 | lead_decel 6-9 | 3 | 1 | 0 |
| lead_brake | 22-29 | 1.5333-2.2667 | 0.75-1 | lead_decel 3.5-6 | 5 | 1 | 0 |

## Preventability

A collision is *unpreventable* if an ideal system braking at 0.9 μg from the moment the hazard appears also collides (`config/reference.yaml`). AC-01 and AC-03 count preventable runs only.

| collisions | preventable_collisions | unpreventable_collisions | unpreventable_runs |
| --- | --- | --- | --- |
| 13 | 13 | 0 | 0 |

## Coverage

108 / 108 coverage cells (100%) meet the minimum run count.

## Triggering conditions and evidence

### TC-01: lead_brake scenario with a distracted driver and lead vehicle deceleration >= 5 m/s^2: failure rate 77% vs 13% outside this condition (lift ~6x), largely independent of initial headway (0.8-2.8s tested). Driver distraction is the dominant causal factor: the identical headway/decel grid with an attentive driver yields only 1.8% failures.

Predicate: `scenario = 'lead_brake' AND driver_state = 'distracted' AND lead_decel >= 5`

```sql
SELECT driver_state, count(*), sum(case when collision or min_ttc<1.5 then 1 else 0 end) as failures FROM runs WHERE scenario='lead_brake' AND lead_decel>=5 GROUP BY driver_state
```

| driver_state | count_star() | failures |
| --- | --- | --- |
| attentive | 34 | 1 |
| distracted | 34 | 26 |

### TC-02: cut_in scenario with short initial headway (<=0.4s) and closing speed >= 6 m/s: failure rate 100% (15/15) regardless of driver state (8/8 attentive, 7/7 distracted), vs 16.5% outside. This is a system-level limitation independent of driver supervision quality, not a foreseeable-misuse-specific issue.

Predicate: `scenario = 'cut_in' AND headway <= 0.4 AND closing_speed >= 6`

```sql
SELECT driver_state, count(*) n, sum(case when collision then 1 else 0 end) collisions, avg(min_ttc) FROM runs WHERE scenario='cut_in' AND headway<=0.4 AND closing_speed>=6 GROUP BY driver_state
```

| driver_state | n | collisions | avg(min_ttc) |
| --- | --- | --- | --- |
| attentive | 10 | 2 | 0.84 |
| distracted | 9 | 2 | 0.76 |

## Hypothesis tests

Every `test_predicate` call, in order, over the agent's own runs.

| # | where | target | inside | outside | rate inside | rate outside | lift |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | `scenario = 'lead_brake' AND driver_state = 'distracted' AND lead_decel > 6` | failure | 9 | 99 | 0.778 | 0.0303 | 25.7 |
| 2 | `scenario = 'lead_brake' AND driver_state = 'attentive' AND lead_decel > 6` | failure | 9 | 99 | 0 | 0.101 | 0 |
| 3 | `scenario = 'cut_in' AND headway < 0.9 AND closing_speed > 6` | failure | 6 | 102 | 0.333 | 0.0784 | 4.25 |
| 4 | `scenario = 'lead_brake' AND driver_state = 'distracted' AND lead_decel > 4 AND headway < 2.0` | failure | 12 | 96 | 0.583 | 0.0312 | 18.7 |
| 5 | `scenario = 'cut_in' AND headway < 0.4 AND closing_speed > 7` | failure | 4 | 160 | 1 | 0.194 | 5.16 |
| 6 | `scenario = 'lead_brake' AND driver_state = 'distracted' AND lead_decel >= 5` | failure | 31 | 178 | 0.774 | 0.129 | 5.99 |
| 7 | `scenario = 'lead_brake' AND driver_state = 'attentive'` | failure | 57 | 152 | 0.0175 | 0.303 | 0.058 |
| 8 | `scenario = 'cut_in' AND headway <= 0.4 AND closing_speed >= 6` | failure | 15 | 194 | 1 | 0.165 | 6.06 |
| 9 | `scenario = 'cut_in' AND headway <= 0.4 AND closing_speed >= 6 AND driver_state = 'attentive'` | failure | 8 | 201 | 1 | 0.194 | 5.15 |

- TC-01: submitted predicate tested 1 time(s) (tests 6).
- TC-02: submitted predicate tested 1 time(s) (tests 8).
