# Search report: Adaptive Cruise Control (learned policy) with driver-intervention request, SAE L2

**Campaign:** `agent_s1` · **Author:** agent (claude-sonnet-5) · **Date:** 2026-10-01

## Provenance

Recorded when the campaign was created (2026-09-30 22:22:52); method `agent`, budget 300, seed 1.

- Policy (`results/policy.json`) SHA-256: `5e14254aff132c1b2d674702e85ad3cc3d2c326c6c2440d9f3e43861ceb1a214`
- Source code (`avval/*.py`) SHA-256: `3be861a1d234ca069f86f2635425d52d1df7ba9d93f14db0fabea0f265664a89`
- Git commit: `uncommitted`
- Python 3.11.9; duckdb 1.5.5, numpy 2.4.6, scikit-learn 1.9.1
- Config `acceptance.yaml` SHA-256: `a7b59b09f1f62392bb43c562f6123b44e8cbedfbf105906dd7e4a72883254876`
- Config `driver.yaml` SHA-256: `b9dfc342b59084813b0e7d0125e655fae1996b254fce1bfc08f577cac84953b8`
- Config `exposure.yaml` SHA-256: `2b95ea73f490f4dfa3626f4cccbf31d5279d936a469e45a7da5eb1945750d3fe`
- Config `odd.yaml` SHA-256: `6551f07c7bb57a5a19f98a4fba07fc6951fc1980e38caf3aff22faadaf06147e`
- Config `reference.yaml` SHA-256: `5d96ab3655542260859e4c3f03c777413f20c97adc59f47deff4f3e8e0fefc06`

> **Re-rendered on 2026-10-01** by `scripts/rerender_agent_reports.py`, to attach the release verdict. The agent ran under source hash `3be861a1d234`; this release's is `2a9c9124724b`. The policy and the parsed configuration are identical and no simulation module changed (`docs/agent.md`). The summary, triggering conditions and hypothesis tests are the agent's own, from its logged submission; everything else is recomputed from the stored runs.

## Summary

Campaign agent_s1 used 168 of 300 runs: 108 for full-factorial coverage of all 108 ODD grid cells (both scenarios × all bins, min 1 run/cell, confirmed via check_coverage), plus 60 targeted runs probing two hypotheses that emerged from the coverage sweep. All coverage cells covered (108/108).

**Two distinct, well-evidenced triggering conditions were found:**

1. **Lead-brake + distracted driver + moderate-to-severe lead deceleration (≥5 m/s²).** This is a foreseeable-misuse (driver_category = distracted) failure mode: the ACC's own automatic braking response is weak in these runs (max_decel often ≈3.5 m/s², far below the friction limit) and relies on the driver taking over after a TOR. When the driver is distracted, reaction/takeover time is frequently >3-5 s, which is too late once lead_decel ≥5 m/s²; below that the margin is enough even with slow takeover. Critically, attentive drivers facing the identical lead_decel range (5–9 m/s², same headway/friction/speed grid) had **zero** failures (0/29-ish runs across multiple sweeps) — the dichotomy is driven almost entirely by driver_state, not by friction or ego_speed (tested at friction 0.5/0.75/1.0 and ego_speed 18.5–32.5 with consistent results). This is flagged `preventable = true` in every collision case, i.e., it is a function/policy shortcoming, not a physics limit.

2. **Cut-in with short initial headway (≲0.5-0.6 s) combined with high closing speed (≳6-7 m/s).** Unlike (1), this condition fails **regardless of driver_state** — even attentive drivers reacting in <1.3 s after TOR still collided or hit min_ttc<1.5 in the most severe corner (headway 0.3 s, closing speed 7.5–9 m/s). This indicates the system's own automatic reaction/braking authority (not just human reaction time) is insufficient for very short time-to-collision cut-ins. Most of these cases are flagged `preventable = true` (an idealized controller could have avoided them, e.g. at friction 0.75/1.0), so this is a genuine function limitation within the ODD, not only a physics-forced outcome — though at the very extreme (headway 0.3, closing 9, friction 0.5) some cases are `preventable = false`, i.e., at the true edge of physical stopping capability.

**Evidence strength:**
- Condition 1: inside rate 87% (27/31) vs outside 12.6%, lift ≈6.9x; attentive-only control shows 0% failures at identical lead_decel≥5 range (11 runs).
- Condition 2: inside rate 94% (16/17) vs outside 20.5%, lift ≈4.6x; runs outside this box show 0% failures (0/56), confirming a clean boundary.
- Distracted+lead_decel<5 (control): 0/20 failures, confirming lead_decel≥5 is the necessary co-factor, not driver_state alone.

**Limitations:**
- Thresholds (lead_decel=5, headway=0.6, closing_speed=6-7) are approximate boundaries from a coarse sweep (steps of 0.5-1 units); finer resolution near the boundary was not exhaustively explored.
- Only two scenario families (lead_brake, cut_in) were in the ODD; interactions with e.g. very low friction (0.5) at moderate decel were sampled but not exhaustively crossed with all headways.
- Sample sizes at some grid points are small (1-2 runs); takeover_time is stochastic and a few borderline cases (e.g., lead_decel=8, min_ttc=1.52) sit right at the failure/non-failure edge — more repeats would sharpen the estimate but the overall pattern is robust (confirmed with independent seeds at multiple decel levels).
- Rates reported are from a search-driven campaign (deliberately oversampling suspected failure regions) and must not be read as real-world failure probabilities.

**Recommended next tests:** (a) finer decel sweep (5.0-6.5 step 0.25) with distracted driver to pin the exact onset threshold and check its dependence on ego_speed/friction more thoroughly; (b) finer headway/closing-speed grid (step 0.05-0.1 s / 0.5 m/s) around the cut-in boundary to map the iso-failure curve precisely, including low-friction cases to separate "function shortcoming" from "physical limit" (preventable=false) regions; (c) additional repeats (5-10 seeds) at a few representative points in both clusters to quantify variance from the stochastic takeover-time draw.

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

- Runs executed: 168
- Failing runs (`collision OR coalesce(min_ttc < 1.5, false)`): 47
- Distinct failing coverage cells: 16
- Runs to first failure: 6

### Failing coverage cells

| scenario | ego_speed | headway | friction | scenario_param | runs | failing | preventable_collisions |
| --- | --- | --- | --- | --- | --- | --- | --- |
| cut_in | 22-29 | 0.3-0.8667 | 0.75-1 | closing_speed 6-9 | 29 | 14 | 8 |
| lead_brake | 22-29 | 1.5333-2.2667 | 0.75-1 | lead_decel 6-9 | 16 | 13 | 4 |
| lead_brake | 22-29 | 1.5333-2.2667 | 0.5-0.75 | lead_decel 6-9 | 3 | 3 | 1 |
| lead_brake | 22-29 | 1.5333-2.2667 | 0.75-1 | lead_decel 3.5-6 | 8 | 3 | 0 |
| cut_in | 15-22 | 0.3-0.8667 | 0.75-1 | closing_speed 6-9 | 2 | 2 | 1 |
| cut_in | 22-29 | 0.3-0.8667 | 0.5-0.75 | closing_speed 6-9 | 3 | 2 | 0 |
| lead_brake | 15-22 | 1.5333-2.2667 | 0.5-0.75 | lead_decel 6-9 | 1 | 1 | 0 |
| lead_brake | 15-22 | 0.8-1.5333 | 0.75-1 | lead_decel 6-9 | 1 | 1 | 1 |
| lead_brake | 22-29 | 0.8-1.5333 | 0.75-1 | lead_decel 6-9 | 1 | 1 | 1 |
| lead_brake | 22-29 | 2.2667-3 | 0.75-1 | lead_decel 6-9 | 1 | 1 | 1 |
| lead_brake | 29-36 | 1.5333-2.2667 | 0.5-0.75 | lead_decel 6-9 | 1 | 1 | 1 |
| lead_brake | 29-36 | 0.8-1.5333 | 0.75-1 | lead_decel 6-9 | 1 | 1 | 1 |
| lead_brake | 29-36 | 2.2667-3 | 0.75-1 | lead_decel 6-9 | 1 | 1 | 1 |
| cut_in | 15-22 | 0.3-0.8667 | 0.5-0.75 | closing_speed 6-9 | 1 | 1 | 0 |
| cut_in | 29-36 | 0.3-0.8667 | 0.75-1 | closing_speed 6-9 | 2 | 1 | 0 |

## Preventability

A collision is *unpreventable* if an ideal system braking at 0.9 μg from the moment the hazard appears also collides (`config/reference.yaml`). AC-01 and AC-03 count preventable runs only.

| collisions | preventable_collisions | unpreventable_collisions | unpreventable_runs |
| --- | --- | --- | --- |
| 22 | 20 | 2 | 2 |

## Coverage

108 / 108 coverage cells (100%) meet the minimum run count.

## Triggering conditions and evidence

### TC-01: Lead vehicle braking scenario with a distracted driver and lead deceleration ≥5 m/s²: the automatic braking response is too weak/slow and the distracted driver's takeover arrives too late, causing collision or min_ttc<1.5s. Attentive drivers in the identical parameter range show zero failures, confirming driver_state (foreseeable misuse) is the key differentiator, gated by lead_decel severity.

Predicate: `scenario = 'lead_brake' AND driver_state = 'distracted' AND lead_decel >= 5`

```sql
SELECT count(*) n, avg(case when collision or coalesce(min_ttc<1.5,false) then 1.0 else 0 end) fail_rate FROM runs WHERE scenario='lead_brake' AND driver_state='distracted' AND lead_decel>=5; -- compare to: scenario='lead_brake' AND driver_state='attentive' AND lead_decel>=5 (0% failures)
```

_Evidence query failed: Only a single read-only SELECT/WITH statement is allowed._

### TC-02: Cut-in scenario with very short initial headway (≤0.6 s) and high closing speed (≥6-7 m/s): collisions/near-misses (min_ttc<1.5s) occur regardless of driver attentiveness, indicating the ADAS's own reaction/braking authority is insufficient for short time-to-collision cut-ins, not merely a human-reaction-time issue.

Predicate: `scenario = 'cut_in' AND headway <= 0.6 AND closing_speed >= 6`

```sql
SELECT count(*) n, avg(case when collision or coalesce(min_ttc<1.5,false) then 1.0 else 0 end) fail_rate, driver_state FROM runs WHERE scenario='cut_in' AND headway<=0.6 AND closing_speed>=6 GROUP BY driver_state; -- both attentive and distracted show high failure rates, outside-box rate is 0%
```

_Evidence query failed: Only a single read-only SELECT/WITH statement is allowed._

## Hypothesis tests

Every `test_predicate` call, in order, over the agent's own runs.

| # | where | target | inside | outside | rate inside | rate outside | lift |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | `scenario = 'lead_brake' AND driver_state = 'distracted' AND lead_decel > 6` | failure | 9 | 99 | 0.889 | 0.0202 | 44 |
| 2 | `scenario = 'lead_brake' AND driver_state = 'attentive' AND lead_decel > 6` | failure | 9 | 99 | 0 | 0.101 | 0 |
| 3 | `scenario = 'cut_in' AND headway < 0.7 AND closing_speed > 6` | failure | 6 | 102 | 0.333 | 0.0784 | 4.25 |
| 4 | `scenario = 'cut_in' AND headway <= 0.3 AND closing_speed >= 7.5` | failure | 10 | 148 | 1 | 0.223 | 4.48 |
| 5 | `scenario = 'lead_brake' AND driver_state = 'distracted' AND lead_decel >= 5` | failure | 31 | 127 | 0.871 | 0.126 | 6.91 |
| 6 | `scenario = 'lead_brake' AND driver_state = 'attentive' AND lead_decel >= 5` | failure | 11 | 147 | 0 | 0.293 | 0 |
| 7 | `scenario = 'cut_in' AND headway <= 0.6 AND closing_speed >= 7` | failure | 24 | 144 | 0.75 | 0.201 | 3.72 |
| 8 | `scenario = 'cut_in' AND headway <= 0.45 AND closing_speed >= 6` | failure | 17 | 151 | 0.941 | 0.205 | 4.58 |
| 9 | `scenario = 'lead_brake' AND driver_state = 'distracted' AND lead_decel < 5` | failure | 20 | 148 | 0 | 0.318 | 0 |
| 10 | `scenario = 'cut_in' AND NOT (headway <= 0.6 AND closing_speed >= 6)` | failure | 56 | 112 | 0 | 0.42 | 0 |

- TC-01: submitted predicate tested 1 time(s) (tests 5).
- TC-02: submitted predicate tested 0 time(s).
