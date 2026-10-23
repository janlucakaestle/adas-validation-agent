# Search report: Adaptive Cruise Control (learned policy) with driver-intervention request, SAE L2

**Campaign:** `agent_s4` · **Author:** agent (claude-sonnet-5) · **Date:** 2026-10-21

## Provenance

- Campaign `agent_s4`: kind `search`, method `agent`, status **COMPLETE**, 258 of 300 planned runs, seed 4, created 2026-10-21 22:09:48
- Release ID: `fe59625d9428753862687a3969fa0abf194b64e8afeabe42898bdbcca7498d81`
- Runtime ID: `d37505bee00e01c235487f54dbb579f8dc71978020d9565f2c940eb2fcf3ae3c`; exposure model ID: `9b025cdb5828fa42574c0dd79797f6b94434d542e7bef4529b3194c10a025abc`; protocol ID: `4a879572d3e65102fa78f013d357c0caaabed603db99992e6a02ba64c8c444a9`
- Data SHA-256: `6230c1ade8ff00b9d84b6efa0020da2b38643f5c7ab27f5a69c32ad3bafda5a7`
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

## Campaign Summary (agent_s4, 258/300 runs used)

Approach: covered the full ODD coverage grid (216 cells; scenario × driver_state × ego_speed × headway × lead_decel/closing_speed × friction) with 1 run/cell (216 runs), then used the remaining budget to drill into the clusters where `collision`/`near_miss` appeared, varying one factor at a time and repeating stochastic cases (random takeover time) to confirm.

### Key findings

**1. lead_brake: distracted driver + short/medium headway + strong achieved lead braking → collisions.**
Across the full coverage sweep, every collision in `lead_brake` occurred with `driver_state='distracted'`. Drilling into the lead_decel/friction interaction showed that the lead vehicle's actual achieved deceleration is capped by `friction` (e.g. at friction=0.5, max_decel saturates near ~4.4 m/s² regardless of the requested `lead_decel` up to 9 m/s²; confirmed via a query on `max_decel` grouped by friction/lead_decel). Once the *achievable* deceleration is high (friction ≥ 0.6 with requested lead_decel ≥ 7 m/s², giving an actual ~5–8.6 m/s² stop), and headway ≤ 1.9 s, distracted-driver runs collide in 21/40 sampled cases (52%) vs 5.5% outside this predicate (lift ≈ 9.5×, 95% CI on inside rate [0.30, 0.74]). The same condition applied to attentive drivers produced 0/12 collisions, because attentive takeover times were consistently <2 s while distracted takeover times of >~3.4 s were the ones that collided (all collisions in the evidence query have takeover_time ≥ 3.44 s, all survivals among distracted have takeover_time ≤ 3.99 s with a narrow overlap zone, consistent with stochastic takeover-time sampling near a hard physical deadline). A follow-up sweep confirmed a threshold between actual decel ~6 m/s² (0/3 collisions even with a 4.4s takeover) and ~7-9 m/s² (collisions appear once takeover_time exceeds ~3.4-4s).

**2. cut_in: ODD-edge short headway + high closing speed → collisions largely independent of driver attentiveness.**
At the extreme corner of the cut-in ODD (headway = 0.3 s, the minimum, combined with closing_speed = 9 m/s, the maximum), 13/14 sampled runs collided (93%, lift ≈ 20.6×), and this held even restricting to attentive drivers (5/6, 83%) — e.g. one attentive driver with a 0.95 s takeover still collided, and most attentive collisions show min_ttc ≈ 0.01–0.04 s at the moment of cut-in, meaning essentially no reaction window exists. This indicates a scenario-severity/system-design gap at the ODD boundary rather than purely a driver-supervision (SOTIF misuse) issue: the function's own automated response is insufficient at this corner for both intended use and foreseeable misuse. Friction (0.5 vs 1.0) and ego_speed (15–36 m/s) did not change the outcome in this corner. A nearby, less extreme point (headway 0.3 s, closing_speed 4.75 m/s) produced no collisions, indicating the hazard is specific to the combination of both extremes, not headway alone.

### Limitations
- Collision/near-miss rates quoted above are campaign-specific search statistics (derived from deliberately adversarial sampling), not real-world incidence rates.
- Representative mid-bin parameter values were used for the broad coverage sweep (not exhaustive within each bin); boundary behavior between tested decel levels (e.g., 6 vs 7 m/s² actual) is only coarsely bracketed.
- `avoidable_by_reference` was not explicitly queried per run; the near-zero min_ttc at the cut-in corner suggests the scenario may be close to physically unavoidable at onset, which would need checking against that column for root-causing whether this is a function deficiency vs. an inherently extreme scenario.
- Takeover time is stochastic; sample sizes per exact cell are modest (3-6 repeats) — enough to show a clear trend but not to pin an exact probability.

### Recommended next tests
- Bisect the actual-achieved-deceleration threshold between 6 and 7 m/s² more finely, and the takeover-time threshold between 3.0–4.0 s, with more repeats to tighten the CI.
- Explore the cut_in boundary more finely (headway between 0.3–0.6 s, closing_speed between 5–9 m/s) to map where the "near-unavoidable" region begins, and cross-reference with `avoidable_by_reference` to separate scenario-inherent severity from system response gaps.
- Test intermediate friction values (0.6–0.9) for cut_in extreme corner since only 0.5 and 1.0 were sampled there.

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

- Runs executed: 258
- Target runs: 24
- Distinct target coverage cells: 15
- Runs to first target run: 12

### Coverage cells with target runs

| scenario | driver_state | ego_speed | headway | friction | scenario_param | runs | collision |
| --- | --- | --- | --- | --- | --- | --- | --- |
| lead_brake | distracted | 22-29 | 0.8-1.5333 | 0.75-1 | lead_decel 6-9 | 7 | 4 |
| lead_brake | distracted | 22-29 | 0.8-1.5333 | 0.5-0.75 | lead_decel 6-9 | 11 | 4 |
| cut_in | distracted | 29-36 | 0.3-0.8667 | 0.5-0.75 | closing_speed 6-9 | 4 | 3 |
| cut_in | distracted | 15-22 | 0.3-0.8667 | 0.5-0.75 | closing_speed 6-9 | 3 | 2 |
| lead_brake | distracted | 15-22 | 0.8-1.5333 | 0.75-1 | lead_decel 6-9 | 1 | 1 |
| lead_brake | distracted | 22-29 | 1.5333-2.2667 | 0.75-1 | lead_decel 6-9 | 1 | 1 |
| lead_brake | distracted | 29-36 | 0.8-1.5333 | 0.75-1 | lead_decel 6-9 | 1 | 1 |
| cut_in | attentive | 15-22 | 0.3-0.8667 | 0.5-0.75 | closing_speed 6-9 | 2 | 1 |
| cut_in | attentive | 15-22 | 0.3-0.8667 | 0.75-1 | closing_speed 6-9 | 2 | 1 |
| cut_in | distracted | 15-22 | 0.3-0.8667 | 0.75-1 | closing_speed 6-9 | 2 | 1 |
| cut_in | attentive | 22-29 | 0.3-0.8667 | 0.5-0.75 | closing_speed 6-9 | 2 | 1 |
| cut_in | distracted | 22-29 | 0.3-0.8667 | 0.5-0.75 | closing_speed 6-9 | 2 | 1 |
| cut_in | attentive | 29-36 | 0.3-0.8667 | 0.75-1 | closing_speed 6-9 | 2 | 1 |
| cut_in | distracted | 29-36 | 0.3-0.8667 | 0.75-1 | closing_speed 6-9 | 2 | 1 |
| cut_in | attentive | 29-36 | 0.3-0.8667 | 0.5-0.75 | closing_speed 6-9 | 3 | 1 |

## Reference outcomes

`avoidable_by_reference`: a fixed brake-only response, starting at hazard onset with perfect knowledge, no steering and no pre-hazard braking (`config/reference.yaml`), avoids contact. FALSE is not a proof of physical inevitability. `handback_required`: braking at a fixed deceleration (the nominal design authority, frozen) from hazard onset does not avoid contact (independent of the tested ACC's authority). Both are scenario properties, computed for every run independently of the system.

| runs | not_avoided_by_reference | handback_required | collisions | collisions_avoidable_by_reference | unresolved |
| --- | --- | --- | --- | --- | --- |
| 258 | 9 | 48 | 24 | 15 | 0 |

## Coverage

216 / 216 coverage cells (100%) meet the minimum run count, over the full set of ODD coverage dimensions: scenario, driver_state, ego_speed, headway, lead_decel, friction. Coverage is structural: it says nothing about how often the function fails in a cell.

## Triggering conditions and evidence

Every condition below passed the mandatory evidence protocol (`avval/evidence.py`). Evidence bundle SHA-256: `f13f44c0abe77b1756b2aaea3ee622261b50f8aaf38b6918383078f72e6a3709`.

### TC-01: lead_brake scenario: a distracted driver combined with short/medium initial headway (<=1.9s) and a strong achievable lead-vehicle deceleration (requested lead_decel>=7 m/s^2 with friction>=0.6, so the actual achieved deceleration is not capped below ~6 m/s^2) leads to collisions when the driver's takeover time is long (observed >~3.4s). Attentive drivers in the identical condition never collided in our sample.

Predicate: `scenario='lead_brake' AND driver_state='distracted' AND headway<=1.9 AND lead_decel>=7 AND friction>=0.6`

- Condition SHA-256 `93b260294d62ad0fce09694588b7425423ec8af25027a15f792e98444527cffa`
- Predicate test `67b2dce7ba40` (target `collision`, on 258 runs): 21 runs inside, target rate inside 0.5238 [95% two-sided 0.2978, 0.7429], outside 0.05485, lift 9.549
- Evidence query `be41904e6873` (result SHA-256 `d2eff0436bd01f5b…`):

```sql
SELECT run_idx, scenario, driver_state, headway, lead_decel, friction, ego_speed, takeover_time, min_ttc, collision FROM runs WHERE scenario='lead_brake' AND driver_state='distracted' AND headway<=1.9 AND lead_decel>=7 AND friction>=0.6 ORDER BY run_idx
```

| run_idx | scenario | driver_state | headway | lead_decel | friction | ego_speed | takeover_time | min_ttc | collision |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 9 | lead_brake | distracted | 1.167 | 7.5 | 0.625 | 18.5 | 2.763 | 1.358 | False |
| 11 | lead_brake | distracted | 1.167 | 7.5 | 0.875 | 18.5 | 5.18 | 0.004 | True |
| 21 | lead_brake | distracted | 1.9 | 7.5 | 0.625 | 18.5 | 3.99 | 1.362 | False |
| 23 | lead_brake | distracted | 1.9 | 7.5 | 0.875 | 18.5 | 4.238 | 1.021 | False |
| 45 | lead_brake | distracted | 1.167 | 7.5 | 0.625 | 25.5 | 4.407 | 0.019 | True |
| 47 | lead_brake | distracted | 1.167 | 7.5 | 0.875 | 25.5 | 3.442 | 0.015 | True |
| 57 | lead_brake | distracted | 1.9 | 7.5 | 0.625 | 25.5 | 4.319 | 1.095 | False |
| 59 | lead_brake | distracted | 1.9 | 7.5 | 0.875 | 25.5 | 6.757 | 0.034 | True |
| 81 | lead_brake | distracted | 1.167 | 7.5 | 0.625 | 32.5 | 3.05 | 0.72 | False |
| 83 | lead_brake | distracted | 1.167 | 7.5 | 0.875 | 32.5 | 4.479 | 0.001 | True |
| 93 | lead_brake | distracted | 1.9 | 7.5 | 0.625 | 32.5 | 3.933 | 0.968 | False |
| 95 | lead_brake | distracted | 1.9 | 7.5 | 0.875 | 32.5 | 3.398 | 1.318 | False |
| 228 | lead_brake | distracted | 1.167 | 7.5 | 0.625 | 25.5 | 3.31 | 0.883 | False |
| 229 | lead_brake | distracted | 1.167 | 7.5 | 0.625 | 25.5 | 3.373 | 0.831 | False |
| 230 | lead_brake | distracted | 1.167 | 7.5 | 0.625 | 25.5 | 4.191 | 0.023 | True |

### TC-02: cut_in scenario: a cut-in at the extreme edge of the ODD -- minimum initial headway (0.3s) combined with maximum closing speed (9 m/s) -- produces collisions in the large majority of runs (93% in our sample) regardless of driver attentiveness, including attentive-driver runs with sub-1s takeover times, indicating the automated/driver response window is essentially absent at this corner rather than this being purely a distraction-driven failure.

Predicate: `scenario='cut_in' AND headway<=0.3 AND closing_speed>=9`

- Condition SHA-256 `ccba55455dbef3d76a56fa132f2cbc9227c3c857d22b9d843385aeaeaf32f43f`
- Predicate test `1f501b406b82` (target `collision`, on 258 runs): 14 runs inside, target rate inside 0.9286 [95% two-sided 0.6613, 0.9982], outside 0.04508, lift 20.6
- Evidence query `c6afe854b08c` (result SHA-256 `3362f42798ec5199…`):

```sql
SELECT run_idx, scenario, driver_state, headway, closing_speed, friction, ego_speed, takeover_time, min_ttc, collision FROM runs WHERE scenario='cut_in' AND headway<=0.3 AND closing_speed>=9 ORDER BY run_idx
```

| run_idx | scenario | driver_state | headway | closing_speed | friction | ego_speed | takeover_time | min_ttc | collision |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 234 | cut_in | distracted | 0.3 | 9.0 | 0.5 | 15.0 | 4.677 | 0.009 | True |
| 235 | cut_in | attentive | 0.3 | 9.0 | 0.5 | 15.0 | 0.953 | 0.009 | True |
| 236 | cut_in | distracted | 0.3 | 9.0 | 0.5 | 36.0 | 5.254 | 0.007 | True |
| 237 | cut_in | attentive | 0.3 | 9.0 | 0.5 | 36.0 | 0.778 | 0.407 | False |
| 238 | cut_in | distracted | 0.3 | 9.0 | 0.5 | 15.0 | 4.355 | 0.009 | True |
| 239 | cut_in | distracted | 0.3 | 9.0 | 0.5 | 36.0 | 6.579 | 0.007 | True |
| 240 | cut_in | attentive | 0.3 | 9.0 | 0.5 | 22.0 | 1.221 | 0.031 | True |
| 241 | cut_in | distracted | 0.3 | 9.0 | 0.5 | 22.0 | 3.754 | 0.031 | True |
| 242 | cut_in | attentive | 0.3 | 9.0 | 0.5 | 29.0 | 2.781 | 0.04 | True |
| 243 | cut_in | distracted | 0.3 | 9.0 | 0.5 | 29.0 | 4.045 | 0.04 | True |
| 244 | cut_in | attentive | 0.3 | 9.0 | 1.0 | 15.0 | 0.82 | 0.009 | True |
| 245 | cut_in | distracted | 0.3 | 9.0 | 1.0 | 15.0 | 3.812 | 0.009 | True |
| 246 | cut_in | attentive | 0.3 | 9.0 | 1.0 | 36.0 | 1.788 | 0.012 | True |
| 247 | cut_in | distracted | 0.3 | 9.0 | 1.0 | 36.0 | 2.492 | 0.007 | True |

## Hypothesis tests

Every `test_predicate` call, in order, over the agent's own runs (full records in the evidence bundle).

| # | id | where | target | runs | inside | rate inside | rate outside | lift |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 8556a8a15e44 | `scenario='lead_brake' AND driver_state='distracted' AND lead_decel>=7` | collision | 216 | 18 | 0.2778 | 0 | - |
| 2 | 01ffd6e3e416 | `scenario='lead_brake' AND driver_state='distracted' AND lead_decel>=7 AND headway<=1.9` | collision | 216 | 12 | 0.4167 | 0 | - |
| 3 | ee3855ea14f5 | `scenario='lead_brake' AND driver_state='distracted' AND headway<=1.9 AND lead_decel>=7 AND friction>=0.6` | collision | 240 | 18 | 0.4444 | 0.02252 | 19.73 |
| 6 | d1eec11a0f40 | `scenario='lead_brake' AND driver_state='attentive' AND headway<=1.9 AND lead_decel>=7 AND friction>=0.6` | collision | 240 | 12 | 0 | 0.05702 | 0 |
| 8 | 533f88fdae19 | `scenario='cut_in' AND headway<=0.3 AND closing_speed>=9` | collision | 240 | 6 | 0.8333 | 0.03419 | 24.38 |
| 9 | f810180f2463 | `scenario='cut_in' AND headway<=0.3 AND closing_speed>=9` | collision | 250 | 14 | 0.9286 | 0.0339 | 27.39 |
| 10 | ba3042151287 | `scenario='cut_in' AND headway<=0.3 AND closing_speed>=9 AND driver_state='attentive'` | collision | 250 | 6 | 0.8333 | 0.06557 | 12.71 |
| 13 | 67b2dce7ba40 | `scenario='lead_brake' AND driver_state='distracted' AND headway<=1.9 AND lead_decel>=7 AND friction>=0.6` | collision | 258 | 21 | 0.5238 | 0.05485 | 9.549 |
| 14 | 1f501b406b82 | `scenario='cut_in' AND headway<=0.3 AND closing_speed>=9` | collision | 258 | 14 | 0.9286 | 0.04508 | 20.6 |
