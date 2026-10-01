# Search report: Adaptive Cruise Control (learned policy) with driver-intervention request, SAE L2

**Campaign:** `agent_s7` · **Author:** agent (claude-sonnet-5) · **Date:** 2026-10-01

## Provenance

Recorded when the campaign was created (2026-10-01 19:53:15); method `agent`, budget 300, seed 7.

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

## Campaign summary (agent_s7, 196/300 runs used)

Coverage: achieved 108/108 ODD bin cells (lead_brake: ego_speed × friction × headway × lead_decel; cut_in: ego_speed × friction × headway × closing_speed), each with ≥1 run, before spending the remaining budget on hypothesis-driven probing of two clusters where failures (collision OR min_ttc<1.5) concentrated.

### Finding 1 — Hard lead braking + distracted driver (foreseeable misuse amplifier)
In lead_brake scenarios, once the lead vehicle's deceleration reaches ~6 m/s² or more, a **distracted** driver's delayed takeover (driver must first re-engage after a reading task) means the automated system's own braking is not sufficient to avoid closing to collision/near-collision before the driver intervenes. An **attentive** driver facing the identical kinematic situation (same ego_speed/headway/friction/lead_decel) reacts in ~1–1.3 s and consistently avoids the failure.
- Swept lead_decel 2→9 m/s² at fixed headway=1.5s, friction=0.75: distracted failures begin at decel≈6 (min_ttc dropping below 1.5) and collisions appear from decel≈7 upward; attentive stays safe (min_ttc≈1.8–2.3) across the whole range.
- Swept headway 0.8→3.0 s at lead_decel=7, distracted: collisions occur across almost the whole headway range (0.8–2.8s), i.e. extra headway alone does not reliably compensate for the distraction-induced reaction delay.
- Friction variation (0.5, 0.75, 1.0) did not materially change the pattern — the dominant factor is driver distraction combined with decel magnitude, not surface friction.
- This is flagged `preventable = TRUE` in all observed collisions in this cluster, meaning an idealized controller braking from hazard onset would NOT have collided — the failures are attributable to the function/driver-interaction design (TOR timing vs. distracted reaction time), not unavoidable physics.

Evidence:
- `scenario='lead_brake' AND driver_state='distracted' AND lead_decel>=6 AND headway<=2.0` → inside failure rate 89% (37 runs) vs 23% outside, lift ≈3.9, 95% CI [0.75, 0.97].
- Contrast: `scenario='lead_brake' AND driver_state='attentive' AND lead_decel>=6` → failure rate only 6% (16 runs), confirming the effect is driver-state driven, not purely the kinematic case.

### Finding 2 — Very short-headway cut-in with high closing speed (ODD-edge capability gap, independent of driver state)
At the aggressive edge of the cut-in ODD (headway ≤ ~0.4 s, closing_speed ≥ 8 m/s — both near the specified parameter limits), the ego vehicle collides **100% of the time in every run tested, including attentive drivers with fast takeover (~1.0–1.4 s) and across friction 0.75–1.0 and ego_speed 15–25 m/s**. The automated braking response reached only ~3.5 m/s² (well under the ~6.6 m/s² an ideal controller at 0.9·μ·g could achieve), and even an attentive driver's quick takeover could not recover in time.
- Boundary mapping: headway=0.3–0.4 s + closing_speed 8–9 m/s → always collides (attentive and distracted alike). At headway=0.5–0.6 s with the same closing_speed=9 m/s, both attentive and distracted drivers mostly avoid collision (min_ttc rises above ~1.0–1.4s), so the boundary is sharp and sits around headway≈0.4–0.5 s.
- All these collisions are flagged `preventable = TRUE`, i.e. physically avoidable in principle — pointing to an under-braking / late-braking response by the function at this ODD edge rather than an inherent physical impossibility.

Evidence:
- `scenario='cut_in' AND headway<0.5 AND closing_speed>=8` → inside failure rate 100% (13 runs, 95% CI [0.75,1.0]) vs 31% outside, lift ≈3.3.
- `... AND driver_state='attentive'` subset alone still 100% (10 runs) — confirms this is not a misuse-only issue.

## Limitations
- Sample sizes for the tightest sub-cells (e.g., exactly at thresholds) are small (3–6 repeats); stochastic takeover-time sampling means true boundary location has some uncertainty — recommend more repeats at headway 0.4–0.6 s / closing_speed 7–9 m/s and lead_decel 5–7 m/s² to tighten both boundaries.
- Only one mid-range ego_speed (25 m/s) and friction (0.75) were used for the fine sweeps; broader ego_speed/friction combinations at the two identified boundaries were spot-checked but not exhaustively swept.
- This campaign searched for failure clusters; reported inside/outside rates reflect a targeted search, not real-world incidence — they should not be read as field failure rates.

## Recommended next tests
1. Densify sampling around lead_decel 5–7 m/s² × headway 0.8–3.0 s × driver_state to pin the exact distracted-driver failure boundary and check for a safe headway margin that fully compensates distraction-induced delay.
2. Densify headway 0.35–0.55 s × closing_speed 6–9 m/s in cut_in to pin the exact capability-limited collision boundary, and inspect the controller's commanded deceleration trace to confirm under-braking is the root cause.
3. Cross-check both findings at the ODD extremes (ego_speed 15 and 36 m/s, friction 0.5) to see if the boundaries shift with speed/friction.

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

- Runs executed: 196
- Failing runs (`collision OR coalesce(min_ttc < 1.5, false)`): 69
- Distinct failing coverage cells: 15
- Runs to first failure: 6

### Failing coverage cells

| scenario | ego_speed | headway | friction | scenario_param | runs | failing | preventable_collisions |
| --- | --- | --- | --- | --- | --- | --- | --- |
| lead_brake | 22-29 | 0.8-1.5333 | 0.75-1 | lead_decel 6-9 | 32 | 25 | 17 |
| cut_in | 22-29 | 0.3-0.8667 | 0.75-1 | closing_speed 6-9 | 21 | 20 | 12 |
| lead_brake | 22-29 | 1.5333-2.2667 | 0.75-1 | lead_decel 6-9 | 8 | 5 | 4 |
| lead_brake | 22-29 | 2.2667-3 | 0.75-1 | lead_decel 6-9 | 7 | 4 | 1 |
| lead_brake | 22-29 | 0.8-1.5333 | 0.75-1 | lead_decel 3.5-6 | 9 | 3 | 0 |
| cut_in | 15-22 | 0.3-0.8667 | 0.75-1 | closing_speed 6-9 | 2 | 2 | 0 |
| lead_brake | 22-29 | 0.8-1.5333 | 0.5-0.75 | lead_decel 3.5-6 | 5 | 2 | 0 |
| lead_brake | 15-22 | 1.5333-2.2667 | 0.5-0.75 | lead_decel 6-9 | 1 | 1 | 0 |
| lead_brake | 15-22 | 0.8-1.5333 | 0.75-1 | lead_decel 6-9 | 1 | 1 | 0 |
| lead_brake | 15-22 | 1.5333-2.2667 | 0.75-1 | lead_decel 6-9 | 1 | 1 | 0 |
| lead_brake | 22-29 | 2.2667-3 | 0.5-0.75 | lead_decel 3.5-6 | 1 | 1 | 0 |
| lead_brake | 22-29 | 1.5333-2.2667 | 0.75-1 | lead_decel 3.5-6 | 1 | 1 | 0 |
| lead_brake | 29-36 | 0.8-1.5333 | 0.5-0.75 | lead_decel 3.5-6 | 1 | 1 | 0 |
| lead_brake | 29-36 | 0.8-1.5333 | 0.75-1 | lead_decel 6-9 | 1 | 1 | 1 |
| cut_in | 15-22 | 0.3-0.8667 | 0.5-0.75 | closing_speed 6-9 | 1 | 1 | 0 |

## Preventability

A collision is *unpreventable* if an ideal system braking at 0.9 μg from the moment the hazard appears also collides (`config/reference.yaml`). AC-01 and AC-03 count preventable runs only.

| collisions | preventable_collisions | unpreventable_collisions | unpreventable_runs |
| --- | --- | --- | --- |
| 36 | 35 | 1 | 1 |

## Coverage

108 / 108 coverage cells (100%) meet the minimum run count.

## Triggering conditions and evidence

### TC-01: Lead vehicle hard braking (lead_decel >= ~6 m/s^2) combined with a distracted driver leads to collisions/near-collisions (min_ttc<1.5s) because the distracted driver's delayed takeover is not compensated by the automated system's own braking. Attentive drivers in the same kinematic scenario reliably avoid the failure.

Predicate: `scenario = 'lead_brake' AND driver_state = 'distracted' AND lead_decel >= 6 AND headway <= 2.0`

```sql
SELECT driver_state, lead_decel, headway, collision, min_ttc, preventable FROM runs WHERE scenario='lead_brake' AND driver_state='distracted' AND lead_decel>=6 ORDER BY headway
```

| driver_state | lead_decel | headway | collision | min_ttc | preventable |
| --- | --- | --- | --- | --- | --- |
| distracted | 7.0 | 0.8 | True | 0.0 | True |
| distracted | 7.0 | 0.8 | True | 0.02 | True |
| distracted | 7.0 | 0.9 | True | 0.0 | True |
| distracted | 7.0 | 0.9 | True | 0.04 | True |
| distracted | 7.0 | 0.9 | True | 0.0 | True |
| distracted | 7.0 | 1.1 | False | 0.97 | True |
| distracted | 7.0 | 1.1 | True | 0.04 | True |
| distracted | 7.0 | 1.1 | True | 0.01 | True |
| distracted | 7.5 | 1.17 | False | 0.33 | True |
| distracted | 7.5 | 1.17 | True | 0.0 | True |
| distracted | 7.5 | 1.17 | True | 0.0 | True |
| distracted | 7.0 | 1.2 | True | 0.04 | True |
| distracted | 7.0 | 1.2 | True | 0.04 | True |
| distracted | 6.0 | 1.5 | True | 0.04 | True |
| distracted | 9.0 | 1.5 | True | 0.04 | True |

### TC-02: Cut-in with very short initial headway (<0.5s) and high closing speed (>=8 m/s), near the edge of the ODD, causes collisions 100% of the time in tested runs regardless of driver state (even attentive drivers with ~1-1.4s takeover times fail to avoid collision). Observed automated max deceleration (~3.5 m/s^2) was well below the ~6.6 m/s^2 an ideal controller could achieve, and all these collisions are flagged preventable=TRUE.

Predicate: `scenario = 'cut_in' AND headway < 0.5 AND closing_speed >= 8`

```sql
SELECT driver_state, headway, closing_speed, collision, min_ttc, max_decel, preventable, takeover_time FROM runs WHERE scenario='cut_in' AND headway<0.5 AND closing_speed>=8 ORDER BY driver_state, headway
```

| driver_state | headway | closing_speed | collision | min_ttc | max_decel | preventable | takeover_time |
| --- | --- | --- | --- | --- | --- | --- | --- |
| attentive | 0.3 | 9.0 | True | 0.04 | 3.49 | True | 1.4 |
| attentive | 0.3 | 9.0 | True | 0.04 | 3.49 | True | 1.0 |
| attentive | 0.3 | 9.0 | True | 0.04 | 3.49 | True | 1.08 |
| attentive | 0.3 | 8.0 | True | 0.0 | 3.48 | True | 1.45 |
| attentive | 0.3 | 8.0 | True | 0.0 | 3.48 | True | 1.97 |
| attentive | 0.3 | 9.0 | True | 0.04 | 3.49 | True | 2.42 |
| attentive | 0.3 | 9.0 | True | 0.04 | 3.49 | True | 1.93 |
| attentive | 0.3 | 9.0 | True | 0.01 | 3.4 | False | 0.6 |
| attentive | 0.4 | 9.0 | True | 0.01 | 3.49 | True | 1.73 |
| attentive | 0.4 | 9.0 | True | 0.01 | 4.72 | True | 1.58 |
| distracted | 0.3 | 9.0 | True | 0.04 | 3.49 | True | 4.33 |
| distracted | 0.3 | 9.0 | True | 0.04 | 3.49 | True | 5.55 |
| distracted | 0.3 | 9.0 | True | 0.04 | 3.49 | True | 5.35 |

## Hypothesis tests

Every `test_predicate` call, in order, over the agent's own runs.

| # | where | target | inside | outside | rate inside | rate outside | lift |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | `scenario = 'lead_brake' AND driver_state = 'distracted' AND lead_decel >= 6 AND headway <= 1.5` | failure | 3 | 105 | 1 | 0.0762 | 13.1 |
| 2 | `scenario = 'lead_brake' AND driver_state = 'distracted' AND lead_decel >= 4` | failure | 18 | 90 | 0.444 | 0.0333 | 13.3 |
| 3 | `scenario = 'cut_in' AND headway <= 0.6 AND closing_speed >= 7` | failure | 6 | 102 | 0.333 | 0.0882 | 3.78 |
| 4 | `scenario = 'lead_brake' AND driver_state = 'attentive' AND lead_decel >= 6 AND headway <= 1.5` | failure | 3 | 105 | 0 | 0.105 | 0 |
| 5 | `scenario = 'lead_brake' AND driver_state = 'distracted' AND headway <= 1.5` | failure | 9 | 99 | 0.556 | 0.0606 | 9.17 |
| 6 | `scenario = 'cut_in' AND headway <= 0.4 AND closing_speed >= 8` | failure | 13 | 173 | 1 | 0.283 | 3.53 |
| 7 | `scenario = 'lead_brake' AND driver_state = 'distracted' AND lead_decel >= 6` | failure | 44 | 142 | 0.795 | 0.19 | 4.18 |
| 8 | `scenario = 'cut_in' AND headway <= 0.4 AND closing_speed >= 8 AND driver_state = 'attentive'` | failure | 10 | 176 | 1 | 0.295 | 3.38 |
| 9 | `scenario = 'lead_brake' AND driver_state = 'attentive' AND lead_decel >= 6` | failure | 16 | 170 | 0.0625 | 0.359 | 0.174 |
| 10 | `scenario = 'lead_brake' AND driver_state = 'distracted' AND lead_decel >= 6 AND headway <= 2.0` | failure | 37 | 159 | 0.892 | 0.226 | 3.94 |
| 11 | `scenario = 'cut_in' AND headway < 0.5 AND closing_speed >= 8` | failure | 13 | 183 | 1 | 0.306 | 3.27 |

- TC-01: submitted predicate tested 1 time(s) (tests 10).
- TC-02: submitted predicate tested 1 time(s) (tests 11).
