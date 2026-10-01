# Search report: Adaptive Cruise Control (learned policy) with driver-intervention request, SAE L2

**Campaign:** `agent_s0` · **Author:** agent (claude-sonnet-5) · **Date:** 2026-10-01

## Provenance

Recorded when the campaign was created (2026-09-30 22:12:40); method `agent`, budget 300, seed 0.

- Policy (`results/policy.json`) SHA-256: `5e14254aff132c1b2d674702e85ad3cc3d2c326c6c2440d9f3e43861ceb1a214`
- Source code (`avval/*.py`) SHA-256: `323ad8e4d13cff08036d2209d5ac43a8e8cf6a051335cfad2a8cc13522959500`
- Git commit: `uncommitted`
- Python 3.11.9; duckdb 1.5.5, numpy 2.4.6, scikit-learn 1.9.1
- Config `acceptance.yaml` SHA-256: `a7b59b09f1f62392bb43c562f6123b44e8cbedfbf105906dd7e4a72883254876`
- Config `driver.yaml` SHA-256: `b9dfc342b59084813b0e7d0125e655fae1996b254fce1bfc08f577cac84953b8`
- Config `exposure.yaml` SHA-256: `2b95ea73f490f4dfa3626f4cccbf31d5279d936a469e45a7da5eb1945750d3fe`
- Config `odd.yaml` SHA-256: `6551f07c7bb57a5a19f98a4fba07fc6951fc1980e38caf3aff22faadaf06147e`
- Config `reference.yaml` SHA-256: `5d96ab3655542260859e4c3f03c777413f20c97adc59f47deff4f3e8e0fefc06`

> **Re-rendered on 2026-10-01** by `scripts/rerender_agent_reports.py`, to attach the release verdict. The agent ran under source hash `323ad8e4d13c`; this release's is `330d6d3bcb9a`. The policy and the parsed configuration are identical and no simulation module changed (`docs/agent.md`). The summary, triggering conditions and hypothesis tests are the agent's own, from its logged submission; everything else is recomputed from the stored runs.

## Summary

## Campaign Summary
Budget used: 177/300 runs (108 for full coverage of all ODD cells, 69 for targeted hypothesis testing/confirmation).

Coverage: all 108 ODD coverage cells (lead_brake and cut_in, cross of ego_speed/friction/headway/lead_decel-or-closing_speed bins) were populated with at least one attentive-driver run; no collisions occurred in the pure coverage sweep, only a couple of borderline low-TTC cases in cut_in with short headway/high closing speed.

Two distinct, well-evidenced triggering conditions were found and confirmed with test_predicate (both showing large lift over the rest of the campaign's runs and tight enough intervals to be credible signals, not noise):

### 1. Tight cut-in with high closing speed ("cut-in TTC cliff")
`scenario='cut_in' AND headway < 0.45 AND closing_speed >= 8` (both near the top of the ODD ranges) drives failure (collision or min_ttc<1.5) in ~95-97% of runs, vs ~11-18% baseline elsewhere, lift ~5-9x. Critically this is **independent of driver_state** (both attentive and distracted drivers collide) because the geometric TTC at the moment of cut-in is so small (≈0.01-1s) that no human reaction time helps. At the very lowest ego speeds (15-18 m/s) the `preventable` flag is `false`, i.e. even an ideal controller braking at 0.9·µ·g would still collide — a genuine physics/ODD-edge limitation. But at ego_speed ≥ 22 m/s the same headway/closing-speed combination is flagged `preventable=true` in essentially all cases (20/20 in one check) — meaning an ideal system could have avoided or mitigated the collision but the function under test did not. This is a genuine SOTIF/function gap, not just an unavoidable physics scenario, once ego speed is moderate-to-high. A headway/closing-speed sweep at ego_speed=36 m/s located the cliff at roughly headway≈0.4-0.45s (below this, failures; at 0.5s+, safe) and closing_speed≈8-9 m/s (below 8, safe; at 9, failures), essentially independent of friction (0.5 vs 0.75 vs 1.0 made no visible difference in this region).

### 2. Distracted driver + lead-vehicle braking at short/moderate headway and moderate-to-high deceleration
`scenario='lead_brake' AND driver_state='distracted' AND headway < 1.6 AND lead_decel > 5` gives an 81% failure rate (13/16 collisions among the cases checked) vs 0% for the **identical parameter combinations with an attentive driver** (0/10, tight CI [0, 0.31]). This is a clean, large, driver-state-only effect: the system's TOR margin is sized for a prompt (attentive) reaction but not for the longer re-engagement time of a distracted driver (observed takeover_time 3-6 s vs ~1-2 s for attentive in the same scenarios). All flagged cases had `preventable=true`, meaning an ideal controller could still have avoided the crash — this is a function/TOR-timing deficiency interacting with foreseeable misuse (distraction), not unavoidable physics. The effect was present even at only moderately aggressive lead_decel=6 m/s² (not just the ODD extreme of 9 m/s²), and repeat runs at headway=1.5s, lead_decel=9 showed it is stochastic (driver reaction-time draw): one repeat avoided collision (min_ttc 0.67) while an identical-parameter repeat collided (min_ttc 0.03), confirming the driver reaction-time distribution is the deciding factor near the boundary.

## Limitations
- This was an exploratory search, not a statistically representative sample of the ODD; reported rates (e.g. 81%, 95%) describe my deliberately adversarial sub-populations, not real-world incidence.
- The cut-in cliff boundary was mapped mainly at friction=0.75 and a few speeds; the exact boundary surface (headway × closing_speed × ego_speed × friction) was not fully swept — only enough points to establish the cliff exists and is preventable at higher speed.
- The lead_brake/distraction condition was probed at a handful of headway/decel/ego_speed combinations; the true boundary (minimum headway or decel at which attentive drivers start to fail, or the minimum distraction-driven reaction time needed to cause collision) was not exhaustively mapped.
- I did not test friction extremes combined with the distraction condition, nor extensively vary ego_speed for the lead_brake/distraction trigger beyond ego_speed=29,36,15,22.

## Recommended next tests
1. Fully map the cut-in cliff boundary surface (headway, closing_speed, ego_speed, friction) to quantify exactly where the function is `preventable=true` (a real fix target) versus `preventable=false` (an ODD/physics limit that may warrant tightening the minimum-headway ODD bound for cut-ins).
2. Determine the minimum lead_decel and maximum headway at which the distracted-driver lead_brake failure appears, to define a precise TOR-timing margin requirement, and check whether raising the TOR lead time or issuing an earlier/more urgent TOR for the distracted state would close the gap.
3. Check for compounding of the two triggers (e.g., cut-in scenario with a distracted driver) and cross-check low-friction (0.5) surfaces more exhaustively for both triggers, since friction was only lightly varied within the adversarial regions found.

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

- Runs executed: 177
- Failing runs (`collision OR coalesce(min_ttc < 1.5, false)`): 50
- Distinct failing coverage cells: 9
- Runs to first failure: 57

### Failing coverage cells

| scenario | ego_speed | headway | friction | scenario_param | runs | failing | preventable_collisions |
| --- | --- | --- | --- | --- | --- | --- | --- |
| cut_in | 29-36 | 0.3-0.8667 | 0.75-1 | closing_speed 6-9 | 24 | 12 | 5 |
| lead_brake | 29-36 | 0.8-1.5333 | 0.75-1 | lead_decel 6-9 | 10 | 9 | 8 |
| cut_in | 15-22 | 0.3-0.8667 | 0.75-1 | closing_speed 6-9 | 8 | 8 | 0 |
| cut_in | 15-22 | 0.3-0.8667 | 0.5-0.75 | closing_speed 6-9 | 6 | 6 | 0 |
| cut_in | 29-36 | 0.3-0.8667 | 0.5-0.75 | closing_speed 6-9 | 6 | 5 | 5 |
| cut_in | 22-29 | 0.3-0.8667 | 0.75-1 | closing_speed 6-9 | 5 | 4 | 2 |
| lead_brake | 29-36 | 0.8-1.5333 | 0.5-0.75 | lead_decel 6-9 | 6 | 3 | 1 |
| lead_brake | 22-29 | 0.8-1.5333 | 0.75-1 | lead_decel 6-9 | 5 | 2 | 0 |
| lead_brake | 15-22 | 0.8-1.5333 | 0.75-1 | lead_decel 6-9 | 2 | 1 | 0 |

## Preventability

A collision is *unpreventable* if an ideal system braking at 0.9 μg from the moment the hazard appears also collides (`config/reference.yaml`). AC-01 and AC-03 count preventable runs only.

| collisions | preventable_collisions | unpreventable_collisions | unpreventable_runs |
| --- | --- | --- | --- |
| 33 | 21 | 12 | 12 |

## Coverage

108 / 108 coverage cells (100%) meet the minimum run count.

## Triggering conditions and evidence

### TC-01: Cut-in with short initial headway (<0.45 s) and high closing speed (>=8 m/s): near-universal failure (collision or min_ttc<1.5s), largely independent of driver attentiveness and friction. At ego_speed>=22 m/s these failures are flagged 'preventable' (an ideal controller could avoid them), indicating a genuine function/SOTIF gap rather than an unavoidable physics limit; at the lowest ego speeds (15-18 m/s) they are physics-limited (preventable=false).

Predicate: `scenario = 'cut_in' AND headway < 0.45 AND closing_speed >= 8 AND ego_speed >= 22`

```sql
SELECT count(*), avg(case when collision or coalesce(min_ttc<1.5,false) then 1.0 else 0.0 end) as failure_rate FROM runs WHERE scenario='cut_in' AND headway<0.45 AND closing_speed>=8 AND ego_speed>=22
```

| count_star() | failure_rate |
| --- | --- |
| 22 | 0.95 |

### TC-02: Lead-vehicle braking at short/moderate headway (<1.6 s) with moderate-to-high deceleration (>5 m/s^2) combined with a DISTRACTED driver: 81% failure rate vs 0% for an attentive driver under the identical parameter grid, driven by the distracted driver's longer takeover time (3-6s observed) consuming the available time-to-collision margin. Failures are flagged 'preventable', indicating a TOR-timing/margin deficiency for the foreseeable-misuse (distracted) driver state.

Predicate: `scenario = 'lead_brake' AND driver_state = 'distracted' AND headway < 1.6 AND lead_decel > 5`

```sql
SELECT driver_state, count(*), avg(case when collision or coalesce(min_ttc<1.5,false) then 1.0 else 0.0 end) as failure_rate FROM runs WHERE scenario='lead_brake' AND headway<1.6 AND lead_decel>5 GROUP BY driver_state
```

| driver_state | count_star() | failure_rate |
| --- | --- | --- |
| distracted | 18 | 0.83 |
| attentive | 12 | 0.0 |

## Hypothesis tests

Every `test_predicate` call, in order, over the agent's own runs.

| # | where | target | inside | outside | rate inside | rate outside | lift |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | `scenario = 'cut_in' AND headway < 0.7 AND closing_speed > 6` | failure | 6 | 102 | 0.333 | 0 | - |
| 2 | `scenario = 'cut_in' AND headway < 0.4 AND closing_speed > 8` | failure | 20 | 120 | 1 | 0.0583 | 17.1 |
| 3 | `scenario = 'lead_brake' AND headway < 1.0 AND lead_decel > 8 AND driver_state = 'distracted'` | failure | 8 | 132 | 0.625 | 0.167 | 3.75 |
| 4 | `scenario = 'cut_in' AND headway < 0.4 AND closing_speed > 8 AND preventable = true` | failure | 10 | 130 | 1 | 0.131 | 7.65 |
| 5 | `scenario = 'lead_brake' AND headway < 1.0 AND lead_decel > 8 AND driver_state = 'attentive'` | failure | 4 | 136 | 0 | 0.199 | 0 |
| 6 | `scenario = 'cut_in' AND headway < 0.5 AND closing_speed > 6 AND ego_speed >= 29` | failure | 10 | 130 | 1 | 0.131 | 7.65 |
| 7 | `scenario = 'lead_brake' AND driver_state = 'distracted' AND headway < 1.6 AND lead_decel > 5` | failure | 16 | 155 | 0.812 | 0.213 | 3.82 |
| 8 | `scenario = 'cut_in' AND headway < 0.45 AND closing_speed >= 8` | failure | 32 | 139 | 0.969 | 0.108 | 8.98 |
| 9 | `scenario = 'lead_brake' AND driver_state = 'attentive' AND headway < 1.6 AND lead_decel > 5` | failure | 10 | 161 | 0 | 0.286 | 0 |
| 10 | `scenario = 'cut_in' AND headway < 0.45 AND closing_speed >= 8 AND ego_speed >= 22` | failure | 20 | 151 | 0.95 | 0.179 | 5.31 |

- TC-01: submitted predicate tested 1 time(s) (tests 10).
- TC-02: submitted predicate tested 1 time(s) (tests 7).
