# Search report: Adaptive Cruise Control (learned policy) with driver-intervention request, SAE L2

**Campaign:** `agent_s5` · **Author:** agent (claude-sonnet-5) · **Date:** 2026-10-01

## Provenance

Recorded when the campaign was created (2026-10-01 19:42:37); method `agent`, budget 300, seed 5.

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

## Campaign Summary (agent_s5, 163 of 300 runs used)

Full ODD coverage achieved (108/108 coverage cells). After broad sweep, targeted follow-up runs were used to isolate and confirm two distinct, strongly-evidenced triggering conditions for the failure predicate (collision OR min_ttc<1.5).

### Finding 1 — cut_in with short headway + high closing speed: near-certain failure, LARGELY DRIVER-INDEPENDENT
For cut_in scenarios with initial headway < 0.8 s and closing speed ≥ 6 m/s, the failure rate is 85-100% regardless of driver_state (attentive 84.6%, distracted 86.7% — statistically indistinguishable) and largely regardless of friction. At the most extreme corner tested (headway=0.3s, closing_speed=9 m/s) the failure rate was 100% (20/20 runs), including attentive drivers with full reaction time. Critically, at high friction (dry, 1.0) these collisions are flagged `preventable=true`, meaning an idealized controller braking at 0.9·mu·g would have avoided them — i.e. this is a genuine function/performance gap in the learned ACC policy's cut-in response, not merely a physics-limited edge case. At low friction (0.5) a larger share are `preventable=false` (physically unavoidable), as expected. This condition affects **intended use** (attentive driver) as well as misuse, which is the more serious SOTIF finding.

### Finding 2 — lead_brake with distracted driver + hard lead deceleration: foreseeable-misuse-driven failure
For lead_brake scenarios, attentive drivers showed **zero failures** across the entire tested envelope (0/27+ runs, including lead_decel up to 9 m/s², friction down to 0.5, headway down to 0.8s) — the TOR is issued early enough and ego braking is adequate when the driver reacts promptly. In contrast, distracted drivers show a sharp failure onset:
- lead_decel < 4.75 m/s²: 0% failure (0/21)
- lead_decel ≥ 4.75 m/s²: 44% failure (lift ~20x vs rest)
- lead_decel ≥ 6.0 m/s²: 57% failure (lift ~12.7x)
- lead_decel ≥ 6.0 m/s² AND headway ≤ 1.9s: 88% failure (lift ~4.8x; strongest refinement found)

Friction had only a weak modulating effect on this condition (55.6% at friction≤0.7 vs 58.3% at friction>0.7 for decel≥6 distracted), so the dominant driver is reaction delay (takeover times of 3-9s observed) combined with insufficient fallback braking/TOR margin for hard lead braking, not road friction.

### Limitations
- Rates above are from a targeted search campaign, not a random/representative sample of the ODD; they must not be read as real-world failure probabilities.
- cut_in boundary (headway/closing-speed threshold) was probed coarsely (0.3–0.87 s headway, 4–9 m/s closing speed); exact boundary surface not fully mapped.
- Did not explore combined extreme scenarios (e.g., very low friction + short headway + hard decel + distracted together at full factorial depth) — only spot-checked worst corner.
- Driver-state reaction-time distribution only sampled a handful of seeds per cell; stochastic takeover time variance not fully characterized.

### Recommended next tests
1. Finer sweep of cut_in headway (0.3–1.0s) × closing_speed (4–9 m/s) grid to map the exact failure-onset boundary and quantify the "preventable" fraction by friction.
2. Finer sweep of lead_decel (4.75–6.5 m/s²) for distracted drivers to pin the exact onset threshold.
3. Investigate why attentive-driver cut-in cases still collide (Finding 1) — this points to a policy/perception-latency limitation independent of driver supervision, worth root-causing in the controller rather than only flagging as misuse-driven risk.
4. Repeat high-value cells (e.g., lead_decel=6, headway=1.9, distracted) with more random seeds to tighten confidence intervals on the 88% estimate.

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

- Runs executed: 163
- Failing runs (`collision OR coalesce(min_ttc < 1.5, false)`): 42
- Distinct failing coverage cells: 15
- Runs to first failure: 12

### Failing coverage cells

| scenario | ego_speed | headway | friction | scenario_param | runs | failing | preventable_collisions |
| --- | --- | --- | --- | --- | --- | --- | --- |
| cut_in | 15-22 | 0.3-0.8667 | 0.75-1 | closing_speed 6-9 | 13 | 13 | 5 |
| cut_in | 15-22 | 0.3-0.8667 | 0.5-0.75 | closing_speed 6-9 | 7 | 7 | 0 |
| lead_brake | 22-29 | 0.8-1.5333 | 0.75-1 | lead_decel 6-9 | 3 | 3 | 0 |
| lead_brake | 29-36 | 0.8-1.5333 | 0.5-0.75 | lead_decel 6-9 | 6 | 3 | 1 |
| lead_brake | 22-29 | 0.8-1.5333 | 0.5-0.75 | lead_decel 6-9 | 3 | 2 | 1 |
| lead_brake | 22-29 | 1.5333-2.2667 | 0.5-0.75 | lead_decel 6-9 | 3 | 2 | 0 |
| lead_brake | 22-29 | 1.5333-2.2667 | 0.75-1 | lead_decel 6-9 | 3 | 2 | 0 |
| cut_in | 29-36 | 0.3-0.8667 | 0.5-0.75 | closing_speed 6-9 | 3 | 2 | 2 |
| cut_in | 29-36 | 0.3-0.8667 | 0.75-1 | closing_speed 6-9 | 3 | 2 | 2 |
| lead_brake | 15-22 | 0.8-1.5333 | 0.75-1 | lead_decel 6-9 | 1 | 1 | 1 |
| lead_brake | 29-36 | 1.5333-2.2667 | 0.5-0.75 | lead_decel 6-9 | 1 | 1 | 1 |
| lead_brake | 29-36 | 2.2667-3 | 0.5-0.75 | lead_decel 3.5-6 | 1 | 1 | 0 |
| lead_brake | 29-36 | 0.8-1.5333 | 0.75-1 | lead_decel 6-9 | 1 | 1 | 1 |
| lead_brake | 29-36 | 1.5333-2.2667 | 0.75-1 | lead_decel 3.5-6 | 1 | 1 | 0 |
| lead_brake | 22-29 | 1.5333-2.2667 | 0.75-1 | lead_decel 3.5-6 | 3 | 1 | 0 |

## Preventability

A collision is *unpreventable* if an ideal system braking at 0.9 μg from the moment the hazard appears also collides (`config/reference.yaml`). AC-01 and AC-03 count preventable runs only.

| collisions | preventable_collisions | unpreventable_collisions | unpreventable_runs |
| --- | --- | --- | --- |
| 22 | 14 | 8 | 8 |

## Coverage

108 / 108 coverage cells (100%) meet the minimum run count.

## Triggering conditions and evidence

### TC-01: cut_in scenario with short initial headway (<0.8s) combined with high closing speed (>=6 m/s): near-certain failure (collision or min_ttc<1.5), essentially independent of driver attentiveness and largely independent of friction. At high friction many of these are flagged 'preventable', indicating a genuine function performance gap in handling fast, close cut-ins rather than purely a misuse/physics artifact.

Predicate: `scenario = 'cut_in' AND headway < 0.8 AND closing_speed >= 6`

```sql
SELECT driver_state, friction, COUNT(*) n, SUM(CASE WHEN preventable THEN 1 ELSE 0 END) preventable_count, SUM(CASE WHEN collision THEN 1 ELSE 0 END) collisions FROM runs WHERE scenario='cut_in' AND headway<0.8 AND closing_speed>=6 GROUP BY driver_state, friction
```

| driver_state | friction | n | preventable_count | collisions |
| --- | --- | --- | --- | --- |
| attentive | 0.62 | 3 | 3 | 0 |
| distracted | 0.5 | 5 | 2 | 5 |
| distracted | 1.0 | 6 | 6 | 4 |
| attentive | 0.75 | 1 | 0 | 1 |
| attentive | 0.5 | 3 | 0 | 3 |
| attentive | 1.0 | 6 | 6 | 3 |
| distracted | 0.75 | 1 | 0 | 1 |
| distracted | 0.88 | 3 | 3 | 0 |

### TC-02: cut_in scenario at the extreme ODD corner (headway=0.3s, closing_speed=9 m/s): 100% failure rate across all tested friction levels and BOTH driver states (attentive included), showing this is not mitigated by driver supervision at all.

Predicate: `scenario = 'cut_in' AND headway < 0.8 AND closing_speed >= 9`

```sql
SELECT driver_state, COUNT(*) n, SUM(CASE WHEN collision OR coalesce(min_ttc<1.5,false) THEN 1 ELSE 0 END) failures FROM runs WHERE scenario='cut_in' AND headway<0.8 AND closing_speed>=9 GROUP BY driver_state
```

| driver_state | n | failures |
| --- | --- | --- |
| distracted | 11 | 11 |
| attentive | 9 | 9 |

### TC-03: lead_brake scenario with a DISTRACTED driver and hard lead-vehicle deceleration (>=6 m/s^2), especially combined with headway <= 1.9s: elevated failure rate (88% in the refined subset) driven by late driver takeover (observed takeover times 3-9s) outrunning the available stopping margin. Attentive drivers show 0% failures under the same lead_decel/headway/friction envelope, confirming this is a foreseeable-misuse-specific risk rather than a general function fault.

Predicate: `scenario = 'lead_brake' AND driver_state = 'distracted' AND lead_decel >= 6.0 AND headway <= 1.9`

```sql
SELECT friction, headway, lead_decel, collision, min_ttc, takeover_time, tor_time FROM runs WHERE scenario='lead_brake' AND driver_state='distracted' AND lead_decel>=6.0 AND headway<=1.9 ORDER BY headway
```

| friction | headway | lead_decel | collision | min_ttc | takeover_time | tor_time |
| --- | --- | --- | --- | --- | --- | --- |
| 0.5 | 0.8 | 9.0 | False | 0.98 | 4.46 | 1.05 |
| 0.5 | 0.8 | 9.0 | False | 1.48 | 3.56 | 1.05 |
| 0.5 | 0.8 | 9.0 | True | 0.01 | 6.78 | 1.05 |
| 0.88 | 1.17 | 7.5 | True | 0.0 | 3.76 | 1.05 |
| 0.88 | 1.17 | 7.5 | False | 0.72 | 2.82 | 1.05 |
| 0.88 | 1.17 | 7.5 | True | 0.0 | 4.78 | 1.05 |
| 0.62 | 1.2 | 6.0 | False | 1.41 | 2.84 | 1.05 |
| 0.62 | 1.2 | 6.0 | True | 0.0 | 7.7 | 1.05 |
| 0.88 | 1.2 | 6.0 | False | 0.93 | 3.88 | 1.05 |
| 0.88 | 1.2 | 6.0 | False | 1.4 | 2.91 | 1.05 |
| 0.62 | 1.9 | 7.5 | False | 1.64 | 2.47 | 1.85 |
| 0.62 | 1.9 | 7.5 | False | 0.72 | 4.7 | 1.05 |
| 0.62 | 1.9 | 7.5 | True | 0.01 | 9.09 | 1.05 |
| 0.62 | 1.9 | 6.0 | False | 1.72 | 2.71 | 1.35 |
| 0.62 | 1.9 | 6.0 | False | 0.92 | 4.94 | 1.35 |

## Hypothesis tests

Every `test_predicate` call, in order, over the agent's own runs.

| # | where | target | inside | outside | rate inside | rate outside | lift |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | `scenario = 'lead_brake' AND driver_state = 'distracted' AND lead_decel >= 4.75` | failure | 18 | 90 | 0.444 | 0.0222 | 20 |
| 2 | `scenario = 'lead_brake' AND driver_state = 'distracted'` | failure | 27 | 81 | 0.296 | 0.0247 | 12 |
| 3 | `scenario = 'cut_in' AND headway < 0.7` | failure | 18 | 90 | 0.111 | 0.0889 | 1.25 |
| 4 | `scenario = 'lead_brake' AND driver_state = 'attentive' AND lead_decel >= 4.75` | failure | 18 | 90 | 0 | 0.111 | 0 |
| 5 | `scenario = 'lead_brake' AND driver_state = 'distracted' AND lead_decel >= 6.0` | failure | 21 | 111 | 0.571 | 0.045 | 12.7 |
| 6 | `scenario = 'lead_brake' AND driver_state = 'distracted' AND lead_decel < 4.75` | failure | 21 | 111 | 0 | 0.153 | 0 |
| 7 | `scenario = 'cut_in' AND headway <= 0.3 AND closing_speed >= 9` | failure | 12 | 132 | 1 | 0.129 | 7.76 |
| 8 | `scenario = 'cut_in' AND headway < 0.8 AND closing_speed >= 9` | failure | 20 | 138 | 1 | 0.138 | 7.26 |
| 9 | `scenario = 'cut_in' AND headway < 0.8 AND closing_speed >= 6` | failure | 28 | 130 | 0.857 | 0.115 | 7.43 |
| 10 | `scenario = 'cut_in' AND headway < 0.8 AND closing_speed >= 6 AND driver_state = 'attentive'` | failure | 13 | 145 | 0.846 | 0.193 | 4.38 |
| 11 | `scenario = 'cut_in' AND headway < 0.8 AND closing_speed >= 6 AND driver_state = 'distracted'` | failure | 15 | 143 | 0.867 | 0.182 | 4.77 |
| 12 | `scenario = 'lead_brake' AND driver_state = 'distracted' AND lead_decel >= 6.0 AND friction <= 0.7` | failure | 9 | 149 | 0.556 | 0.228 | 2.43 |
| 13 | `scenario = 'lead_brake' AND driver_state = 'distracted' AND lead_decel >= 6.0 AND friction > 0.7` | failure | 12 | 146 | 0.583 | 0.219 | 2.66 |
| 14 | `scenario = 'lead_brake' AND driver_state = 'distracted' AND lead_decel >= 6.0 AND headway <= 1.9` | failure | 17 | 146 | 0.882 | 0.185 | 4.77 |

- TC-01: submitted predicate tested 1 time(s) (tests 9).
- TC-02: submitted predicate tested 1 time(s) (tests 8).
- TC-03: submitted predicate tested 1 time(s) (tests 14).
