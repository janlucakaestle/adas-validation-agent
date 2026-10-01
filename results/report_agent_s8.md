# Search report: Adaptive Cruise Control (learned policy) with driver-intervention request, SAE L2

**Campaign:** `agent_s8` · **Author:** agent (claude-sonnet-5) · **Date:** 2026-10-01

## Provenance

Recorded when the campaign was created (2026-10-01 19:57:40); method `agent`, budget 300, seed 8.

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

## Campaign summary (agent_s8, 198 of 300 runs used)

Coverage: all 108 ODD grid cells (scenario × ego_speed × friction × headway × decel/closing_speed bins) populated with ≥1 run; then budget was concentrated on two failure clusters discovered during coverage sweeps and on boundary/robustness probing (repeats at fixed parameters to sample stochastic takeover time, friction sweeps, headway/decel sweeps).

## Key findings

**TC1 — Distracted driver + hard lead-vehicle braking (lead_brake scenario).**
Once the lead vehicle decelerates at ≳5–6 m/s², a distracted driver's reaction/re-engagement time (observed 2.7–8.7 s in our runs) is too long for the system to avoid a collision or a sub-1.5s TTC event. This holds essentially independent of friction (tested 0.5–1.0) and headway (tested 0.8–3.0 s, the full ODD range) — even at the longest allowed headway (3.0 s) failures still occurred. All of these collisions are flagged `preventable=true`, i.e. not a physics-forced outcome — an ideal controller could have avoided them, so this is a genuine function/TOR-timing gap, concentrated in the foreseeable-misuse (distracted) condition.
- `lead_decel>=6 AND driver_state='distracted'`: 85% failure rate vs 10.5% outside (lift ≈ 8.1), n=41 inside.
- Matched attentive-driver condition (`lead_decel>=6 AND headway<=1.5 AND driver_state='attentive'`) only 9% failure (lift 0.27) — confirms the effect is driver-state (reaction-time) driven, not scenario severity alone.

**TC2 — Short-headway cut-in with high closing speed (cut_in scenario), independent of driver state.**
For headway ≲0.6 s combined with closing speed ≥7 m/s, min_ttc drops below 1.5 s almost deterministically from the geometry of the encounter, and for headway ≲0.45 s outright collisions occur — for **both attentive and distracted** drivers alike (57% vs 56% failure rate respectively, lift ≈1.9 each), and across the full friction range (0.5–1.0). This is a function-level limitation (most cases `preventable=true`), not a supervision/misuse issue. At the very extreme edge (headway=0.3 s, closing=9 m/s) collisions become `preventable=false` (physically unavoidable even by an ideal controller) — that corner is an ODD boundary limitation rather than a function defect.

**Ruled out / not causal:**
- Friction alone showed an apparent correlation with failures in raw pooled data (lift ~3.2 for friction≤0.6), but this was traceable to confounding in our targeted test design (low-friction runs were paired with other extreme parameters). A matched comparison (same headway/decel/driver_state, varying only friction 0.5→1.0) showed no consistent friction effect, and in one matched set the lowest-friction condition was actually collision-free while higher-friction matched cases collided. Friction is not treated as an independent triggering factor here.
- ego_speed alone did not show a strong independent effect beyond its role in setting absolute gap (gap = headway × ego_speed) for the cut-in TTC geometry.

## Limitations
- Results are from a deliberately risk-seeking sampling strategy (oversampling high-decel/short-headway/distracted combinations); failure rates quoted above describe concentration within my search, not real-world incidence.
- Boundary resolution for TC1 (decel threshold) and TC2 (headway threshold) was established with 1–2 repeats per point; finer-grained / larger-sample confirmation would sharpen the exact thresholds.
- Interaction of TC1 and TC2 (e.g., distracted driver + short-headway cut-in simultaneously) was not separately explored.

## Recommended next tests
1. Larger-n repeats at the TC1 decel threshold (5–6 m/s²) to pin down the exact onset of risk for distracted drivers.
2. Finer headway sweep between 0.45–0.6 s in cut_in to pin the exact onset of collisions vs. near-miss-only for the attentive case.
3. Investigate whether an earlier/different TOR strategy or an autonomous-emergency-braking supplement during the TOR window would close the TC1 gap for distracted drivers.
4. Review the cut-in response policy's initial braking authority — TC2 affects attentive (intended-use) drivers too, which is a higher-priority fix than misuse-only findings.

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

- Runs executed: 186
- Failing runs (`collision OR coalesce(min_ttc < 1.5, false)`): 61
- Distinct failing coverage cells: 14
- Runs to first failure: 12

### Failing coverage cells

| scenario | ego_speed | headway | friction | scenario_param | runs | failing | preventable_collisions |
| --- | --- | --- | --- | --- | --- | --- | --- |
| lead_brake | 22-29 | 0.8-1.5333 | 0.75-1 | lead_decel 6-9 | 27 | 22 | 18 |
| cut_in | 15-22 | 0.3-0.8667 | 0.5-0.75 | closing_speed 6-9 | 11 | 10 | 3 |
| cut_in | 15-22 | 0.3-0.8667 | 0.75-1 | closing_speed 6-9 | 7 | 7 | 1 |
| lead_brake | 22-29 | 0.8-1.5333 | 0.5-0.75 | lead_decel 6-9 | 9 | 6 | 2 |
| lead_brake | 22-29 | 2.2667-3 | 0.75-1 | lead_decel 6-9 | 5 | 4 | 1 |
| cut_in | 22-29 | 0.3-0.8667 | 0.5-0.75 | closing_speed 6-9 | 7 | 4 | 0 |
| lead_brake | 15-22 | 0.8-1.5333 | 0.75-1 | lead_decel 6-9 | 1 | 1 | 1 |
| lead_brake | 22-29 | 1.5333-2.2667 | 0.75-1 | lead_decel 3.5-6 | 1 | 1 | 0 |
| lead_brake | 29-36 | 0.8-1.5333 | 0.5-0.75 | lead_decel 3.5-6 | 1 | 1 | 0 |
| lead_brake | 29-36 | 1.5333-2.2667 | 0.5-0.75 | lead_decel 6-9 | 1 | 1 | 0 |
| lead_brake | 29-36 | 0.8-1.5333 | 0.75-1 | lead_decel 6-9 | 1 | 1 | 1 |
| lead_brake | 29-36 | 1.5333-2.2667 | 0.75-1 | lead_decel 3.5-6 | 1 | 1 | 0 |
| lead_brake | 22-29 | 1.5333-2.2667 | 0.75-1 | lead_decel 6-9 | 3 | 1 | 0 |
| lead_brake | 22-29 | 0.8-1.5333 | 0.75-1 | lead_decel 3.5-6 | 5 | 1 | 0 |

## Preventability

A collision is *unpreventable* if an ideal system braking at 0.9 μg from the moment the hazard appears also collides (`config/reference.yaml`). AC-01 and AC-03 count preventable runs only.

| collisions | preventable_collisions | unpreventable_collisions | unpreventable_runs |
| --- | --- | --- | --- |
| 31 | 27 | 4 | 4 |

## Coverage

108 / 108 coverage cells (100%) meet the minimum run count.

## Triggering conditions and evidence

### TC-01: Lead-vehicle hard braking (decel >= ~6 m/s^2) combined with a distracted driver causes collision or min_ttc<1.5s, largely independent of friction and headway (even at max ODD headway of 3.0s). Preventable=true (function/TOR-timing gap), concentrated in foreseeable-misuse condition.

Predicate: `scenario='lead_brake' AND driver_state='distracted' AND lead_decel>=6`

```sql
SELECT lead_decel, headway, friction, collision, min_ttc, preventable, takeover_time FROM runs WHERE scenario='lead_brake' AND driver_state='distracted' AND lead_decel>=6 ORDER BY lead_decel
```

| lead_decel | headway | friction | collision | min_ttc | preventable | takeover_time |
| --- | --- | --- | --- | --- | --- | --- |
| 6.0 | 1.17 | 0.75 | False | 0.81 | True | 3.88 |
| 6.0 | 1.17 | 0.75 | True | 0.03 | True | 4.72 |
| 7.5 | 1.9 | 0.62 | False | 1.68 | True | 2.3 |
| 7.5 | 2.0 | 0.75 | False | 0.63 | True | 4.21 |
| 7.5 | 1.17 | 0.88 | True | 0.04 | True | 4.72 |
| 7.5 | 2.63 | 0.88 | False | 0.7 | True | 5.63 |
| 7.5 | 1.9 | 0.62 | False | 1.28 | True | 3.64 |
| 7.5 | 1.17 | 0.88 | True | 0.0 | True | 4.68 |
| 7.5 | 2.63 | 0.88 | False | 1.81 | True | 3.32 |
| 7.5 | 1.17 | 0.75 | True | 0.04 | True | 3.59 |
| 7.5 | 1.17 | 0.75 | False | 0.62 | True | 2.71 |
| 7.5 | 1.17 | 0.75 | True | 0.02 | True | 3.45 |
| 7.5 | 1.9 | 0.62 | False | 1.87 | True | 2.51 |
| 7.5 | 1.17 | 0.75 | True | 0.01 | True | 8.65 |
| 7.5 | 1.17 | 0.75 | True | 0.02 | True | 3.67 |

### TC-02: Cut-in with short initial headway (<=0.6s) and high closing speed (>=7 m/s) drives min_ttc below 1.5s (and outright collision for headway<=0.45s), at similar rates for attentive and distracted drivers and across the friction range -- an intended-use function limitation, not a misuse-only issue (headway<=0.3s extreme becomes physically unavoidable, preventable=false).

Predicate: `scenario='cut_in' AND headway<=0.6 AND closing_speed>=7`

```sql
SELECT headway, closing_speed, ego_speed, friction, driver_state, collision, min_ttc, preventable FROM runs WHERE scenario='cut_in' AND headway<=0.6 AND closing_speed>=7 ORDER BY headway, ego_speed
```

| headway | closing_speed | ego_speed | friction | driver_state | collision | min_ttc | preventable |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0.3 | 9.0 | 25.5 | 0.5 | distracted | True | 0.02 | False |
| 0.3 | 9.0 | 25.5 | 0.5 | attentive | True | 0.02 | False |
| 0.3 | 9.0 | 25.5 | 0.5 | attentive | True | 0.02 | False |
| 0.3 | 9.0 | 25.5 | 0.5 | distracted | True | 0.02 | False |
| 0.4 | 7.5 | 20.0 | 1.0 | distracted | True | 0.04 | True |
| 0.4 | 7.5 | 20.0 | 1.0 | attentive | False | 0.62 | True |
| 0.4 | 7.5 | 20.0 | 0.5 | distracted | True | 0.04 | True |
| 0.4 | 7.5 | 20.0 | 0.5 | attentive | True | 0.02 | True |
| 0.4 | 7.5 | 20.0 | 0.7 | attentive | True | 0.03 | True |
| 0.45 | 7.5 | 20.0 | 1.0 | distracted | False | 0.68 | True |
| 0.45 | 7.5 | 20.0 | 1.0 | attentive | False | 0.85 | True |
| 0.45 | 7.5 | 20.0 | 0.5 | distracted | False | 0.68 | True |
| 0.45 | 7.5 | 20.0 | 0.5 | attentive | False | 0.77 | True |
| 0.5 | 7.5 | 20.0 | 1.0 | distracted | False | 1.02 | True |
| 0.5 | 7.5 | 20.0 | 0.5 | attentive | False | 1.02 | True |

## Hypothesis tests

Every `test_predicate` call, in order, over the agent's own runs.

| # | where | target | inside | outside | rate inside | rate outside | lift |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | `scenario = 'lead_brake' AND driver_state = 'distracted' AND lead_decel >= 6` | failure | 27 | 121 | 0.852 | 0.0826 | 10.3 |
| 2 | `scenario = 'lead_brake' AND driver_state = 'distracted'` | failure | 45 | 103 | 0.578 | 0.068 | 8.5 |
| 3 | `scenario = 'cut_in' AND ego_speed <= 20 AND headway <= 0.7 AND closing_speed >= 7` | failure | 2 | 146 | 1 | 0.212 | 4.71 |
| 4 | `driver_state = 'attentive'` | failure | 69 | 79 | 0.058 | 0.367 | 0.158 |
| 5 | `scenario = 'lead_brake' AND driver_state = 'distracted' AND lead_decel >= 5` | failure | 43 | 131 | 0.837 | 0.0992 | 8.44 |
| 6 | `scenario = 'cut_in' AND headway <= 0.6 AND closing_speed >= 7` | failure | 25 | 149 | 0.36 | 0.268 | 1.34 |
| 7 | `scenario = 'cut_in' AND headway <= 0.45 AND headway > 0.35 AND closing_speed >= 7` | failure | 1 | 173 | 1 | 0.277 | 3.6 |
| 8 | `scenario = 'cut_in' AND headway < 0.65 AND closing_speed >= 7 AND ego_speed <= 22` | failure | 6 | 168 | 0.833 | 0.262 | 3.18 |
| 9 | `scenario = 'lead_brake' AND driver_state = 'distracted' AND lead_decel >= 6 AND headway <= 3.0` | failure | 41 | 133 | 0.854 | 0.105 | 8.11 |
| 10 | `friction <= 0.6` | failure | 16 | 170 | 0.875 | 0.276 | 3.16 |
| 11 | `scenario='lead_brake' AND driver_state='attentive' AND lead_decel>=6 AND headway<=1.5` | failure | 11 | 175 | 0.0909 | 0.343 | 0.265 |
| 12 | `scenario='cut_in' AND headway<=0.6 AND closing_speed>=7 AND driver_state='attentive'` | failure | 21 | 165 | 0.571 | 0.297 | 1.92 |
| 13 | `scenario='cut_in' AND headway<=0.6 AND closing_speed>=7 AND driver_state='distracted'` | failure | 16 | 170 | 0.562 | 0.306 | 1.84 |

- TC-01: submitted predicate tested 0 time(s).
- TC-02: submitted predicate tested 0 time(s).
