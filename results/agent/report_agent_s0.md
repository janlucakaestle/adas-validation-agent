# Search report: Adaptive Cruise Control (learned policy) with driver-intervention request, SAE L2

**Campaign:** `agent_s0` · **Author:** agent (claude-sonnet-5) · **Date:** 2026-10-21

## Provenance

- Campaign `agent_s0`: kind `search`, method `agent`, status **COMPLETE**, 256 of 300 planned runs, seed 0, created 2026-10-21 21:47:13
- Release ID: `fe59625d9428753862687a3969fa0abf194b64e8afeabe42898bdbcca7498d81`
- Runtime ID: `d37505bee00e01c235487f54dbb579f8dc71978020d9565f2c940eb2fcf3ae3c`; exposure model ID: `9b025cdb5828fa42574c0dd79797f6b94434d542e7bef4529b3194c10a025abc`; protocol ID: `4a879572d3e65102fa78f013d357c0caaabed603db99992e6a02ba64c8c444a9`
- Data SHA-256: `f99693a89101039ad6dd4e1cbd2c0b46ef933bb435d10a2b405fa60b28818b1c`
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

## Campaign summary (agent_s0, 256/300 runs used)

Approach: covered the full ODD coverage grid (216 cells, bin-midpoint sampling across scenario × driver_state × ego_speed × headway × friction × lead_decel/closing_speed), then used the collision/near_miss hot-spots found in `runs` to form and confirm two triggering-condition hypotheses with targeted probes and repeated stochastic trials.

### Key findings

1. **Severe lead-vehicle braking + distracted driver (lead_brake).** Across the full coverage sweep, every collision in the lead_brake scenario occurred with `driver_state='distracted'`, and collisions concentrated at the top lead_decel bin (`lead_decel >= 6 m/s^2`, i.e. 6–9 m/s² range). With attentive drivers, the same severe-braking parameter space (`lead_decel>=6`) produced **zero** collisions in 18 runs. With distracted drivers it produced a collision rate of ~54% over 28 runs (lift ≈5.6×, significant 95% CI excludes the outside rate). Repeating one representative case (ego 25.5 m/s, headway 1.17 s, friction 0.75, lead_decel 7.5 m/s², distracted) 10 times gave 8/10 collisions, confirming the effect is large and repeatable, driven by the driver's (randomly sampled) takeover_time: collisions occur when takeover_time stretches past ~3 s while min_ttc collapses toward 0. All these collisions are flagged `avoidable_by_reference = true`, i.e. a simple brake-only reference response starting at hazard onset would have avoided contact — this is a genuine function/TOR-timing shortfall for foreseeable-misuse (distracted) drivers under severe lead braking, not an inherently unavoidable physical situation.

2. **Extreme, fast cut-in (short headway + high closing speed).** At the ODD boundary `headway <= 0.3 s` and `closing_speed >= 9 m/s`, collisions are near-certain: 21/22 collected runs collided (95% CI ~0.77–1.0), vs ~7% baseline collision rate elsewhere (lift ≈14×). Unlike the lead_brake finding, this condition causes collisions **even for attentive drivers** (3/3 collided in a small boundary probe, min_ttc at cut-in was often <0.03 s, i.e. essentially no reaction window) — confirmed also 100% (19/19) for distracted drivers in the larger sample. Most of these cases are flagged `avoidable_by_reference = true`, so the system's response to very late/fast cut-ins is itself deficient, not merely facing a physically impossible scenario (a few low-speed cases are `avoidable_by_reference=false`, suggesting at very low ego speed the scenario can be physically unavoidable even for a perfect reference responder).

### Limitations
- Only two scenario families (lead_brake, cut_in) and the documented ODD ranges were explored; rates reported are from a search-driven, non-uniform sample and must not be read as real-world incident rates.
- Boundaries were probed coarsely (e.g., lead_decel threshold tested at 4.5 vs 6; headway/closing-speed boundary tested at a few points near 0.3 s / 9 m/s); finer sweeps could sharpen the exact thresholds.
- Takeover_time is stochastic per run; collision occurrence at a fixed parameter combination is probabilistic, driven by the random reaction-time draw, so repeated sampling (done for both conditions) is needed to characterize rates reliably.

### Recommended next tests
- Finer sweep of lead_decel between 4.5 and 6 m/s² (distracted) to localize the exact onset of elevated risk.
- Finer sweep of headway between 0.3–0.5 s and closing_speed between 7–9 m/s to localize the cut-in boundary, and check if friction further modulates it.
- Investigate TOR timing/latency logic specifically for distracted drivers under high-severity lead braking and fast cut-ins, since both findings are flagged avoidable-by-reference.

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

- Runs executed: 256
- Target runs: 37
- Distinct target coverage cells: 13
- Runs to first target run: 60

### Coverage cells with target runs

| scenario | driver_state | ego_speed | headway | friction | scenario_param | runs | collision |
| --- | --- | --- | --- | --- | --- | --- | --- |
| cut_in | distracted | 22-29 | 0.3-0.8667 | 0.75-1 | closing_speed 6-9 | 14 | 13 |
| lead_brake | distracted | 22-29 | 0.8-1.5333 | 0.75-1 | lead_decel 6-9 | 11 | 9 |
| cut_in | distracted | 29-36 | 0.3-0.8667 | 0.5-0.75 | closing_speed 6-9 | 12 | 3 |
| cut_in | distracted | 15-22 | 0.3-0.8667 | 0.5-0.75 | closing_speed 6-9 | 3 | 2 |
| cut_in | attentive | 29-36 | 0.3-0.8667 | 0.5-0.75 | closing_speed 6-9 | 4 | 2 |
| lead_brake | distracted | 15-22 | 0.8-1.5333 | 0.75-1 | lead_decel 6-9 | 1 | 1 |
| lead_brake | distracted | 22-29 | 0.8-1.5333 | 0.5-0.75 | lead_decel 6-9 | 1 | 1 |
| lead_brake | distracted | 29-36 | 0.8-1.5333 | 0.5-0.75 | lead_decel 6-9 | 1 | 1 |
| lead_brake | distracted | 29-36 | 0.8-1.5333 | 0.75-1 | lead_decel 6-9 | 1 | 1 |
| lead_brake | distracted | 29-36 | 1.5333-2.2667 | 0.5-0.75 | lead_decel 6-9 | 1 | 1 |
| lead_brake | distracted | 29-36 | 2.2667-3 | 0.5-0.75 | lead_decel 3.5-6 | 1 | 1 |
| lead_brake | distracted | 29-36 | 2.2667-3 | 0.5-0.75 | lead_decel 6-9 | 1 | 1 |
| cut_in | distracted | 29-36 | 0.3-0.8667 | 0.75-1 | closing_speed 6-9 | 2 | 1 |

## Reference outcomes

`avoidable_by_reference`: a fixed brake-only response, starting at hazard onset with perfect knowledge, no steering and no pre-hazard braking (`config/reference.yaml`), avoids contact. FALSE is not a proof of physical inevitability. `handback_required`: braking at a fixed deceleration (the nominal design authority, frozen) from hazard onset does not avoid contact (independent of the tested ACC's authority). Both are scenario properties, computed for every run independently of the system.

| runs | not_avoided_by_reference | handback_required | collisions | collisions_avoidable_by_reference | unresolved |
| --- | --- | --- | --- | --- | --- |
| 256 | 2 | 52 | 37 | 35 | 0 |

## Coverage

216 / 216 coverage cells (100%) meet the minimum run count, over the full set of ODD coverage dimensions: scenario, driver_state, ego_speed, headway, lead_decel, friction. Coverage is structural: it says nothing about how often the function fails in a cell.

## Triggering conditions and evidence

Every condition below passed the mandatory evidence protocol (`avval/evidence.py`). Evidence bundle SHA-256: `b633fda5267df12ef1459240bb39a96ccc27d9df1e84ad74d0cd2d181d454942`.

### TC-01: Lead vehicle brakes severely (lead_decel >= 6 m/s^2) while the driver is distracted: the ADAS issues a TOR but the distracted driver's delayed takeover frequently arrives too late, producing collisions that a simple reference brake response would have avoided. No such collisions occur with attentive drivers under the same severe-braking conditions.

Predicate: `scenario='lead_brake' AND driver_state='distracted' AND lead_decel >= 6`

- Condition SHA-256 `9d73d710264769297d8689ae935794c995f5c619f6a53386ee4cb79964a275d9`
- Predicate test `83b9b8744639` (target `collision`, on 256 runs): 28 runs inside, target rate inside 0.5357 [95% two-sided 0.3387, 0.7249], outside 0.09649, lift 5.552
- Evidence query `76d4a87d1041` (result SHA-256 `95f3768b428a795e…`):

```sql
SELECT ego_speed, headway, friction, lead_decel, collision, takeover_time, min_ttc, avoidable_by_reference FROM runs WHERE scenario='lead_brake' AND driver_state='distracted' AND lead_decel >= 6 ORDER BY collision DESC
```

| ego_speed | headway | friction | lead_decel | collision | takeover_time | min_ttc | avoidable_by_reference |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 25.5 | 1.167 | 0.75 | 7.5 | True | 6.189 | 0.012 | True |
| 32.5 | 1.9 | 0.625 | 7.5 | True | 5.92 | 0.033 | True |
| 25.5 | 1.167 | 0.75 | 7.5 | True | 5.347 | 0.012 | True |
| 25.5 | 1.167 | 0.75 | 7.5 | True | 3.158 | 0.041 | True |
| 25.5 | 1.167 | 0.75 | 7.5 | True | 5.455 | 0.012 | True |
| 25.5 | 1.167 | 0.75 | 7.5 | True | 5.366 | 0.012 | True |
| 25.5 | 1.167 | 0.625 | 7.5 | True | 4.516 | 0.041 | True |
| 18.5 | 1.167 | 0.875 | 7.5 | True | 7.21 | 0.004 | True |
| 25.5 | 1.167 | 0.75 | 7.5 | True | 6.43 | 0.012 | True |
| 25.5 | 1.167 | 0.75 | 7.5 | True | 5.39 | 0.012 | True |
| 25.5 | 1.167 | 0.75 | 7.5 | True | 5.222 | 0.012 | True |
| 32.5 | 2.633 | 0.625 | 7.5 | True | 6.639 | 0.005 | True |
| 32.5 | 1.167 | 0.625 | 7.5 | True | 4.008 | 0.025 | True |
| 32.5 | 1.167 | 0.875 | 7.5 | True | 4.492 | 0.001 | True |
| 25.5 | 1.167 | 0.875 | 7.5 | True | 5.229 | 0.038 | True |

### TC-02: Very short initial headway combined with high closing speed at cut-in (headway <= 0.3 s and closing_speed >= 9 m/s) leaves almost no reaction time (min_ttc often < 0.03 s at cut-in): collisions occur in nearly all runs, including for attentive drivers, and most are flagged avoidable by a simple reference brake response, indicating a system deficiency at this ODD boundary rather than pure physical inevitability.

Predicate: `scenario='cut_in' AND headway <= 0.3 AND closing_speed >= 9`

- Condition SHA-256 `4df503878aaeb46b24058c6af0efab8ed46f125912da0f9d0c77d9707f46b79a`
- Predicate test `1ab492b316e2` (target `collision`, on 256 runs): 22 runs inside, target rate inside 0.9545 [95% two-sided 0.7716, 0.9988], outside 0.06838, lift 13.96
- Evidence query `9743e54f217b` (result SHA-256 `25b071072bc8cc91…`):

```sql
SELECT ego_speed, headway, friction, closing_speed, driver_state, collision, takeover_time, min_ttc, avoidable_by_reference FROM runs WHERE scenario='cut_in' AND headway <= 0.3 AND closing_speed >= 9 ORDER BY collision DESC
```

| ego_speed | headway | friction | closing_speed | driver_state | collision | takeover_time | min_ttc | avoidable_by_reference |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 36.0 | 0.3 | 0.5 | 9.0 | distracted | True | 4.581 | 0.007 | True |
| 36.0 | 0.3 | 0.5 | 9.0 | distracted | True | 5.229 | 0.007 | True |
| 36.0 | 0.3 | 0.5 | 9.0 | distracted | True | 3.751 | 0.007 | True |
| 15.0 | 0.3 | 0.5 | 9.0 | distracted | True | 3.615 | 0.009 | False |
| 15.0 | 0.3 | 0.5 | 9.0 | distracted | True | 3.999 | 0.009 | False |
| 36.0 | 0.3 | 1.0 | 9.0 | distracted | True | 3.651 | 0.007 | True |
| 36.0 | 0.3 | 0.5 | 9.0 | attentive | True | 1.618 | 0.022 | True |
| 36.0 | 0.3 | 0.5 | 9.0 | attentive | True | 2.315 | 0.007 | True |
| 22.0 | 0.3 | 0.75 | 9.0 | distracted | True | 7.248 | 0.031 | True |
| 22.0 | 0.3 | 0.75 | 9.0 | distracted | True | 6.558 | 0.031 | True |
| 22.0 | 0.3 | 0.75 | 9.0 | distracted | True | 7.971 | 0.031 | True |
| 25.5 | 0.3 | 0.75 | 9.0 | distracted | True | 5.231 | 0.021 | True |
| 25.5 | 0.3 | 0.75 | 9.0 | distracted | True | 7.163 | 0.021 | True |
| 25.5 | 0.3 | 0.75 | 9.0 | distracted | True | 5.911 | 0.021 | True |
| 25.5 | 0.3 | 0.75 | 9.0 | distracted | True | 4.607 | 0.021 | True |

## Hypothesis tests

Every `test_predicate` call, in order, over the agent's own runs (full records in the evidence bundle).

| # | id | where | target | runs | inside | rate inside | rate outside | lift |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 70158d8cd073 | `scenario='lead_brake' AND driver_state='distracted' AND lead_decel >= 6` | collision | 216 | 18 | 0.3889 | 0.005051 | 77 |
| 2 | cc0b4d6edd6e | `scenario='lead_brake' AND driver_state='distracted' AND lead_decel >= 6 AND ego_speed >= 25` | collision | 216 | 12 | 0.5 | 0.009804 | 51 |
| 3 | 97db78ba0452 | `scenario='lead_brake' AND driver_state='attentive' AND lead_decel >= 6` | collision | 216 | 18 | 0 | 0.0404 | 0 |
| 4 | 7dcc41998481 | `scenario='lead_brake' AND driver_state='distracted' AND lead_decel >= 4.5` | near_miss | 216 | 36 | 0.3056 | 0 | - |
| 5 | 5a39cf4809ab | `scenario='cut_in' AND headway <= 0.3 AND closing_speed >= 9` | collision | 236 | 12 | 0.9167 | 0.03571 | 25.67 |
| 6 | fb16bb16cb4e | `scenario='cut_in' AND headway <= 0.3 AND closing_speed >= 9 AND driver_state='distracted'` | collision | 236 | 9 | 1 | 0.04405 | 22.7 |
| 9 | 4c24a7daa3a0 | `scenario='lead_brake' AND driver_state='distracted' AND lead_decel >= 4.5` | collision | 236 | 36 | 0.2222 | 0.055 | 4.04 |
| 11 | 83b9b8744639 | `scenario='lead_brake' AND driver_state='distracted' AND lead_decel >= 6` | collision | 256 | 28 | 0.5357 | 0.09649 | 5.552 |
| 12 | 1ab492b316e2 | `scenario='cut_in' AND headway <= 0.3 AND closing_speed >= 9` | collision | 256 | 22 | 0.9545 | 0.06838 | 13.96 |
| 13 | 11e77e13b000 | `scenario='cut_in' AND headway <= 0.3 AND closing_speed >= 9 AND driver_state='distracted'` | collision | 256 | 19 | 1 | 0.07595 | 13.17 |
