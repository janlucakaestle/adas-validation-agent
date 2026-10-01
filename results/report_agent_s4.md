# Search report: Adaptive Cruise Control (learned policy) with driver-intervention request, SAE L2

**Campaign:** `agent_s4` · **Author:** agent (claude-sonnet-5) · **Date:** 2026-10-01

## Provenance

Recorded when the campaign was created (2026-10-01 19:37:30); method `agent`, budget 300, seed 4.

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

## Campaign summary (agent_s4, 155/300 runs used)

Coverage: achieved full coverage of all 108 ODD bins (cut_in: ego_speed × headway × friction × closing_speed; lead_brake: ego_speed × friction × headway × lead_decel), each with ≥1 run, plus targeted follow-up runs (incl. repeated seeds) to probe boundaries and stochastic driver-takeover variability.

Two clear, evidenced triggering conditions for the failure predicate (collision OR min_ttc<1.5) were found, one driven mainly by foreseeable misuse (distracted driver) and one that is largely scenario/physics-driven regardless of driver state.

### 1. Hard lead-vehicle braking + distracted driver (lead_brake scenario)
When the lead vehicle brakes hard (lead_decel ≳ 4.75 m/s², i.e. upper half of the ODD range) and the driver is distracted (foreseeable misuse, slow to re-engage after the TOR), the function collides or loses adequate TTC margin far more often than under attentive supervision.
- `scenario='lead_brake' AND driver_state='distracted' AND lead_decel>=4.75`: inside failure rate 0.56 (27 runs) vs 0.19 outside, lift ≈3.0.
- Narrowing to `lead_decel>=6.0`: inside rate 0.73 (15 runs), lift ≈3.7; with additionally `takeover_time>=3.0`: inside rate 0.83 (12 runs), lift ≈4.1.
- Matched attentive-driver cases at the same severe settings (lead_decel up to 9, friction 1.0, short headway 0.8 s) never collided in our runs (0/12-18), though TTC margins were sometimes thin (min_ttc ≈1.3-1.5 s), showing the scenario is already demanding even for attentive drivers.
- Critically, 100% of the collisions in the `distracted + lead_decel>=4.75` group are flagged `preventable=true` — an ideal controller braking at 0.9·µ·g would have avoided them. The function under-brakes autonomously (max_decel often only ~3.5 m/s² even when ~8.8 m/s² was physically available at friction=1.0), relying on the driver to take over and brake harder; distracted drivers' longer reaction times then cause collisions. This is a genuine function deficiency, not a physics-limited edge case.
- Friction increases severity further (fail rate 0.40 at µ=0.625 → 0.67 at µ=0.875 → 1.0 at µ=1.0 for this slice), consistent with the lead vehicle being able to realize its full commanded deceleration at higher friction.
- Repeated-seed tests at a fixed boundary case (ego 25.5, headway 1.9 s, µ=0.625, lead_decel 7.5) showed outcome is sensitive to the random takeover-time draw: longer draws (≳4 s) produced collisions/near misses, shorter draws (~0.8-1 s, typical attentive) stayed safe — confirming driver reaction time is the proximate stochastic driver of this failure mode.

### 2. Very short headway + high closing-speed cut-in
`scenario='cut_in' AND headway<=0.4 AND closing_speed>=6.0` (i.e. headway near the ODD lower bound of 0.3 s, closing speed in the upper part of its range): inside failure rate 1.0 (12/12 runs), lift ≈8.0 vs 0.125 outside. A relaxed version `headway<=0.5 AND closing_speed>=6.0` still gives rate 0.89 (18 runs), lift ≈5.3.
- This occurs essentially independent of driver_state and ego_speed: both attentive and distracted drivers collide, because min_ttc collapses to ~0.01-0.04 s almost immediately at cut-in (the outcome is decided before any driver takeover can act).
- `preventable` is mixed: at friction=0.5 most of these collisions are `preventable=false` (an ideal system would also crash — genuine physics/ODD-edge limitation of very short headway + fast cut-in). At friction=1.0, however, roughly half are `preventable=true` (achieved max_decel well below the ~8.8 m/s² available), indicating the braking policy does not use the available tyre grip aggressively enough in this corner, compounding the physical difficulty.
- Boundary check: at headway=0.8 s with the same closing speed (9 m/s) the function is safe for ego_speed ≥22 m/s (min_ttc 1.8-3.2 s); only the lowest ego_speed (15 m/s) remains borderline (min_ttc 0.72 s). At headway=0.3 s even closing_speed as low as 3.5 m/s is safe (min_ttc≈1.3-3.1 s) — so the failure is specifically the combination of minimal headway with high closing speed, not either factor alone.

## Limitations
- This is a hypothesis-driven, non-uniform sample (coverage sweep + targeted probing); rates reported above describe concentration within my own runs, not real-world failure probabilities.
- Distracted-driver outcomes are stochastic (randomized takeover/reaction time); I only resampled a few boundary cells (3-6 repeats) to check sensitivity — more repeats would tighten the rate estimates.
- I did not exhaustively sweep closing_speed/headway/friction/ego_speed jointly at fine resolution near the two identified boundaries; the thresholds quoted (lead_decel≈4.75-6, headway≈0.4-0.5, closing_speed≈6) are approximate transition zones, not precisely fitted boundaries.
- cut_in headway<0.4s combined with low closing speed, and lead_brake with low lead_decel (<3.5) were not found to fail in my sampling — not formally proven safe, just unobserved as failing.

## Recommended next tests
1. Finer sweep of lead_decel (4.0-6.0 in steps of 0.5) crossed with takeover-time distribution (many repeats) to localize the exact decel/headway threshold at which distracted-driver collisions become likely, and to quantify how much autonomous braking authority (max_decel) the policy uses before vs after TOR.
2. Finer sweep of cut_in headway (0.3-0.6) × closing_speed (5-9) × friction, with more repeats, to separate the physics-limited (preventable=false) region from the function-deficient (preventable=true) region, and to check whether increasing braking aggressiveness at high friction would remove the preventable collisions.
3. More repeats of boundary lead_brake cases to convert the observed lift into a more stable estimate, given driver-reaction-time stochasticity.

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

- Runs executed: 155
- Failing runs (`collision OR coalesce(min_ttc < 1.5, false)`): 39
- Distinct failing coverage cells: 19
- Runs to first failure: 3

### Failing coverage cells

| scenario | ego_speed | headway | friction | scenario_param | runs | failing | preventable_collisions |
| --- | --- | --- | --- | --- | --- | --- | --- |
| cut_in | 15-22 | 0.3-0.8667 | 0.5-0.75 | closing_speed 6-9 | 5 | 5 | 0 |
| lead_brake | 15-22 | 0.8-1.5333 | 0.75-1 | lead_decel 6-9 | 5 | 5 | 2 |
| cut_in | 15-22 | 0.3-0.8667 | 0.75-1 | closing_speed 6-9 | 4 | 4 | 1 |
| cut_in | 29-36 | 0.3-0.8667 | 0.5-0.75 | closing_speed 6-9 | 8 | 4 | 2 |
| lead_brake | 29-36 | 0.8-1.5333 | 0.75-1 | lead_decel 6-9 | 4 | 3 | 2 |
| cut_in | 29-36 | 0.3-0.8667 | 0.75-1 | closing_speed 6-9 | 5 | 3 | 3 |
| cut_in | 22-29 | 0.3-0.8667 | 0.5-0.75 | closing_speed 6-9 | 4 | 2 | 0 |
| lead_brake | 22-29 | 1.5333-2.2667 | 0.5-0.75 | lead_decel 6-9 | 7 | 2 | 1 |
| lead_brake | 15-22 | 1.5333-2.2667 | 0.5-0.75 | lead_decel 6-9 | 1 | 1 | 0 |
| lead_brake | 22-29 | 0.8-1.5333 | 0.75-1 | lead_decel 6-9 | 1 | 1 | 0 |
| lead_brake | 22-29 | 1.5333-2.2667 | 0.75-1 | lead_decel 3.5-6 | 1 | 1 | 0 |
| lead_brake | 22-29 | 2.2667-3 | 0.75-1 | lead_decel 6-9 | 1 | 1 | 0 |
| lead_brake | 29-36 | 0.8-1.5333 | 0.5-0.75 | lead_decel 3.5-6 | 1 | 1 | 1 |
| lead_brake | 29-36 | 1.5333-2.2667 | 0.5-0.75 | lead_decel 6-9 | 1 | 1 | 1 |
| lead_brake | 29-36 | 2.2667-3 | 0.5-0.75 | lead_decel 3.5-6 | 1 | 1 | 1 |

## Preventability

A collision is *unpreventable* if an ideal system braking at 0.9 μg from the moment the hazard appears also collides (`config/reference.yaml`). AC-01 and AC-03 count preventable runs only.

| collisions | preventable_collisions | unpreventable_collisions | unpreventable_runs |
| --- | --- | --- | --- |
| 25 | 16 | 9 | 9 |

## Coverage

108 / 108 coverage cells (100%) meet the minimum run count.

## Triggering conditions and evidence

### TC-01: Hard lead-vehicle braking (lead_decel >= ~4.75 m/s^2, upper half of ODD) combined with a distracted driver: the system's autonomous braking authority is insufficient and relies on driver takeover; distracted drivers' longer reaction times lead to collisions/near-misses that an ideal controller (0.9*mu*g) would have avoided (preventable=true in all observed collisions in this slice).

Predicate: `scenario = 'lead_brake' AND driver_state = 'distracted' AND lead_decel >= 4.75`

```sql
SELECT friction, count(*) n, sum(case when collision then 1 else 0 end) coll, avg(case when coalesce(min_ttc<1.5,false) or collision then 1 else 0 end) fail_rate FROM runs WHERE scenario='lead_brake' AND driver_state='distracted' AND lead_decel>=4.75 GROUP BY friction ORDER BY friction
```

| friction | n | coll | fail_rate |
| --- | --- | --- | --- |
| 0.62 | 15 | 4 | 0.4 |
| 0.88 | 9 | 2 | 0.67 |
| 1.0 | 3 | 3 | 1.0 |

### TC-02: Stronger form of condition 1 restricted to the more severe braking and longer takeover delay: near three-quarters of these runs fail.

Predicate: `scenario = 'lead_brake' AND driver_state = 'distracted' AND lead_decel >= 6.0 AND takeover_time >= 3.0`

```sql
SELECT * FROM runs WHERE scenario='lead_brake' AND driver_state='distracted' AND lead_decel>=6.0 AND takeover_time>=3.0
```

| campaign | run_idx | seed | scenario | ego_speed | headway | initial_gap_m | lead_decel | closing_speed | friction | driver_state | driver_category | collision | impact_speed | min_ttc | min_ttc_accel | min_thw | min_gap | max_decel | max_jerk | max_jerk_raw | tor_issued | tor_time | takeover_time | duration | preventable | ccd_preventable |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| agent_s4 | 59 | 480544878 | lead_brake | 18.5 | 1.9 | 35.15 | 7.5 | nan | 0.62 | distracted | foreseeable_misuse | False | 0.0 | 1.36 | 1.55 | 1.36 | 1.67 | 3.5 | 1.93 | 7.7 | True | 1.85 | 4.7 | 19.95 | True | None |
| agent_s4 | 65 | 2016717040 | lead_brake | 18.5 | 1.17 | 21.58 | 7.5 | nan | 0.88 | distracted | foreseeable_misuse | True | 3.32 | 0.0 | 0.0 | 0.0 | nan | 3.5 | 3.83 | 4.74 | True | 1.05 | 4.82 | 5.25 | True | None |
| agent_s4 | 77 | 1022285776 | lead_brake | 25.5 | 1.9 | 48.45 | 7.5 | nan | 0.62 | distracted | foreseeable_misuse | True | 5.22 | 0.01 | 0.01 | 0.01 | nan | 5.52 | 4.04 | 25.0 | True | 1.05 | 6.07 | 7.25 | True | None |
| agent_s4 | 89 | 776991924 | lead_brake | 25.5 | 2.63 | 67.15 | 7.5 | nan | 0.88 | distracted | foreseeable_misuse | False | 0.0 | 0.3 | 0.66 | 0.3 | 0.34 | 7.73 | 8.45 | 25.0 | True | 1.2 | 6.01 | 8.15 | True | None |
| agent_s4 | 95 | 2066968926 | lead_brake | 32.5 | 1.9 | 61.75 | 7.5 | nan | 0.62 | distracted | foreseeable_misuse | True | 5.35 | 0.03 | 0.03 | 0.03 | nan | 5.52 | 4.04 | 25.0 | True | 1.05 | 4.63 | 7.95 | True | None |
| agent_s4 | 101 | 1588006697 | lead_brake | 32.5 | 1.17 | 37.92 | 7.5 | nan | 0.88 | distracted | foreseeable_misuse | True | 7.43 | 0.01 | 0.01 | 0.01 | nan | 7.73 | 8.45 | 25.0 | True | 1.05 | 3.23 | 5.95 | True | None |
| agent_s4 | 107 | 1153565619 | lead_brake | 32.5 | 2.63 | 85.58 | 7.5 | nan | 0.88 | distracted | foreseeable_misuse | False | 0.0 | 1.74 | 2.08 | 1.74 | 1.76 | 7.66 | 8.31 | 25.0 | True | 1.05 | 3.53 | 19.95 | True | None |
| agent_s4 | 134 | 388156459 | lead_brake | 20.0 | 0.8 | 16.0 | 9.0 | nan | 1.0 | distracted | foreseeable_misuse | True | 7.45 | 0.03 | 0.03 | 0.03 | nan | 3.5 | 5.22 | 8.69 | True | 1.05 | 4.83 | 4.05 | True | None |
| agent_s4 | 136 | 1955519436 | lead_brake | 36.0 | 0.8 | 28.8 | 9.0 | nan | 1.0 | distracted | foreseeable_misuse | True | 18.41 | 0.04 | 0.04 | 0.04 | nan | 3.5 | 4.87 | 9.36 | True | 1.05 | 5.67 | 4.65 | True | None |
| agent_s4 | 137 | 1882127290 | lead_brake | 36.0 | 3.0 | 108.0 | 9.0 | nan | 1.0 | distracted | foreseeable_misuse | True | 5.32 | 0.03 | 0.03 | 0.03 | nan | 8.83 | 10.66 | 25.0 | True | 1.05 | 5.21 | 8.05 | True | None |
| agent_s4 | 150 | 870266107 | lead_brake | 25.5 | 1.9 | 48.45 | 7.5 | nan | 0.62 | distracted | foreseeable_misuse | False | 0.0 | 1.57 | 1.65 | 1.57 | 1.72 | 5.52 | 4.04 | 25.0 | True | 1.05 | 3.43 | 19.95 | True | None |
| agent_s4 | 151 | 1086397362 | lead_brake | 25.5 | 1.9 | 48.45 | 7.5 | nan | 0.62 | distracted | foreseeable_misuse | False | 0.0 | 1.1 | 1.34 | 1.1 | 1.67 | 5.52 | 4.04 | 25.0 | True | 1.05 | 4.26 | 19.95 | True | None |

### TC-03: Cut-in with very short initial headway (<=0.4-0.5 s, near ODD lower bound) combined with high closing speed (>=6 m/s): min_ttc collapses to near-zero before any driver takeover can matter, producing near-certain failure independent of driver_state; partly a physics-limited ODD edge (preventable=false at low friction) but partly a genuine under-braking function deficiency at high friction (preventable=true, achieved deceleration well below available grip).

Predicate: `scenario='cut_in' AND headway<=0.5 AND closing_speed>=6.0`

```sql
SELECT friction, preventable, count(*) n, sum(case when collision then 1 else 0 end) coll FROM runs WHERE scenario='cut_in' AND headway<=0.5 AND closing_speed>=6.0 GROUP BY friction, preventable ORDER BY friction
```

| friction | preventable | n | coll |
| --- | --- | --- | --- |
| 0.5 | True | 3 | 2 |
| 0.5 | False | 7 | 7 |
| 1.0 | True | 6 | 5 |
| 1.0 | False | 2 | 2 |

## Hypothesis tests

Every `test_predicate` call, in order, over the agent's own runs.

| # | where | target | inside | outside | rate inside | rate outside | lift |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | `scenario = 'lead_brake' AND driver_state = 'distracted'` | failure | 27 | 81 | 0.407 | 0.0247 | 16.5 |
| 2 | `scenario = 'lead_brake' AND driver_state = 'distracted' AND lead_decel >= 4.75` | failure | 18 | 90 | 0.611 | 0.0222 | 27.5 |
| 3 | `scenario = 'lead_brake' AND driver_state = 'distracted' AND lead_decel >= 4.75 AND friction <= 0.625` | failure | 9 | 99 | 0.556 | 0.0808 | 6.88 |
| 4 | `scenario = 'lead_brake' AND driver_state = 'distracted' AND takeover_time >= 3.0` | failure | 15 | 93 | 0.667 | 0.0323 | 20.7 |
| 5 | `scenario = 'lead_brake' AND driver_state = 'distracted' AND lead_decel >= 4.75 AND ego_speed >= 25` | failure | 12 | 96 | 0.75 | 0.0417 | 18 |
| 6 | `scenario = 'lead_brake' AND driver_state='attentive' AND lead_decel >= 4.75 AND ego_speed >= 25` | failure | 12 | 96 | 0 | 0.135 | 0 |
| 7 | `scenario='cut_in' AND closing_speed>=7.5 AND headway<=0.6` | failure | 6 | 102 | 0.333 | 0.108 | 3.09 |
| 8 | `scenario='cut_in' AND headway<=0.4 AND closing_speed>=7.5` | failure | 12 | 112 | 1 | 0.125 | 8 |
| 9 | `scenario='cut_in' AND headway<=0.4 AND closing_speed>=6.0` | failure | 12 | 112 | 1 | 0.125 | 8 |
| 10 | `scenario='lead_brake' AND driver_state='distracted' AND lead_decel>=6.0` | failure | 12 | 128 | 0.833 | 0.195 | 4.27 |
| 11 | `scenario='lead_brake' AND driver_state='attentive' AND lead_decel>=9.0` | failure | 1 | 139 | 1 | 0.245 | 4.09 |
| 12 | `scenario = 'lead_brake' AND driver_state = 'distracted' AND lead_decel >= 4.75` | failure | 27 | 128 | 0.556 | 0.188 | 2.96 |
| 13 | `scenario='cut_in' AND headway<=0.5 AND closing_speed>=6.0` | failure | 18 | 137 | 0.889 | 0.168 | 5.29 |
| 14 | `scenario='lead_brake' AND driver_state='distracted' AND lead_decel>=6.0` | failure | 15 | 140 | 0.733 | 0.2 | 3.67 |
| 15 | `scenario='lead_brake' AND driver_state='distracted' AND lead_decel>=6.0 AND takeover_time>=3.0` | failure | 12 | 143 | 0.833 | 0.203 | 4.11 |

- TC-01: submitted predicate tested 2 time(s) (tests 2, 12).
- TC-02: submitted predicate tested 0 time(s).
- TC-03: submitted predicate tested 1 time(s) (tests 13).
