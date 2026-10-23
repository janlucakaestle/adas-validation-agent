# Search report: Adaptive Cruise Control (learned policy) with driver-intervention request, SAE L2

**Campaign:** `agent_s6` · **Author:** agent (claude-sonnet-5) · **Date:** 2026-10-21

## Provenance

- Campaign `agent_s6`: kind `search`, method `agent`, status **COMPLETE**, 268 of 300 planned runs, seed 6, created 2026-10-21 22:20:36
- Release ID: `fe59625d9428753862687a3969fa0abf194b64e8afeabe42898bdbcca7498d81`
- Runtime ID: `d37505bee00e01c235487f54dbb579f8dc71978020d9565f2c940eb2fcf3ae3c`; exposure model ID: `9b025cdb5828fa42574c0dd79797f6b94434d542e7bef4529b3194c10a025abc`; protocol ID: `4a879572d3e65102fa78f013d357c0caaabed603db99992e6a02ba64c8c444a9`
- Data SHA-256: `bd706445028f72439228ded7f11134790531252883ab846eb237e83936b5004c`
- Policy SHA-256: `5e14254aff132c1b2d674702e85ad3cc3d2c326c6c2440d9f3e43861ceb1a214`; source code SHA-256: `3cc05645a19f25d7a70ab70c09cfd95b61bc4682a260b32515ad05a5b87daeee`; git commit `43d549f3981403b13317ba99cffb86c97d5e5abe` (traceability only)
- Python 3.11.9 on Windows AMD64; PyYAML 6.0.3, anthropic 1.8.0, duckdb 1.5.5, matplotlib 3.11.2, numpy 2.4.6, pandas 3.0.5, pyarrow 25.0.1, scikit-learn 1.9.1, scipy 1.17.1
- Lock file: matches
- Parsed config `acceptance` SHA-256: `0a49d9d0083831e7beab7389706a8d66ac11a05d1784b88f48d4ec5862fca628`
- Parsed config `driver` SHA-256: `6165e60b72b4fb58f35b0e3fdbb746aa9dd8689df8cede4878c5ec78e6c38355`
- Parsed config `exposure` SHA-256: `9b025cdb5828fa42574c0dd79797f6b94434d542e7bef4529b3194c10a025abc`
- Parsed config `odd` SHA-256: `64b0f925ef6f25d076435ab2497a1bcaf272a9e7f08e10a3b8e2e1a76cf5eef6`
- Parsed config `reference` SHA-256: `9a6c5660e2b64562e00d39cc2d10432e57184d5e65aa49367758f78875cc93f2`
- Parsed config `sim` SHA-256: `71ed89eee9d3a8a80d3ac3f3d9afd072164c93be4239999e8027c331100a9bb0`

**Scope.** Every number below is conditional on this release's simulator, ODD, exposure model, driver model, controller and configuration (release ID above). Exposure weights, acceptance thresholds and several driver parameters are placeholders (`TODO(data)` in `config/`), so the numbers show the method, not real-world risk.

## Summary

## Campaign summary (agent_s6, 268/300 runs used)

Approach: broad coverage sweep across the full coverage grid (lead_brake: ego_speed × headway × lead_decel × friction × driver_state; cut_in: ego_speed × headway × closing_speed × friction × driver_state, using bin-midpoint values), followed by targeted boundary probing and repeated sampling once collision clusters emerged, to characterize two distinct triggering conditions for the `collision` target.

### Finding 1 — Distracted driver + severe lead braking (lead_brake)
Across the coverage sweep, every collision in the `lead_brake` scenario occurred with `driver_state='distracted'` and a high lead deceleration (empirically ≳6.5 m/s², i.e. the upper part of the ODD decel range), combined with headway short enough that the pre-TOR following distance does not leave margin for the driver's reaction+braking delay (headway below ~2.3 s in our samples; at headway=3.0 s even lead_decel=9 did not collide). Friction also needed to be ≳0.6 — at the very low end of the ODD (0.5) the same distracted/high-decel/short-headway combination did not produce a collision, consistent with reduced realized lead deceleration at very low friction.
Restricting to `driver_state='attentive'` under the identical lead_decel/friction/headway envelope produced **zero** collisions (0/21 runs, vs 61% inside the distracted predicate), confirming the driver's re-engagement delay (not the base ACC control) is the dominant discriminator here. Repeated sampling of one representative case (es=25.5, headway=1.17, lead_decel=7.5, friction=0.625, distracted) gave 6/8 collisions, showing the outcome is stochastic (driven by the random takeover_time draw) but highly likely once this condition holds.

### Finding 2 — Minimal-headway, maximal-closing-speed cut-in (cut_in)
At the extreme corner of the cut-in ODD (headway at its lower bound, 0.3 s, together with closing speed at its upper bound, 9 m/s), collisions occurred frequently (83% of sampled runs) **regardless of driver_state** — attentive drivers collided in 67% of these runs too (6/9), essentially the same order as distracted (vs ~10-13% baseline collision rate outside this predicate in our campaign). min_ttc in these cases is typically ~0.01–0.04 s, i.e. contact is essentially already determined at/just after the cut-in event, before any driver or extra system action can plausibly prevent it. This indicates a scenario-level/base-controller limitation at this ODD corner rather than purely a driver-takeover (supervision) issue — some attentive-driver runs did avoid contact (e.g. es=36, friction=1.0), suggesting the boundary is sharp and sensitive to speed/friction, but the overall rate is high for both driver states.

## Limitations
- Rates quoted are over my own deliberately-skewed sampling (oversampling boundary/extreme cells) and must not be read as real-world collision frequencies.
- Coverage swept bin midpoints plus some boundary/edge probes; not every corner of the 216-cell grid was exhaustively repeated.
- `avoidable_by_reference` was not used as a filter; some flagged collisions may be scenario-inherently unavoidable even by a perfect brake-only reference response — follow-up should cross-check against that column before concluding the function itself is deficient.
- Threshold values (lead_decel≈6.5, headway≈2.3 s, friction≈0.6) are approximate, derived from a limited number of boundary probes; finer sweeps would sharpen them.

## Recommended next tests
1. Finer sweep of lead_decel (5–8 m/s², 0.5 steps) and headway (1.5–2.5 s) at fixed friction to map the exact collision boundary surface for distracted drivers.
2. Finer sweep of cut-in headway (0.3–0.6 s) and closing speed (7–9 m/s) crossed with friction/speed to find where attentive-driver collisions disappear — determine whether a faster/more conservative ACC reaction could close this gap even without driver input.
3. Cross-reference both triggering sets against `avoidable_by_reference` to separate "function deficiency" collisions from scenario-inherently-unavoidable ones.
4. Additional repeats (10–20 each) of near-boundary cases to tighten confidence intervals on collision probability given the stochastic takeover_time.

## Release verdict (from estimation campaign `estimate`): NO-GO

Not computed from this search campaign; same release ID `fe59625d94287538…`. criteria AC-01, AC-03, AC-04 failed. no requirement defined for AC-09, AC-10.

- **Engineering verdict** (evidence against the configured targets): **NO-GO**
- **Requirement maturity:** not approved: AC-01, AC-02, AC-03, AC-04, AC-07, AC-08, AC-09, AC-10. A provisional, illustrative or undefined requirement can never authorise release (a violation still counts as NO-GO).
- **Formal release decision:** **NO-GO**

| id | name | value | one-sided 95% bound | n | n needed | min_n | target | vs target | requirement | supports formal GO |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| AC-01 | Collisions with attentive supervision, scenarios avoidable by the ideal reference | 0.0008629 | 0.001054 (upper) | 79966 | 29956 | 100 | <= 0.0001 (zero goal) | FAIL | illustrative | no |
| AC-02 | 5th-percentile effective minimum TTC | 1.865 | 1.859 (lower) | 100000 | 59 | 100 | >= 1.5 | PASS | illustrative | no |
| AC-03 | Collisions under foreseeable misuse, scenarios avoidable by the ideal reference | 0.01877 | 0.02043 (upper) | 20031 | 59 | 100 | <= 0.05 | FAIL | illustrative | no |
| AC-04 | 95th-percentile jerk while automated longitudinal control is active | 4.949 | 4.964 (upper) | 100000 | 59 | 100 | <= 5 | FAIL | illustrative | no |
| AC-07 | Missed or late hand-back when one is required | 0 | 0.001131 (upper) | 2647 | 299 | 100 | <= 0.01; max_tor_latency_s = 0.5 | PASS | illustrative | no |
| AC-08 | Hand-backs in scenarios that do not require one | 0.2017 | 0.2038 (upper) | 97353 | 11 | 100 | <= 0.25 | PASS | illustrative | no |
| AC-09 | Overall collisions with attentive supervision (reference-independent) | 0.0009003 | 0.001095 (upper) | 79969 | - | 100 | none defined | NO REQUIREMENT | undefined | no |
| AC-10 | Overall collisions under foreseeable misuse (reference-independent) | 0.01877 | 0.02043 (upper) | 20031 | - | 100 | none defined | NO REQUIREMENT | undefined | no |

Statistical result: exact one-sided Clopper-Pearson bounds for rates and exact distribution-free order-statistic bounds for quantiles, at 95% one-sided confidence. Engineering comparison ('vs target'): PASS needs the bound to meet the target (in every stratum where strata are listed); FAIL means the point estimate violates it (or a zero goal is falsified); NO REQUIREMENT means no target exists. 'requirement' is the effective maturity (the weakest of the criterion's own status and the definitions its population uses); only 'approved' can support a formal GO. 'n needed' is the smallest sample at which a PASS is possible at all.

- **AC-01:** zero goal falsified: 69 event(s) observed. An observed event cannot be erased by additional event-free runs. Permanent under the zero goal: observed events cannot be erased by more successful runs.

  AC-02 by stratum:

| stratum | n | value | lower | upper | status |
| --- | --- | --- | --- | --- | --- |
| scenario=cut_in | 39919 | 2.431 | 2.401 | 2.47 | PASS |
| scenario=lead_brake | 60081 | 1.795 | 1.786 | 1.802 | PASS |

- **AC-03:** decided by stratum [{'handback_required': True}] Existing evidence is already sufficient for this criterion under the current simulator, models and acceptance rules: additional IID sampling of the unchanged release is unlikely to reverse it (the opposite one-sided 95% bound already violates the threshold).

  AC-03 by stratum:

| stratum | n | value | lower | upper | status |
| --- | --- | --- | --- | --- | --- |
| handback_required=False | 19494 | 0.006156 | 0.005264 | 0.00716 | PASS |
| handback_required=True | 537 | 0.4767 | 0.4405 | 0.5131 | FAIL |

- **AC-04:** decided by stratum [{'scenario': 'cut_in'}] Existing evidence is already sufficient for this criterion under the current simulator, models and acceptance rules: additional IID sampling of the unchanged release is unlikely to reverse it (the opposite one-sided 95% bound already violates the threshold).

  AC-04 by stratum:

| stratum | n | value | lower | upper | status |
| --- | --- | --- | --- | --- | --- |
| scenario=cut_in | 39919 | 5.172 | 5.167 | 5.177 | FAIL |
| scenario=lead_brake | 60081 | 3.859 | 3.85 | 3.87 | PASS |

- **AC-09:** no target is defined: statistics only
- **AC-10:** no target is defined: statistics only

**Descriptive measures (INFO, never gating).** Rows marked *conditional* select runs by the system's own outputs and must not be read as safety evidence.

| id | name | value | one-sided 95% bounds [lower, upper] | n | conditional on outputs |
| --- | --- | --- | --- | --- | --- |
| AC-06 | Share of runs not avoided by the ideal reference (information only) | 3e-05 | [8.177e-06, 7.753e-05] | 100000 | no |
| AC-02-S | 5th-percentile minimum TTC of collision-free runs (descriptive, survivor-only) | 1.888 | [1.882, 1.895] | 99552 | yes |
| AC-03-C | Collisions after a hand-back to a distracted driver (descriptive, conditional) | 0.08397 | [0.07724, 0.0911] | 4478 | yes |

## Discovery

Search campaigns choose where to look, so their rates say nothing about real-world risk and are not reported. What matters is what the search found and how fast. Discovery target: `collision` = `collision` (`config/discovery.yaml`; a search heuristic, not an acceptance criterion).

- Runs executed: 268
- Target runs: 33
- Distinct target coverage cells: 15
- Runs to first target run: 12

### Coverage cells with target runs

| scenario | driver_state | ego_speed | headway | friction | scenario_param | runs | collision |
| --- | --- | --- | --- | --- | --- | --- | --- |
| lead_brake | distracted | 22-29 | 0.8-1.5333 | 0.5-0.75 | lead_decel 6-9 | 13 | 9 |
| cut_in | distracted | 29-36 | 0.3-0.8667 | 0.75-1 | closing_speed 6-9 | 5 | 4 |
| lead_brake | distracted | 29-36 | 0.8-1.5333 | 0.75-1 | lead_decel 6-9 | 3 | 3 |
| cut_in | attentive | 15-22 | 0.3-0.8667 | 0.5-0.75 | closing_speed 6-9 | 4 | 3 |
| cut_in | distracted | 15-22 | 0.3-0.8667 | 0.5-0.75 | closing_speed 6-9 | 4 | 3 |
| lead_brake | distracted | 15-22 | 0.8-1.5333 | 0.75-1 | lead_decel 6-9 | 3 | 2 |
| lead_brake | distracted | 22-29 | 1.5333-2.2667 | 0.5-0.75 | lead_decel 6-9 | 1 | 1 |
| lead_brake | distracted | 22-29 | 0.8-1.5333 | 0.75-1 | lead_decel 6-9 | 2 | 1 |
| lead_brake | distracted | 29-36 | 0.8-1.5333 | 0.5-0.75 | lead_decel 6-9 | 2 | 1 |
| cut_in | attentive | 15-22 | 0.3-0.8667 | 0.75-1 | closing_speed 6-9 | 2 | 1 |
| cut_in | distracted | 15-22 | 0.3-0.8667 | 0.75-1 | closing_speed 6-9 | 2 | 1 |
| cut_in | attentive | 29-36 | 0.3-0.8667 | 0.5-0.75 | closing_speed 6-9 | 2 | 1 |
| cut_in | distracted | 29-36 | 0.3-0.8667 | 0.5-0.75 | closing_speed 6-9 | 2 | 1 |
| lead_brake | distracted | 22-29 | 2.2667-3 | 0.5-0.75 | lead_decel 6-9 | 3 | 1 |
| cut_in | attentive | 29-36 | 0.3-0.8667 | 0.75-1 | closing_speed 6-9 | 5 | 1 |

## Reference outcomes

`avoidable_by_reference`: a fixed brake-only response, starting at hazard onset with perfect knowledge, no steering and no pre-hazard braking (`config/reference.yaml`), avoids contact. FALSE is not a proof of physical inevitability. `handback_required`: braking at a fixed deceleration (the nominal design authority, frozen) from hazard onset does not avoid contact (independent of the tested ACC's authority). Both are scenario properties, computed for every run independently of the system.

| runs | not_avoided_by_reference | handback_required | collisions | collisions_avoidable_by_reference | unresolved |
| --- | --- | --- | --- | --- | --- |
| 268 | 8 | 68 | 33 | 25 | 0 |

## Coverage

216 / 216 coverage cells (100%) meet the minimum run count, over the full set of ODD coverage dimensions: scenario, driver_state, ego_speed, headway, lead_decel, friction. Coverage is structural: it says nothing about how often the function fails in a cell.

## Triggering conditions and evidence

Every condition below passed the mandatory evidence protocol (`avval/evidence.py`). Evidence bundle SHA-256: `9068f244787eea540a6d89d3d13428b2132f1dc85ef7d3b81a7d68502bf2a63f`.

### TC-01: Lead-vehicle emergency braking (lead_brake) with a distracted driver: when the lead decelerates hard (≳6.5 m/s², within the ODD's upper decel range) on a road with at least moderate friction (>0.5) at a short-to-moderate headway (<2.3 s), the driver's takeover delay after the TOR frequently prevents timely braking and leads to a rear-end collision. Under the identical scenario parameters, attentive drivers show 0% collisions, confirming driver re-engagement delay as the discriminating factor.

Predicate: `scenario='lead_brake' AND driver_state='distracted' AND lead_decel>=6.5 AND friction>0.5 AND headway<2.3`

- Condition SHA-256 `e2c1e6aa6fcf3cb8348bf10d0589817049700f8be8434a29317bd9caf18e851e`
- Predicate test `c150b9c9138e` (target `collision`, on 268 runs): 29 runs inside, target rate inside 0.6207 [95% two-sided 0.4226, 0.7931], outside 0.06276, lift 9.89
- Evidence query `21f163197ffa` (result SHA-256 `f7173a763b337e52…`):

```sql
SELECT run_idx, ego_speed, headway, lead_decel, friction, driver_state, collision, min_ttc, takeover_time FROM runs WHERE scenario='lead_brake' AND driver_state='distracted' AND lead_decel>=6.5 AND friction>0.5 AND headway<2.3 ORDER BY run_idx
```

| run_idx | ego_speed | headway | lead_decel | friction | driver_state | collision | min_ttc | takeover_time |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 9 | 18.5 | 1.167 | 7.5 | 0.625 | distracted | False | 0.915 | 3.808 |
| 11 | 18.5 | 1.167 | 7.5 | 0.875 | distracted | True | 0.012 | 4.078 |
| 21 | 18.5 | 1.9 | 7.5 | 0.625 | distracted | False | 1.375 | 3.738 |
| 23 | 18.5 | 1.9 | 7.5 | 0.875 | distracted | False | 1.106 | 3.909 |
| 45 | 25.5 | 1.167 | 7.5 | 0.625 | distracted | True | 0.027 | 5.797 |
| 47 | 25.5 | 1.167 | 7.5 | 0.875 | distracted | False | 0.791 | 2.809 |
| 57 | 25.5 | 1.9 | 7.5 | 0.625 | distracted | True | 0.009 | 6.505 |
| 59 | 25.5 | 1.9 | 7.5 | 0.875 | distracted | False | 0.574 | 4.227 |
| 81 | 32.5 | 1.167 | 7.5 | 0.625 | distracted | True | 0.002 | 3.865 |
| 83 | 32.5 | 1.167 | 7.5 | 0.875 | distracted | True | 0.008 | 3.921 |
| 93 | 32.5 | 1.9 | 7.5 | 0.625 | distracted | False | 1.325 | 3.63 |
| 95 | 32.5 | 1.9 | 7.5 | 0.875 | distracted | False | 1.084 | 3.623 |
| 219 | 15.0 | 0.8 | 9.0 | 1.0 | distracted | True | 0.036 | 5.458 |
| 223 | 36.0 | 0.8 | 9.0 | 1.0 | distracted | True | 0.043 | 4.762 |
| 232 | 25.5 | 1.167 | 7.5 | 0.625 | distracted | True | 0.005 | 4.481 |

### TC-02: Cut-in with near-ODD-boundary parameters: minimal initial headway (0.3 s, the ODD lower bound) combined with maximal closing speed (9 m/s, the ODD upper bound) produces frequent collisions (83% of sampled runs) regardless of driver_state (attentive drivers collide in 67% of these runs too), with min_ttc typically ~0.01-0.04 s at the moment of cut-in, indicating the hazard is essentially already unavoidable by the time it is detected rather than being primarily a driver-supervision failure.

Predicate: `scenario='cut_in' AND headway<=0.3 AND closing_speed>=9`

- Condition SHA-256 `7f2aeb7d5b03113fe361aa92e988cc8d22b9171aa902d8a75c4da0e602b17576`
- Predicate test `95a630a30462` (target `collision`, on 268 runs): 18 runs inside, target rate inside 0.8333 [95% two-sided 0.5858, 0.9642], outside 0.072, lift 11.57
- Evidence query `62893723f591` (result SHA-256 `4a6584b04eb60275…`):

```sql
SELECT run_idx, ego_speed, headway, closing_speed, friction, driver_state, collision, min_ttc, takeover_time FROM runs WHERE scenario='cut_in' AND headway<=0.3 AND closing_speed>=9 ORDER BY run_idx
```

| run_idx | ego_speed | headway | closing_speed | friction | driver_state | collision | min_ttc | takeover_time |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 224 | 15.0 | 0.3 | 9.0 | 0.5 | attentive | True | 0.009 | 1.513 |
| 225 | 15.0 | 0.3 | 9.0 | 0.5 | distracted | True | 0.009 | 2.54 |
| 226 | 15.0 | 0.3 | 9.0 | 1.0 | attentive | True | 0.009 | 0.568 |
| 227 | 15.0 | 0.3 | 9.0 | 1.0 | distracted | True | 0.009 | 4.216 |
| 228 | 36.0 | 0.3 | 9.0 | 0.5 | attentive | True | 0.036 | 1.503 |
| 229 | 36.0 | 0.3 | 9.0 | 0.5 | distracted | True | 0.007 | 3.113 |
| 230 | 36.0 | 0.3 | 9.0 | 1.0 | attentive | False | 0.697 | 0.846 |
| 231 | 36.0 | 0.3 | 9.0 | 1.0 | distracted | True | 0.007 | 6.462 |
| 251 | 36.0 | 0.3 | 9.0 | 1.0 | attentive | False | 0.574 | 1.01 |
| 252 | 36.0 | 0.3 | 9.0 | 1.0 | attentive | True | 0.007 | 1.873 |
| 253 | 36.0 | 0.3 | 9.0 | 1.0 | attentive | False | 0.606 | 0.972 |
| 254 | 36.0 | 0.3 | 9.0 | 1.0 | distracted | True | 0.007 | 4.653 |
| 255 | 36.0 | 0.3 | 9.0 | 1.0 | distracted | True | 0.007 | 6.037 |
| 256 | 36.0 | 0.3 | 9.0 | 1.0 | distracted | True | 0.007 | 4.491 |
| 257 | 15.0 | 0.3 | 9.0 | 0.5 | attentive | True | 0.009 | 1.202 |

## Hypothesis tests

Every `test_predicate` call, in order, over the agent's own runs (full records in the evidence bundle).

| # | id | where | target | runs | inside | rate inside | rate outside | lift |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2 | c150b9c9138e | `scenario='lead_brake' AND driver_state='distracted' AND lead_decel>=6.5 AND friction>0.5 AND headway<2.3` | collision | 268 | 29 | 0.6207 | 0.06276 | 9.89 |
| 3 | 95a630a30462 | `scenario='cut_in' AND headway<=0.3 AND closing_speed>=9` | collision | 268 | 18 | 0.8333 | 0.072 | 11.57 |
| 4 | dd51db18e1cd | `scenario='lead_brake' AND driver_state='attentive' AND lead_decel>=6.5 AND friction>0.5 AND headway<2.3` | collision | 268 | 21 | 0 | 0.1336 | 0 |
| 5 | 3b03910d4152 | `scenario='cut_in' AND headway<=0.3 AND closing_speed>=9 AND driver_state='attentive'` | collision | 268 | 9 | 0.6667 | 0.1042 | 6.395 |
