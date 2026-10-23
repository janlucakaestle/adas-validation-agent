# Search report: Adaptive Cruise Control (learned policy) with driver-intervention request, SAE L2

**Campaign:** `agent_s3` · **Author:** agent (claude-sonnet-5) · **Date:** 2026-10-21

## Provenance

- Campaign `agent_s3`: kind `search`, method `agent`, status **COMPLETE**, 259 of 300 planned runs, seed 3, created 2026-10-21 22:03:18
- Release ID: `fe59625d9428753862687a3969fa0abf194b64e8afeabe42898bdbcca7498d81`
- Runtime ID: `d37505bee00e01c235487f54dbb579f8dc71978020d9565f2c940eb2fcf3ae3c`; exposure model ID: `9b025cdb5828fa42574c0dd79797f6b94434d542e7bef4529b3194c10a025abc`; protocol ID: `4a879572d3e65102fa78f013d357c0caaabed603db99992e6a02ba64c8c444a9`
- Data SHA-256: `edcf557a0a450ed69a88f6e01984107bab9069c1c08be05579170de987e3f92e`
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

## Campaign summary (agent_s3, 259/300 runs used)

I first covered the full ODD coverage grid (216/216 cells, one run each) across both scenarios (lead_brake, cut_in), both driver states, and all parameter bins. This located zero collisions in cut_in and a handful in lead_brake, all with a distracted driver. I then used targeted follow-up runs (with repeats, since takeover_time is randomly sampled) to map the boundaries of two triggering conditions.

### Finding 1: lead_brake — distracted driver + strong lead braking (foreseeable misuse)
Across lead_brake runs, **every** collision occurred with driver_state='distracted' (0/54 attentive runs collided). Within distracted runs, restricting to lead_decel ≥ 6 m/s² and headway ≤ 2.63 s raises the collision rate to 50% (vs ~7.9% outside this region, lift ≈ 6.4x). The mechanism is clear in the data: the distracted-driver takeover_time (often 3–8 s) frequently exceeds the time remaining before the closing gap becomes unrecoverable once the system issues a TOR; whether a given run collides is highly sensitive to the sampled takeover_time, so the condition is stochastic rather than deterministic — repeated sampling at the same nominal parameters sometimes collides and sometimes doesn't, consistent with a reaction-time race.

### Finding 2: cut_in — very short headway + high closing speed (function limitation, both driver states)
A severe, close-to-deterministic condition exists in cut_in independent of driver attentiveness: when headway ≤ 0.4 s and closing_speed ≥ 9 m/s (both at/near the ODD extremes), **100% of runs collided (18/18)**, vs ~6.2% outside, including attentive-driver runs with takeover_time well under 2 s and even at high friction (1.0). This indicates the available time from cut-in to contact is shorter than any feasible response (system + driver), i.e. a scenario/function-level limit rather than a driver-supervision failure. Just one bin outward (headway 0.5–0.58 s at the same closing speed) the same parameter neighborhood shows a sharp drop to 0% collision (though min_ttc fell to ~0.9–1.4 s, i.e. near-misses), showing a narrow but steep boundary around headway≈0.4–0.5s at max closing speed.

## Limitations
- Collision/near-miss *rates* quoted above are search-driven (I oversampled risky regions) and must not be read as real-world incidence rates; they describe only the relative sensitivity found in these runs.
- The lead_brake condition is stochastic (depends on randomly sampled takeover_time); the quoted 50% rate is specific to the tested sub-region (ego=18.5–32.5 m/s, friction 0.5–1.0, lead_decel 6–9, headway 0.8–2.63) and is not a fixed probability of the function.
- The cut_in condition was probed at only a few points near the boundary (headway 0.3–0.58 s, closing_speed 9 m/s, friction 0.5–1.0); the exact boundary surface (as a function of ego speed, friction) was not fully mapped within budget.
- `avoidable_by_reference` was not analyzed in this campaign; it would help separate "unavoidable by any response" cases from ones the reference controller could have handled.

## Recommended next tests
- Map the cut_in headway/closing_speed boundary more finely (e.g. 0.05 s steps) and across the full ego_speed/friction range to quantify how function-level margin shrinks.
- For lead_brake, run repeated trials (10–20) at fixed (headway, lead_decel) near the 50% boundary to get a tighter stochastic collision-rate estimate and correlate directly with sampled takeover_time.
- Cross-check both conditions against `avoidable_by_reference` to separate "system should have done better" cases from genuinely unavoidable geometry.

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

- Runs executed: 259
- Target runs: 33
- Distinct target coverage cells: 13
- Runs to first target run: 66

### Coverage cells with target runs

| scenario | driver_state | ego_speed | headway | friction | scenario_param | runs | collision |
| --- | --- | --- | --- | --- | --- | --- | --- |
| lead_brake | distracted | 22-29 | 0.8-1.5333 | 0.75-1 | lead_decel 6-9 | 10 | 6 |
| cut_in | distracted | 15-22 | 0.3-0.8667 | 0.5-0.75 | closing_speed 6-9 | 6 | 5 |
| cut_in | distracted | 29-36 | 0.3-0.8667 | 0.5-0.75 | closing_speed 6-9 | 6 | 5 |
| lead_brake | distracted | 22-29 | 1.5333-2.2667 | 0.75-1 | lead_decel 6-9 | 7 | 4 |
| cut_in | attentive | 15-22 | 0.3-0.8667 | 0.5-0.75 | closing_speed 6-9 | 4 | 3 |
| cut_in | attentive | 29-36 | 0.3-0.8667 | 0.5-0.75 | closing_speed 6-9 | 4 | 3 |
| lead_brake | distracted | 15-22 | 0.8-1.5333 | 0.75-1 | lead_decel 6-9 | 1 | 1 |
| lead_brake | distracted | 22-29 | 0.8-1.5333 | 0.5-0.75 | lead_decel 6-9 | 1 | 1 |
| lead_brake | distracted | 29-36 | 0.8-1.5333 | 0.5-0.75 | lead_decel 6-9 | 1 | 1 |
| lead_brake | distracted | 29-36 | 1.5333-2.2667 | 0.5-0.75 | lead_decel 6-9 | 1 | 1 |
| lead_brake | distracted | 29-36 | 0.8-1.5333 | 0.75-1 | lead_decel 6-9 | 1 | 1 |
| cut_in | attentive | 22-29 | 0.3-0.8667 | 0.75-1 | closing_speed 6-9 | 2 | 1 |
| cut_in | attentive | 22-29 | 0.3-0.8667 | 0.5-0.75 | closing_speed 6-9 | 4 | 1 |

## Reference outcomes

`avoidable_by_reference`: a fixed brake-only response, starting at hazard onset with perfect knowledge, no steering and no pre-hazard braking (`config/reference.yaml`), avoids contact. FALSE is not a proof of physical inevitability. `handback_required`: braking at a fixed deceleration (the nominal design authority, frozen) from hazard onset does not avoid contact (independent of the tested ACC's authority). Both are scenario properties, computed for every run independently of the system.

| runs | not_avoided_by_reference | handback_required | collisions | collisions_avoidable_by_reference | unresolved |
| --- | --- | --- | --- | --- | --- |
| 259 | 8 | 49 | 33 | 25 | 0 |

## Coverage

216 / 216 coverage cells (100%) meet the minimum run count, over the full set of ODD coverage dimensions: scenario, driver_state, ego_speed, headway, lead_decel, friction. Coverage is structural: it says nothing about how often the function fails in a cell.

## Triggering conditions and evidence

Every condition below passed the mandatory evidence protocol (`avval/evidence.py`). Evidence bundle SHA-256: `f13bda0a722258e53af21e6999a3682239f17baf2e6e1d011c7be03a2de763af`.

### TC-01: Lead-brake scenario with a distracted (foreseeable-misuse) driver and strong lead-vehicle braking at short-to-moderate headway: collisions occur only when the driver is distracted, concentrated at lead_decel >= 6 m/s^2 and headway <= 2.63 s, with a 50% collision rate in this region vs ~7.9% outside (lift ~6.4x). Mechanism: distracted takeover_time (often 3-8s) frequently exceeds the remaining time budget before the gap becomes unrecoverable.

Predicate: `scenario = 'lead_brake' AND driver_state = 'distracted' AND lead_decel >= 6 AND headway <= 2.63`

- Condition SHA-256 `a207b61fc461883466067c476305002f512713db368d0abc7e73214b21e42e81`
- Predicate test `f96556317067` (target `collision`, on 259 runs): 30 runs inside, target rate inside 0.5 [95% two-sided 0.313, 0.687], outside 0.0786, lift 6.361
- Evidence query `c159601b028d` (result SHA-256 `96461a8a6e9ba070…`):

```sql
SELECT scenario, driver_state, headway, lead_decel, friction, ego_speed, collision, min_ttc, takeover_time FROM runs WHERE scenario = 'lead_brake' AND driver_state = 'distracted' AND lead_decel >= 6 AND headway <= 2.63 ORDER BY headway, lead_decel
```

| scenario | driver_state | headway | lead_decel | friction | ego_speed | collision | min_ttc | takeover_time |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| lead_brake | distracted | 0.8 | 6.0 | 0.75 | 25.5 | False | 0.344 | 3.851 |
| lead_brake | distracted | 0.8 | 7.5 | 0.75 | 25.5 | True | 0.029 | 4.352 |
| lead_brake | distracted | 0.8 | 9.0 | 0.75 | 25.5 | True | 0.029 | 4.623 |
| lead_brake | distracted | 1.167 | 7.5 | 0.875 | 32.5 | True | 0.001 | 8.011 |
| lead_brake | distracted | 1.167 | 7.5 | 0.625 | 18.5 | False | 0.523 | 5.497 |
| lead_brake | distracted | 1.167 | 7.5 | 0.875 | 18.5 | True | 0.036 | 3.961 |
| lead_brake | distracted | 1.167 | 7.5 | 0.625 | 25.5 | True | 0.026 | 4.018 |
| lead_brake | distracted | 1.167 | 7.5 | 0.875 | 25.5 | True | 0.026 | 3.202 |
| lead_brake | distracted | 1.167 | 7.5 | 0.625 | 32.5 | True | 0.047 | 4.353 |
| lead_brake | distracted | 1.17 | 6.0 | 0.75 | 25.5 | False | 1.462 | 2.953 |
| lead_brake | distracted | 1.17 | 7.5 | 0.75 | 25.5 | True | 0.016 | 5.166 |
| lead_brake | distracted | 1.17 | 9.0 | 0.75 | 25.5 | False | 0.782 | 2.69 |
| lead_brake | distracted | 1.5 | 6.0 | 0.75 | 25.5 | False | 1.259 | 3.891 |
| lead_brake | distracted | 1.5 | 7.5 | 0.75 | 25.5 | True | 0.047 | 7.807 |
| lead_brake | distracted | 1.5 | 9.0 | 0.75 | 25.5 | True | 0.031 | 4.15 |

### TC-02: Cut-in scenario with very short initial headway (<=0.4s) combined with high closing speed (>=9 m/s, near the ODD max): contact occurs in 100% of tested runs (18/18) regardless of driver_state (attentive or distracted) and across friction 0.5-1.0 and ego_speed 15-36 m/s, including cases with sub-2s attentive takeover times, vs ~6.2% outside this region. This indicates a function/scenario-level limitation (insufficient time to avoid contact) rather than purely a driver-supervision gap; one headway bin further out (~0.5-0.58s) the same closing speed no longer collides, showing a sharp boundary.

Predicate: `scenario = 'cut_in' AND headway <= 0.4 AND closing_speed >= 9`

- Condition SHA-256 `52ff8a4377cfb69abae8282b7814b378a9cc7afd6151c07cdb61e907b7bd89ec`
- Predicate test `ee6ce50a0e8b` (target `collision`, on 259 runs): 18 runs inside, target rate inside 1 [95% two-sided 0.8147, 1], outside 0.06224, lift 16.07
- Evidence query `97585d182259` (result SHA-256 `d4f35be2aa988709…`):

```sql
SELECT scenario, driver_state, headway, closing_speed, friction, ego_speed, collision, min_ttc, takeover_time FROM runs WHERE scenario = 'cut_in' AND headway <= 0.4 AND closing_speed >= 9 ORDER BY driver_state, ego_speed
```

| scenario | driver_state | headway | closing_speed | friction | ego_speed | collision | min_ttc | takeover_time |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| cut_in | attentive | 0.3 | 9.0 | 0.5 | 15.0 | True | 0.009 | 0.9 |
| cut_in | attentive | 0.3 | 9.0 | 0.5 | 15.0 | True | 0.009 | 1.199 |
| cut_in | attentive | 0.3 | 9.0 | 0.5 | 15.0 | True | 0.009 | 1.213 |
| cut_in | attentive | 0.3 | 9.0 | 1.0 | 25.5 | True | 0.045 | 0.799 |
| cut_in | attentive | 0.4 | 9.0 | 0.5 | 25.5 | True | 0.021 | 2.368 |
| cut_in | attentive | 0.3 | 9.0 | 0.5 | 36.0 | True | 0.039 | 1.128 |
| cut_in | attentive | 0.3 | 9.0 | 0.5 | 36.0 | True | 0.042 | 1.337 |
| cut_in | attentive | 0.3 | 9.0 | 0.5 | 36.0 | True | 0.007 | 1.916 |
| cut_in | distracted | 0.3 | 9.0 | 0.5 | 15.0 | True | 0.009 | 4.441 |
| cut_in | distracted | 0.3 | 9.0 | 0.5 | 15.0 | True | 0.009 | 3.302 |
| cut_in | distracted | 0.3 | 9.0 | 0.5 | 15.0 | True | 0.009 | 4.432 |
| cut_in | distracted | 0.3 | 9.0 | 0.5 | 15.0 | True | 0.009 | 3.748 |
| cut_in | distracted | 0.3 | 9.0 | 0.5 | 15.0 | True | 0.009 | 4.857 |
| cut_in | distracted | 0.3 | 9.0 | 0.5 | 36.0 | True | 0.007 | 4.546 |
| cut_in | distracted | 0.3 | 9.0 | 0.5 | 36.0 | True | 0.007 | 3.172 |

## Hypothesis tests

Every `test_predicate` call, in order, over the agent's own runs (full records in the evidence bundle).

| # | id | where | target | runs | inside | rate inside | rate outside | lift |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 50dd41caed33 | `scenario = 'lead_brake' AND driver_state = 'distracted' AND lead_decel >= 6` | collision | 237 | 39 | 0.3846 | 0 | - |
| 1 | a475663511d3 | `scenario = 'lead_brake' AND driver_state = 'distracted'` | collision | 237 | 75 | 0.2 | 0 | - |
| 2 | c452ead63055 | `scenario = 'lead_brake' AND driver_state = 'distracted' AND lead_decel >= 6 AND headway <= 2.63` | collision | 237 | 30 | 0.5 | 0 | - |
| 3 | c6240ba98a9f | `scenario = 'lead_brake' AND driver_state = 'attentive'` | collision | 237 | 54 | 0 | 0.08197 | 0 |
| 4 | 9701f853346b | `scenario = 'cut_in'` | near_miss | 237 | 108 | 0 | 0.1783 | 0 |
| 5 | 2aa8ae1d56dd | `scenario = 'cut_in' AND driver_state = 'distracted' AND closing_speed >= 7.5` | near_miss | 237 | 18 | 0 | 0.105 | 0 |
| 6 | 54fdb387cae7 | `scenario = 'cut_in' AND headway <= 0.4 AND closing_speed >= 9` | collision | 259 | 18 | 1 | 0.06224 | 16.07 |
| 7 | 2ae61a963365 | `scenario = 'cut_in' AND headway <= 0.4 AND closing_speed >= 9` | near_miss | 259 | 18 | 1 | 0.09959 | 10.04 |
| 10 | f96556317067 | `scenario = 'lead_brake' AND driver_state = 'distracted' AND lead_decel >= 6 AND headway <= 2.63` | collision | 259 | 30 | 0.5 | 0.0786 | 6.361 |
| 11 | ee6ce50a0e8b | `scenario = 'cut_in' AND headway <= 0.4 AND closing_speed >= 9` | collision | 259 | 18 | 1 | 0.06224 | 16.07 |
