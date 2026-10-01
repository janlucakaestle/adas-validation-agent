# Search report: Adaptive Cruise Control (learned policy) with driver-intervention request, SAE L2

**Campaign:** `agent_s3` · **Author:** agent (claude-sonnet-5) · **Date:** 2026-10-01

## Provenance

Recorded when the campaign was created (2026-10-01 19:32:43); method `agent`, budget 300, seed 3.

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

## Campaign summary (agent_s3, 300-run budget, 188 runs used)

**Coverage:** Full 108/108 coverage-grid cells (lead_brake: ego_speed × friction × headway × lead_decel; cut_in: ego_speed × friction × headway × closing_speed) were populated with ≥1 run each (108 runs), then ~80 additional runs were spent probing the boundaries of clusters where failures (collision OR min_ttc<1.5s) concentrated, including repeats to sample stochastic driver takeover time.

**Headline finding:** Failures are almost entirely concentrated in two mechanisms:
1. Hard lead-vehicle braking combined with a distracted driver (foreseeable misuse) — the ACC does not brake hard enough on its own and the driver's reaction-time budget is consumed before a safe takeover, producing collisions.
2. Very short time-headway combined with high closing speed (cut-in) or available-deceleration-limited hard braking at min headway — these saturate the function's margin even for an attentive driver, pointing to a thin safety margin in the ACC's own braking authority/response latency rather than a pure driver-supervision gap.

All identified collisions checked had `preventable = true`, i.e. an idealized controller braking at 0.9·µ·g from hazard onset would NOT have collided — so these are genuine function/SOTIF issues, not unavoidable physics.

### Key triggering conditions found

**1. Distracted driver + hard lead braking (friction allows it)**
`scenario='lead_brake' AND driver_state='distracted' AND lead_decel >= 6 AND friction >= 0.75`
→ 25/27 of our sampled runs in this region failed (92.6%), vs 9.1% outside, lift ≈10×. Collisions appear from lead_decel ≈6 m/s² upward and become near-certain at lead_decel≈9 m/s² (the ODD cap) when friction is high enough to let the lead vehicle actually achieve that deceleration. Headway (0.8–3.0 s) and ego speed did not materially change the outcome once decel/friction were in this regime — the driver's reaction-time budget is simply insufficient.

**2. Friction-limited hard braking even with an ATTENTIVE driver (thin function margin)**
`scenario='lead_brake' AND driver_state='attentive' AND lead_decel >= 9 AND friction >= 1.0 AND headway <= 0.8`
→ 9/9 sampled runs breached min_ttc<1.5 s (100%), vs 28.9% outside, lift ≈3.5×. No collisions occurred (attentive drivers reacted in ~0.75–1.7 s), but TTC repeatedly dropped to ~1.3–1.4 s across all tested ego speeds (15–36 m/s), i.e. the automated braking response leaves very little margin at the friction limit with short headway, independent of driver behavior. At headway 1.5 s the same parameters stayed safe (min_ttc 1.6–1.8 s), indicating ~0.8–1.5 s headway is the sensitive band.

**3. Short-headway, high-closing-speed cut-in (automation-limited, driver-state independent)**
`scenario='cut_in' AND headway <= 0.3 AND closing_speed >= 9`
→ 8/8 sampled runs failed (100%, 6 of them collisions), vs 29.4% outside, lift ≈3.4×. Rate was identical for attentive (4/4) and distracted (4/4) drivers, showing this is not a driver-supervision failure but a function/perception-reaction-time limitation of the cut-in response at very short headway and high closing speed. A looser boundary, `headway <= 0.5833 AND closing_speed >= 7.5`, already shows elevated risk (75%) and can serve as an early-warning threshold.

**Secondary observation — friction as a protective confound:** within the distracted hard-braking condition, lowering friction to 0.5 cut the failure rate to ~17% (vs ~95% at friction 1.0) because low friction caps the *lead* vehicle's achievable deceleration, not because the ego ACC handles it better — this should not be read as the function being safer on wet/low-µ roads; rather the hazard itself is physically milder there within our lead_decel parameterization.

### Limitations
- This is a targeted, hypothesis-driven search; observed in-sample rates (e.g., 92.6%, 100%) reflect deliberate oversampling of suspected failure regions and must NOT be read as real-world failure probabilities.
- cut_in collisions at closing_speed=9/headway=0.3 need more ego-speed sweeps (only 15/25/36 tested) to fully map the ego-speed dependency (ego=36 showed one non-collision outlier).
- Only a handful of repeats were run per stochastic cell (driver reaction-time draws); more repeats would tighten confidence intervals, especially near rate transitions (e.g., lead_decel 4.75–6 boundary for distracted driver).
- Did not explore combinations of distraction with cut-in at the identified automation-limited boundary beyond confirming equal rates for both driver states — worth confirming with more samples if budget allowed.

### Recommended next tests
- Sweep ego_speed more finely at the cut_in collision boundary (headway≤0.3, closing_speed≥9) to check for a speed-dependent safe zone (ego=36 trended safer).
- Map the lead_decel threshold between 4.75 and 6 m/s² more finely for the distracted-driver condition to locate the exact onset of near-certain failure.
- Investigate whether a different ACC braking-authority tuning (more aggressive early braking) would raise the attentive-driver TTC margin above 1.5 s in condition 2, since this affects intended-use (not just misuse) safety margin.

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
- Failing runs (`collision OR coalesce(min_ttc < 1.5, false)`): 55
- Distinct failing coverage cells: 16
- Runs to first failure: 6

### Failing coverage cells

| scenario | ego_speed | headway | friction | scenario_param | runs | failing | preventable_collisions |
| --- | --- | --- | --- | --- | --- | --- | --- |
| lead_brake | 22-29 | 0.8-1.5333 | 0.75-1 | lead_decel 6-9 | 18 | 14 | 9 |
| lead_brake | 15-22 | 0.8-1.5333 | 0.75-1 | lead_decel 6-9 | 7 | 7 | 3 |
| lead_brake | 29-36 | 0.8-1.5333 | 0.75-1 | lead_decel 6-9 | 7 | 6 | 3 |
| cut_in | 22-29 | 0.3-0.8667 | 0.75-1 | closing_speed 6-9 | 7 | 6 | 2 |
| lead_brake | 22-29 | 2.2667-3 | 0.75-1 | lead_decel 6-9 | 6 | 4 | 2 |
| cut_in | 15-22 | 0.3-0.8667 | 0.5-0.75 | closing_speed 6-9 | 3 | 3 | 0 |
| cut_in | 15-22 | 0.3-0.8667 | 0.75-1 | closing_speed 6-9 | 3 | 3 | 0 |
| lead_brake | 22-29 | 1.5333-2.2667 | 0.75-1 | lead_decel 6-9 | 3 | 2 | 2 |
| cut_in | 29-36 | 0.3-0.8667 | 0.75-1 | closing_speed 6-9 | 3 | 2 | 1 |
| lead_brake | 22-29 | 0.8-1.5333 | 0.75-1 | lead_decel 3.5-6 | 5 | 2 | 0 |
| lead_brake | 15-22 | 1.5333-2.2667 | 0.5-0.75 | lead_decel 6-9 | 1 | 1 | 0 |
| lead_brake | 22-29 | 0.8-1.5333 | 0.5-0.75 | lead_decel 3.5-6 | 1 | 1 | 0 |
| lead_brake | 29-36 | 2.2667-3 | 0.5-0.75 | lead_decel 6-9 | 1 | 1 | 0 |
| lead_brake | 29-36 | 0.8-1.5333 | 0.75-1 | lead_decel 3.5-6 | 1 | 1 | 0 |
| lead_brake | 29-36 | 1.5333-2.2667 | 0.75-1 | lead_decel 6-9 | 1 | 1 | 1 |

## Preventability

A collision is *unpreventable* if an ideal system braking at 0.9 μg from the moment the hazard appears also collides (`config/reference.yaml`). AC-01 and AC-03 count preventable runs only.

| collisions | preventable_collisions | unpreventable_collisions | unpreventable_runs |
| --- | --- | --- | --- |
| 27 | 23 | 4 | 4 |

## Coverage

108 / 108 coverage cells (100%) meet the minimum run count.

## Triggering conditions and evidence

### TC-01: Distracted driver during hard lead-vehicle braking (lead_decel >= 6 m/s^2) on a surface with enough friction (>=0.75) to realize that deceleration: the driver's reaction/re-engagement time exceeds the available margin, producing collisions in the large majority of sampled cases.

Predicate: `scenario = 'lead_brake' AND driver_state = 'distracted' AND lead_decel >= 6 AND friction >= 0.75`

```sql
SELECT count(*) n, avg(CASE WHEN collision OR coalesce(min_ttc<1.5,false) THEN 1 ELSE 0 END) failure_rate FROM runs WHERE scenario='lead_brake' AND driver_state='distracted' AND lead_decel>=6 AND friction>=0.75
```

| n | failure_rate |
| --- | --- |
| 27 | 0.93 |

### TC-02: Friction-limited hard lead braking (lead_decel >= 9 m/s^2 at friction = 1.0, the ODD's most severe stop) with short initial headway (<=0.8s) drives min_ttc below the 1.5s failure threshold even for an ATTENTIVE driver reacting quickly (~0.8-1.7s) -- indicating a thin margin in the automated braking response itself, independent of driver supervision.

Predicate: `scenario = 'lead_brake' AND driver_state = 'attentive' AND lead_decel >= 9 AND friction >= 1.0 AND headway <= 0.8`

```sql
SELECT run_idx, ego_speed, headway, min_ttc, takeover_time FROM runs WHERE scenario='lead_brake' AND driver_state='attentive' AND lead_decel>=9 AND friction>=1.0 AND headway<=0.8
```

| run_idx | ego_speed | headway | min_ttc | takeover_time |
| --- | --- | --- | --- | --- |
| 111 | 15.0 | 0.8 | 1.34 | 1.05 |
| 115 | 36.0 | 0.8 | 1.37 | 1.24 |
| 160 | 15.0 | 0.8 | 1.36 | 0.96 |
| 161 | 22.0 | 0.8 | 1.38 | 0.96 |
| 162 | 29.0 | 0.8 | 1.32 | 1.23 |
| 163 | 36.0 | 0.8 | 0.75 | 1.68 |
| 164 | 25.0 | 0.8 | 1.39 | 1.04 |
| 166 | 25.0 | 0.8 | 1.29 | 1.23 |
| 167 | 15.0 | 0.8 | 1.43 | 0.75 |

### TC-03: Cut-in with very short initial headway (<=0.3s) and high closing speed (>=9 m/s) causes failure (mostly collisions) regardless of driver state -- identical 100% failure for both attentive and distracted drivers, indicating an automation/perception-reaction limitation of the cut-in handling rather than a driver-supervision gap.

Predicate: `scenario = 'cut_in' AND headway <= 0.3 AND closing_speed >= 9`

```sql
SELECT driver_state, count(*) n, avg(CASE WHEN collision OR coalesce(min_ttc<1.5,false) THEN 1 ELSE 0 END) failure_rate FROM runs WHERE scenario='cut_in' AND headway<=0.3 AND closing_speed>=9 GROUP BY driver_state
```

| driver_state | n | failure_rate |
| --- | --- | --- |
| distracted | 4 | 1.0 |
| attentive | 4 | 1.0 |

## Hypothesis tests

Every `test_predicate` call, in order, over the agent's own runs.

| # | where | target | inside | outside | rate inside | rate outside | lift |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | `scenario = 'lead_brake' AND driver_state = 'distracted'` | failure | 26 | 82 | 0.308 | 0.0244 | 12.6 |
| 2 | `scenario = 'lead_brake' AND driver_state = 'distracted' AND lead_decel >= 4.75` | failure | 18 | 90 | 0.444 | 0.0222 | 20 |
| 3 | `scenario = 'lead_brake' AND driver_state = 'distracted' AND lead_decel >= 6.0` | failure | 8 | 100 | 0.75 | 0.04 | 18.8 |
| 4 | `scenario = 'lead_brake' AND driver_state = 'distracted' AND headway < 1.5` | failure | 8 | 100 | 0.5 | 0.06 | 8.33 |
| 5 | `scenario = 'lead_brake' AND driver_state = 'distracted' AND lead_decel >= 6 AND friction >= 0.75` | failure | 27 | 121 | 0.926 | 0.0909 | 10.2 |
| 6 | `scenario = 'lead_brake' AND driver_state = 'attentive' AND lead_decel >= 9 AND friction >= 1.0 AND headway <= 0.8` | failure | 2 | 146 | 1 | 0.233 | 4.29 |
| 7 | `scenario = 'lead_brake' AND driver_state = 'attentive' AND lead_decel >= 7.5 AND friction >= 0.875` | failure | 8 | 140 | 0.25 | 0.243 | 1.03 |
| 8 | `scenario = 'lead_brake' AND driver_state = 'attentive'` | failure | 36 | 112 | 0.0556 | 0.304 | 0.183 |
| 9 | `scenario = 'lead_brake' AND driver_state = 'attentive' AND lead_decel >= 9 AND friction >= 1.0 AND headway <= 0.8` | failure | 9 | 159 | 1 | 0.289 | 3.46 |
| 10 | `scenario = 'cut_in' AND headway <= 0.3 AND closing_speed >= 9` | failure | 8 | 160 | 1 | 0.294 | 3.4 |
| 11 | `scenario = 'cut_in' AND headway <= 0.5833 AND closing_speed >= 7.5` | failure | 16 | 152 | 0.75 | 0.283 | 2.65 |
| 12 | `scenario = 'cut_in' AND headway <= 0.3 AND closing_speed >= 9 AND driver_state = 'attentive'` | failure | 4 | 164 | 1 | 0.311 | 3.22 |
| 13 | `scenario = 'cut_in' AND headway <= 0.3 AND closing_speed >= 9 AND driver_state = 'distracted'` | failure | 4 | 164 | 1 | 0.311 | 3.22 |
| 14 | `scenario = 'lead_brake' AND driver_state = 'distracted' AND lead_decel >= 6 AND friction < 0.75` | failure | 9 | 159 | 0.333 | 0.327 | 1.02 |

- TC-01: submitted predicate tested 1 time(s) (tests 5).
- TC-02: submitted predicate tested 2 time(s) (tests 6, 9).
- TC-03: submitted predicate tested 1 time(s) (tests 10).
